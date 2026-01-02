# Helios ML Pipeline Documentation

## Overview

The Helios ML pipeline provides time-series forecasting and anomaly detection for infrastructure metrics. It's designed to be cloud-agnostic and supports multiple forecasting models.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       ML PIPELINE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  Data Fetcher   │───▶│    Feature      │                    │
│  │  (Cloud APIs)   │    │  Engineering    │                    │
│  └─────────────────┘    └────────┬────────┘                    │
│                                  │                              │
│                                  ▼                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Model Training                        │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │   │
│  │  │  Baseline   │ │  Prophet    │ │  XGBoost    │       │   │
│  │  │  (MA+Trend) │ │ (Forecast)  │ │ (Anomaly)   │       │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                  │                              │
│                                  ▼                              │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   Artifacts     │    │    Metrics      │                    │
│  │   (models/)     │    │  (artifacts/)   │                    │
│  └─────────────────┘    └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
ml/
├── __init__.py
├── config.py                # Configuration settings
├── train.py                 # Training pipeline orchestrator
├── requirements.txt         # Python dependencies
│
├── pipeline/
│   ├── __init__.py
│   ├── data_fetcher.py      # Cloud metrics fetcher
│   └── feature_engineering.py
│
├── models/
│   ├── __init__.py
│   ├── baseline.py          # Moving Average + Trend
│   ├── prophet_model.py     # Prophet forecasting
│   └── xgboost_anomaly.py   # XGBoost anomaly detection
│
├── inference/               # (Phase 5)
│   └── ...
│
├── artifacts/               # Training outputs
│   ├── metrics_*.json
│   └── data_summary_*.json
│
└── data/                    # Training data
    └── training_data_24h.csv
```

---

## Configuration

### `config.py`

```python
from dataclasses import dataclass, field

@dataclass
class GCPConfig:
    project_id: str = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
    region: str = os.environ.get("GCP_REGION", "us-central1")
    gke_cluster: str = os.environ.get("GKE_CLUSTER_NAME", "helios-dev-gke")

@dataclass
class MetricsConfig:
    container_metrics: List[str] = field(default_factory=lambda: [
        "kubernetes.io/container/cpu/limit_utilization",
        "kubernetes.io/container/memory/used_bytes",
        "kubernetes.io/container/memory/limit_utilization",
    ])
    
    cloudsql_metrics: List[str] = field(default_factory=lambda: [
        "cloudsql.googleapis.com/database/cpu/utilization",
        "cloudsql.googleapis.com/database/memory/utilization",
        "cloudsql.googleapis.com/database/postgresql/num_backends",
    ])

@dataclass
class ModelConfig:
    moving_average_window: int = 12      # 12 × 5min = 1 hour
    prophet_seasonality_mode: str = "multiplicative"
    xgb_n_estimators: int = 100
    anomaly_threshold_sigma: float = 2.5

@dataclass
class HeliosConfig:
    gcp: GCPConfig
    metrics: MetricsConfig
    model: ModelConfig
    default_lookback_hours: int = 24
    aggregation_interval_minutes: int = 5
```

---

## Data Fetcher

### Usage

```python
from pipeline.data_fetcher import CloudMonitoringFetcher

fetcher = CloudMonitoringFetcher(project_id="your-project")

# Fetch all metrics
df = fetcher.fetch_all_metrics(hours=24, namespace="saleor")

# Fetch specific metrics
container_df = fetcher.fetch_container_metrics(hours=6, namespace="saleor")
db_df = fetcher.fetch_cloudsql_metrics(hours=6)
```

### Output Format

```
              timestamp  memory_bytes  cpu_utilization  memory_utilization  db_cpu  db_memory  db_connections
0   2026-01-01 00:00:00    102400000            0.15                0.052    0.05       0.25             1.0
1   2026-01-01 00:05:00    103500000            0.18                0.053    0.05       0.25             1.0
...
```

### Supported Cloud Providers

| Provider | Adapter | Status |
|----------|---------|--------|
| GCP | `CloudMonitoringFetcher` | ✅ Implemented |
| AWS | `CloudWatchFetcher` | 🔲 Planned |
| Azure | `AzureMonitorFetcher` | 🔲 Planned |
| Prometheus | `PrometheusFetcher` | 🔲 Planned |

---

## Feature Engineering

### Usage

```python
from pipeline.feature_engineering import FeatureEngineer

engineer = FeatureEngineer()

