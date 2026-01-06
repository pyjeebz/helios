"""
Prophet Forecasting Model

Time-series forecasting with seasonality handling for infrastructure metrics.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from prophet import Prophet

# Suppress Prophet's verbose logging
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


@dataclass
class ProphetPrediction:
    """Container for Prophet predictions."""
    forecast: pd.DataFrame
    trend: pd.Series
    seasonality: dict[str, pd.Series]
    changepoints: list


class ProphetForecaster:
    """
    Prophet-based forecasting for infrastructure metrics.

    Ideal for:
    - Traffic patterns (daily/weekly seasonality)
    - Resource usage forecasting
    - Capacity planning with uncertainty intervals

    Prophet handles:
    - Missing data gracefully
    - Outliers
    - Multiple seasonalities
    - Trend changes (changepoints)
    """

    def __init__(
        self,
        seasonality_mode: str = "multiplicative",
        changepoint_prior_scale: float = 0.05,
        yearly_seasonality: bool = False,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = True,
        interval_width: float = 0.95,
    ):
        """
        Initialize Prophet forecaster.

        Args:
            seasonality_mode: "additive" or "multiplicative"
            changepoint_prior_scale: Flexibility of trend changes (higher = more flexible)
            yearly_seasonality: Include yearly patterns
            weekly_seasonality: Include weekly patterns (Mon-Sun)
            daily_seasonality: Include daily patterns (24-hour cycle)
            interval_width: Confidence interval width (0.95 = 95%)
        """
        self.seasonality_mode = seasonality_mode
        self.changepoint_prior_scale = changepoint_prior_scale
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.interval_width = interval_width

        self.model_: Optional[Prophet] = None
        self.is_fitted_: bool = False

    def _create_model(self) -> Prophet:
        """Create a new Prophet model instance."""
        return Prophet(
            seasonality_mode=self.seasonality_mode,
            changepoint_prior_scale=self.changepoint_prior_scale,
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            interval_width=self.interval_width,
        )

    def _prepare_data(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
    ) -> pd.DataFrame:
        """
        Prepare data for Prophet (requires 'ds' and 'y' columns).

        Args:
            df: Input DataFrame
            timestamp_col: Name of timestamp column
            value_col: Name of value column

        Returns:
            DataFrame with 'ds' and 'y' columns
        """
        prophet_df = pd.DataFrame({
            "ds": pd.to_datetime(df[timestamp_col]),
            "y": df[value_col].astype(float),
        })

        # Remove NaN values
        prophet_df = prophet_df.dropna()

        return prophet_df

    def fit(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
    ) -> "ProphetForecaster":
        """
        Fit the Prophet model.

        Args:
            df: DataFrame with timestamp and value columns
            timestamp_col: Name of timestamp column
            value_col: Name of value/metric column

        Returns:
            self
        """
        prophet_df = self._prepare_data(df, timestamp_col, value_col)

        if len(prophet_df) < 2:
            raise ValueError("Need at least 2 data points to fit")

        self.model_ = self._create_model()
        self.model_.fit(prophet_df)
        self.is_fitted_ = True

        return self

    def predict(
        self,
        periods: int = 12,
        freq: str = "5min",
        include_history: bool = False,
    ) -> ProphetPrediction:
        """
        Generate forecasts.

        Args:
            periods: Number of future periods to forecast
            freq: Frequency of predictions (pandas offset alias)
            include_history: Whether to include historical fitted values

        Returns:
            ProphetPrediction with forecast DataFrame and components
        """
        if not self.is_fitted_:
            raise ValueError("Model must be fitted before prediction")

        # Create future dataframe
        future = self.model_.make_future_dataframe(
            periods=periods,
            freq=freq,
            include_history=include_history,
        )

        # Generate predictions
        forecast = self.model_.predict(future)

        # Extract trend
        trend = forecast["trend"]

        # Extract seasonality components
        seasonality = {}
        for col in forecast.columns:
            if col.endswith("_seasonality") or col in ["weekly", "daily", "yearly"]:
                seasonality[col] = forecast[col]

        # Get changepoints
        changepoints = list(self.model_.changepoints) if self.model_.changepoints is not None else []

        return ProphetPrediction(
            forecast=forecast,
            trend=trend,
            seasonality=seasonality,
            changepoints=changepoints,
        )

    def evaluate(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.8,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
    ) -> dict[str, float]:
        """
        Evaluate model with train/test split.

        Args:
            df: Full dataset
            train_ratio: Proportion for training
            timestamp_col: Timestamp column name
            value_col: Value column name

        Returns:
            Dictionary of evaluation metrics
        """
        prophet_df = self._prepare_data(df, timestamp_col, value_col)

        split_idx = int(len(prophet_df) * train_ratio)
        train_df = prophet_df.iloc[:split_idx]
        test_df = prophet_df.iloc[split_idx:]

        if len(test_df) == 0:
            raise ValueError("Test set is empty")

        # Fit on training data
        model = self._create_model()
        model.fit(train_df)

        # Predict for test period
        future = model.make_future_dataframe(
            periods=len(test_df),
            freq=pd.infer_freq(prophet_df["ds"]) or "5min",
            include_history=False,
        )
        forecast = model.predict(future)

        # Align predictions with actuals
        y_true = test_df["y"].values[:len(forecast)]
        y_pred = forecast["yhat"].values[:len(y_true)]

        # Calculate metrics
        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100

        # Coverage: % of actuals within prediction intervals
        lower = forecast["yhat_lower"].values[:len(y_true)]
        upper = forecast["yhat_upper"].values[:len(y_true)]
        coverage = np.mean((y_true >= lower) & (y_true <= upper)) * 100

        return {
            "mae": mae,
            "mse": mse,
            "rmse": rmse,
            "mape": mape,
            "coverage": coverage,
            "train_size": len(train_df),
            "test_size": len(test_df),
        }

    def cross_validate(
        self,
        df: pd.DataFrame,
        initial: str = "1 hour",
        period: str = "30 minutes",
        horizon: str = "1 hour",
        timestamp_col: str = "timestamp",
        value_col: str = "value",
    ) -> pd.DataFrame:
        """
        Perform time-series cross-validation.

        Args:
            df: Full dataset
            initial: Initial training period
            period: Period between cutoff dates
            horizon: Forecast horizon
            timestamp_col: Timestamp column
            value_col: Value column

        Returns:
            DataFrame with cross-validation results
        """
        from prophet.diagnostics import cross_validation, performance_metrics

        prophet_df = self._prepare_data(df, timestamp_col, value_col)

        model = self._create_model()
        model.fit(prophet_df)

        cv_results = cross_validation(
            model,
            initial=initial,
            period=period,
            horizon=horizon,
        )

        metrics = performance_metrics(cv_results)
        return metrics

    def get_components(self) -> dict:
        """Get model components for interpretation."""
        if not self.is_fitted_:
            raise ValueError("Model must be fitted first")

        return {
            "seasonality_mode": self.seasonality_mode,
            "changepoint_prior_scale": self.changepoint_prior_scale,
            "n_changepoints": len(self.model_.changepoints) if self.model_.changepoints is not None else 0,
            "seasonalities": list(self.model_.seasonalities.keys()),
        }


def train_prophet(
    df: pd.DataFrame,
    target_col: str,
    timestamp_col: str = "timestamp",
    evaluate: bool = True,
) -> tuple[ProphetForecaster, Optional[dict[str, float]]]:
    """
    Convenience function to train Prophet model.

    Args:
        df: Input DataFrame
        target_col: Column to forecast
        timestamp_col: Timestamp column name
        evaluate: Whether to evaluate with train/test split

    Returns:
        Tuple of (trained model, evaluation metrics or None)
    """
    model = ProphetForecaster()

    metrics = None
    if evaluate:
        metrics = model.evaluate(
            df,
            timestamp_col=timestamp_col,
            value_col=target_col,
        )

    # Fit on full data
    model.fit(df, timestamp_col=timestamp_col, value_col=target_col)

    return model, metrics


if __name__ == "__main__":
    # Test with synthetic data
    np.random.seed(42)
    n = 288  # 24 hours at 5-min intervals

    dates = pd.date_range(start="2025-12-30", periods=n, freq="5min")

    # Generate data with daily seasonality
    hour = dates.hour + dates.minute / 60
    daily_pattern = 20 * np.sin(2 * np.pi * hour / 24 - np.pi/2)  # Peak at noon
    trend = np.linspace(0, 10, n)
    noise = np.random.randn(n) * 3

    values = 100 + trend + daily_pattern + noise

    df = pd.DataFrame({
        "timestamp": dates,
        "rps": values,
    })

    # Train and evaluate
    model, metrics = train_prophet(df, "rps", evaluate=True)

    print("Prophet Model Evaluation")
    print("=" * 40)
    for metric, value in metrics.items():
        if isinstance(value, float):
            print(f"{metric:20s}: {value:.4f}")
        else:
            print(f"{metric:20s}: {value}")

    # Make prediction
    pred = model.predict(periods=12)
    print("\nForecast (next 12 periods):")
    print(pred.forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail())
