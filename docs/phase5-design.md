# Phase 5: Inference Service Design

## Overview

Phase 5 implements the **Helios Inference Service** - a real-time prediction API that serves ML models and provides actionable scaling recommendations.

---

## Goals

1. **Serve trained models** via REST API
2. **Expose Prometheus metrics** for integration with KEDA
3. **Provide recommendations** for scaling and resource optimization
4. **Enable autoscaling** through KEDA + Prometheus integration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 5 ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INFERENCE SERVICE (FastAPI)                       │   │
│  │  Port: 8080                                                          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │   │
│  │  │ /health   │ │ /predict  │ │ /detect   │ │/recommend │           │   │
│  │  │ /ready    │ │           │ │           │ │           │           │   │
│  │  │ /models   │ │           │ │           │ │           │           │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │ /metrics (Prometheus format)                                   │  │   │
│  │  │ - helios_predicted_cpu                                         │  │   │
│  │  │ - helios_predicted_memory                                      │  │   │
│  │  │ - helios_anomaly_score                                         │  │   │
│  │  │ - helios_recommended_replicas                                  │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                            │                                               │
│                            │ Prometheus scrape                             │
│                            ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        PROMETHEUS                                    │   │
│  │  - Scrapes /metrics endpoint                                        │   │
│  │  - Stores time-series data                                          │   │
│  │  - Provides PromQL interface                                        │   │
│  └─────────────────────────┬───────────────────────────────────────────┘   │
│                            │                                               │
│         ┌──────────────────┼──────────────────┐                           │
│         ▼                  ▼                  ▼                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │   Grafana   │    │    KEDA     │    │Alertmanager │                   │
│  │ (dashboards)│    │ (autoscale) │    │  (alerts)   │                   │
│  └─────────────┘    └──────┬──────┘    └─────────────┘                   │
│                            │                                               │
│                            ▼                                               │
│                     ┌─────────────┐                                       │
│                     │ Target HPA  │                                       │
│                     │ (Saleor)    │                                       │
│                     └─────────────┘                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Inference Service (FastAPI)

**Location:** `ml/inference/`

```
ml/inference/
├── __init__.py
├── app.py              # FastAPI application
├── config.py           # Service configuration
├── models.py           # Pydantic request/response schemas
├── model_manager.py    # Load and manage ML models
├── predictor.py        # Prediction logic
├── anomaly_detector.py # Anomaly scoring logic
├── recommender.py      # Recommendation engine
└── metrics.py          # Prometheus metrics
```

### 2. Real-time Scoring Loop

**Location:** `ml/scoring/`

```
ml/scoring/
├── __init__.py
├── scorer.py           # Main scoring loop
├── metrics_stream.py   # Fetch latest metrics from cloud
└── publisher.py        # Update Prometheus gauges
```

### 3. Kubernetes Manifests

**Location:** `infra/kubernetes/helios-inference/`

```
infra/kubernetes/helios-inference/
├── namespace.yaml
├── configmap.yaml
├── deployment.yaml
├── service.yaml
├── serviceaccount.yaml
├── pod-monitoring.yaml
└── kustomization.yaml
```

### 4. KEDA Integration

**Location:** `infra/kubernetes/keda/`

```
infra/kubernetes/keda/
├── namespace.yaml
├── scaledobject-saleor.yaml
└── kustomization.yaml
```

### 5. Grafana Dashboards

**Location:** `infra/kubernetes/grafana/dashboards/`

```
infra/kubernetes/grafana/dashboards/
├── helios-overview.json
├── helios-predictions.json
├── helios-anomalies.json
└── helios-recommendations.json
```

### 6. Alertmanager Rules

**Location:** `infra/kubernetes/alertmanager/`

```
infra/kubernetes/alertmanager/
├── alertmanager-config.yaml
└── helios-rules.yaml
```

---

## API Specification

### Health & Info

```yaml
GET /health
Response:
  {
    "status": "healthy",
    "timestamp": "2026-01-02T10:00:00Z"
  }

GET /ready
Response:
  {
    "ready": true,
    "models_loaded": ["baseline", "prophet", "xgboost"]
  }

GET /models
Response:
  {
    "models": [
      {
        "name": "baseline",
        "version": "1.0.0",
        "loaded_at": "2026-01-02T09:00:00Z",
        "metrics": {"mape": 0.026}
      },
      {
        "name": "prophet",
        "version": "1.0.0",
        "loaded_at": "2026-01-02T09:00:00Z",
        "metrics": {"coverage": 0.469}
      },
      {
        "name": "xgboost",
        "version": "1.0.0",
        "loaded_at": "2026-01-02T09:00:00Z",
        "metrics": {"anomaly_rate": 0.0069}
      }
    ]
  }
```