# Transform raw metrics (7 columns) → features (108 columns)
features_df = engineer.transform(raw_df)
```

### Features Generated

| Category | Features | Count |
|----------|----------|-------|
| **Temporal** | hour, day_of_week, is_weekend, sin/cos encodings | 8 |
| **Lag** | lag_1, lag_3, lag_6, lag_12 per metric | 28 |
| **Rolling Mean** | rolling_mean_3, _6, _12 per metric | 21 |
| **Rolling Std** | rolling_std_3, _6, _12 per metric | 21 |
| **Rolling Min/Max** | rolling_min_6, rolling_max_6 per metric | 14 |
| **Percent Change** | pct_change_1, pct_change_3 per metric | 14 |
| **Cross-metric** | cpu_memory_ratio, etc. | 2 |
| **Total** | | **108** |

### Example

```python
# Input: 7 raw metrics
['timestamp', 'memory_bytes', 'cpu_utilization', 'memory_utilization', 
 'db_cpu', 'db_memory', 'db_connections']

# Output: 108 features
['hour', 'day_of_week', 'is_weekend', 'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
 'memory_bytes_lag_1', 'memory_bytes_lag_3', 'memory_bytes_lag_6', 'memory_bytes_lag_12',
 'memory_bytes_rolling_mean_3', 'memory_bytes_rolling_mean_6', 'memory_bytes_rolling_mean_12',
 'memory_bytes_rolling_std_3', 'memory_bytes_rolling_std_6', 'memory_bytes_rolling_std_12',
 'memory_bytes_rolling_min_6', 'memory_bytes_rolling_max_6',
 'memory_bytes_pct_change_1', 'memory_bytes_pct_change_3',
 ... # Same for each metric
 'cpu_memory_ratio']
```

---

## Models

### 1. Baseline Model (Moving Average + Trend)

**Purpose:** Simple, fast, reliable benchmark.

```python
from models.baseline import BaselineModel

model = BaselineModel(window=12, trend_window=24)
model.fit(train_df, target='cpu_utilization')
predictions = model.predict(periods=12)
```

**Algorithm:**
1. Calculate moving average over last `window` periods
2. Fit linear trend over last `trend_window` periods
3. Extrapolate: `prediction = moving_avg + trend * periods_ahead`

**Performance:**
- MAE: 2.5M
- MAPE: **2.6%**
- Skill Score: -0.098 (compared to naive)

---

### 2. Prophet Model

**Purpose:** Seasonality-aware time-series forecasting.

```python
from models.prophet_model import ProphetForecaster

model = ProphetForecaster(
    seasonality_mode='multiplicative',
    changepoint_prior_scale=0.05
)
model.fit(train_df, target='cpu_utilization')
predictions = model.predict(periods=12, return_confidence=True)
```

**Features:**
- Daily seasonality detection
- Weekly seasonality detection
- Automatic changepoint detection
- Confidence intervals

**Performance:**
- MAE: 25M
- MAPE: 21.1%
- Coverage: **46.9%** (% of actuals within confidence interval)

**Note:** Prophet performs better with more data (weeks/months).

---

### 3. XGBoost Anomaly Detector

**Purpose:** Detect unusual patterns in metrics.

```python
from models.xgboost_anomaly import XGBoostAnomalyDetector

detector = XGBoostAnomalyDetector(
    n_estimators=100,
    threshold_sigma=2.5
)
detector.fit(train_features)
anomaly_scores = detector.predict(test_features)
is_anomaly = detector.detect(test_features)
```

**Algorithm:**
1. Train XGBoost regressor to predict each metric
2. Calculate reconstruction error (actual - predicted)
3. Anomaly score = error / historical_std
4. Flag as anomaly if score > threshold_sigma

**Performance:**
- Threshold: 3.0M
- Anomaly Rate: **0.69%**
- Top Feature: `memory_utilization` (98.6% importance)

---

## Training Pipeline

### Run Training

```bash
cd ml
python train.py
```

### Pipeline Stages

1. **Fetch Data** - Pull metrics from Cloud Monitoring
2. **Feature Engineering** - Generate 108 features from 7 raw metrics
3. **Train Baseline** - Moving Average + Trend model
4. **Train Prophet** - Facebook Prophet forecaster
5. **Train Anomaly Detector** - XGBoost reconstruction model
6. **Evaluate** - Compare model performance
7. **Save Artifacts** - Store models and metrics

### Output

```
============================================================
HELIOS ML TRAINING PIPELINE
============================================================
Started at: 2026-01-01 10:00:00
Config: 24 hours, namespace='saleor'

