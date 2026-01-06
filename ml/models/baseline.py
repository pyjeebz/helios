"""
Baseline Model: Moving Average + Trend

Simple but effective baseline for time-series forecasting.
This model should be beaten by more sophisticated approaches.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class BaselinePrediction:
    """Container for baseline model predictions."""

    forecast: np.ndarray
    trend: float
    moving_average: float
    confidence_lower: np.ndarray
    confidence_upper: np.ndarray


class BaselineModel:
    """
    Baseline forecasting model using Moving Average + Linear Trend.

    This provides a simple benchmark that any ML model should beat.

    Model: forecast[t+h] = MA + trend * h

    Where:
    - MA = moving average of last `window` observations
    - trend = average change per period
    """

    def __init__(
        self,
        window: int = 12,
        trend_window: int = 24,
        confidence_level: float = 0.95,
    ):
        """
        Initialize baseline model.

        Args:
            window: Window size for moving average (in data points)
            trend_window: Window for calculating trend
            confidence_level: Confidence level for prediction intervals
        """
        self.window = window
        self.trend_window = trend_window
        self.confidence_level = confidence_level

        # Fitted parameters
        self.moving_average_: Optional[float] = None
        self.trend_: Optional[float] = None
        self.std_: Optional[float] = None
        self.is_fitted_: bool = False

    def fit(self, y: pd.Series) -> "BaselineModel":
        """
        Fit the baseline model.

        Args:
            y: Time series values (should be sorted by time)

        Returns:
            self
        """
        y = np.asarray(y)

        if len(y) < self.window:
            raise ValueError(f"Need at least {self.window} observations, got {len(y)}")

        # Calculate moving average (last `window` observations)
        self.moving_average_ = np.mean(y[-self.window :])

        # Calculate trend (average change per period)
        trend_data = y[-self.trend_window :] if len(y) >= self.trend_window else y
        changes = np.diff(trend_data)
        self.trend_ = np.mean(changes) if len(changes) > 0 else 0.0

        # Calculate standard deviation for confidence intervals
        # Use residuals from moving average prediction
        ma_values = pd.Series(y).rolling(self.window).mean().dropna()
        residuals = y[-len(ma_values) :] - ma_values.values
        self.std_ = np.std(residuals) if len(residuals) > 0 else np.std(y)

        self.is_fitted_ = True
        return self

    def predict(self, periods: int = 12) -> BaselinePrediction:
        """
        Make forecasts for future periods.

        Args:
            periods: Number of periods to forecast

        Returns:
            BaselinePrediction with forecast and confidence intervals
        """
        if not self.is_fitted_:
            raise ValueError("Model must be fitted before prediction")

        # Generate forecasts: MA + trend * horizon
        horizons = np.arange(1, periods + 1)
        forecast = self.moving_average_ + self.trend_ * horizons

        # Calculate confidence intervals
        # Uncertainty grows with horizon
        z_score = 1.96 if self.confidence_level == 0.95 else 2.576  # 95% or 99%
        uncertainty = self.std_ * np.sqrt(horizons)

        confidence_lower = forecast - z_score * uncertainty
        confidence_upper = forecast + z_score * uncertainty

        return BaselinePrediction(
            forecast=forecast,
            trend=self.trend_,
            moving_average=self.moving_average_,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
        )

    def evaluate(
        self,
        y_true: np.ndarray,
        y_train: np.ndarray,
    ) -> dict[str, float]:
        """
        Evaluate model on test data.

        Args:
            y_true: Actual values for test period
            y_train: Training data (to fit on)

        Returns:
            Dictionary of evaluation metrics
        """
        # Fit on training data
        self.fit(y_train)

        # Predict for test period length
        pred = self.predict(periods=len(y_true))
        y_pred = pred.forecast

        # Calculate metrics
        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100

        # Naive baseline: predict last value
        naive_pred = np.full_like(y_true, y_train[-1])
        naive_mae = np.mean(np.abs(y_true - naive_pred))

        # Skill score vs naive
        skill_score = 1 - (mae / naive_mae) if naive_mae > 0 else 0

        return {
            "mae": mae,
            "mse": mse,
            "rmse": rmse,
            "mape": mape,
            "skill_score": skill_score,
            "trend": self.trend_,
            "moving_average": self.moving_average_,
        }

    def get_params(self) -> dict:
        """Get model parameters."""
        return {
            "window": self.window,
            "trend_window": self.trend_window,
            "confidence_level": self.confidence_level,
            "moving_average": self.moving_average_,
            "trend": self.trend_,
            "std": self.std_,
        }


def train_baseline(
    series: pd.Series,
    train_ratio: float = 0.8,
    window: int = 12,
) -> tuple[BaselineModel, dict[str, float]]:
    """
    Train and evaluate baseline model.

    Args:
        series: Time series data
        train_ratio: Proportion of data for training
        window: Moving average window

    Returns:
        Tuple of (trained model, evaluation metrics)
    """
    values = series.values
    split_idx = int(len(values) * train_ratio)

    train = values[:split_idx]
    test = values[split_idx:]

    model = BaselineModel(window=window)
    metrics = model.evaluate(test, train)

    return model, metrics


if __name__ == "__main__":
    # Test with synthetic data
    np.random.seed(42)
    n = 200

    # Generate data with trend and seasonality
    t = np.arange(n)
    trend = 0.1 * t
    seasonality = 10 * np.sin(2 * np.pi * t / 24)  # Daily pattern
    noise = np.random.randn(n) * 2
    y = 50 + trend + seasonality + noise

    # Train/test split
    train_y = y[:160]
    test_y = y[160:]

    # Fit and evaluate
    model = BaselineModel(window=12)
    metrics = model.evaluate(test_y, train_y)

    print("Baseline Model Evaluation")
    print("=" * 40)
    for metric, value in metrics.items():
        print(f"{metric:20s}: {value:.4f}")

    # Make predictions
    model.fit(y)
    pred = model.predict(periods=12)
    print("\nForecast (next 12 periods):")
    print(f"  Trend: {pred.trend:.4f} per period")
    print(f"  MA: {pred.moving_average:.2f}")
    print(f"  Forecast: {pred.forecast[:5]}...")
