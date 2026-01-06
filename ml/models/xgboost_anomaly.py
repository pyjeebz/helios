"""
XGBoost Anomaly Detector

Supervised anomaly detection using XGBoost for infrastructure metrics.
Detects unusual patterns in multi-variate time series data.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


@dataclass
class AnomalyResult:
    """Container for anomaly detection results."""
    scores: np.ndarray
    predictions: np.ndarray
    threshold: float
    anomaly_indices: np.ndarray
    feature_importance: dict[str, float]


class XGBoostAnomalyDetector:
    """
    XGBoost-based anomaly detector using reconstruction error.

    Approach:
    1. Train XGBoost to predict a target metric from other features
    2. Large prediction errors indicate anomalies
    3. Uses rolling z-score of errors for adaptive thresholding

    Best for:
    - Multi-variate anomaly detection
    - Detecting unusual relationships between metrics
    - Catching issues like "CPU high but RPS low" (unusual)
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        threshold_sigma: float = 2.5,
        contamination: float = 0.05,
    ):
        """
        Initialize anomaly detector.

        Args:
            n_estimators: Number of XGBoost trees
            max_depth: Max tree depth
            learning_rate: Learning rate
            threshold_sigma: Standard deviations for anomaly threshold
            contamination: Expected proportion of anomalies (for percentile threshold)
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.threshold_sigma = threshold_sigma
        self.contamination = contamination

        self.model_: Optional[xgb.XGBRegressor] = None
        self.scaler_: Optional[StandardScaler] = None
        self.threshold_: Optional[float] = None
        self.feature_names_: list[str] = []
        self.is_fitted_: bool = False

    def _create_model(self) -> xgb.XGBRegressor:
        """Create XGBoost regressor."""
        return xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        validation_split: float = 0.2,
    ) -> "XGBoostAnomalyDetector":
        """
        Fit the anomaly detector.

        Args:
            X: Feature matrix
            y: Target variable (metric to predict)
            validation_split: Proportion for validation

        Returns:
            self
        """
        self.feature_names_ = list(X.columns)

        # Scale features
        self.scaler_ = StandardScaler()
        X_scaled = self.scaler_.fit_transform(X)

        # Split for validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y, test_size=validation_split, random_state=42
        )

        # Train model
        self.model_ = self._create_model()
        self.model_.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # Calculate threshold based on training errors
        train_pred = self.model_.predict(X_scaled)
        errors = np.abs(y.values - train_pred)

        # Use either sigma-based or percentile threshold
        mean_error = np.mean(errors)
        std_error = np.std(errors)
        sigma_threshold = mean_error + self.threshold_sigma * std_error
        percentile_threshold = np.percentile(errors, (1 - self.contamination) * 100)

        # Use the more conservative (higher) threshold
        self.threshold_ = max(sigma_threshold, percentile_threshold)

        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame, y: pd.Series) -> AnomalyResult:
        """
        Detect anomalies in new data.

        Args:
            X: Feature matrix
            y: Target variable (actual values)

        Returns:
            AnomalyResult with scores, predictions, and anomaly indices
        """
        if not self.is_fitted_:
            raise ValueError("Model must be fitted before prediction")

        # Scale features
        X_scaled = self.scaler_.transform(X)

        # Get predictions
        y_pred = self.model_.predict(X_scaled)

        # Calculate anomaly scores (absolute errors)
        scores = np.abs(y.values - y_pred)

        # Classify anomalies
        predictions = (scores > self.threshold_).astype(int)
        anomaly_indices = np.where(predictions == 1)[0]

        # Get feature importance
        importance = dict(zip(
            self.feature_names_,
            self.model_.feature_importances_
        ))
        # Sort by importance
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        return AnomalyResult(
            scores=scores,
            predictions=predictions,
            threshold=self.threshold_,
            anomaly_indices=anomaly_indices,
            feature_importance=importance,
        )

    def score_anomalies(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        return_details: bool = False,
    ) -> np.ndarray:
        """
        Get anomaly scores without classification.

        Args:
            X: Feature matrix
            y: Target variable
            return_details: Return detailed prediction info

        Returns:
            Array of anomaly scores
        """
        result = self.predict(X, y)

        if return_details:
            return result
        return result.scores

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        y_anomaly_labels: Optional[np.ndarray] = None,
    ) -> dict[str, float]:
        """
        Evaluate anomaly detector.

        Args:
            X: Feature matrix
            y: Target variable
            y_anomaly_labels: True anomaly labels (1=anomaly, 0=normal)

        Returns:
            Dictionary of evaluation metrics
        """
        result = self.predict(X, y)

        metrics = {
            "threshold": self.threshold_,
            "n_anomalies_detected": len(result.anomaly_indices),
            "anomaly_rate": len(result.anomaly_indices) / len(y),
            "mean_score": np.mean(result.scores),
            "max_score": np.max(result.scores),
            "std_score": np.std(result.scores),
        }

        # If true labels provided, calculate precision/recall
        if y_anomaly_labels is not None:
            true_positives = np.sum((result.predictions == 1) & (y_anomaly_labels == 1))
            false_positives = np.sum((result.predictions == 1) & (y_anomaly_labels == 0))
            false_negatives = np.sum((result.predictions == 0) & (y_anomaly_labels == 1))

            precision = true_positives / (true_positives + false_positives + 1e-8)
            recall = true_positives / (true_positives + false_negatives + 1e-8)
            f1 = 2 * precision * recall / (precision + recall + 1e-8)

            metrics.update({
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            })

        return metrics

    def get_top_features(self, n: int = 10) -> dict[str, float]:
        """Get top N most important features."""
        if not self.is_fitted_:
            raise ValueError("Model must be fitted first")

        importance = dict(zip(
            self.feature_names_,
            self.model_.feature_importances_
        ))
        sorted_importance = dict(sorted(
            importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:n])

        return sorted_importance


class IsolationForestAnomalyDetector:
    """
    Isolation Forest for unsupervised anomaly detection.

    Use when you don't have a clear target variable.
    Detects points that are "easy to isolate" from the rest.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        from sklearn.ensemble import IsolationForest

        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.model_ = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
        )
        self.scaler_ = StandardScaler()
        self.is_fitted_ = False

    def fit(self, X: pd.DataFrame) -> "IsolationForestAnomalyDetector":
        """Fit the isolation forest."""
        X_scaled = self.scaler_.fit_transform(X)
        self.model_.fit(X_scaled)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict anomalies.

        Returns:
            Array where -1 = anomaly, 1 = normal
        """
        X_scaled = self.scaler_.transform(X)
        return self.model_.predict(X_scaled)

    def score_samples(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get anomaly scores.

        Lower scores = more anomalous.
        """
        X_scaled = self.scaler_.transform(X)
        return self.model_.score_samples(X_scaled)


