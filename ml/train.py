"""
Helios ML Training Pipeline

Orchestrates data fetching, feature engineering, model training, and evaluation.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.append("..")

from config import config
from models.baseline import BaselineModel
from models.prophet_model import ProphetForecaster
from models.xgboost_anomaly import XGBoostAnomalyDetector
from pipeline.data_fetcher import CloudMonitoringFetcher
from pipeline.feature_engineering import FeatureEngineer


class HeliosTrainingPipeline:
    """
    End-to-end training pipeline for Helios ML models.

    Pipeline stages:
    1. Fetch data from Cloud Monitoring
    2. Engineer features
    3. Train baseline model (benchmark)
    4. Train Prophet forecaster
    5. Train XGBoost anomaly detector
    6. Evaluate and compare models
    7. Save artifacts
    """

    def __init__(
        self,
        output_dir: str = "artifacts",
        target_metric: str = "rps",
    ):
        """
        Initialize training pipeline.

        Args:
            output_dir: Directory for saving model artifacts
            target_metric: Primary metric to forecast
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_metric = target_metric

        # Initialize components
        self.fetcher = CloudMonitoringFetcher()
        self.feature_engineer = FeatureEngineer()

        # Models
        self.baseline_model: Optional[BaselineModel] = None
        self.prophet_model: Optional[ProphetForecaster] = None
        self.anomaly_detector: Optional[XGBoostAnomalyDetector] = None

        # Results
        self.metrics_: dict = {}
        self.data_: Optional[pd.DataFrame] = None

    def fetch_data(
        self,
        hours: int = 6,
        namespace: str = "saleor",
    ) -> pd.DataFrame:
        """
        Fetch metrics data from Cloud Monitoring.

        Args:
            hours: Hours of historical data
            namespace: Kubernetes namespace

        Returns:
            Raw metrics DataFrame
        """
        print(f"\n{'='*60}")
        print("Stage 1: Fetching Data")
        print(f"{'='*60}")

        df = self.fetcher.fetch_all_metrics(hours=hours, namespace=namespace)

        # If no data from Cloud Monitoring, try loading from CSV
        if df.empty or len(df.columns) <= 1:
            print("No Cloud Monitoring data, attempting to load from CSV...")
            df = self._load_from_csv()

        self.data_ = df
        print(f"✓ Loaded {len(df)} records with {len(df.columns)} columns")

        return df

    def _load_from_csv(self) -> pd.DataFrame:
        """Load data from saved CSV files as fallback."""
        # First try the real metrics CSV
        real_data_path = Path("data/training_data_real.csv")
        if real_data_path.exists():
            print(f"Loading from {real_data_path}")
            df = pd.read_csv(real_data_path, parse_dates=["timestamp"])
            return df

        # Try loadtest stats CSVs
        csv_path = Path("../data/loadtest")
        csv_files = list(csv_path.glob("*_stats.csv"))

        if csv_files:
            print(f"Found {len(csv_files)} CSV files, but format not compatible")

        # Generate synthetic data for testing
        print("No compatible data found, using synthetic data...")
        return self._generate_synthetic_data()

    def _generate_synthetic_data(self) -> pd.DataFrame:
        """Generate synthetic data for testing pipeline."""
        np.random.seed(42)
        n = 288  # 24 hours at 5-min intervals

        dates = pd.date_range(end=datetime.utcnow(), periods=n, freq="5min")

        # Generate realistic patterns
        hour = dates.hour + dates.minute / 60

        # Daily traffic pattern (peak at 2pm, low at 4am)
        daily_pattern = 50 * np.sin(2 * np.pi * (hour - 4) / 24)

        # Trend
        trend = np.linspace(0, 20, n)

        # Base values + patterns + noise
        rps = 100 + daily_pattern + trend + np.random.randn(n) * 10
        cpu = 30 + 0.3 * rps + np.random.randn(n) * 5
        memory = 50 + 0.1 * rps + np.random.randn(n) * 3
        latency = 50 + 0.2 * (cpu - 30) + np.random.randn(n) * 5

        df = pd.DataFrame({
            "timestamp": dates,
            "rps": np.maximum(rps, 0),
            "cpu_usage": np.clip(cpu, 0, 100),
            "memory_usage": np.clip(memory, 0, 100),
            "latency_p95": np.maximum(latency, 10),
        })

        return df

    def engineer_features(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Apply feature engineering.

        Args:
            df: Input DataFrame (uses cached data if None)

        Returns:
            Feature-engineered DataFrame
        """
        print(f"\n{'='*60}")
        print("Stage 2: Feature Engineering")
        print(f"{'='*60}")

        df = df if df is not None else self.data_
        if df is None:
            raise ValueError("No data available. Call fetch_data first.")

        # Get numeric columns for feature engineering
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols = [c for c in numeric_cols if c in ["rps", "cpu_usage", "memory_usage", "latency_p95"]]

        if not target_cols:
            target_cols = numeric_cols[:4]  # Use first 4 numeric columns

        df_features = self.feature_engineer.transform(df, target_columns=target_cols)

        print(f"✓ Generated {len(df_features.columns)} features from {len(df.columns)} columns")
        print(f"  New features: {len(df_features.columns) - len(df.columns)}")

        return df_features

    def train_baseline(
        self,
        df: pd.DataFrame,
        target: str = None,
    ) -> dict[str, float]:
        """
        Train baseline model.

        Args:
            df: DataFrame with features
            target: Target column name

        Returns:
            Evaluation metrics
        """
        print(f"\n{'='*60}")
        print("Stage 3: Training Baseline Model")
        print(f"{'='*60}")

        target = target or self.target_metric

        if target not in df.columns:
            print(f"Warning: Target '{target}' not found. Using first numeric column.")
            target = df.select_dtypes(include=[np.number]).columns[0]

        series = df[target].dropna()

        # Train/test split (use smaller split for small datasets)
        split_ratio = 0.6 if len(series) < 50 else 0.8
        split_idx = int(len(series) * split_ratio)
        train = series.values[:split_idx]
        test = series.values[split_idx:]

        # Adjust window size for small datasets
        window = min(6, len(train) // 2)

        self.baseline_model = BaselineModel(window=window)
        metrics = self.baseline_model.evaluate(test, train)

        self.metrics_["baseline"] = metrics

        print("✓ Baseline Model Results:")
        print(f"  MAE:  {metrics['mae']:.4f}")
        print(f"  RMSE: {metrics['rmse']:.4f}")
        print(f"  MAPE: {metrics['mape']:.2f}%")
        print(f"  Skill Score: {metrics['skill_score']:.4f}")

        return metrics

    def train_prophet(
        self,
        df: pd.DataFrame,
        target: str = None,
    ) -> dict[str, float]:
        """
        Train Prophet forecaster.

        Args:
            df: DataFrame with timestamp and target
            target: Target column name

        Returns:
            Evaluation metrics
        """
        print(f"\n{'='*60}")
        print("Stage 4: Training Prophet Forecaster")
        print(f"{'='*60}")

        target = target or self.target_metric

        if target not in df.columns:
            target = df.select_dtypes(include=[np.number]).columns[0]

        self.prophet_model = ProphetForecaster()

        metrics = self.prophet_model.evaluate(
            df,
            timestamp_col="timestamp",
            value_col=target,
        )

        # Fit on full data
        self.prophet_model.fit(df, timestamp_col="timestamp", value_col=target)

        self.metrics_["prophet"] = metrics

        print("✓ Prophet Model Results:")
        print(f"  MAE:  {metrics['mae']:.4f}")
        print(f"  RMSE: {metrics['rmse']:.4f}")
        print(f"  MAPE: {metrics['mape']:.2f}%")
        print(f"  Coverage: {metrics['coverage']:.1f}%")

        return metrics

    def train_anomaly_detector(
        self,
        df: pd.DataFrame,
        target: str = None,
    ) -> dict[str, float]:
        """
        Train XGBoost anomaly detector.

        Args:
            df: Feature-engineered DataFrame
            target: Target column for reconstruction

        Returns:
            Evaluation metrics
        """
        print(f"\n{'='*60}")
        print("Stage 5: Training Anomaly Detector")
        print(f"{'='*60}")

        target = target or self.target_metric

        if target not in df.columns:
            target = df.select_dtypes(include=[np.number]).columns[0]

        # Prepare features (exclude timestamp and target)
        feature_cols = [c for c in df.columns
                       if c not in ["timestamp", target]
                       and df[c].dtype in [np.float64, np.int64]]

        # Drop rows with NaN
        df_clean = df[feature_cols + [target]].dropna()

        if len(df_clean) < 50:
            print("Warning: Not enough data for anomaly detection")
            return {}

        X = df_clean[feature_cols]
        y = df_clean[target]

        self.anomaly_detector = XGBoostAnomalyDetector()
        self.anomaly_detector.fit(X, y)

        metrics = self.anomaly_detector.evaluate(X, y)
        self.metrics_["anomaly_detector"] = metrics

        print("✓ Anomaly Detector Results:")
        print(f"  Threshold: {metrics['threshold']:.4f}")
        print(f"  Anomalies Detected: {metrics['n_anomalies_detected']}")
        print(f"  Anomaly Rate: {metrics['anomaly_rate']*100:.2f}%")

        # Print top features
        top_features = self.anomaly_detector.get_top_features(5)
        print("\n  Top Features:")
        for feat, imp in top_features.items():
            print(f"    {feat}: {imp:.4f}")

        return metrics

    def compare_models(self) -> pd.DataFrame:
        """Compare all trained models."""
        print(f"\n{'='*60}")
        print("Model Comparison")
        print(f"{'='*60}")

        comparison = []

        if "baseline" in self.metrics_:
            comparison.append({
                "Model": "Baseline (MA+Trend)",
                "MAE": self.metrics_["baseline"]["mae"],
                "RMSE": self.metrics_["baseline"]["rmse"],
                "MAPE": self.metrics_["baseline"]["mape"],
            })

        if "prophet" in self.metrics_:
            comparison.append({
                "Model": "Prophet",
                "MAE": self.metrics_["prophet"]["mae"],
                "RMSE": self.metrics_["prophet"]["rmse"],
                "MAPE": self.metrics_["prophet"]["mape"],
            })

        df_comparison = pd.DataFrame(comparison)

        if not df_comparison.empty:
            print(df_comparison.to_string(index=False))

            # Calculate improvement
            if len(comparison) >= 2:
                improvement = (
                    (comparison[0]["MAE"] - comparison[1]["MAE"])
                    / comparison[0]["MAE"] * 100
                )
                print(f"\n✓ Prophet vs Baseline: {improvement:.1f}% MAE improvement")

        return df_comparison

    def save_artifacts(self):
        """Save trained models and metrics."""
        print(f"\n{'='*60}")
        print("Saving Artifacts")
        print(f"{'='*60}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save metrics
        metrics_path = self.output_dir / f"metrics_{timestamp}.json"
        with open(metrics_path, "w") as f:
            # Convert numpy types to Python types
            metrics_serializable = {}
            for model, m in self.metrics_.items():
                metrics_serializable[model] = {
                    k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                    for k, v in m.items()
                }
            json.dump(metrics_serializable, f, indent=2)

        print(f"✓ Saved metrics to {metrics_path}")

        # Save data summary
        if self.data_ is not None:
            summary_path = self.output_dir / f"data_summary_{timestamp}.json"
            summary = {
                "n_records": len(self.data_),
                "n_columns": len(self.data_.columns),
                "columns": list(self.data_.columns),
                "date_range": {
                    "start": str(self.data_["timestamp"].min()) if "timestamp" in self.data_.columns else None,
                    "end": str(self.data_["timestamp"].max()) if "timestamp" in self.data_.columns else None,
                }
            }
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"✓ Saved data summary to {summary_path}")

    def run(
        self,
        hours: int = 6,
        namespace: str = "saleor",
    ) -> dict:
        """
        Run the complete training pipeline.

        Args:
            hours: Hours of historical data
            namespace: Kubernetes namespace

        Returns:
            Dictionary with all results
        """
        print("\n" + "="*60)
        print("HELIOS ML TRAINING PIPELINE")
        print("="*60)
        print(f"Started at: {datetime.now()}")
        print(f"Config: {hours} hours, namespace='{namespace}'")

        # Stage 1: Fetch data
        df = self.fetch_data(hours=hours, namespace=namespace)

        # Stage 2: Feature engineering
        df_features = self.engineer_features(df)

        # Stage 3: Train baseline
        self.train_baseline(df)

        # Stage 4: Train Prophet
        self.train_prophet(df)

        # Stage 5: Train anomaly detector
        self.train_anomaly_detector(df_features)

        # Compare models
        comparison = self.compare_models()

        # Save artifacts
        self.save_artifacts()

        print("\n" + "="*60)
        print("PIPELINE COMPLETE")
        print("="*60)

        return {
            "metrics": self.metrics_,
            "comparison": comparison,
            "data_shape": df.shape,
            "features_shape": df_features.shape,
        }


def main():
    """Main entry point for training."""
    pipeline = HeliosTrainingPipeline(
        output_dir="artifacts",
        target_metric="rps",
    )

    # Use config for lookback hours
    results = pipeline.run(hours=config.default_lookback_hours, namespace="saleor")

    return results


if __name__ == "__main__":
    main()
