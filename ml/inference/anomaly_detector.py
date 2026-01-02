"""Anomaly detection service."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .config import config
from .model_manager import model_manager, InMemoryAnomalyDetector
from .models import (
    Anomaly,
    AnomalyRequest,
    AnomalyResponse,
    MetricName,
    ModelType,
    Severity,
)

logger = logging.getLogger(__name__)


class AnomalyDetectorService:
    """Service for detecting anomalies in metrics."""
    
    def __init__(self):
        self._detection_count = 0
        self._anomalies_found = 0
    
    @property
    def detection_count(self) -> int:
        """Total detection requests processed."""
        return self._detection_count
    
    @property
    def anomalies_found(self) -> int:
        """Total anomalies detected."""
        return self._anomalies_found
    
    def detect(self, request: AnomalyRequest) -> AnomalyResponse:
        """Detect anomalies in provided metrics data.
        
        Args:
            request: Request containing metrics data and threshold
            
        Returns:
            AnomalyResponse with detected anomalies
        """
        self._detection_count += 1
        
        # Get detector model
        detector = model_manager.get_model(ModelType.XGBOOST)
        if detector is None:
            logger.warning("No anomaly detector loaded, using inline detection")
            detector = InMemoryAnomalyDetector(threshold_sigma=request.threshold_sigma)
        
        # Process each metric
        anomalies: List[Anomaly] = []
        total_points = 0
        
        for metric_name, data_points in request.metrics.items():
            total_points += len(data_points)
            
            # Extract values and timestamps
            values = [dp.value for dp in data_points]
            timestamps = [dp.timestamp for dp in data_points]
            
            # Skip if not enough data
            if len(values) < config.anomaly.min_data_points:
                logger.warning(
                    f"Not enough data points for {metric_name}: "
                    f"{len(values)} < {config.anomaly.min_data_points}"
                )
                continue
            
            # Detect anomalies for this metric
            metric_anomalies = self._detect_metric_anomalies(
                metric_name=metric_name.value if isinstance(metric_name, MetricName) else str(metric_name),
                values=values,
                timestamps=timestamps,
                detector=detector,
                threshold=request.threshold_sigma,
            )
            
            anomalies.extend(metric_anomalies)
        
        self._anomalies_found += len(anomalies)
        
        # Build response
        return AnomalyResponse(
            data_points_analyzed=total_points,
            anomalies_detected=len(anomalies),
            anomalies=anomalies,
            summary=self._build_summary(anomalies, total_points),
        )
    
    def _detect_metric_anomalies(
        self,
        metric_name: str,
        values: List[float],
        timestamps: List[datetime],
        detector: Any,
        threshold: float,
    ) -> List[Anomaly]:
        """Detect anomalies in a single metric's data."""
        anomalies = []
        
        # Calculate statistics for this metric
        mean_val = np.mean(values)
        std_val = np.std(values)
        if std_val < 1e-10:
            std_val = 0.001  # Avoid division by zero
        
        # If using trained XGBoost detector
        if hasattr(detector, 'predict') and not isinstance(detector, InMemoryAnomalyDetector):
            try:
                # This would use the trained model
                scores = self._get_xgboost_scores(detector, values)
            except Exception as e:
                logger.warning(f"XGBoost scoring failed: {e}, using statistical method")
                scores = [abs(v - mean_val) / std_val for v in values]
        else:
            # Statistical z-score method
            scores = [abs(v - mean_val) / std_val for v in values]
        
        # Find anomalies
        for i, (value, score, ts) in enumerate(zip(values, scores, timestamps)):
            if score > threshold:
                severity = self._calculate_severity(score)
                anomalies.append(Anomaly(
                    metric=metric_name,
                    timestamp=ts,
                    value=value,
                    expected_value=mean_val,
                    anomaly_score=float(score),
                    severity=severity,
                    description=self._generate_description(
                        metric_name, value, mean_val, score, severity
                    ),
                ))
        
        return anomalies
    
    def _get_xgboost_scores(self, detector: Any, values: List[float]) -> List[float]:
        """Get anomaly scores from XGBoost model."""
        # This would be implemented based on actual model structure
        # For now, return placeholder
        import numpy as np
        predictions = detector.predict(np.array(values).reshape(-1, 1))
        residuals = np.abs(np.array(values) - predictions)
        std = np.std(residuals) if np.std(residuals) > 0 else 1.0
        return (residuals / std).tolist()
    
    def _calculate_severity(self, score: float) -> Severity:
        """Calculate severity based on anomaly score."""
        thresholds = config.anomaly.severity_thresholds
        
        if score >= thresholds.get("critical", 4.0):
            return Severity.CRITICAL
        elif score >= thresholds.get("high", 3.0):
            return Severity.HIGH
        elif score >= thresholds.get("medium", 2.5):
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _generate_description(
        self,
        metric: str,
        value: float,
        expected: float,
        score: float,
        severity: Severity,
    ) -> str:
        """Generate human-readable anomaly description."""
        direction = "above" if value > expected else "below"
        percent_diff = abs(value - expected) / expected * 100 if expected != 0 else 0
        
        if severity == Severity.CRITICAL:
            urgency = "Critical anomaly detected!"
        elif severity == Severity.HIGH:
            urgency = "Significant anomaly detected."
        elif severity == Severity.MEDIUM:
            urgency = "Moderate anomaly detected."
        else:
            urgency = "Minor anomaly detected."
        
        return (
            f"{urgency} {metric} is {percent_diff:.1f}% {direction} expected value "
            f"(actual: {value:.4f}, expected: {expected:.4f}, score: {score:.2f}σ)"
        )
    
    def _build_summary(
        self, 
        anomalies: List[Anomaly], 
        total_points: int
    ) -> Dict[str, Any]:
        """Build anomaly detection summary."""
        if not anomalies:
            return {
                "status": "healthy",
                "anomaly_rate": 0.0,
                "by_severity": {},
                "by_metric": {},
            }
        
        # Count by severity
        by_severity = {}
        for a in anomalies:
            sev = a.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Count by metric
        by_metric = {}
        for a in anomalies:
            by_metric[a.metric] = by_metric.get(a.metric, 0) + 1
        
        # Determine status
        if by_severity.get("critical", 0) > 0:
            status = "critical"
        elif by_severity.get("high", 0) > 0:
            status = "warning"
        else:
            status = "attention"
        
        return {
            "status": status,
            "anomaly_rate": len(anomalies) / total_points if total_points > 0 else 0.0,
            "by_severity": by_severity,
            "by_metric": by_metric,
            "max_score": max(a.anomaly_score for a in anomalies),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "total_detections": self._detection_count,
            "total_anomalies_found": self._anomalies_found,
            "avg_anomalies_per_request": (
                self._anomalies_found / self._detection_count 
                if self._detection_count > 0 else 0.0
            ),
        }


# Global detector instance
anomaly_detector_service = AnomalyDetectorService()