### Prediction

```yaml
POST /predict
Request:
  {
    "metrics": {
      "cpu_utilization": 0.45,
      "memory_utilization": 0.62,
      "memory_bytes": 536870912,
      "db_cpu": 0.30,
      "db_memory": 0.55,
      "db_connections": 15
    },
    "periods": 12,
    "model": "baseline"  # Optional: baseline, prophet, or auto
  }

Response:
  {
    "predictions": [
      {
        "period": 1,
        "timestamp": "2026-01-02T10:05:00Z",
        "cpu_utilization": 0.48,
        "memory_utilization": 0.63,
        "confidence_lower": 0.42,
        "confidence_upper": 0.54
      },
      # ... 12 periods
    ],
    "model_used": "baseline",
    "confidence": 0.87
  }
```

### Anomaly Detection

```yaml
POST /detect
Request:
  {
    "metrics": {
      "cpu_utilization": 0.95,
      "memory_utilization": 0.88,
      "memory_bytes": 1073741824,
      "db_cpu": 0.85,
      "db_memory": 0.75,
      "db_connections": 150
    }
  }

Response:
  {
    "anomaly_score": 2.8,
    "is_anomaly": true,
    "threshold": 2.5,
    "severity": "warning",  # normal, warning, critical
    "contributing_features": [
      {"feature": "db_connections", "contribution": 0.45},
      {"feature": "cpu_utilization", "contribution": 0.30},
      {"feature": "memory_utilization", "contribution": 0.25}
    ]
  }
```

### Recommendations

```yaml
POST /recommend
Request:
  {
    "namespace": "saleor",
    "deployment": "saleor-api",
    "current_replicas": 2,
    "current_metrics": {
      "cpu_utilization": 0.75,
      "memory_utilization": 0.60
    },
    "predicted_metrics": {
      "cpu_utilization": 0.85,
      "memory_utilization": 0.65
    },
    "anomaly_score": 1.2
  }

Response:
  {
    "recommendations": [
      {
        "type": "scaling",
        "action": "scale_up",
        "target_replicas": 4,
        "reason": "Predicted CPU 85% exceeds threshold 80%",
        "confidence": 0.87,
        "urgency": "medium",
        "execute_by": "2026-01-02T10:15:00Z"
      }
    ],
    "summary": "Scale up recommended before predicted load increase"
  }
```

### Prometheus Metrics

```yaml
GET /metrics
Response (text/plain):
  # HELP helios_predicted_cpu Predicted CPU utilization
  # TYPE helios_predicted_cpu gauge
  helios_predicted_cpu{namespace="saleor",deployment="saleor-api",horizon="5m"} 0.48
  helios_predicted_cpu{namespace="saleor",deployment="saleor-api",horizon="30m"} 0.72
  
  # HELP helios_anomaly_score Current anomaly score
  # TYPE helios_anomaly_score gauge
  helios_anomaly_score{namespace="saleor",deployment="saleor-api"} 1.2
  
  # HELP helios_anomaly_detected Whether anomaly is detected (0/1)
  # TYPE helios_anomaly_detected gauge
  helios_anomaly_detected{namespace="saleor",deployment="saleor-api"} 0
  
  # HELP helios_recommended_replicas Recommended replica count
  # TYPE helios_recommended_replicas gauge
  helios_recommended_replicas{namespace="saleor",deployment="saleor-api"} 4
  
  # HELP helios_inference_duration_seconds Inference latency
  # TYPE helios_inference_duration_seconds histogram
  helios_inference_duration_seconds_bucket{endpoint="/predict",le="0.1"} 950
  helios_inference_duration_seconds_bucket{endpoint="/predict",le="0.5"} 999
  helios_inference_duration_seconds_bucket{endpoint="/predict",le="1.0"} 1000
```

---

## KEDA ScaledObject

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: saleor-api-scaler
  namespace: saleor
