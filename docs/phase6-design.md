# Phase 6: Cost Intelligence Dashboard

## Overview

Phase 6 implements the **Helios Cost Intelligence Dashboard** - a comprehensive cost analysis and optimization platform that helps teams understand and reduce their cloud infrastructure spending.

---

## Goals

1. **Visualize costs** in real-time with breakdown by service, namespace, and resource type
2. **Calculate savings** from ML-driven autoscaling recommendations
3. **Identify optimization opportunities** through resource efficiency analysis
4. **Track cost trends** over time with forecasting

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 6 ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    COST INTELLIGENCE API (FastAPI)                   │   │
│  │  Port: 8081                                                          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │   │
│  │  │ /costs    │ │ /savings  │ │ /forecast │ │/efficiency│           │   │
│  │  │           │ │           │ │           │ │           │           │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │   │
│  └──────────────────────────────────┬──────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA SOURCES                                      │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │GCP Billing  │ │ Kubernetes  │ │ Prometheus  │ │  Inference  │   │   │
│  │  │  Export     │ │  Metrics    │ │  Metrics    │ │  Service    │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    GRAFANA DASHBOARD                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ Cost Overview | Savings | Resource Efficiency | Forecasts   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Cost Intelligence API

**Location:** `ml/cost_intelligence/`

```
ml/cost_intelligence/
├── __init__.py
├── app.py              # FastAPI application
├── config.py           # Service configuration
├── models.py           # Pydantic schemas
├── cost_calculator.py  # Cost calculation logic
├── savings_analyzer.py # Savings from optimizations
├── efficiency.py       # Resource efficiency metrics
├── forecaster.py       # Cost forecasting
└── gcp_billing.py      # GCP billing data integration
```

### 2. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/costs` | GET | Current cost breakdown |
| `/costs/history` | GET | Historical cost data |
| `/savings` | GET | Savings from optimizations |
| `/savings/potential` | GET | Potential future savings |
| `/efficiency` | GET | Resource efficiency metrics |
| `/forecast` | GET | Cost forecasts |

### 3. Cost Models

**GKE Autopilot Pricing (us-central1):**
- vCPU: $0.0445/hour
- Memory: $0.0049/GB/hour
- Ephemeral Storage: $0.0001/GB/hour

**Example Calculations:**
```python
# Pod cost per hour
pod_cost = (cpu_cores * 0.0445) + (memory_gb * 0.0049)

# Monthly cost estimate
monthly_cost = pod_cost * replicas * 24 * 30
```

---

## Data Sources

### 1. Kubernetes Metrics

From Prometheus:
- `container_cpu_usage_seconds_total`
- `container_memory_usage_bytes`
- `kube_pod_info`
- `kube_deployment_spec_replicas`

### 2. GCP Billing Export

BigQuery export:
- Daily cost data
- Service breakdown
- SKU-level details

### 3. Inference Service

From Helios Inference:
- `helios_recommended_replicas`
- Historical scaling decisions
- Optimization actions taken

---

## Grafana Dashboard Panels

### 1. Cost Overview
- Total daily/weekly/monthly spend
- Cost by namespace
- Cost trend chart
- Top 5 expensive workloads

### 2. Savings Dashboard
- Total savings from autoscaling
- Savings by optimization type
- Before/After comparisons
- ROI metrics

### 3. Resource Efficiency
- CPU efficiency (usage vs requests)
- Memory efficiency
- Over-provisioned resources
- Right-sizing recommendations

### 4. Cost Forecasts
- 7/30/90 day projections
- Budget vs actual
- Anomaly detection (cost spikes)

---

## Metrics Exported

```prometheus
# Current cost metrics
helios_cost_current{namespace="saleor", resource="cpu"} 12.50
helios_cost_current{namespace="saleor", resource="memory"} 4.20
helios_cost_current{namespace="helios", resource="cpu"} 3.80

# Savings metrics
helios_savings_total{type="autoscaling"} 156.00
helios_savings_total{type="rightsizing"} 45.00

# Efficiency metrics
helios_efficiency_cpu{namespace="saleor"} 0.65
helios_efficiency_memory{namespace="saleor"} 0.72

# Forecast metrics
helios_cost_forecast{period="7d"} 450.00
helios_cost_forecast{period="30d"} 1850.00
```

---

## Implementation Plan

### Week 1: API Foundation
- [ ] Create FastAPI service structure
- [ ] Implement cost calculator
- [ ] Add GCP billing integration stub

### Week 2: Savings Analysis
- [ ] Calculate savings from autoscaling
- [ ] Track optimization history
- [ ] Build efficiency metrics

### Week 3: Dashboard & Integration
- [ ] Create Grafana dashboard
- [ ] Deploy to Kubernetes
- [ ] Integration testing

---

## Deployment

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helios-cost-intelligence
  namespace: helios
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: cost-api
          image: gcr.io/PROJECT_ID/helios-cost-intelligence:latest
          ports:
            - containerPort: 8081
          env:
            - name: GCP_PROJECT
              value: "YOUR_GCP_PROJECT_ID"
```
