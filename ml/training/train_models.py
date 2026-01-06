"""
Train ML models for Helios inference service.

This script trains:
1. Time series forecasting model (XGBoost) for CPU/memory predictions
2. Anomaly detection model (Isolation Forest)

Usage:
    python train_models.py --output-dir ./models
"""

import argparse
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Optional: XGBoost for time series
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("Warning: XGBoost not installed, using baseline model")


def generate_synthetic_data(
    n_days: int = 30,
    interval_minutes: int = 5
) -> pd.DataFrame:
    """
    Generate synthetic infrastructure metrics data.

    Creates realistic patterns:
    - Daily seasonality (business hours vs night)
    - Weekly patterns (weekday vs weekend)
    - Random spikes and anomalies
    """
    timestamps = pd.date_range(
        start=datetime.now() - timedelta(days=n_days),
        end=datetime.now(),
        freq=f"{interval_minutes}min"
    )

    n_points = len(timestamps)

    # Base patterns
    hour_of_day = np.array([t.hour for t in timestamps])
    day_of_week = np.array([t.dayofweek for t in timestamps])

    # Daily pattern: higher during business hours (9-17)
    daily_pattern = np.where(
        (hour_of_day >= 9) & (hour_of_day <= 17),
        0.6,  # Business hours base
        0.2   # Off hours base
    )

    # Weekly pattern: lower on weekends
    weekly_pattern = np.where(day_of_week < 5, 1.0, 0.5)

    # CPU utilization
    cpu_base = daily_pattern * weekly_pattern
    cpu_noise = np.random.normal(0, 0.05, n_points)
    cpu_spikes = np.random.choice([0, 0.3], n_points, p=[0.98, 0.02])
    cpu_utilization = np.clip(cpu_base + cpu_noise + cpu_spikes, 0, 1)

    # Memory utilization (more stable, gradual changes)
    memory_base = 0.4 + 0.2 * daily_pattern * weekly_pattern
    memory_noise = np.random.normal(0, 0.02, n_points)
    memory_utilization = np.clip(memory_base + memory_noise, 0, 1)

    # Request rate (correlated with CPU)
    request_rate = cpu_utilization * 1000 + np.random.normal(0, 50, n_points)
    request_rate = np.clip(request_rate, 0, None)

    # Response latency (increases with load)
    latency_base = 50 + 200 * cpu_utilization
    latency_noise = np.random.exponential(20, n_points)
    response_latency = latency_base + latency_noise

    df = pd.DataFrame({
        'timestamp': timestamps,
        'cpu_utilization': cpu_utilization,
        'memory_utilization': memory_utilization,
        'request_rate': request_rate,
        'response_latency_ms': response_latency,
        'hour': hour_of_day,
        'day_of_week': day_of_week,
        'is_business_hours': ((hour_of_day >= 9) & (hour_of_day <= 17)).astype(int),
        'is_weekend': (day_of_week >= 5).astype(int)
    })

    return df


def create_features(df: pd.DataFrame, metric: str, lookback: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """
    Create features for time series prediction.

    Features:
    - Lagged values (lookback periods)
    - Rolling statistics
    - Time features
    """
    values = df[metric].values

    features = []
    targets = []

    for i in range(lookback, len(values) - 1):
        # Lagged values
        lags = values[i-lookback:i]

        # Rolling statistics
        rolling_mean = np.mean(lags)
        rolling_std = np.std(lags)
        rolling_min = np.min(lags)
        rolling_max = np.max(lags)

        # Time features
        hour = df['hour'].iloc[i]
        day_of_week = df['day_of_week'].iloc[i]
        is_business = df['is_business_hours'].iloc[i]
        is_weekend = df['is_weekend'].iloc[i]

        feature_vector = np.concatenate([
            lags,
            [rolling_mean, rolling_std, rolling_min, rolling_max],
            [hour / 24, day_of_week / 7, is_business, is_weekend]
        ])

        features.append(feature_vector)
        targets.append(values[i + 1])

    return np.array(features), np.array(targets)


def train_forecasting_model(
    df: pd.DataFrame,
    metric: str,
    lookback: int = 12
) -> dict[str, Any]:
    """Train XGBoost model for time series forecasting."""

    X, y = create_features(df, metric, lookback)

    # Split train/test
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    if HAS_XGBOOST:
        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            objective='reg:squarederror',
            random_state=42
        )
        model.fit(X_train_scaled, y_train)

        # Evaluate
        train_pred = model.predict(X_train_scaled)
        test_pred = model.predict(X_test_scaled)
    else:
        # Simple baseline: predict mean of recent values
        model = None
        train_pred = np.full_like(y_train, np.mean(y_train))
        test_pred = np.full_like(y_test, np.mean(y_test))

    train_mse = np.mean((train_pred - y_train) ** 2)
    test_mse = np.mean((test_pred - y_test) ** 2)

    return {
        'model': model,
        'scaler': scaler,
        'lookback': lookback,
        'metric': metric,
        'train_mse': float(train_mse),
        'test_mse': float(test_mse),
        'train_samples': len(X_train),
        'test_samples': len(X_test)
    }


