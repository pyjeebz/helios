# Helios Architecture Design

## 1. System Overview

Helios is a **predictive infrastructure intelligence platform** that uses machine learning to forecast resource demand and provide proactive scaling recommendations.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              HELIOS PLATFORM                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Metrics    │───▶│     ML       │───▶│  Inference   │───▶│   Output     │  │
│  │   Adapter    │    │   Pipeline   │    │   Service    │    │   Layer      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         ▲                                       │                    │          │
│         │                                       ▼                    ▼          │
│  ┌──────────────┐                     ┌──────────────┐    ┌──────────────┐     │
│  │   Cloud      │                     │    KEDA      │    │   Grafana    │     │
│  │   Provider   │                     │  Autoscaler  │    │   Dashboard  │     │
│  └──────────────┘                     └──────────────┘    └──────────────┘     │
│         ▲                                       │                              │
└─────────│───────────────────────────────────────│──────────────────────────────┘
          │                                       │
          │                                       ▼
┌─────────────────────┐                ┌─────────────────────┐
│   Target Workload   │◀───────────────│   Kubernetes HPA    │
│   (e.g., Saleor)    │                └─────────────────────┘
└─────────────────────┘
```

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Multi-Cloud** | Works on GKE, EKS, AKS, or any Kubernetes cluster |
| **Cloud-Agnostic** | Pluggable adapters for metrics sources |
| **Prometheus-Native** | Standard metrics format for easy integration |
| **Progressive** | Start simple (baseline), add complexity as needed |
| **Observable** | Full visibility into predictions and decisions |

---

## 2. Component Architecture

### 2.1 Metrics Adapter Layer

**Purpose:** Abstract cloud provider differences, provide unified metrics interface.

```
┌─────────────────────────────────────────────────────────────────┐
│                    METRICS ADAPTER LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    GCP      │  │    AWS      │  │   Azure     │             │
│  │  Adapter    │  │  Adapter    │  │  Adapter    │             │
│  │  (Cloud     │  │  (Cloud     │  │  (Azure     │             │
│  │  Monitoring)│  │  Watch)     │  │  Monitor)   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
│                 ┌─────────────────┐                             │
│                 │ Prometheus      │ (Alternative: direct scrape)│
│                 │ Adapter         │                             │
│                 └────────┬────────┘                             │
│                          ▼                                      │
│                 ┌─────────────────┐                             │
│                 │ Unified Metrics │                             │
│                 │ Interface       │                             │
│                 └─────────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

**Adapter Interface:**

```python
class MetricsAdapter(ABC):
    """Abstract base for cloud-agnostic metrics fetching."""
    
    @abstractmethod
    def fetch_container_metrics(
        self, 
        namespace: str, 
        hours: int
    ) -> pd.DataFrame:
        """Fetch CPU, memory metrics for containers."""
        pass
    
    @abstractmethod  
    def fetch_database_metrics(
        self,
        instance_id: str,
        hours: int
    ) -> pd.DataFrame:
        """Fetch database CPU, connections, etc."""
        pass
```

**Implemented Adapters:**

| Adapter | Source | Status |
|---------|--------|--------|
| `GCPMetricsAdapter` | Cloud Monitoring API | ✅ Implemented |
| `AWSMetricsAdapter` | CloudWatch API | 🔲 Planned |
| `AzureMetricsAdapter` | Azure Monitor API | 🔲 Planned |
| `PrometheusMetricsAdapter` | Prometheus Query API | 🔲 Planned |

**Metrics Collected:**

```yaml
container_metrics:
  - cpu_utilization          # 0-1 ratio
  - memory_utilization       # 0-1 ratio  
  - memory_bytes             # Absolute memory usage
  - restart_count            # Container restarts

database_metrics:
  - db_cpu_utilization       # 0-1 ratio
  - db_memory_utilization    # 0-1 ratio
  - db_connections           # Active connections
  - db_replication_lag       # Seconds (if replica)

cache_metrics:
  - redis_memory_utilization # 0-1 ratio
  - redis_connections        # Connected clients
  - redis_hit_rate           # Cache hit ratio
```

---

### 2.2 ML Pipeline

