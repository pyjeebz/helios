"""Predictor service for time-series forecasting."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from .config import config
from .model_manager import InMemoryBaseline, model_manager
from .models import (
    ModelType,
    PredictionPoint,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger(__name__)


class PredictorService:
    """Service for generating time-series predictions."""

    def __init__(self):
        self._cache: dict[str, tuple] = {}  # (response, timestamp)
        self._prediction_count = 0

    @property
    def prediction_count(self) -> int:
        """Total predictions made."""
        return self._prediction_count

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Generate predictions for a metric.

        Args:
            request: Prediction request with metric, periods, model type

        Returns:
            PredictionResponse with forecasted values
        """
        # Check cache
        cache_key = f"{request.metric}:{request.periods}:{request.model}"
        if config.model.cache_predictions:
            cached = self._get_cached(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                return cached

        # Get model
        model = model_manager.get_model(request.model)
        if model is None:
            # Fallback to baseline
            logger.warning(f"Model {request.model} not available, using baseline")
            model = model_manager.get_model(ModelType.BASELINE)

        # Generate predictions
        if request.model == ModelType.PROPHET and hasattr(model, 'make_future_dataframe'):
            predictions = self._predict_prophet(model, request)
        else:
            predictions = self._predict_baseline(model, request)

        # Build response
        response = PredictionResponse(
            metric=request.metric.value,
            model=request.model.value,
            periods=request.periods,
            predictions=predictions,
            metadata={
                "cache_hit": False,
                "model_version": model_manager.get_model_info(request.model).version
                    if model_manager.get_model_info(request.model) else "unknown"
            }
        )

        # Cache response
        if config.model.cache_predictions:
            self._cache[cache_key] = (response, datetime.utcnow())

        self._prediction_count += 1
        return response

    def _predict_baseline(
        self,
        model: Any,
        request: PredictionRequest
    ) -> list[PredictionPoint]:
        """Generate predictions using baseline model."""
        metric_name = request.metric.value

        # Get predictions
        if isinstance(model, InMemoryBaseline):
            values = model.predict(metric_name, request.periods)
            if request.include_confidence:
                lower, upper = model.get_confidence_interval(metric_name, request.periods)
            else:
                lower = upper = [None] * request.periods
        else:
            # Assume trained model with predict method
            try:
                values = model.predict(periods=request.periods)
                if hasattr(model, 'get_confidence_interval') and request.include_confidence:
                    lower, upper = model.get_confidence_interval(request.periods)
                else:
                    lower = upper = [None] * request.periods
            except Exception as e:
                logger.error(f"Model prediction failed: {e}")
                # Return flat prediction
                values = [0.0] * request.periods
                lower = upper = [None] * request.periods

        # Build prediction points
        base_time = datetime.utcnow()
        interval = timedelta(minutes=5)  # 5-minute intervals

        predictions = []
        for i, value in enumerate(values):
            predictions.append(PredictionPoint(
                timestamp=base_time + interval * (i + 1),
                value=float(value),
                lower_bound=float(lower[i]) if lower[i] is not None else None,
                upper_bound=float(upper[i]) if upper[i] is not None else None,
            ))

        return predictions

    def _predict_prophet(
        self,
        model: Any,
        request: PredictionRequest
    ) -> list[PredictionPoint]:
        """Generate predictions using Prophet model."""
        try:
            # Create future dataframe
            future = model.make_future_dataframe(
                periods=request.periods,
                freq='5min'
            )

            # Generate forecast
            forecast = model.predict(future)

            # Get last N predictions (the forecast periods)
            forecast_rows = forecast.tail(request.periods)

            predictions = []
            for _, row in forecast_rows.iterrows():
                predictions.append(PredictionPoint(
                    timestamp=row['ds'].to_pydatetime(),
                    value=float(row['yhat']),
                    lower_bound=float(row['yhat_lower']) if request.include_confidence else None,
                    upper_bound=float(row['yhat_upper']) if request.include_confidence else None,
                ))

            return predictions

        except Exception as e:
            logger.error(f"Prophet prediction failed: {e}")
            # Fallback to baseline
            baseline = model_manager.get_model(ModelType.BASELINE)
            return self._predict_baseline(baseline, request)

    def _get_cached(self, key: str) -> Optional[PredictionResponse]:
        """Get cached prediction if valid."""
        if key not in self._cache:
            return None

        response, cached_at = self._cache[key]
        age = (datetime.utcnow() - cached_at).total_seconds()

        if age > config.model.cache_ttl_seconds:
            del self._cache[key]
            return None

        # Update metadata to indicate cache hit
        response.metadata["cache_hit"] = True
        return response

    def clear_cache(self):
        """Clear prediction cache."""
        self._cache.clear()
        logger.info("Prediction cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get predictor statistics."""
        return {
            "total_predictions": self._prediction_count,
            "cache_size": len(self._cache),
            "cache_enabled": config.model.cache_predictions,
        }


# Global predictor instance
predictor_service = PredictorService()