def train_anomaly_detector(
    X: pd.DataFrame,
    y: pd.Series,
    method: str = "xgboost",
) -> tuple[XGBoostAnomalyDetector, dict[str, float]]:
    """
    Train an anomaly detector.

    Args:
        X: Feature matrix
        y: Target variable (for XGBoost) or None
        method: "xgboost" or "isolation_forest"

    Returns:
        Tuple of (trained detector, evaluation metrics)
    """
    if method == "xgboost":
        detector = XGBoostAnomalyDetector()
        detector.fit(X, y)
        metrics = detector.evaluate(X, y)
        return detector, metrics
    else:
        raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    # Test with synthetic data
    np.random.seed(42)
    n = 500

    # Generate normal data
    X = pd.DataFrame({
        "cpu_usage": np.random.randn(n) * 10 + 50,
        "memory_usage": np.random.randn(n) * 15 + 70,
        "request_rate": np.random.randn(n) * 20 + 100,
        "latency_lag_1": np.random.randn(n) * 5 + 50,
        "latency_lag_3": np.random.randn(n) * 5 + 50,
    })

    # Target: latency (correlated with other features + noise)
    y = pd.Series(
        0.3 * X["cpu_usage"] +
        0.2 * X["memory_usage"] +
        0.1 * X["request_rate"] +
        np.random.randn(n) * 5
    )

    # Inject some anomalies
    anomaly_idx = [50, 100, 200, 350, 450]
    for idx in anomaly_idx:
        y.iloc[idx] = y.iloc[idx] + 50  # Spike in latency

    # Train detector
    detector = XGBoostAnomalyDetector(threshold_sigma=2.0)
    detector.fit(X, y)

    # Evaluate
    result = detector.predict(X, y)

    print("XGBoost Anomaly Detector")
    print("=" * 40)
    print(f"Threshold: {result.threshold:.2f}")
    print(f"Anomalies detected: {len(result.anomaly_indices)}")
    print(f"Injected anomalies: {anomaly_idx}")
    print(f"Detected indices: {result.anomaly_indices[:10]}...")

    print("\nTop features:")
    for feat, imp in list(result.feature_importance.items())[:5]:
        print(f"  {feat}: {imp:.4f}")