**Purpose:** Train and evaluate forecasting and anomaly detection models.

```
┌─────────────────────────────────────────────────────────────────┐
│                       ML PIPELINE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Data Fetcher                            │   │
│  │  • Cloud Monitoring API integration                      │   │
│  │  • Time alignment (5-min buckets)                        │   │
│  │  • Multi-metric merging                                  │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Feature Engineering                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │ Temporal │ │   Lag    │ │ Rolling  │ │ Percent  │   │   │
│  │  │ Features │ │ Features │ │ Stats    │ │ Change   │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  │                                                         │   │
│  │  Input: 7 raw metrics → Output: 108 features            │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Model Training                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │   Baseline   │  │   Prophet    │  │   XGBoost    │  │   │
│  │  │  (MA+Trend)  │  │ (Forecaster) │  │  (Anomaly)   │  │   │
│  │  │              │  │              │  │              │  │   │
│  │  │  MAPE: 2.6%  │  │  Cov: 46.9%  │  │  Rate: 0.69% │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Artifacts Storage                          │   │
│  │  • Model weights (joblib/pickle)                        │   │
│  │  • Training metrics (JSON)                              │   │
│  │  • Data summaries                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Model Details:**

| Model | Type | Purpose | Key Metrics |
|-------|------|---------|-------------|
| **Baseline** | Moving Average + Linear Trend | Simple forecasting benchmark | MAE, MAPE, Skill Score |
| **Prophet** | Facebook Prophet | Seasonality-aware forecasting | MAE, MAPE, Coverage |
| **XGBoost** | Gradient Boosting | Anomaly detection | Threshold, Anomaly Rate |

**Feature Engineering (108 features from 7 inputs):**

```python
# Temporal features (8)
hour, day_of_week, is_weekend
hour_sin, hour_cos, day_sin, day_cos
minutes_since_midnight

# Per-metric features (14 per metric × 7 metrics = 98)
lag_1, lag_3, lag_6, lag_12
rolling_mean_3, rolling_mean_6, rolling_mean_12
rolling_std_3, rolling_std_6, rolling_std_12
rolling_min_6, rolling_max_6
pct_change_1, pct_change_3

# Cross-metric (2)
cpu_memory_ratio
```

---

### 2.3 Inference Service

**Purpose:** Serve predictions, anomaly scores, and recommendations via REST API.

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFERENCE SERVICE (FastAPI)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Endpoints                         │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │   │
│  │  │ /predict  │ │ /detect   │ │/recommend │ │/metrics │ │   │
│  │  │           │ │           │ │           │ │(Prom)   │ │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────┼───────────────────────────────┐   │
│  │                Model Manager                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │   Baseline   │  │   Prophet    │  │   XGBoost    │  │   │
│  │  │    Model     │  │    Model     │  │    Model     │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Recommendation Engine                       │   │
│  │  • Scale up/down decisions                              │   │
│  │  • Resource limit suggestions                           │   │
│  │  • Proactive alerts                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**API Specification:**

| Endpoint | Method | Request | Response |
|----------|--------|---------|----------|
| `/health` | GET | - | `{status, models_loaded}` |
| `/models` | GET | - | List of loaded models |
| `/predict` | POST | `{metrics, periods}` | Forecasts + confidence |
| `/detect` | POST | `{metrics}` | Anomaly score + flag |
| `/recommend` | POST | `{metrics, forecasts}` | Scaling advice |
| `/metrics` | GET | - | Prometheus format |

**Prometheus Metrics Exposed:**

```prometheus
# Predictions as gauges
helios_predicted_cpu{namespace="saleor", deployment="api"} 0.72
helios_predicted_memory{namespace="saleor", deployment="api"} 0.58

# Anomaly scores
helios_anomaly_score{namespace="saleor", deployment="api"} 0.23
helios_anomaly_detected{namespace="saleor", deployment="api"} 0