Stage 1: Fetching Data
✓ Container metrics: 156 points
✓ Database metrics: 167 points
Fetched 167 data points with 7 features

Stage 2: Feature Engineering
✓ Generated 108 features from 7 columns

Stage 3: Training Baseline Model
✓ Baseline Model Results:
  MAE:  2488517.0087
  MAPE: 2.60%

Stage 4: Training Prophet Forecaster
✓ Prophet Model Results:
  MAE:  25083119.5657
  MAPE: 21.13%
  Coverage: 46.9%

Stage 5: Training Anomaly Detector
✓ Anomaly Detector Results:
  Threshold: 3036349.9072
  Anomalies Detected: 1
  Anomaly Rate: 0.69%

Model Comparison
              Model          MAE         RMSE      MAPE
Baseline (MA+Trend) 2.488517e+06 8.599812e+06  2.598730
            Prophet 2.508312e+07 2.995725e+07 21.125974

PIPELINE COMPLETE
```

---

## Artifacts

### Metrics JSON

```json
{
  "timestamp": "2026-01-01T10:00:00",
  "data_points": 167,
  "features": 108,
  "models": {
    "baseline": {
      "mae": 2488517.0,
      "mape": 0.026,
      "skill_score": -0.098
    },
    "prophet": {
      "mae": 25083119.5,
      "mape": 0.211,
      "coverage": 0.469
    },
    "xgboost_anomaly": {
      "threshold": 3036349.9,
      "anomaly_rate": 0.0069,
      "anomalies_detected": 1
    }
  }
}
```

### Data Summary JSON

```json
{
  "timestamp": "2026-01-01T10:00:00",
  "shape": [167, 7],
  "time_range": {
    "start": "2025-12-31T10:00:00",
    "end": "2026-01-01T10:00:00"
  },
  "columns": ["timestamp", "memory_bytes", "cpu_utilization", ...],
  "statistics": {
    "cpu_utilization": {
      "mean": 0.098,
      "std": 0.159,
      "min": 0.004,
      "max": 0.502
    },
    ...
  }
}
```

---

## Dependencies

### `requirements.txt`

```
# Core
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0

# Cloud
google-cloud-monitoring>=2.16.0

# Models
prophet>=1.1.0
xgboost>=2.0.0

# API (Phase 5)
fastapi>=0.104.0
uvicorn>=0.24.0
prometheus-client>=0.19.0

# Utilities
pydantic>=2.5.0
joblib>=1.3.0
```

### Install

```bash
cd ml
pip install -r requirements.txt
```

---

## Extending the Pipeline

### Adding a New Model

1. Create `ml/models/your_model.py`:

```python
from typing import Dict, Any
import pandas as pd

class YourModel:
    def __init__(self, **params):
        self.params = params
        self.model_ = None
    
    def fit(self, df: pd.DataFrame, target: str) -> 'YourModel':
        # Training logic
        return self
    
    def predict(self, periods: int) -> pd.DataFrame:
        # Prediction logic
        return predictions
    
    def evaluate(self, actual: pd.Series) -> Dict[str, float]:
        # Evaluation metrics
        return {'mae': ..., 'mape': ...}
```

2. Register in `ml/models/__init__.py`:

```python
from .your_model import YourModel
```

3. Add to training pipeline in `ml/train.py`.

### Adding a New Metrics Adapter

1. Create `ml/pipeline/adapters/aws_adapter.py`:

```python
from abc import ABC, abstractmethod
import pandas as pd

class MetricsAdapter(ABC):
    @abstractmethod
    def fetch_container_metrics(self, namespace: str, hours: int) -> pd.DataFrame:
        pass

class AWSCloudWatchAdapter(MetricsAdapter):
    def __init__(self, region: str):
        import boto3
        self.client = boto3.client('cloudwatch', region_name=region)
    
    def fetch_container_metrics(self, namespace: str, hours: int) -> pd.DataFrame:
        # CloudWatch implementation
        pass
```

2. Update `config.py` to support provider selection.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `No module named 'google'` | Missing dependency | `pip install google-cloud-monitoring` |
| `404 metric not found` | Metric not available | Check metric name in Cloud Console |
| `Empty DataFrame` | No data in time range | Increase `hours` parameter |
| `Prophet NaN predictions` | Not enough data | Need at least 2 full seasonality cycles |
| `XGBoost memory error` | Too many features | Reduce lag/rolling windows |

### Debug Commands

```bash
# List available metrics
cd ml
python list_metrics.py

# Check data availability
python check_data.py

# Test fetcher
python test_fetch.py
```
