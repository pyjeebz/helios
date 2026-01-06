"""
Feature Engineering for Time Series

Transforms raw metrics into ML-ready features with temporal patterns.
"""

from typing import Optional

import numpy as np
import pandas as pd


class FeatureEngineer:
    """
    Creates features for time-series forecasting and anomaly detection.

    Features include:
    - Lag features (t-1, t-2, ..., t-n)
    - Rolling statistics (mean, std, min, max)
    - Time-based features (hour, day_of_week, is_weekend)
    - Rate of change features
    """

    def __init__(
        self,
        lag_periods: list[int] = [1, 2, 3, 6, 12],
        rolling_windows: list[int] = [3, 6, 12],
    ):
        """
        Initialize feature engineer.

        Args:
            lag_periods: Lag periods to create (in data intervals)
            rolling_windows: Rolling window sizes for statistics
        """
        self.lag_periods = lag_periods
        self.rolling_windows = rolling_windows

    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add time-based features.

        Args:
            df: DataFrame with 'timestamp' column

        Returns:
            DataFrame with added time features
        """
        df = df.copy()

        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must have 'timestamp' column")

        ts = pd.to_datetime(df["timestamp"])

        # Hour of day (cyclical encoding)
        df["hour"] = ts.dt.hour
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        # Day of week (cyclical encoding)
        df["day_of_week"] = ts.dt.dayofweek
        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        # Binary features
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
        df["is_business_hours"] = ((df["hour"] >= 9) & (df["hour"] <= 17)).astype(int)

        # Minute of day (for finer granularity)
        df["minute_of_day"] = ts.dt.hour * 60 + ts.dt.minute

        return df

    def add_lag_features(
        self,
        df: pd.DataFrame,
        columns: list[str],
        lag_periods: Optional[list[int]] = None,
    ) -> pd.DataFrame:
        """
        Add lag features for specified columns.

        Args:
            df: Input DataFrame
            columns: Columns to create lags for
            lag_periods: Override default lag periods

        Returns:
            DataFrame with lag features
        """
        df = df.copy()
        lag_periods = lag_periods or self.lag_periods

        for col in columns:
            if col not in df.columns:
                continue
            for lag in lag_periods:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)

        return df

    def add_rolling_features(
        self,
        df: pd.DataFrame,
        columns: list[str],
        windows: Optional[list[int]] = None,
    ) -> pd.DataFrame:
        """
        Add rolling statistics features.

        Args:
            df: Input DataFrame
            columns: Columns to compute rolling stats for
            windows: Override default rolling windows

        Returns:
            DataFrame with rolling features
        """
        df = df.copy()
        windows = windows or self.rolling_windows

        for col in columns:
            if col not in df.columns:
                continue
            for window in windows:
                df[f"{col}_roll_mean_{window}"] = df[col].rolling(window).mean()
                df[f"{col}_roll_std_{window}"] = df[col].rolling(window).std()
                df[f"{col}_roll_min_{window}"] = df[col].rolling(window).min()
                df[f"{col}_roll_max_{window}"] = df[col].rolling(window).max()

        return df

    def add_rate_of_change(
        self,
        df: pd.DataFrame,
        columns: list[str],
        periods: list[int] = [1, 3, 6],
    ) -> pd.DataFrame:
        """
        Add rate of change (percent change) features.

        Args:
            df: Input DataFrame
            columns: Columns to compute rate of change for
            periods: Periods for percent change calculation

        Returns:
            DataFrame with rate of change features
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                continue
            for period in periods:
                df[f"{col}_pct_change_{period}"] = df[col].pct_change(period)
                df[f"{col}_diff_{period}"] = df[col].diff(period)

        return df

    def transform(
        self,
        df: pd.DataFrame,
        target_columns: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Apply all feature engineering transformations.

        Args:
            df: Raw metrics DataFrame
            target_columns: Columns to create features for. If None, uses all numeric columns.

        Returns:
            Feature-engineered DataFrame
        """
        df = df.copy()

        # Determine target columns
        if target_columns is None:
            target_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            target_columns = [c for c in target_columns if c != "timestamp"]

        # Add time features
        df = self.add_time_features(df)

        # Add lag features
        df = self.add_lag_features(df, target_columns)

        # Add rolling features
        df = self.add_rolling_features(df, target_columns)

        # Add rate of change features
        df = self.add_rate_of_change(df, target_columns)

        return df

    def prepare_for_training(
        self,
        df: pd.DataFrame,
        target_column: str,
        drop_na: bool = True,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features and target for model training.

        Args:
            df: Feature-engineered DataFrame
            target_column: Column to predict
            drop_na: Whether to drop rows with NaN values

        Returns:
            Tuple of (features DataFrame, target Series)
        """
        df = df.copy()

        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not in DataFrame")

        # Separate features and target
        y = df[target_column]

        # Drop non-feature columns
        drop_cols = ["timestamp", target_column]
        X = df.drop(columns=[c for c in drop_cols if c in df.columns])

        # Drop non-numeric columns
        X = X.select_dtypes(include=[np.number])

        if drop_na:
            # Find valid indices (no NaN in either X or y)
            valid_idx = X.dropna().index.intersection(y.dropna().index)
            X = X.loc[valid_idx]
            y = y.loc[valid_idx]

        return X, y


def engineer_features(df: pd.DataFrame, target: str = "rps") -> tuple[pd.DataFrame, pd.Series]:
    """
    Convenience function to engineer features and prepare for training.

    Args:
        df: Raw metrics DataFrame
        target: Target column to predict

    Returns:
        Tuple of (features, target)
    """
    engineer = FeatureEngineer()
    df_features = engineer.transform(df)
    X, y = engineer.prepare_for_training(df_features, target)
    return X, y


if __name__ == "__main__":
    # Test with sample data
    np.random.seed(42)
    dates = pd.date_range(start="2025-12-31", periods=100, freq="5min")
    sample_df = pd.DataFrame(
        {
            "timestamp": dates,
            "cpu_usage": np.random.randn(100).cumsum() + 50,
            "memory_usage": np.random.randn(100).cumsum() + 70,
            "rps": np.abs(np.random.randn(100) * 10 + 50),
        }
    )

    engineer = FeatureEngineer()
    result = engineer.transform(sample_df)
    print(f"Original columns: {len(sample_df.columns)}")
    print(f"Engineered columns: {len(result.columns)}")
    print(f"\nNew features:\n{[c for c in result.columns if c not in sample_df.columns][:10]}...")