# Recommendations  
helios_recommended_replicas{namespace="saleor", deployment="api"} 3
helios_recommendation_confidence{namespace="saleor", deployment="api"} 0.87
```

---

### 2.4 Recommendation Engine

**Purpose:** Convert forecasts into actionable scaling recommendations.

```
┌─────────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION ENGINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Input Signals                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Forecasts  │  │  Anomaly    │  │  Current    │     │   │
│  │  │  (Prophet/  │  │  Scores     │  │  State      │     │   │
│  │  │  Baseline)  │  │  (XGBoost)  │  │  (K8s API)  │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Decision Rules                          │   │
│  │                                                          │   │
│  │  IF predicted_cpu_30min > 80% AND confidence > 0.8:     │   │
│  │      → SCALE_UP                                         │   │
│  │                                                          │   │
│  │  IF cpu_utilization < 20% for 1h:                       │   │
│  │      → SCALE_DOWN                                       │   │
│  │                                                          │   │
│  │  IF anomaly_detected AND severity > threshold:          │   │
│  │      → ALERT (warning/critical)                         │   │
│  │                                                          │   │
│  │  IF memory_utilization > 85%:                           │   │
│  │      → INCREASE_MEMORY_LIMIT                            │   │
│  │                                                          │   │
│  │  IF predicted_traffic_spike > 2x baseline:              │   │
│  │      → PREEMPTIVE_SCALE (before spike)                  │   │
│  │                                                          │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Recommendation Output                      │   │
│  │  {                                                       │   │
│  │    "action": "scale_up",                                │   │
│  │    "target_replicas": 5,                                │   │
│  │    "current_replicas": 3,                               │   │
│  │    "reason": "Predicted CPU 82% in 30 min",            │   │
│  │    "confidence": 0.87,                                  │   │
│  │    "urgency": "medium"                                  │   │
│  │  }                                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Recommendation Types:**

| Type | Trigger | Action |
|------|---------|--------|
| `SCALE_UP` | Predicted high CPU/memory | Increase replicas |
| `SCALE_DOWN` | Low utilization for 1h+ | Decrease replicas |
| `INCREASE_MEMORY` | Memory > 85% | Adjust resource limits |
| `DECREASE_CPU` | CPU consistently < 20% | Reduce CPU requests |
| `ALERT_WARNING` | Anomaly detected | Notify operators |
| `ALERT_CRITICAL` | Severe anomaly | Page on-call |
| `PREEMPTIVE_SCALE` | Predicted spike | Scale before event |

---

### 2.5 Autoscaling Integration (KEDA)

**Purpose:** Automatically scale workloads based on Helios predictions.

```
┌─────────────────────────────────────────────────────────────────┐
│                     KEDA INTEGRATION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Helios Inference Service                    │   │
│  │                                                          │   │
│  │  GET /metrics → helios_predicted_cpu = 0.72             │   │
│  │                                                          │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │ Prometheus scrape                  │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Prometheus                            │   │
│  │                                                          │   │
│  │  helios_predicted_cpu{deployment="saleor-api"} 0.72     │   │
│  │                                                          │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │ PromQL query                       │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  KEDA ScaledObject                       │   │
│  │                                                          │   │
│  │  triggers:                                              │   │
│  │    - type: prometheus                                   │   │
│  │      metadata:                                          │   │
│  │        query: helios_predicted_cpu{deployment="..."}    │   │
│  │        threshold: "70"                                  │   │
│  │                                                          │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │ Scale decision                     │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Kubernetes HPA / Deployment                 │   │
│  │                                                          │   │
│  │  replicas: 3 → 5                                        │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Why KEDA?**

| Feature | Benefit |
|---------|---------|
| **Multi-cloud** | Works on GKE, EKS, AKS, any K8s |
| **Prometheus native** | Standard metrics integration |
| **Scale to zero** | Cost savings for idle workloads |
| **CNCF graduated** | Production-ready, vendor-neutral |
| **50+ scalers** | Future extensibility |

---

## 3. Data Flow

### 3.1 Training Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    Cloud     │───▶│    Data      │───▶│   Feature    │───▶│    Model     │
│  Monitoring  │    │   Fetcher    │    │  Engineering │    │   Training   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                                                                    ▼
                                                            ┌──────────────┐
                                                            │  Artifacts   │
                                                            │   Storage    │
                                                            └──────────────┘
```

