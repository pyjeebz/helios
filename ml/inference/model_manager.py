"""Model manager for loading and managing ML models."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from .config import config
from .models import ModelInfo, ModelType

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages loading, caching, and serving ML models."""
    
    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = Path(models_dir or config.model.models_dir)
        self._models: Dict[str, Any] = {}
        self._model_info: Dict[str, ModelInfo] = {}
        self._loaded_at: Optional[datetime] = None
        
    @property
    def is_loaded(self) -> bool:
        """Check if any models are loaded."""
        return len(self._models) > 0
    
    @property
    def model_count(self) -> int:
        """Number of loaded models."""
        return len(self._models)
    
    def load_models(self) -> Dict[str, bool]:
        """Load all enabled models from disk.
        
        Returns:
            Dict mapping model name to load success status
        """
        results = {}
        
        # Load baseline model
        if config.model.baseline_enabled:
            results["baseline"] = self._load_baseline()
        
        # Load Prophet model
        if config.model.prophet_enabled:
            results["prophet"] = self._load_prophet()
        
        # Load XGBoost anomaly detector
        if config.model.xgboost_enabled:
            results["xgboost"] = self._load_xgboost()
        
        self._loaded_at = datetime.utcnow()
        logger.info(f"Loaded {sum(results.values())}/{len(results)} models")
        
        return results
    
    def _load_baseline(self) -> bool:
        """Load baseline model."""
        try:
            model_path = self.models_dir / "baseline_model.joblib"
            if model_path.exists():
                self._models["baseline"] = joblib.load(model_path)
                self._model_info["baseline"] = ModelInfo(
                    name="baseline",
                    type=ModelType.BASELINE,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["cpu_utilization", "memory_utilization"],
                    performance={"mape": 0.026}
                )
                logger.info("Loaded baseline model")
                return True
            else:
                # Create in-memory baseline if no saved model
                self._models["baseline"] = InMemoryBaseline()
                self._model_info["baseline"] = ModelInfo(
                    name="baseline",
                    type=ModelType.BASELINE,
                    version="1.0.0-inmemory",
                    loaded_at=datetime.utcnow(),
                    metrics=["cpu_utilization", "memory_utilization"],
                    performance={}
                )
                logger.info("Created in-memory baseline model")
                return True
        except Exception as e:
            logger.error(f"Failed to load baseline model: {e}")
            return False
    
    def _load_prophet(self) -> bool:
        """Load Prophet model."""
        try:
            model_path = self.models_dir / "prophet_model.joblib"
            if model_path.exists():
                self._models["prophet"] = joblib.load(model_path)
                self._model_info["prophet"] = ModelInfo(
                    name="prophet",
                    type=ModelType.PROPHET,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["cpu_utilization", "memory_bytes"],
                    performance={"mape": 0.211, "coverage": 0.469}
                )
                logger.info("Loaded Prophet model")
                return True
            else:
                logger.warning("Prophet model file not found, skipping")
                return False
        except Exception as e:
            logger.error(f"Failed to load Prophet model: {e}")
            return False
    
    def _load_xgboost(self) -> bool:
        """Load XGBoost anomaly detector."""
        try:
            model_path = self.models_dir / "xgboost_anomaly.joblib"
            if model_path.exists():
                self._models["xgboost"] = joblib.load(model_path)
                self._model_info["xgboost"] = ModelInfo(
                    name="xgboost",
                    type=ModelType.XGBOOST,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["anomaly_detection"],
                    performance={"anomaly_rate": 0.0069}
                )
                logger.info("Loaded XGBoost model")
                return True
            else:
                # Create in-memory detector if no saved model
                self._models["xgboost"] = InMemoryAnomalyDetector()
                self._model_info["xgboost"] = ModelInfo(
                    name="xgboost",
                    type=ModelType.XGBOOST,
                    version="1.0.0-inmemory",
                    loaded_at=datetime.utcnow(),
                    metrics=["anomaly_detection"],
                    performance={}
                )
                logger.info("Created in-memory anomaly detector")
                return True
        except Exception as e:
            logger.error(f"Failed to load XGBoost model: {e}")
            return False
    
    def get_model(self, model_type: ModelType) -> Optional[Any]:
        """Get a loaded model by type."""
        type_to_name = {
            ModelType.BASELINE: "baseline",
            ModelType.PROPHET: "prophet",
            ModelType.XGBOOST: "xgboost",
        }
        name = type_to_name.get(model_type)
        return self._models.get(name)
    
    def get_model_info(self, model_type: ModelType) -> Optional[ModelInfo]:
        """Get info about a loaded model."""
        type_to_name = {
            ModelType.BASELINE: "baseline",
            ModelType.PROPHET: "prophet",
            ModelType.XGBOOST: "xgboost",
        }
        name = type_to_name.get(model_type)
        return self._model_info.get(name)
    
    def list_models(self) -> List[ModelInfo]:
        """List all loaded models."""
        return list(self._model_info.values())
    
    def get_status(self) -> Dict[str, Any]:
        """Get model manager status."""
        return {
            "loaded": self.is_loaded,
            "model_count": self.model_count,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
            "models": {name: info.model_dump() for name, info in self._model_info.items()}
        }


