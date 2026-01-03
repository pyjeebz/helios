# Helios - Complete Setup Guide

## Prerequisites

- Google Cloud SDK (`gcloud`)
- Terraform >= 1.0
- kubectl
- Python 3.11+
- Docker (optional, for local builds)

---

## Step 1: Initial Setup

```powershell
# Clone the repository (if not already done)
git clone https://github.com/your-org/helios.git
cd helios

# Set your GCP Project ID
$GCP_PROJECT_ID = "your-gcp-project-id"

# Run the setup script (creates .env and updates manifests)
.\scripts\setup.ps1 -ProjectId $GCP_PROJECT_ID
```

---

## Step 2: GCP Authentication

```powershell
# Login to GCP
gcloud auth login

# Set the project
gcloud config set project $GCP_PROJECT_ID

# Enable required APIs
gcloud services enable `
    container.googleapis.com `
    cloudbuild.googleapis.com `
    monitoring.googleapis.com `
    cloudresourcemanager.googleapis.com `
    sqladmin.googleapis.com `
    redis.googleapis.com `
    storage.googleapis.com

# Set up Application Default Credentials (for local development)
gcloud auth application-default login
```

---

## Step 3: Provision Infrastructure with Terraform

```powershell
# Navigate to Terraform directory
cd infra/terraform/gcp

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var="project_id=$GCP_PROJECT_ID"

# Apply (creates GKE cluster, CloudSQL, Redis, etc.)
terraform apply -var="project_id=$GCP_PROJECT_ID"

# Get GKE credentials
gcloud container clusters get-credentials helios-dev-gke --region us-central1

# Return to project root
cd ../../..
```

---

## Step 4: Deploy Monitoring Stack

```powershell
# Create namespaces
kubectl create namespace monitoring
kubectl create namespace helios

# Deploy Prometheus & Grafana
kubectl apply -k infra/kubernetes/monitoring/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=300s
```

---

## Step 5: Deploy Demo Application (Saleor)

```powershell
# Deploy Saleor e-commerce platform
kubectl apply -k infra/kubernetes/saleor/overlays/dev/

# Wait for deployment
kubectl wait --for=condition=available deployment/saleor-api -n saleor --timeout=300s

# Verify
kubectl get pods -n saleor
```

---

## Step 6: Set Up Python Environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install ML dependencies
pip install -r ml/requirements.txt
```

---

## Step 7: Train ML Models

```powershell
# Navigate to ML directory
cd ml

# Fetch real metrics data (requires GKE cluster running)
python fetch_real_data.py

# Train the models
python train.py

# Upload models to GCS
$BUCKET = "helios-models-$GCP_PROJECT_ID"
gcloud storage buckets create gs://$BUCKET --location=us-central1
gcloud storage cp models/*.joblib gs://$BUCKET/models/

# Return to root
cd ..
```

---

## Step 8: Build & Deploy Inference Service

```powershell
# Build with Cloud Build
gcloud builds submit --config=cloudbuild.yaml --substitutions=_TAG_NAME=0.2.0

# Deploy to Kubernetes
kubectl apply -k infra/kubernetes/helios-inference/

# Wait for deployment
kubectl wait --for=condition=available deployment/helios-inference -n helios --timeout=300s

# Verify
kubectl get pods -n helios
```

---

## Step 9: Build & Deploy Cost Intelligence Service

```powershell
# Build with Cloud Build
gcloud builds submit --config=cloudbuild-cost.yaml --substitutions=_TAG_NAME=0.1.1

# Deploy to Kubernetes
kubectl apply -k infra/kubernetes/helios-cost/

# Wait for deployment
kubectl wait --for=condition=available deployment/helios-cost-intelligence -n helios --timeout=300s
```

---

## Step 10: Deploy KEDA for Auto-Scaling

```powershell
# Install KEDA
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace

# Apply ScaledObject for Saleor
kubectl apply -f infra/kubernetes/keda/saleor-scaledobject.yaml
```

---

## Step 11: Verify Deployment

```powershell
# Check all Helios services
kubectl get all -n helios

# Port-forward inference service
kubectl port-forward svc/helios-inference 8080:8080 -n helios

# In another terminal - test the API
Invoke-RestMethod -Uri "http://localhost:8080/health"
Invoke-RestMethod -Uri "http://localhost:8080/predict?metric=cpu&horizon=15"
Invoke-RestMethod -Uri "http://localhost:8080/detect"
Invoke-RestMethod -Uri "http://localhost:8080/recommend"

# Port-forward cost intelligence
kubectl port-forward svc/helios-cost-intelligence 8081:8081 -n helios

# Test cost APIs
Invoke-RestMethod -Uri "http://localhost:8081/costs/summary"
Invoke-RestMethod -Uri "http://localhost:8081/savings"
Invoke-RestMethod -Uri "http://localhost:8081/efficiency/summary"
```

---

## Step 12: Access Dashboards

```powershell
# Grafana (default: admin/admin)
kubectl port-forward svc/grafana 3000:80 -n monitoring
# Open: http://localhost:3000

# Prometheus
kubectl port-forward svc/prometheus-server 9090:80 -n monitoring
# Open: http://localhost:9090
```

---

## Step 13: Run Load Tests (Optional)

```powershell
# Deploy Locust
kubectl apply -k infra/kubernetes/locust/

# Port-forward Locust UI
kubectl port-forward svc/locust-master 8089:8089 -n locust
# Open: http://localhost:8089

# Or run locally
cd loadtest
pip install locust
locust -f locustfiles/locustfile.py --host=http://saleor-api.saleor.svc.cluster.local
```

---

## Quick Reference Commands

```powershell
# View logs
kubectl logs -f deployment/helios-inference -n helios
kubectl logs -f deployment/helios-cost-intelligence -n helios

# Scale deployments
kubectl scale deployment/helios-inference --replicas=3 -n helios

# Check metrics
kubectl get --raw /apis/external.metrics.k8s.io/v1beta1

# Restart deployment
kubectl rollout restart deployment/helios-inference -n helios

# Delete everything (cleanup)
terraform destroy -var="project_id=$GCP_PROJECT_ID"
```

---

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Your GCP project ID | `my-project-123456` |
| `GCP_REGION` | GCP region | `us-central1` |
| `GKE_CLUSTER_NAME` | GKE cluster name | `helios-dev-gke` |
| `MODELS_GCS_BUCKET` | GCS bucket for models | `helios-models-xxx` |

---

## Troubleshooting

### Pods not starting
```powershell
kubectl describe pod <pod-name> -n helios
kubectl logs <pod-name> -n helios
```

### Model loading errors
```powershell
# Verify models exist in GCS
gcloud storage ls gs://helios-models-$GCP_PROJECT_ID/models/
```

### Permission errors
```powershell
# Check service account permissions
gcloud projects get-iam-policy $GCP_PROJECT_ID
```