### 3.2 Inference Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Client     │───▶│  Inference   │───▶│    Model     │───▶│   Response   │
│   Request    │    │   Service    │    │   Execution  │    │  (JSON/Prom) │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### 3.3 Autoscaling Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Inference   │───▶│  Prometheus  │───▶│    KEDA      │───▶│     HPA      │
│  /metrics    │    │   (scrape)   │    │  (evaluate)  │    │   (scale)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                                                                    ▼
                                                            ┌──────────────┐
                                                            │  Deployment  │
                                                            │  (replicas)  │
                                                            └──────────────┘
```

---

## 4. Technology Stack

### 4.1 ML Pipeline

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.11+ | ML ecosystem |
| **Data** | Pandas, NumPy | Data manipulation |
| **Forecasting** | Prophet | Time-series prediction |
| **Anomaly** | XGBoost, Scikit-learn | Anomaly detection |
| **API** | FastAPI | High-performance REST |
| **Metrics** | prometheus-client | Prometheus exposition |

### 4.2 Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **IaC** | Terraform | Multi-cloud provisioning |
| **Orchestration** | Kubernetes | Container orchestration |
| **Autoscaling** | KEDA | Event-driven autoscaling |
| **Monitoring** | Prometheus | Metrics collection |
| **Visualization** | Grafana | Dashboards |
| **Alerting** | Alertmanager | Alert routing |

### 4.3 Cloud Support Matrix

| Feature | GCP | AWS | Azure | On-Prem |
|---------|-----|-----|-------|---------|
| **Metrics Adapter** | ✅ Cloud Monitoring | 🔲 CloudWatch | 🔲 Azure Monitor | ✅ Prometheus |
| **Kubernetes** | ✅ GKE | ✅ EKS | ✅ AKS | ✅ Any |
| **Database** | ✅ Cloud SQL | ✅ RDS | ✅ Azure SQL | ✅ PostgreSQL |
| **Cache** | ✅ Memorystore | ✅ ElastiCache | ✅ Azure Cache | ✅ Redis |
| **Storage** | ✅ GCS | ✅ S3 | ✅ Blob | ✅ MinIO |

---

## 5. Kubernetes Architecture

### 5.1 Namespace Layout

```
Namespaces:
├── helios              # Helios inference service
├── saleor              # Demo application (Saleor e-commerce)
├── loadtest            # Locust load testing
├── monitoring          # Prometheus, Grafana, Alertmanager
├── keda                # KEDA operator
└── gke-gmp-system      # GKE Managed Prometheus (GCP only)
```

### 5.2 Helios Deployment

```yaml
# infra/kubernetes/helios-inference/
├── namespace.yaml
├── deployment.yaml      # Inference service (FastAPI)
├── service.yaml         # ClusterIP service
├── configmap.yaml       # Configuration
├── serviceaccount.yaml  # For Workload Identity
├── pod-monitoring.yaml  # Prometheus scrape config
└── kustomization.yaml
```

### 5.3 Resource Estimates

| Service | CPU Request | Memory Request | Replicas |
|---------|-------------|----------------|----------|
| **Inference Service** | 250m | 512Mi | 2 |
| **Saleor API** | 250m | 512Mi | 1-10 (scaled) |
| **Saleor Dashboard** | 50m | 64Mi | 1 |
| **Locust Master** | 100m | 256Mi | 1 |
| **Locust Worker** | 200m | 256Mi | 2 |

---

## 6. Security

### 6.1 Authentication & Access

| Layer | Mechanism |
|-------|-----------|
| **API** | API keys / JWT tokens |
| **K8s** | RBAC, ServiceAccounts |
| **Cloud** | Workload Identity (GCP), IAM Roles (AWS) |
| **Network** | NetworkPolicies, ClusterIP |

### 6.2 Workload Identity (GCP Example)

```yaml
# ServiceAccount with GCP Workload Identity
apiVersion: v1
kind: ServiceAccount
metadata:
  name: helios-inference
  namespace: helios
  annotations:
    iam.gke.io/gcp-service-account: helios-inference@PROJECT.iam.gserviceaccount.com