class InMemoryBaseline:
    """Simple in-memory baseline model for when no trained model exists."""
    
    def __init__(self, window: int = 12):
        self.window = window
        self._history: Dict[str, List[float]] = {}
    
    def update(self, metric: str, value: float):
        """Update history with new value."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)
        # Keep only last 1000 points
        self._history[metric] = self._history[metric][-1000:]
    
    def predict(self, metric: str, periods: int) -> List[float]:
        """Predict future values using simple moving average."""
        history = self._history.get(metric, [])
        
        if len(history) < self.window:
            # Not enough data, return flat prediction
            last_value = history[-1] if history else 0.0
            return [last_value] * periods
        
        # Calculate moving average
        ma = np.mean(history[-self.window:])
        
        # Calculate trend
        if len(history) >= self.window * 2:
            prev_ma = np.mean(history[-self.window*2:-self.window])
            trend = (ma - prev_ma) / self.window
        else:
            trend = 0.0
        
        # Generate predictions
        predictions = []
        for i in range(periods):
            pred = ma + trend * (i + 1)
            predictions.append(max(0, pred))  # Ensure non-negative
        
        return predictions
    
    def get_confidence_interval(self, metric: str, periods: int, confidence: float = 0.95) -> tuple:
        """Get confidence interval for predictions."""
        history = self._history.get(metric, [])
        
        if len(history) < self.window:
            return ([0.0] * periods, [1.0] * periods)
        
        std = np.std(history[-self.window:])
        z_score = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
        
        predictions = self.predict(metric, periods)
        lower = [max(0, p - z_score * std) for p in predictions]
        upper = [p + z_score * std for p in predictions]
        
        return (lower, upper)


class InMemoryAnomalyDetector:
    """Simple in-memory anomaly detector for when no trained model exists."""
    
    def __init__(self, threshold_sigma: float = 2.5):
        self.threshold_sigma = threshold_sigma
        self._stats: Dict[str, Dict[str, float]] = {}
    
    def fit(self, metric: str, values: List[float]):
        """Fit detector on historical data."""
        if len(values) < 2:
            self._stats[metric] = {"mean": values[0] if values else 0.0, "std": 0.1}
            return
        
        self._stats[metric] = {
            "mean": np.mean(values),
            "std": max(np.std(values), 0.001)  # Avoid division by zero
        }
    
    def score(self, metric: str, value: float) -> float:
        """Calculate anomaly score for a value."""
        stats = self._stats.get(metric, {"mean": 0.0, "std": 1.0})
        return abs(value - stats["mean"]) / stats["std"]
    
    def is_anomaly(self, metric: str, value: float) -> bool:
        """Check if value is an anomaly."""
        return self.score(metric, value) > self.threshold_sigma
    
    def detect(self, data: Dict[str, List[float]]) -> List[Dict[str, Any]]:
        """Detect anomalies in data.
        
        Args:
            data: Dict mapping metric name to list of values
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        for metric, values in data.items():
            # Auto-fit if not already done
            if metric not in self._stats and len(values) > 10:
                # Use first 80% for fitting
                fit_size = int(len(values) * 0.8)
                self.fit(metric, values[:fit_size])
            
            for i, value in enumerate(values):
                score = self.score(metric, value)
                if score > self.threshold_sigma:
                    anomalies.append({
                        "metric": metric,
                        "index": i,
                        "value": value,
                        "score": score,
                        "expected": self._stats.get(metric, {}).get("mean", 0.0)
                    })
        
        return anomalies


# Global model manager instance
model_manager = ModelManager()