def train_anomaly_detector(df: pd.DataFrame) -> dict[str, Any]:
    """Train Isolation Forest for anomaly detection."""

    # Use multiple metrics for anomaly detection
    features = df[['cpu_utilization', 'memory_utilization']].values

    # Scale
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Train Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,  # Expect 5% anomalies
        random_state=42,
        n_jobs=-1
    )
    model.fit(features_scaled)

    # Get anomaly scores
    scores = model.decision_function(features_scaled)
    predictions = model.predict(features_scaled)

    n_anomalies = np.sum(predictions == -1)

    return {
        'model': model,
        'scaler': scaler,
        'n_samples': len(features),
        'n_anomalies': int(n_anomalies),
        'anomaly_rate': float(n_anomalies / len(features)),
        'score_threshold': float(np.percentile(scores, 5))
    }


def save_model(
    model_data: dict[str, Any],
    output_dir: Path,
    model_name: str,
    version: str = "1.0.0"
) -> str:
    """Save model and metadata."""

    model_dir = output_dir / model_name / version
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = model_dir / "model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model_data['model'],
            'scaler': model_data['scaler']
        }, f)

    # Save metadata
    metadata = {
        'name': model_name,
        'version': version,
        'created_at': datetime.utcnow().isoformat(),
        'framework': 'xgboost' if HAS_XGBOOST else 'baseline',
        'metrics': {}
    }

    # Copy non-model fields to metadata
    for key, value in model_data.items():
        if key not in ['model', 'scaler']:
            metadata['metrics'][key] = value

    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved {model_name} v{version} to {model_dir}")
    return str(model_dir)


def main():
    parser = argparse.ArgumentParser(description="Train Helios ML models")
    parser.add_argument('--output-dir', type=str, default='./models',
                        help='Output directory for trained models')
    parser.add_argument('--days', type=int, default=30,
                        help='Days of synthetic data to generate')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("HELIOS ML MODEL TRAINING")
    print("=" * 60)

    # Generate synthetic training data
    print(f"\n1. Generating {args.days} days of synthetic data...")
    df = generate_synthetic_data(n_days=args.days)
    print(f"   Generated {len(df)} data points")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Train CPU forecasting model
    print("\n2. Training CPU utilization forecasting model...")
    cpu_model = train_forecasting_model(df, 'cpu_utilization')
    print(f"   Train MSE: {cpu_model['train_mse']:.6f}")
    print(f"   Test MSE:  {cpu_model['test_mse']:.6f}")
    save_model(cpu_model, output_dir, 'cpu_forecaster', '1.0.0')

    # Train Memory forecasting model
    print("\n3. Training Memory utilization forecasting model...")
    mem_model = train_forecasting_model(df, 'memory_utilization')
    print(f"   Train MSE: {mem_model['train_mse']:.6f}")
    print(f"   Test MSE:  {mem_model['test_mse']:.6f}")
    save_model(mem_model, output_dir, 'memory_forecaster', '1.0.0')

    # Train anomaly detector
    print("\n4. Training anomaly detection model...")
    anomaly_model = train_anomaly_detector(df)
    print(f"   Samples:      {anomaly_model['n_samples']}")
    print(f"   Anomalies:    {anomaly_model['n_anomalies']} ({anomaly_model['anomaly_rate']:.1%})")
    save_model(anomaly_model, output_dir, 'anomaly_detector', '1.0.0')

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"\nModels saved to: {output_dir.absolute()}")
    print("\nTo deploy, copy models to GCS:")
    print(f"  gsutil -m cp -r {output_dir}/* gs://helios-models/")


if __name__ == '__main__':
    main()
