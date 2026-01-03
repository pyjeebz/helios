# Helios SaaS Platform Architecture

## Executive Summary

Helios SaaS is a multi-tenant predictive infrastructure intelligence platform that enables organizations to forecast resource demands, detect anomalies, and receive proactive scaling recommendations before performance issues occur.

**Business Value:**
- Reduce infrastructure costs by 20-40% through predictive scaling
- Eliminate reactive firefighting with proactive alerts
- Self-service onboarding in under 10 minutes
- Pay-per-use pricing aligned with customer value

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Multi-Tenancy Strategy](#2-multi-tenancy-strategy)
3. [Database Design](#3-database-design)
4. [API Gateway & Authentication](#4-api-gateway--authentication)
5. [Core Services](#5-core-services)
6. [Data Collection Methods](#6-data-collection-methods)
7. [ML Pipeline](#7-ml-pipeline)
8. [Billing & Metering](#8-billing--metering)
9. [Security & Compliance](#9-security--compliance)
10. [Customer Portal](#10-customer-portal)
11. [Infrastructure](#11-infrastructure)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            HELIOS SAAS PLATFORM                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│    ┌─────────────────────────────────────────────────────────────────────┐     │
│    │                     CUSTOMER TOUCHPOINTS                             │     │
│    │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐    │     │
│    │   │  Portal  │   │   API    │   │  Agent   │   │   Webhooks   │    │     │
│    │   │   (UI)   │   │ (REST)   │   │  (SDK)   │   │ (Callbacks)  │    │     │
│    │   └────┬─────┘   └────┬─────┘   └────┬─────┘   └──────┬───────┘    │     │
│    └────────┼──────────────┼──────────────┼────────────────┼────────────┘     │
│             │              │              │                │                   │
│             ▼              ▼              ▼                ▼                   │
│    ┌─────────────────────────────────────────────────────────────────────┐    │
│    │                      API GATEWAY (Kong)                              │    │
│    │         Authentication │ Rate Limiting │ Routing │ Logging           │    │
│    └─────────────────────────────────┬───────────────────────────────────┘    │
│                                      │                                        │
│    ┌─────────────────────────────────┼───────────────────────────────────┐    │
│    │                         CORE SERVICES                                │    │
│    │                                 │                                    │    │
│    │   ┌──────────────┐   ┌─────────┴────────┐   ┌──────────────┐        │    │
│    │   │   Tenant     │   │    Ingestion     │   │   Inference  │        │    │
│    │   │   Service    │   │    Service       │   │   Service    │        │    │
│    │   │ • Onboarding │   │ • Metrics recv   │   │ • /predict   │        │    │
│    │   │ • API Keys   │   │ • Validation     │   │ • /detect    │        │    │
│    │   │ • Settings   │   │ • Routing        │   │ • /recommend │        │    │
│    │   └──────────────┘   └──────────────────┘   └──────────────┘        │    │
│    │                                                                      │    │
│    │   ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐        │    │
│    │   │   ML         │   │    Alerting      │   │    Billing   │        │    │
│    │   │   Pipeline   │   │    Service       │   │    Service   │        │    │
│    │   │ • Training   │   │ • Webhooks       │   │ • Metering   │        │    │
│    │   │ • Models     │   │ • Slack/PD       │   │ • Stripe     │        │    │
│    │   │ • Serving    │   │ • Email          │   │ • Invoicing  │        │    │
│    │   └──────────────┘   └──────────────────┘   └──────────────┘        │    │
│    └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                        │
│    ┌─────────────────────────────────┼───────────────────────────────────┐    │
│    │                         DATA LAYER                                   │    │
│    │   ┌──────────────┐   ┌─────────┴────────┐   ┌──────────────┐        │    │
│    │   │  PostgreSQL  │   │   TimescaleDB    │   │     GCS      │        │    │
│    │   │ • Tenants    │   │ • Metrics        │   │ • ML Models  │        │    │
│    │   │ • Users      │   │ • Predictions    │   │ • Artifacts  │        │    │
│    │   │ • Settings   │   │ • Anomalies      │   │ • Exports    │        │    │
│    │   └──────────────┘   └──────────────────┘   └──────────────┘        │    │
│    │                                                                      │    │
│    │   ┌──────────────┐   ┌──────────────────┐                           │    │
│    │   │    Redis     │   │    Pub/Sub       │                           │    │
│    │   │ • Cache      │   │ • Events         │                           │    │
│    │   │ • Sessions   │   │ • Async Jobs     │                           │    │
│    │   │ • Rate Limit │   │ • Notifications  │                           │    │
│    │   └──────────────┘   └──────────────────┘                           │    │
│    └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Customer Infrastructure          Helios SaaS Platform
─────────────────────           ────────────────────────────────────────

┌─────────────────┐             ┌─────────────────────────────────────┐
│  App Servers    │             │                                     │
│  Databases      │   metrics   │  ┌─────────┐      ┌─────────────┐  │
│  Kubernetes     │────────────▶│  │Ingestion│─────▶│ TimescaleDB │  │
│  Cloud Services │   (push)    │  └─────────┘      └──────┬──────┘  │
└─────────────────┘             │                          │         │
        │                       │                          ▼         │
        │                       │  ┌──────────────────────────────┐  │
        │    ┌──────────────────│  │      ML Pipeline             │  │
        │    │                  │  │  • Feature Engineering       │  │
        │    │   predictions    │  │  • Model Training            │  │
        │    │   & alerts       │  │  • Anomaly Detection         │  │
        ▼    ▼                  │  └──────────────┬───────────────┘  │
┌─────────────────┐             │                 │                  │
│  Slack/PD/      │◀────────────│  ┌──────────────▼───────────────┐  │
│  Webhook        │   alerts    │  │      Inference Service       │  │
└─────────────────┘             │  │  • Real-time predictions     │  │
        │                       │  │  • Scaling recommendations   │  │
        ▼                       │  └──────────────────────────────┘  │
┌─────────────────┐             │                                    │
│  HPA/KEDA       │◀────────────│  (optional: auto-scaling webhook) │
│  Auto-scaling   │             │                                    │
└─────────────────┘             └────────────────────────────────────┘
```

---

## 2. Multi-Tenancy Strategy

### Isolation Levels

| Level | Description | Use Case | Pros | Cons |
|-------|-------------|----------|------|------|
| **Shared DB + RLS** | Single database, row-level security | Starter tier | Cost efficient | Limited isolation |
| **Schema per Tenant** | Separate schema per customer | Professional tier | Good isolation | Migration complexity |
| **Database per Tenant** | Dedicated database instance | Enterprise tier | Full isolation | Higher cost |

### Recommended Approach: Hybrid

```
┌─────────────────────────────────────────────────────────────────┐
│                     TENANT ISOLATION STRATEGY                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Starter Tier ($99/mo)          Professional Tier ($299/mo)     │
│  ┌───────────────────┐          ┌───────────────────┐          │
│  │  Shared Database  │          │  Schema per Tenant │          │
│  │  + Row-Level      │          │  + Dedicated       │          │
│  │    Security       │          │    Connection Pool │          │
│  │                   │          │                    │          │
│  │  tenant_id column │          │  tenant_abc.metrics│          │
│  │  on all tables    │          │  tenant_xyz.metrics│          │
│  └───────────────────┘          └───────────────────┘          │
│                                                                 │
│  Enterprise Tier (Custom)                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Dedicated Database Instance                 │   │
│  │              + VPC Peering Option                        │   │
│  │              + Custom Retention                          │   │
│  │              + Dedicated ML Resources                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Context Propagation

```python
# middleware/tenant_context.py
from contextvars import ContextVar
from fastapi import Request, HTTPException

current_tenant: ContextVar[str] = ContextVar('current_tenant', default=None)

class TenantMiddleware:
    async def __call__(self, request: Request, call_next):
        api_key = request.headers.get("X-API-Key")
        
        if api_key:
            tenant = await self.validate_api_key(api_key)
            if not tenant:
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            current_tenant.set(tenant.id)
            request.state.db.execute(f"SET app.current_tenant = '{tenant.id}'")
        
        response = await call_next(request)
        return response
```

---

## 3. Database Design

### Core Schema

```sql
-- =====================================================
-- TENANT MANAGEMENT
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Organizations (top-level tenant)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'starter',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users within organizations
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    password_hash VARCHAR(255),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, email)
);

-- API Keys for programmatic access
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    key_prefix VARCHAR(8) NOT NULL,
    scopes JSONB DEFAULT '["read", "write"]',
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- METRICS & TIME-SERIES (TimescaleDB)
-- =====================================================

CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    org_id UUID NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    labels JSONB DEFAULT '{}',
    source VARCHAR(100)
);

SELECT create_hypertable('metrics', 'time');

-- Continuous aggregate for faster queries
CREATE MATERIALIZED VIEW metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    org_id,
    metric_name,
    AVG(value) AS avg_value,
    MAX(value) AS max_value,
    MIN(value) AS min_value,
    COUNT(*) AS sample_count
FROM metrics
GROUP BY bucket, org_id, metric_name;

-- =====================================================
-- ML MODELS & PREDICTIONS
-- =====================================================

CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    target_metric VARCHAR(255) NOT NULL,
    artifact_path VARCHAR(500) NOT NULL,
    metrics JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE predictions (
    time TIMESTAMPTZ NOT NULL,
    org_id UUID NOT NULL,
    model_id UUID REFERENCES models(id),
    metric_name VARCHAR(255) NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    confidence_lower DOUBLE PRECISION,
    confidence_upper DOUBLE PRECISION,
    horizon_minutes INTEGER NOT NULL,
    actual_value DOUBLE PRECISION
);

SELECT create_hypertable('predictions', 'time');

CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    expected_value DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(50) DEFAULT 'open',
    acknowledged_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ
);

-- =====================================================
-- ALERTING & NOTIFICATIONS
-- =====================================================

CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    condition VARCHAR(50) NOT NULL,
    threshold DOUBLE PRECISION,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    channel_type VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- BILLING & USAGE
-- =====================================================

CREATE TABLE usage_records (
    time TIMESTAMPTZ NOT NULL,
    org_id UUID NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    quantity BIGINT NOT NULL
);

SELECT create_hypertable('usage_records', 'time');

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255),
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- ROW-LEVEL SECURITY
-- =====================================================

ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE models ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_metrics ON metrics
    USING (org_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation_predictions ON predictions
    USING (org_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation_anomalies ON anomalies
    USING (org_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation_models ON models
    USING (org_id = current_setting('app.current_tenant')::UUID);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX idx_metrics_org_time ON metrics (org_id, time DESC);
CREATE INDEX idx_metrics_org_name ON metrics (org_id, metric_name);
CREATE INDEX idx_predictions_org_time ON predictions (org_id, time DESC);
CREATE INDEX idx_anomalies_org_status ON anomalies (org_id, status);
CREATE INDEX idx_api_keys_hash ON api_keys (key_hash);
```

---

## 4. API Gateway & Authentication

### Kong Configuration

```yaml
# kong/kong.yaml
_format_version: "3.0"

services:
  - name: tenant-service
    url: http://helios-tenant.helios.svc:8080
    routes:
      - name: tenant-routes
        paths:
          - /api/v1/organizations
          - /api/v1/users
          - /api/v1/api-keys
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          policy: redis
      - name: key-auth
        config:
          key_names: ["X-API-Key"]
  
  - name: inference-service
    url: http://helios-inference.helios.svc:8080
    routes:
      - name: inference-routes
        paths:
          - /api/v1/predict
          - /api/v1/detect
          - /api/v1/recommend
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
      - name: key-auth

  - name: ingestion-service
    url: http://helios-ingest.helios.svc:8080
    routes:
      - name: ingest-routes
        paths:
          - /api/v1/ingest
          - /api/v1/prometheus/write
    plugins:
      - name: rate-limiting
        config:
          second: 1000
      - name: key-auth

consumers:
  - username: starter-tier
    plugins:
      - name: rate-limiting
        config:
          minute: 100
          hour: 5000
  
  - username: professional-tier
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
          hour: 50000
  
  - username: enterprise-tier
    plugins:
      - name: rate-limiting
        config:
          minute: 10000
          hour: 500000
```

### Authentication Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Customer   │     │  API Gateway │     │   Backend    │
│   Request    │     │    (Kong)    │     │   Service    │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │  POST /api/v1/predict                   │
       │  X-API-Key: hlx_abc123...               │
       │───────────────────▶│                    │
       │                    │ Validate API Key   │
       │                    │ Check Rate Limit   │
       │                    │ Add Headers:       │
       │                    │ X-Tenant-ID        │
       │                    │───────────────────▶│
       │                    │                    │ Set DB tenant
       │                    │◀───────────────────│
       │◀───────────────────│                    │
       │   Response         │                    │
```

---

## 5. Core Services

### Service Overview

| Service | Responsibility | Port | Replicas |
|---------|---------------|------|----------|
| **Tenant Service** | Org management, API keys, settings | 8080 | 2 |
| **Ingestion Service** | Receive & validate metrics | 8081 | 3-10 (HPA) |
| **Inference Service** | Predictions, anomalies, recommendations | 8082 | 3-10 (HPA) |
| **ML Pipeline** | Model training (async jobs) | N/A | 1-5 workers |
| **Alerting Service** | Notifications dispatch | 8083 | 2 |
| **Billing Service** | Usage tracking, Stripe integration | 8084 | 2 |

### API Endpoints

**Tenant Service:**
- `POST /api/v1/organizations` - Create organization
- `GET /api/v1/organizations/{id}` - Get organization
- `POST /api/v1/api-keys` - Create API key
- `DELETE /api/v1/api-keys/{id}` - Revoke API key

**Inference Service:**
- `POST /api/v1/predict` - Get predictions
- `POST /api/v1/detect` - Anomaly detection
- `POST /api/v1/recommend` - Scaling recommendations
- `GET /api/v1/models` - List tenant's models

**Ingestion Service:**
- `POST /api/v1/ingest` - Ingest metrics batch
- `POST /api/v1/prometheus/write` - Prometheus remote_write

**Billing Service:**
- `GET /api/v1/billing/usage` - Current usage
- `GET /api/v1/billing/invoices` - Invoice history
- `POST /webhooks/stripe` - Stripe webhooks

---

## 6. Data Collection Methods

### Option 1: Helios Agent (Recommended)

```bash
# Install and run
pip install helios-agent
helios-agent --api-key hlx_xxx --endpoint https://api.helios.io
```

### Option 2: Prometheus Remote Write

```yaml
# Customer's prometheus.yml
remote_write:
  - url: https://api.helios.io/api/v1/prometheus/write
    headers:
      X-API-Key: hlx_customer_api_key
    write_relabel_configs:
      - source_labels: [__name__]
        regex: '(container_cpu.*|container_memory.*|http_requests_total)'
        action: keep
```

### Option 3: Direct API Push

```python
import requests

requests.post(
    "https://api.helios.io/api/v1/ingest",
    headers={"X-API-Key": "hlx_xxx"},
    json={"metrics": [
        {"name": "cpu", "value": 0.75, "timestamp": "2026-01-03T12:00:00Z"}
    ]}
)
```

---

## 7. ML Pipeline

### Per-Tenant Model Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ML PIPELINE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │  Scheduler  │───▶│  Training   │───▶│    Model Store      │ │
│  │  (Celery)   │    │  Worker     │    │    (GCS)            │ │
│  │ • Nightly   │    │ • XGBoost   │    │ gs://helios-models/ │ │
│  │ • On-demand │    │ • Prophet   │    │ ├── tenant_abc/     │ │
│  └─────────────┘    └─────────────┘    │ │   ├── cpu.joblib  │ │
│                                        │ │   └── anomaly.pkl │ │
│                                        │ └── tenant_xyz/     │ │
│                                        └─────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Model Registry (DB)                    │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │ tenant_id │ model_name  │ version │ metrics       │  │   │
│  │  ├───────────┼─────────────┼─────────┼───────────────┤  │   │
│  │  │ abc123    │ cpu_forecast│ v3      │ MAE: 2.3%     │  │   │
│  │  │ abc123    │ anomaly_det │ v2      │ F1: 0.94      │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Training Configuration

```json
{
    "ml_config": {
        "training_schedule": "0 2 * * *",
        "training_days": 14,
        "forecast_horizons": [15, 30, 60],
        "forecast_metrics": ["cpu", "memory", "requests"],
        "anomaly_sensitivity": 2.5
    }
}
```

---

## 8. Billing & Metering

### Pricing Tiers

| Feature | Starter ($99/mo) | Professional ($299/mo) | Enterprise (Custom) |
|---------|------------------|------------------------|---------------------|
| Metrics/month | 10M | 100M | Unlimited |
| Predictions/month | 100K | 1M | Unlimited |
| Data retention | 7 days | 30 days | 90+ days |
| Alert channels | 2 | 10 | Unlimited |
| Custom models | ❌ | ✅ | ✅ |
| API rate limit | 100/min | 1000/min | Custom |
| Support | Email | Chat + SLA | Dedicated |
| SSO/SAML | ❌ | ✅ | ✅ |

### Usage-Based Add-ons

- Extra metrics: $0.10 per 1M
- Extra predictions: $0.50 per 10K
- Custom model training: $50/run

### Stripe Integration

```python
# Track usage
stripe.SubscriptionItem.create_usage_record(
    subscription_item_id,
    quantity=metrics_count,
    timestamp=int(datetime.utcnow().timestamp())
)
```

---

## 9. Security & Compliance

### Security Measures

| Layer | Implementation |
|-------|----------------|
| **Transport** | TLS 1.3 everywhere |
| **Authentication** | API keys (hashed), OAuth 2.0, SAML SSO |
| **Authorization** | RBAC (owner, admin, member, viewer) |
| **Data at Rest** | AES-256 encryption |
| **Secrets** | Google Secret Manager |
| **Audit Logging** | All API calls logged |
| **Network** | VPC, private GKE nodes |

### RBAC Model

| Role | Permissions |
|------|-------------|
| **Owner** | Full access, can delete organization |
| **Admin** | Manage users, settings, API keys |
| **Member** | View data, manage dashboards |
| **Viewer** | Read-only access |

### Compliance Roadmap

| Standard | Status | Timeline |
|----------|--------|----------|
| **GDPR** | ✅ Ready | Now |
| **SOC 2 Type II** | 🔄 Planned | Q2 2026 |
| **HIPAA** | 🔄 Planned | Q3 2026 |
| **ISO 27001** | 🔄 Planned | Q4 2026 |

---

## 10. Customer Portal

### Portal Features

```
┌─────────────────────────────────────────────────────────────────┐
│                     HELIOS CUSTOMER PORTAL                       │
├─────────────────────────────────────────────────────────────────┤
│  NAVIGATION              │  DASHBOARD                           │
│  • Dashboard             │  ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  • Metrics Explorer      │  │ Metrics │ │Predict. │ │Anomalies││
│  • Predictions           │  │ 2.3M/day│ │ 15K/day │ │ 3 open  ││
│  • Anomalies             │  └─────────┘ └─────────┘ └─────────┘│
│  • Alerts                │                                      │
│  • Models                │  [Chart: Actual vs Predicted CPU]   │
│  • Settings              │  [Chart: Anomaly Timeline]          │
│    - Organization        │                                      │
│    - Team Members        │                                      │
│    - API Keys            │                                      │
│    - Integrations        │                                      │
│    - Billing             │                                      │
└──────────────────────────┴──────────────────────────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Next.js 14 |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Charts | Recharts |
| State | TanStack Query |
| Auth | NextAuth.js |

---

## 11. Infrastructure

### Multi-Region Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    GLOBAL INFRASTRUCTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                    ┌──────────────────┐                         │
│                    │  Cloud DNS       │                         │
│                    │  (GeoDNS)        │                         │
│                    └────────┬─────────┘                         │
│           ┌─────────────────┼─────────────────┐                 │
│           ▼                 ▼                 ▼                 │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │  US-CENTRAL1    │ │  EUROPE-WEST1   │ │  ASIA-EAST1     │   │
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │   │
│  │ │ GKE Cluster │ │ │ │ GKE Cluster │ │ │ │ GKE Cluster │ │   │
│  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │   │
│  │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │   │
│  │ │ Cloud SQL   │ │ │ │ Cloud SQL   │ │ │ │ Cloud SQL   │ │   │
│  │ │ (Primary)   │ │ │ │ (Replica)   │ │ │ │ (Replica)   │ │   │
│  │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Resource Allocation

| Service | CPU Request | Memory Request | Replicas |
|---------|-------------|----------------|----------|
| Inference | 500m | 1Gi | 3-10 |
| Ingestion | 250m | 512Mi | 3-20 |
| Tenant | 100m | 256Mi | 2 |
| Alerting | 100m | 256Mi | 2 |
| Billing | 100m | 256Mi | 2 |

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [ ] Multi-tenant database schema
- [ ] API Gateway with authentication
- [ ] Tenant Service (CRUD, API keys)
- [ ] Basic usage tracking

### Phase 2: Core Features (Weeks 4-6)
- [ ] Ingestion Service (metrics collection)
- [ ] Per-tenant model storage
- [ ] Adapt existing Inference Service
- [ ] Real-time anomaly detection

### Phase 3: Portal & Billing (Weeks 7-9)
- [ ] Customer portal (Next.js)
- [ ] Stripe integration
- [ ] Self-service onboarding
- [ ] Usage dashboards

### Phase 4: Production (Weeks 10-12)
- [ ] Security hardening
- [ ] Multi-region deployment
- [ ] Monitoring & alerting
- [ ] Documentation & launch

---

## Business Model Summary

### Open Core Strategy

| Component | License | Availability |
|-----------|---------|--------------|
| **Core ML Models** | Apache 2.0 | Open Source |
| **Basic Inference API** | Apache 2.0 | Open Source |
| **Multi-tenant Platform** | Proprietary | SaaS Only |
| **Enterprise Features** | Proprietary | Commercial License |
| **Customer Portal** | Proprietary | SaaS Only |

### Revenue Streams

| Stream | Target | Price |
|--------|--------|-------|
| SaaS Subscriptions | SMB, Mid-market | $99-$999/mo |
| Enterprise License | Large orgs | $50K-$200K/yr |
| Professional Services | All tiers | $200-$400/hr |
| Managed Service | Compliance orgs | $2K-$10K/mo |

---

## Appendix: Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database** | PostgreSQL + TimescaleDB | Best for time-series + ACID |
| **API Gateway** | Kong | Open source, extensible |
| **Auth** | API Keys + OAuth | Simple for API, SSO for portal |
| **ML Framework** | XGBoost + Prophet | Production-proven, fast |
| **Billing** | Stripe | Industry standard |
| **Portal** | Next.js | SSR, great DX |
| **Infrastructure** | GKE Autopilot | Managed, cost-efficient |
