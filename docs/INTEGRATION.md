# Helios Integration Guide

## Integrating Helios into Existing Infrastructure

This guide explains how to deploy Helios into an existing customer environment to provide predictive infrastructure intelligence.

---

## Table of Contents

1. [Integration Architecture](#integration-architecture)
2. [Deployment Options](#deployment-options)
3. [Step-by-Step Integration](#step-by-step-integration)
4. [Gaming App Example](#gaming-app-example)
5. [Custom Metrics Configuration](#custom-metrics-configuration)
6. [Multi-Tenant Setup](#multi-tenant-setup)

---

## Integration Architecture

Helios connects to your existing observability stack - it doesn't replace it:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CUSTOMER INFRASTRUCTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Gaming App      │    │ API Servers     │    │ Database        │         │
│  │ (Unity/Unreal)  │    │ (Node.js/Go)    │    │ (PostgreSQL)    │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
│           └──────────────────────┼──────────────────────┘                   │
│                                  │                                          │
│                                  ▼                                          │
│                    ┌─────────────────────────┐                              │
│                    │ Existing Prometheus     │◄─── Customer's existing      │
│                    │ (or Datadog/CloudWatch) │     monitoring stack         │
│                    └────────────┬────────────┘                              │
│                                 │                                           │
│  ┌──────────────────────────────┼───────────────────────────────────────┐  │
│  │                              │         HELIOS (NEW)                   │  │
│  │                              ▼                                        │  │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │  │
│  │  │ Metrics Adapter │──▶│ ML Pipeline     │──▶│ Inference API   │     │  │
│  │  │ • Prometheus    │   │ • Training      │   │ • /predict      │     │  │
│  │  │ • Datadog       │   │ • XGBoost       │   │ • /detect       │     │  │
│  │  │ • CloudWatch    │   │ • Prophet       │   │ • /recommend    │     │  │
│  │  └─────────────────┘   └─────────────────┘   └────────┬────────┘     │  │
│  │                                                       │              │  │
│  │                                          ┌────────────┼────────────┐ │  │
│  │                                          ▼            ▼            ▼ │  │
│  │                                    ┌──────────┐ ┌──────────┐ ┌─────┐ │  │
│  │                                    │ Webhook  │ │ Slack    │ │ API │ │  │
│  │                                    │ (custom) │ │ Alerts   │ │     │ │  │
│  │                                    └──────────┘ └──────────┘ └─────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Options

### Option 1: Sidecar Deployment (Recommended for Single Customer)

Deploy Helios alongside existing services in the customer's cluster:

```yaml
# helios-customer-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helios-inference
  namespace: helios
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: helios-inference
          image: gcr.io/YOUR_PROJECT/helios-inference:latest
          env:
            - name: PROMETHEUS_URL
              value: "http://prometheus.monitoring:9090"  # Customer's Prometheus
            - name: CUSTOMER_ID
              value: "gaming-corp"
            - name: METRICS_NAMESPACE
              value: "gaming-app"
```

### Option 2: SaaS / Multi-Tenant

Run Helios as a service that multiple customers connect to:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HELIOS SaaS PLATFORM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Customer A        Customer B        Customer C                │
│   (Gaming)          (E-commerce)      (Fintech)                 │
│       │                 │                 │                     │
│       ▼                 ▼                 ▼                     │
│   ┌───────────────────────────────────────────────────────┐    │
│   │              Helios API Gateway                        │    │
│   │              (tenant isolation)                        │    │
│   └───────────────────────────────────────────────────────┘    │
│                           │                                     │
│   ┌───────────┬───────────┼───────────┬───────────────┐        │
│   ▼           ▼           ▼           ▼               ▼        │
│ ┌─────┐   ┌─────┐    ┌─────────┐  ┌─────────┐   ┌─────────┐   │
│ │ML-A │   │ML-B │    │ML-C     │  │Models   │   │Dashboard│   │
│ │     │   │     │    │         │  │Store    │   │(Grafana)│   │
│ └─────┘   └─────┘    └─────────┘  └─────────┘   └─────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Option 3: Agent-Based (Remote Monitoring)

Install a lightweight agent that pushes metrics to Helios:

```python
# helios_agent.py - Install on customer infrastructure
from helios_sdk import HeliosAgent

agent = HeliosAgent(
    api_key="customer-api-key",
    endpoint="https://helios.yourcompany.com",
    customer_id="gaming-corp"
)

# Auto-discover and forward metrics
agent.discover_prometheus("http://localhost:9090")
agent.start()
```

---

## Step-by-Step Integration

### Step 1: Assess Customer's Current Stack

```powershell
# Questions to answer:
# 1. What monitoring system? (Prometheus, Datadog, CloudWatch, etc.)
# 2. What cloud provider? (GCP, AWS, Azure, on-prem)
# 3. What orchestration? (Kubernetes, ECS, VMs)
# 4. What are the key services to monitor?
```

### Step 2: Configure Metrics Adapter

Create a customer-specific configuration:

```python
# ml/adapters/gaming_corp_config.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class GamingCorpConfig:
    """Configuration for Gaming Corp integration."""
    
    customer_id: str = "gaming-corp"
    
    # Their Prometheus endpoint
    prometheus_url: str = "http://prometheus.gaming-corp.internal:9090"
    
    # Key metrics to monitor
    metrics: List[str] = field(default_factory=lambda: [
        # Game server metrics
        "game_server_active_players",
        "game_server_matches_in_progress", 
        "game_server_queue_length",
        "game_server_latency_ms",
        
        # Infrastructure metrics
        "container_cpu_usage_seconds_total",
        "container_memory_usage_bytes",
        "http_requests_total",
        "http_request_duration_seconds",
        
        # Database metrics
        "pg_stat_activity_count",
        "pg_database_size_bytes",
    ])
    
    # Gaming-specific thresholds
    thresholds: dict = field(default_factory=lambda: {
        "max_players_per_server": 100,
        "latency_warning_ms": 50,
        "latency_critical_ms": 100,
        "queue_length_scale_trigger": 50,
    })
```

### Step 3: Train Models on Customer Data

```python
# ml/train_customer.py
import os
from config import GamingCorpConfig
from pipeline.data_fetcher import DataFetcher
from models.xgboost_forecaster import XGBoostForecaster

def train_for_customer(customer_config):
    """Train models specific to customer's patterns."""
    
    # Fetch historical data (7-30 days recommended)
    fetcher = DataFetcher(
        prometheus_url=customer_config.prometheus_url,
        metrics=customer_config.metrics
    )
    
    data = fetcher.fetch_historical(days=14)
    
    # Train forecasting models
    cpu_model = XGBoostForecaster(target="cpu")
    cpu_model.train(data)
    
    memory_model = XGBoostForecaster(target="memory")
    memory_model.train(data)
    
    # Train anomaly detection on their normal patterns
    anomaly_model = IsolationForestDetector()
    anomaly_model.train(data)
    
    # Save models with customer prefix
    cpu_model.save(f"models/{customer_config.customer_id}_cpu_forecaster.joblib")
    memory_model.save(f"models/{customer_config.customer_id}_memory_forecaster.joblib")
    anomaly_model.save(f"models/{customer_config.customer_id}_anomaly_detector.joblib")

if __name__ == "__main__":
    config = GamingCorpConfig()
    train_for_customer(config)
```

### Step 4: Deploy Customer Instance

```yaml
# infra/kubernetes/customers/gaming-corp/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helios-gaming-corp
  namespace: helios
  labels:
    customer: gaming-corp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: helios-inference
      customer: gaming-corp
  template:
    metadata:
      labels:
        app: helios-inference
        customer: gaming-corp
    spec:
      containers:
        - name: inference
          image: gcr.io/YOUR_PROJECT/helios-inference:latest
          ports:
            - containerPort: 8080
          env:
            - name: CUSTOMER_ID
              value: "gaming-corp"
            - name: PROMETHEUS_URL
              value: "http://prometheus.gaming-corp.internal:9090"
            - name: MODEL_PREFIX
              value: "gaming-corp"
            - name: GCS_BUCKET
              value: "helios-models-production"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
```

### Step 5: Configure Webhooks/Alerts

```yaml
# Customer alert configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: helios-alerts-gaming-corp
data:
  alerts.yaml: |
    webhooks:
      - name: slack
        url: "https://hooks.slack.com/services/CUSTOMER_WEBHOOK"
        events:
          - anomaly_detected
          - scaling_recommended
          - capacity_warning
      
      - name: pagerduty
        url: "https://events.pagerduty.com/v2/enqueue"
        routing_key: "CUSTOMER_ROUTING_KEY"
        events:
          - anomaly_detected
          - capacity_critical
    
    thresholds:
      anomaly_alert: 2.5  # Z-score
      capacity_warning: 0.75
      capacity_critical: 0.90
```

---

## Gaming App Example

### Gaming-Specific Challenges

| Challenge | Helios Solution |
|-----------|-----------------|
| **Spike traffic** (game launches, events) | Prophet model with custom seasonality for scheduled events |
| **Match-based scaling** | Custom metrics: `active_matches`, `players_in_queue` |
| **Regional patterns** | Time-zone aware forecasting |
| **Real-time requirements** | Sub-second latency detection |

### Custom Metrics for Gaming

```python
# ml/adapters/gaming_metrics.py
"""
Gaming-specific metric transformations and features.
"""

GAMING_METRICS = {
    # Player activity
    "concurrent_users": {
        "prometheus_query": "sum(game_active_sessions)",
        "forecast_horizon": "1h",
        "seasonality": ["hourly", "daily", "weekly"],
    },
    
    # Match orchestration  
    "matches_in_progress": {
        "prometheus_query": "sum(game_matches_active)",
        "scale_trigger": "matches_in_queue > 100",
    },
    
    # Server capacity
    "server_utilization": {
        "prometheus_query": "avg(game_server_players / game_server_capacity)",
        "warning_threshold": 0.8,
        "critical_threshold": 0.95,
    },
    
    # Latency (critical for gaming)
    "game_latency_p99": {
        "prometheus_query": "histogram_quantile(0.99, game_request_latency_bucket)",
        "anomaly_detection": True,
        "alert_threshold_ms": 100,
    },
}

def create_gaming_features(df):
    """Create gaming-specific features for ML models."""
    
    # Time-based features
    df['hour'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    # Peak hours (typically 6 PM - 11 PM local time)
    df['is_peak_hour'] = df['hour'].between(18, 23).astype(int)
    
    # Rolling statistics for player counts
    df['players_rolling_1h'] = df['concurrent_users'].rolling('1H').mean()
    df['players_rolling_24h'] = df['concurrent_users'].rolling('24H').mean()
    
    # Match queue pressure
    df['queue_pressure'] = df['matches_in_queue'] / df['matches_in_progress'].clip(lower=1)
    
    # Server headroom
    df['server_headroom'] = 1 - df['server_utilization']
    
    return df
```

### Gaming-Specific Scaling Rules

```yaml
# infra/kubernetes/customers/gaming-corp/keda-scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: game-server-scaler
  namespace: gaming
spec:
  scaleTargetRef:
    name: game-server
  minReplicaCount: 5
  maxReplicaCount: 100
  
  triggers:
    # Scale based on Helios predictions
    - type: prometheus
      metadata:
        serverAddress: http://helios-inference.helios:8080
        metricName: helios_predicted_players_1h
        threshold: "80"  # Players per server
        query: |
          helios_forecast_value{
            customer="gaming-corp",
            metric="concurrent_users",
            horizon="1h"
          }
    
    # Emergency scale on queue length
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring:9090
        metricName: game_match_queue
        threshold: "50"
        query: sum(game_matches_in_queue)
    
    # Scale based on anomaly detection
    - type: prometheus
      metadata:
        serverAddress: http://helios-inference.helios:8080
        metricName: helios_anomaly_score
        threshold: "2.5"
        query: |
          helios_anomaly_score{
            customer="gaming-corp",
            metric="concurrent_users"
          }

  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 30  # Fast scale-up for gaming
          policies:
            - type: Percent
              value: 100
              periodSeconds: 15
        scaleDown:
          stabilizationWindowSeconds: 300  # Slow scale-down
          policies:
            - type: Percent
              value: 10
              periodSeconds: 60
```

### Event-Based Scaling (Game Launches, Tournaments)

```python
# ml/adapters/gaming_events.py
"""
Handle scheduled gaming events that cause predictable traffic spikes.
"""

from datetime import datetime, timedelta
from typing import List

class GamingEventScheduler:
    """Manage known events that affect traffic."""
    
    def __init__(self):
        self.events = []
    
    def add_event(self, name: str, start: datetime, duration_hours: int, 
                  expected_multiplier: float):
        """
        Add a scheduled event.
        
        Args:
            name: Event name (e.g., "Season 5 Launch")
            start: Event start time
            duration_hours: How long the spike lasts
            expected_multiplier: Expected traffic multiplier (e.g., 3.0 = 3x normal)
        """
        self.events.append({
            "name": name,
            "start": start,
            "end": start + timedelta(hours=duration_hours),
            "multiplier": expected_multiplier,
        })
    
    def get_multiplier(self, timestamp: datetime) -> float:
        """Get the expected traffic multiplier for a given time."""
        for event in self.events:
            if event["start"] <= timestamp <= event["end"]:
                return event["multiplier"]
        return 1.0
    
    def adjust_forecast(self, forecast: float, timestamp: datetime) -> float:
        """Adjust ML forecast based on scheduled events."""
        multiplier = self.get_multiplier(timestamp)
        return forecast * multiplier


# Example usage
scheduler = GamingEventScheduler()

# Add known events
scheduler.add_event(
    name="Season 5 Launch",
    start=datetime(2026, 1, 15, 10, 0),  # 10 AM UTC
    duration_hours=48,
    expected_multiplier=5.0  # Expect 5x normal traffic
)

scheduler.add_event(
    name="Weekend Tournament",
    start=datetime(2026, 1, 18, 14, 0),  # Saturday 2 PM UTC
    duration_hours=8,
    expected_multiplier=2.5
)
```

### Gaming Dashboard (Grafana)

```json
{
  "dashboard": {
    "title": "Helios - Gaming Corp",
    "panels": [
      {
        "title": "Player Forecast (1 Hour)",
        "type": "timeseries",
        "targets": [
          {
            "expr": "game_active_sessions",
            "legendFormat": "Actual Players"
          },
          {
            "expr": "helios_forecast_value{customer='gaming-corp', metric='concurrent_users', horizon='1h'}",
            "legendFormat": "Predicted (1h)"
          }
        ]
      },
      {
        "title": "Anomaly Detection",
        "type": "stat",
        "targets": [
          {
            "expr": "helios_anomaly_score{customer='gaming-corp'}",
            "legendFormat": "Anomaly Score"
          }
        ],
        "thresholds": [
          {"value": 0, "color": "green"},
          {"value": 2, "color": "yellow"},
          {"value": 3, "color": "red"}
        ]
      },
      {
        "title": "Scaling Recommendations",
        "type": "table",
        "targets": [
          {
            "expr": "helios_recommendation{customer='gaming-corp'}",
            "format": "table"
          }
        ]
      },
      {
        "title": "Server Capacity Headroom",
        "type": "gauge",
        "targets": [
          {
            "expr": "1 - avg(game_server_players / game_server_capacity)",
            "legendFormat": "Available Capacity"
          }
        ]
      }
    ]
  }
}
```

---

## Custom Metrics Configuration

### Adapter Interface

```python
# ml/adapters/base.py
from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd

class MetricsAdapter(ABC):
    """Base class for metrics adapters."""
    
    @abstractmethod
    def fetch_metrics(self, start_time, end_time) -> pd.DataFrame:
        """Fetch metrics from the source system."""
        pass
    
    @abstractmethod
    def get_current_metrics(self) -> Dict[str, float]:
        """Get current metric values."""
        pass
    
    @abstractmethod
    def list_available_metrics(self) -> List[str]:
        """List all available metrics."""
        pass


class PrometheusAdapter(MetricsAdapter):
    """Adapter for Prometheus-compatible systems."""
    
    def __init__(self, url: str, queries: Dict[str, str]):
        self.url = url
        self.queries = queries
    
    def fetch_metrics(self, start_time, end_time) -> pd.DataFrame:
        # Implementation...
        pass


class DatadogAdapter(MetricsAdapter):
    """Adapter for Datadog."""
    
    def __init__(self, api_key: str, app_key: str):
        self.api_key = api_key
        self.app_key = app_key
    
    def fetch_metrics(self, start_time, end_time) -> pd.DataFrame:
        # Implementation using Datadog API...
        pass


class CloudWatchAdapter(MetricsAdapter):
    """Adapter for AWS CloudWatch."""
    
    def __init__(self, region: str, namespace: str):
        self.region = region
        self.namespace = namespace
    
    def fetch_metrics(self, start_time, end_time) -> pd.DataFrame:
        # Implementation using boto3...
        pass
```

---

## Multi-Tenant Setup

### Database Schema

```sql
-- Multi-tenant schema for Helios SaaS
CREATE TABLE customers (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    plan VARCHAR(50) DEFAULT 'standard',  -- standard, pro, enterprise
    settings JSONB DEFAULT '{}'
);

CREATE TABLE customer_metrics (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    metric_name VARCHAR(255) NOT NULL,
    prometheus_query TEXT,
    forecast_enabled BOOLEAN DEFAULT true,
    anomaly_enabled BOOLEAN DEFAULT true,
    thresholds JSONB DEFAULT '{}'
);

CREATE TABLE models (
    id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    model_type VARCHAR(50) NOT NULL,  -- forecaster, anomaly_detector
    model_path VARCHAR(500) NOT NULL,
    trained_at TIMESTAMP DEFAULT NOW(),
    metrics JSONB,  -- Training metrics (MAE, accuracy, etc.)
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    timestamp TIMESTAMP NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    predicted_value FLOAT NOT NULL,
    actual_value FLOAT,
    horizon_minutes INT NOT NULL,
    model_id UUID REFERENCES models(id)
);

CREATE TABLE anomalies (
    id BIGSERIAL PRIMARY KEY,
    customer_id UUID REFERENCES customers(id),
    detected_at TIMESTAMP NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    anomaly_score FLOAT NOT NULL,
    description TEXT,
    acknowledged BOOLEAN DEFAULT false
);
```

### API with Tenant Isolation

```python
# ml/inference/app_multitenant.py
from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Optional

app = FastAPI(title="Helios Multi-Tenant API")

async def get_customer(x_api_key: str = Header(...)):
    """Validate API key and return customer context."""
    customer = await db.customers.find_one({"api_key": x_api_key})
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return customer

@app.get("/predict")
async def predict(
    metric: str,
    horizon: int = 15,
    customer = Depends(get_customer)
):
    """Get prediction for customer's metric."""
    
    # Load customer-specific model
    model = load_model(f"{customer['id']}_forecaster")
    
    # Get customer's current metrics
    adapter = get_adapter(customer)
    current_data = adapter.get_current_metrics()
    
    # Generate prediction
    prediction = model.predict(current_data, horizon)
    
    return {
        "customer": customer["name"],
        "metric": metric,
        "horizon_minutes": horizon,
        "predicted_value": prediction,
        "timestamp": datetime.utcnow().isoformat()
    }
```

---

## Pricing Model Considerations

| Tier | Features | Metrics | Retention | Price |
|------|----------|---------|-----------|-------|
| **Starter** | Basic forecasting | 10 | 7 days | $99/mo |
| **Pro** | + Anomaly detection, webhooks | 50 | 30 days | $299/mo |
| **Enterprise** | + Custom models, SLA, support | Unlimited | 90 days | Custom |

---

## Next Steps for Customer Integration

1. **Discovery Call**: Understand their stack and pain points
2. **POC Deployment**: 2-week trial with their data
3. **Model Training**: Train on 14-30 days of historical data
4. **Integration**: Connect to their alerting systems
5. **Tuning**: Adjust thresholds based on feedback
6. **Production**: Full deployment with monitoring