spec:
  scaleTargetRef:
    name: saleor-api
  minReplicaCount: 1
  maxReplicaCount: 10
  pollingInterval: 30
  cooldownPeriod: 300
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring.svc:9090
        metricName: helios_predicted_cpu
        query: |
          helios_predicted_cpu{
            namespace="saleor",
            deployment="saleor-api",
            horizon="30m"
          }
        threshold: "70"
        activationThreshold: "50"
```

---

## Configuration

### Environment Variables

```bash
# Service
HELIOS_PORT=8080
HELIOS_LOG_LEVEL=INFO

# Models
HELIOS_MODEL_PATH=/app/models
HELIOS_MODEL_REFRESH_INTERVAL=3600

# Metrics
HELIOS_METRICS_NAMESPACE=saleor
HELIOS_METRICS_DEPLOYMENT=saleor-api

# Cloud (for real-time scoring)
GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
HELIOS_SCORING_INTERVAL=300

# Thresholds
HELIOS_CPU_SCALE_UP=0.80
HELIOS_CPU_SCALE_DOWN=0.20
HELIOS_MEMORY_WARNING=0.85
HELIOS_ANOMALY_THRESHOLD=2.5
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: helios-config
  namespace: helios
data:
  config.yaml: |
    service:
      port: 8080
      log_level: INFO
    
    scoring:
      interval_seconds: 300
      namespace: saleor
      deployment: saleor-api
    
    thresholds:
      cpu_scale_up: 0.80
      cpu_scale_down: 0.20
      memory_warning: 0.85
      anomaly_sigma: 2.5
    
    scaling:
      min_replicas: 1
      max_replicas: 10
      cooldown_seconds: 300
```

---

## Implementation Order

| Step | Task | Est. Time |
|------|------|-----------|
| 5.1 | Pydantic schemas (`models.py`) | 15 min |
| 5.2 | Model manager (`model_manager.py`) | 20 min |
| 5.3 | Predictor (`predictor.py`) | 15 min |
| 5.4 | Anomaly detector (`anomaly_detector.py`) | 15 min |
| 5.5 | Recommender (`recommender.py`) | 25 min |
| 5.6 | Prometheus metrics (`metrics.py`) | 15 min |
| 5.7 | FastAPI app (`app.py`) | 20 min |
| 5.8 | Real-time scorer (`scoring/`) | 25 min |
| 5.9 | Dockerfile | 10 min |
| 5.10 | K8s manifests | 20 min |
| 5.11 | KEDA ScaledObject | 15 min |
| 5.12 | Grafana dashboards | 20 min |
| 5.13 | Alertmanager rules | 15 min |
| 5.14 | Testing & validation | 30 min |

**Total: ~4 hours**

---

## Success Criteria

- [ ] `/health` responds < 100ms
- [ ] `/predict` returns forecasts with confidence intervals
- [ ] `/detect` flags anomalies correctly
- [ ] `/recommend` provides actionable scaling advice
- [ ] `/metrics` exposes Prometheus gauges
- [ ] KEDA scales Saleor based on predictions
- [ ] Grafana shows predictions vs actuals
- [ ] Alerts fire on anomaly detection

---

## Testing Plan

### Unit Tests
```bash
cd ml
pytest tests/inference/
```

### Integration Tests
```bash
# Port-forward inference service
kubectl port-forward -n helios svc/helios-inference 8080:8080

# Test health
curl http://localhost:8080/health

# Test predict
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"metrics": {"cpu_utilization": 0.5}, "periods": 6}'

# Test detect
curl -X POST http://localhost:8080/detect \
  -H "Content-Type: application/json" \
  -d '{"metrics": {"cpu_utilization": 0.95}}'

# Test metrics
curl http://localhost:8080/metrics
```

### Load Test
```bash
# Use Locust to stress test inference service
locust -f loadtest/inference_test.py --host=http://localhost:8080
```

---

## Rollback Plan

1. **If inference service fails:**
   - KEDA continues using last known metric values
   - Revert to standard CPU-based HPA as fallback

2. **If predictions are inaccurate:**
   - Disable KEDA ScaledObject
   - Investigate model drift
   - Retrain with fresh data

3. **If alerts are noisy:**
   - Adjust thresholds in ConfigMap
   - Add silencing rules in Alertmanager
