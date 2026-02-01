"""Model manager for loading and managing ML models."""

import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np

from .config import config
from .models import ModelInfo, ModelType

logger = logging.getLogger(__name__)

# Optional GCS support
try:
    from google.cloud import storage

    HAS_GCS = True
except ImportError:
    HAS_GCS = False
    logger.warning("google-cloud-storage not installed, GCS support disabled")


class ModelManager:
    """Manages loading, caching, and serving ML models."""

    def __init__(self, models_dir: Optional[str] = None, gcs_bucket: Optional[str] = None):
        self.models_dir = Path(models_dir or config.model.models_dir)
        self.gcs_bucket = gcs_bucket or os.environ.get("MODELS_GCS_BUCKET")
        self._models: dict[str, Any] = {}
        self._model_info: dict[str, ModelInfo] = {}
        self._loaded_at: Optional[datetime] = None
        self._gcs_client = None

    def _get_gcs_client(self):
        """Get or create GCS client."""
        if self._gcs_client is None and HAS_GCS:
            self._gcs_client = storage.Client()
        return self._gcs_client

    def _download_from_gcs(self, gcs_path: str, local_path: Path) -> bool:
        """Download a file from GCS."""
        if not HAS_GCS or not self.gcs_bucket:
            return False
        try:
            client = self._get_gcs_client()
            bucket = client.bucket(self.gcs_bucket)
            blob = bucket.blob(gcs_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local_path))
            logger.info(f"Downloaded gs://{self.gcs_bucket}/{gcs_path} to {local_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to download from GCS: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        """Check if any models are loaded."""
        return len(self._models) > 0

    @property
    def model_count(self) -> int:
        """Number of loaded models."""
        return len(self._models)

    def load_models(self) -> dict[str, bool]:
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
        """Load baseline model (CPU forecaster from GCS)."""
        try:
            # Try to load CPU forecaster from GCS
            model_path = self.models_dir / "cpu_forecaster" / "1.0.0" / "model.pkl"
            gcs_path = "cpu_forecaster/1.0.0/model.pkl"

            # Download from GCS if not exists locally
            if not model_path.exists() and self.gcs_bucket:
                self._download_from_gcs(gcs_path, model_path)

            if model_path.exists():
                with open(model_path, "rb") as f:
                    model_data = pickle.load(f)
                
                # Check if it's the new portable format
                if model_data.get("type") == "baseline":
                    # Create a PortableBaseline from saved parameters
                    self._models["baseline"] = PortableBaseline(
                        moving_average=model_data.get("moving_average", 0.5),
                        trend=model_data.get("trend", 0.0),
                        std=model_data.get("std", 0.1),
                        window=model_data.get("window", 12),
                    )
                    logger.info("Loaded portable baseline model")
                else:
                    # Old format - try to use as TrainedForecaster
                    self._models["baseline"] = TrainedForecaster(
                        model=model_data.get("model"), scaler=model_data.get("scaler"), lookback=12
                    )
                    logger.info("Loaded trained baseline model from GCS")
                
                self._model_info["baseline"] = ModelInfo(
                    name="baseline",
                    type=ModelType.BASELINE,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["cpu_utilization", "memory_utilization"],
                    performance={},
                )
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
                    performance={},
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
                model_data = joblib.load(model_path)
                
                # Check if it's the new portable format
                if isinstance(model_data, dict) and model_data.get("type") == "prophet":
                    self._models["prophet"] = PortableProphet(model=model_data.get("model"))
                    metrics = model_data.get("metrics", {})
                    logger.info("Loaded portable Prophet model")
                else:
                    # Old format - use directly
                    self._models["prophet"] = model_data
                    metrics = {}
                
                self._model_info["prophet"] = ModelInfo(
                    name="prophet",
                    type=ModelType.PROPHET,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["cpu_utilization", "memory_bytes"],
                    performance={"mape": metrics.get("mape", 0.0), "coverage": metrics.get("coverage", 0.0)},
                )
                return True
            else:
                logger.warning("Prophet model file not found, skipping")
                return False
        except Exception as e:
            logger.error(f"Failed to load Prophet model: {e}")
            return False

    def _load_xgboost(self) -> bool:
        """Load XGBoost anomaly detector from GCS."""
        try:
            # Try to load anomaly detector from GCS
            model_path = self.models_dir / "anomaly_detector" / "1.0.0" / "model.pkl"
            gcs_path = "anomaly_detector/1.0.0/model.pkl"

            # Download from GCS if not exists locally
            if not model_path.exists() and self.gcs_bucket:
                self._download_from_gcs(gcs_path, model_path)

            if model_path.exists():
                with open(model_path, "rb") as f:
                    model_data = pickle.load(f)
                
                # Check if it's the new portable format
                if model_data.get("type") == "xgboost_anomaly":
                    self._models["xgboost"] = TrainedAnomalyDetector(
                        model=model_data.get("model"),
                        scaler=model_data.get("scaler"),
                        threshold_sigma=model_data.get("threshold_sigma", 2.5),
                    )
                    # Store threshold
                    self._models["xgboost"].threshold_ = model_data.get("threshold")
                    self._models["xgboost"].feature_names_ = model_data.get("feature_names", [])
                    logger.info("Loaded portable XGBoost anomaly detector")
                else:
                    self._models["xgboost"] = TrainedAnomalyDetector(
                        model=model_data.get("model"), scaler=model_data.get("scaler")
                    )
                
                self._model_info["xgboost"] = ModelInfo(
                    name="xgboost",
                    type=ModelType.XGBOOST,
                    version="1.0.0",
                    loaded_at=datetime.utcnow(),
                    metrics=["anomaly_detection"],
                    performance={},
                )
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
                    performance={},
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

    def list_models(self) -> list[ModelInfo]:
        """List all loaded models."""
        return list(self._model_info.values())

    def get_status(self) -> dict[str, Any]:
        """Get model manager status."""
        return {
            "loaded": self.is_loaded,
            "model_count": self.model_count,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
            "models": {name: info.model_dump() for name, info in self._model_info.items()},
        }


class PortableBaseline:
    """Baseline model loaded from portable saved parameters."""

    def __init__(self, moving_average: float, trend: float, std: float, window: int = 12):
        self.moving_average = moving_average
        self.trend = trend
        self.std = std
        self.window = window

    def update(self, metric: str, value: float):
        """No-op for portable model - uses saved parameters."""
        pass

    def predict(self, metric: str, periods: int) -> list[float]:
        """Predict using saved moving average and trend."""
        predictions = []
        for i in range(periods):
            pred = self.moving_average + self.trend * (i + 1)
            predictions.append(max(0, pred))
        return predictions

    def get_confidence_interval(self, metric: str, periods: int, confidence: float = 0.95) -> tuple:
        """Get confidence interval using saved standard deviation."""
        z_score = 1.96 if confidence == 0.95 else 2.576
        predictions = self.predict(metric, periods)
        lower = [max(0, p - z_score * self.std) for p in predictions]
        upper = [p + z_score * self.std for p in predictions]
        return (lower, upper)


class PortableProphet:
    """Prophet model wrapper for portable saved model."""

    def __init__(self, model):
        self.model = model

    def predict(self, metric: str, periods: int) -> list[float]:
        """Generate predictions using Prophet model."""
        import pandas as pd
        from datetime import datetime, timedelta
        
        if self.model is None:
            return [0.5] * periods
        
        try:
            # Create future dataframe
            future = self.model.make_future_dataframe(periods=periods, freq='5min')
            forecast = self.model.predict(future)
            
            # Get last `periods` predictions
            predictions = forecast['yhat'].tail(periods).tolist()
            return [max(0, p) for p in predictions]
        except Exception:
            return [0.5] * periods

    def get_confidence_interval(self, metric: str, periods: int, confidence: float = 0.95) -> tuple:
        """Get Prophet confidence intervals."""
        import pandas as pd
        
        if self.model is None:
            return ([0.4] * periods, [0.6] * periods)
        
        try:
            future = self.model.make_future_dataframe(periods=periods, freq='5min')
            forecast = self.model.predict(future)
            
            lower = forecast['yhat_lower'].tail(periods).tolist()
            upper = forecast['yhat_upper'].tail(periods).tolist()
            return (lower, upper)
        except Exception:
            predictions = self.predict(metric, periods)
            return ([p * 0.9 for p in predictions], [p * 1.1 for p in predictions])


class InMemoryBaseline:
    """Simple in-memory baseline model for when no trained model exists."""

    def __init__(self, window: int = 12):
        self.window = window
        self._history: dict[str, list[float]] = {}

    def update(self, metric: str, value: float):
        """Update history with new value."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)
        # Keep only last 1000 points
        self._history[metric] = self._history[metric][-1000:]

    def predict(self, metric: str, periods: int) -> list[float]:
        """Predict future values using simple moving average."""
        history = self._history.get(metric, [])

        if len(history) < self.window:
            # Not enough data, return flat prediction
            last_value = history[-1] if history else 0.0
            return [last_value] * periods

        # Calculate moving average
        ma = np.mean(history[-self.window :])

        # Calculate trend
        if len(history) >= self.window * 2:
            prev_ma = np.mean(history[-self.window * 2 : -self.window])
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

        std = np.std(history[-self.window :])
        z_score = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%

        predictions = self.predict(metric, periods)
        lower = [max(0, p - z_score * std) for p in predictions]
        upper = [p + z_score * std for p in predictions]

        return (lower, upper)


class TrainedForecaster:
    """Wrapper for trained XGBoost forecasting model."""

    def __init__(self, model: Any, scaler: Any, lookback: int = 12):
        self.model = model
        self.scaler = scaler
        self.lookback = lookback
        self._history: dict[str, list[float]] = {}

    def update(self, metric: str, value: float):
        """Update history with new value."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)
        self._history[metric] = self._history[metric][-1000:]

    def predict(self, metric: str, periods: int) -> list[float]:
        """Predict using trained model."""
        history = self._history.get(metric, [])

        if len(history) < self.lookback or self.model is None:
            # Fall back to simple prediction
            last_value = history[-1] if history else 0.5
            return [last_value] * periods

        predictions = []
        current_history = list(history[-self.lookback :])

        for _ in range(periods):
            # Create features
            lags = np.array(current_history[-self.lookback :])
            rolling_mean = np.mean(lags)
            rolling_std = np.std(lags)
            rolling_min = np.min(lags)
            rolling_max = np.max(lags)

            # Time features (use defaults)
            features = np.concatenate(
                [
                    lags,
                    [rolling_mean, rolling_std, rolling_min, rolling_max],
                    [0.5, 0.5, 1.0, 0.0],  # Default time features
                ]
            ).reshape(1, -1)

            # Scale and predict
            if self.scaler:
                features = self.scaler.transform(features)

            pred = float(self.model.predict(features)[0])
            pred = max(0, min(1, pred))  # Clamp to [0, 1]
            predictions.append(pred)
            current_history.append(pred)

        return predictions

    def get_confidence_interval(self, metric: str, periods: int, confidence: float = 0.95) -> tuple:
        """Get confidence intervals."""
        predictions = self.predict(metric, periods)
        # Simple uncertainty estimate
        margin = 0.1 if confidence == 0.95 else 0.15
        lower = [max(0, p - margin) for p in predictions]
        upper = [min(1, p + margin) for p in predictions]
        return (lower, upper)


class TrainedAnomalyDetector:
    """Wrapper for trained Isolation Forest anomaly detector."""

    def __init__(self, model: Any, scaler: Any, threshold_sigma: float = 2.5):
        self.model = model  # IsolationForest
        self.scaler = scaler
        self.threshold_sigma = threshold_sigma
        self._stats: dict[str, dict[str, float]] = {}

    def fit(self, metric: str, values: list[float]):
        """Store statistics for the metric."""
        if len(values) >= 2:
            self._stats[metric] = {"mean": np.mean(values), "std": max(np.std(values), 0.001)}

    def score(self, metric: str, value: float) -> float:
        """Calculate anomaly score."""
        if self.model is None:
            # Fall back to z-score
            stats = self._stats.get(metric, {"mean": 0.5, "std": 0.2})
            return abs(value - stats["mean"]) / stats["std"]

        # Use Isolation Forest decision function (inverted so higher = more anomalous)
        features = np.array([[value, value]])  # Simplified 2D input
        if self.scaler:
            features = self.scaler.transform(features)
        score = -self.model.decision_function(features)[0]
        return max(0, score * 5)  # Scale to roughly match sigma

    def is_anomaly(self, metric: str, value: float) -> bool:
        """Check if value is anomaly."""
        return self.score(metric, value) > self.threshold_sigma

    def detect(self, data: dict[str, list[float]]) -> list[dict[str, Any]]:
        """Detect anomalies in data."""
        anomalies = []

        for metric, values in data.items():
            if len(values) < 5:
                continue

            # Fit on data
            self.fit(metric, values)

            # Check each point
            for i, value in enumerate(values):
                score = self.score(metric, value)
                if score > self.threshold_sigma:
                    anomalies.append(
                        {
                            "metric": metric,
                            "index": i,
                            "value": value,
                            "score": score,
                            "expected": self._stats.get(metric, {}).get("mean", 0.5),
                        }
                    )

        return anomalies


class InMemoryAnomalyDetector:
    """Simple in-memory anomaly detector for when no trained model exists."""

    def __init__(self, threshold_sigma: float = 2.5):
        self.threshold_sigma = threshold_sigma
        self._stats: dict[str, dict[str, float]] = {}

    def fit(self, metric: str, values: list[float]):
        """Fit detector on historical data."""
        if len(values) < 2:
            self._stats[metric] = {"mean": values[0] if values else 0.0, "std": 0.1}
            return

        self._stats[metric] = {
            "mean": np.mean(values),
            "std": max(np.std(values), 0.001),  # Avoid division by zero
        }

    def score(self, metric: str, value: float) -> float:
        """Calculate anomaly score for a value."""
        stats = self._stats.get(metric, {"mean": 0.0, "std": 1.0})
        return abs(value - stats["mean"]) / stats["std"]

    def is_anomaly(self, metric: str, value: float) -> bool:
        """Check if value is an anomaly."""
        return self.score(metric, value) > self.threshold_sigma

    def detect(self, data: dict[str, list[float]]) -> list[dict[str, Any]]:
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
                    anomalies.append(
                        {
                            "metric": metric,
                            "index": i,
                            "value": value,
                            "score": score,
                            "expected": self._stats.get(metric, {}).get("mean", 0.0),
                        }
                    )

        return anomalies


# Global model manager instance
model_manager = ModelManager()
