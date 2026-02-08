# Helios

**Predictive Infrastructure Intelligence Platform**

[![CI](https://github.com/pyjeebz/helios/actions/workflows/ci.yml/badge.svg)](https://github.com/pyjeebz/helios/actions/workflows/ci.yml)
[![Release](https://github.com/pyjeebz/helios/actions/workflows/release.yml/badge.svg)](https://github.com/pyjeebz/helios/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Helios uses machine learning to forecast infrastructure demand, detect anomalies, and provide proactive scaling recommendations. It supports multi-cloud metrics collection, real-time dashboards, and extensible agent architecture.

---

## 🚀 Quick Start

### Option 1: Docker (Easiest)

```bash
docker run -d -p 8080:8080 ghcr.io/pyjeebz/helios/inference:latest
# Open http://localhost:8080
```

### Option 2: Local Development

**Prerequisites:** Python 3.10+, Node.js 18+

```bash
# Clone and setup
git clone https://github.com/pyjeebz/helios.git
cd helios

# Python environment
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r ml/inference/requirements.txt

# Start backend (Terminal 1)
python -m uvicorn ml.inference.app:app --host 0.0.0.0 --port 8080

# Start frontend (Terminal 2)
cd ml/inference/web
npm install
npm run dev
# Open http://localhost:3000
```

### Option 3: Kubernetes (Helm)

```bash
helm repo add helios https://pyjeebz.github.io/helios
helm install helios helios/helios
```

### First Steps After Setup

1. **Deployments** → Create a deployment (e.g., `my-app-prod`)
2. **Install Agent** → Copy commands, run on your server
3. **Dashboard** → View predictions, anomalies, recommendations

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Traffic Forecasting** | Predict CPU, memory, and request rates |
| **Anomaly Detection** | Real-time detection using ML/statistics |
| **Scaling Recommendations** | Proactive advice for resource scaling |
| **Multi-Cloud Support** | GCP, AWS, Azure, Prometheus, custom sources |
| **Web Dashboard** | Real-time charts, agent map, predictions, anomalies |
| **CLI Tools** | `helios` CLI for predictions, anomaly detection, recommendations |
| **Pluggable Storage** | In-memory (dev), PostgreSQL, TimescaleDB, InfluxDB (planned) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Helios Agent ──► ML Pipeline ──► Inference Service (API)   │
│     │                │                │                     │
│     ▼                ▼                ▼                     │
│  Metrics         Training         Predictions/Anomalies     │
│     │                │                │                     │
│     └─────────────► Storage Backend (pluggable)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
helios/
├── agent/              # Metrics collection agent (pluggable sources)
├── cli/                # CLI tools for predictions/anomalies/recommendations
├── ml/                 # ML models, training, inference service (FastAPI)
│   └── inference/web/  # Vue.js web dashboard
├── infra/              # Kubernetes, Terraform, Docker, Helm
├── charts/helios/      # Helm chart
├── docs/               # Documentation
```

---

## 🤖 Helios Agent

Collects metrics from:
- System (CPU, memory, disk, network)
- Prometheus
- GCP Cloud Monitoring
- AWS CloudWatch (planned)
- Azure Monitor (planned)
- Datadog (planned)

### Installation

```bash
pip install helios-platform-agent
pip install helios-platform-agent[gcp]      # GCP
pip install helios-platform-agent[aws]      # AWS
pip install helios-platform-agent[azure]    # Azure
pip install helios-platform-agent[all]      # All backends
```

### Configuration

```yaml
agent:
  collection_interval: 60
  log_level: INFO

sources:
  - type: system
    enabled: true
    config:
      collect_cpu: true
      collect_memory: true
  - type: prometheus
    enabled: true
    config:
      url: http://prometheus:9090
      queries:
        - name: cpu_usage
          query: rate(container_cpu_usage_seconds_total[5m])
helios:
  endpoint: http://helios-inference:8080
```

---

## 🖥️ Web Dashboard

The Vue.js dashboard provides AI-powered insights for your infrastructure:

| Feature | Description |
|---------|-------------|
| **Multi-Deployment Management** | Create and switch between deployments (prod, staging, dev) |
| **Agent Installation** | Copy-paste commands with live connection status |
| **AI Predictions** | Forecast CPU, memory, and resource usage |
| **Anomaly Detection** | Real-time detection of unusual patterns |
| **Recommendations** | Proactive scaling advice with confidence scores |

### Running the Dashboard

```bash
cd ml/inference/web
npm install
npm run dev        # Development: http://localhost:3000
npm run build      # Production build to ../static
```

### User Flow

1. **Create a deployment** (`/deployments`) - e.g., `ecommerce-prod`
2. **Install the agent** (`/install`) - copy commands, run on your server
3. **View AI insights** - predictions, anomalies, and recommendations appear automatically

---

## 🧠 ML Training

- Baseline (moving average/trend)
- Prophet (seasonality)
- XGBoost (anomaly detection)
- Models train on collected metrics (manual/auto)

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/v1/ingest` | POST | Ingest metrics from agent |
| `/api/v1/predict` | POST | Forecast future metrics |
| `/api/v1/detect` | POST | Anomaly detection |
| `/api/v1/recommend` | POST | Scaling recommendations |
| `/api/metrics` | GET | List available metric names |
| `/api/metrics/{name}` | GET | Get time-series data |

---

## ☸️ Kubernetes Deployment

- Helm chart for easy install
- K8s manifests for inference service, monitoring, autoscaling

---

## 📈 Roadmap

### ✅ Completed
- Agent with pluggable backends (GCP, Prometheus, System)
- ML pipeline (Baseline, Prophet, XGBoost)
- Inference service (FastAPI)
- CLI tools (predict, detect, recommend)
- Kubernetes/Helm deployment
- Web dashboard (Vue.js) with multi-deployment support
- Agent installation flow
- AI-focused insights (predictions, anomalies, recommendations)

### 🚧 In Progress
- Agent management controls (pause/resume, collection interval)
- Automated model retraining
- Pluggable storage backend

### 🔮 Future
- Multi-cluster support
- Deep learning models (LSTM, Transformer)
- Alerting integrations (Slack, PagerDuty)
- User authentication/RBAC
- Landing page

---

## 🧪 Testing

```bash
cd ml && pytest tests/
cd agent && pytest
cd cli && pytest
```

---

## 📝 License

Apache 2.0 - See [LICENSE](LICENSE)

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request