```

---

## 7. Observability

### 7.1 Helios Self-Monitoring

```yaml
Metrics (Prometheus):
  # Inference latency
  - helios_inference_duration_seconds
  - helios_inference_requests_total
  
  # Model performance
  - helios_prediction_confidence
  - helios_anomaly_detections_total
  
  # Recommendation tracking
  - helios_recommendations_total
  - helios_scaling_actions_total

Logging (Structured JSON):
  - Request/response logs
  - Model inference traces
  - Recommendation audit trail

Dashboards (Grafana):
  - Helios Overview (predictions vs actuals)
  - Anomaly Timeline
  - Scaling History
  - Model Performance
```

### 7.2 Alert Rules

```yaml
# Alertmanager rules
groups:
  - name: helios
    rules:
      - alert: HeliosHighAnomalyRate
        expr: rate(helios_anomaly_detections_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High anomaly detection rate"
      
      - alert: HeliosInferenceLatency
        expr: helios_inference_duration_seconds > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Inference latency too high"
```

---

## 8. Development Phases

### ✅ Phase 1: Foundation (Complete)
- [x] Project structure
- [x] Terraform modules (GKE, Cloud SQL, Redis, GCS)
- [x] GKE Autopilot cluster
- [x] Networking (VPC, subnets)

### ✅ Phase 2: Demo Application (Complete)
- [x] Saleor e-commerce deployment
- [x] Cloud SQL PostgreSQL integration
- [x] Redis caching
- [x] GCS media storage

### ✅ Phase 3: Observability (Complete)
- [x] GKE Managed Prometheus
- [x] PodMonitoring resources
- [x] Locust load testing (4 personas)
- [x] Metrics collection validated

### ✅ Phase 4: ML Pipeline (Complete)
- [x] Cloud Monitoring data fetcher
- [x] Feature engineering (108 features)
- [x] Baseline model (MA + Trend) - 2.6% MAPE
- [x] Prophet forecasting - 46.9% coverage
- [x] XGBoost anomaly detection - 0.69% anomaly rate
- [x] Training pipeline orchestration

### 🔲 Phase 5: Inference Service (In Progress)
- [ ] FastAPI inference service
- [ ] /predict, /detect, /recommend endpoints
- [ ] Prometheus /metrics endpoint
- [ ] Kubernetes deployment
- [ ] KEDA ScaledObject
- [ ] Grafana dashboards
- [ ] Alertmanager integration

### 🔲 Phase 6: Multi-Cloud (Planned)
- [ ] AWS CloudWatch adapter
- [ ] Azure Monitor adapter
- [ ] Prometheus adapter (generic)
- [ ] Cross-cloud testing

### 🔲 Phase 7: Advanced Models (Planned)
- [ ] LSTM sequence model
- [ ] Transformer architecture
- [ ] Ensemble methods
- [ ] Online learning

---

## 9. Appendix

### A. Configuration Reference

```yaml
# Helios configuration
gcp:
  project_id: "your-project-id"
  region: "us-central1"

metrics:
  lookback_hours: 24
  aggregation_interval_minutes: 5

models:
  baseline:
    moving_average_window: 12
    trend_window: 24
  prophet:
    seasonality_mode: "multiplicative"
    changepoint_prior_scale: 0.05
  xgboost:
    n_estimators: 100
    max_depth: 6
    anomaly_threshold_sigma: 2.5

scaling:
  cpu_scale_up_threshold: 0.80
  cpu_scale_down_threshold: 0.20
  memory_warning_threshold: 0.85
  min_replicas: 1
  max_replicas: 10
  cooldown_seconds: 300
```

### B. Glossary

| Term | Definition |
|------|------------|
| **MAPE** | Mean Absolute Percentage Error |
| **Coverage** | % of actuals within prediction interval |
| **Anomaly Score** | Distance from normal (in std deviations) |
| **KEDA** | Kubernetes Event-Driven Autoscaling |
| **HPA** | Horizontal Pod Autoscaler |
| **Workload Identity** | GCP service account for K8s pods |

### C. References

- [KEDA Documentation](https://keda.sh/docs/)
- [Prophet Documentation](https://facebook.github.io/prophet/)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Prometheus Client](https://github.com/prometheus/client_python)
- [GKE Managed Prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus)
