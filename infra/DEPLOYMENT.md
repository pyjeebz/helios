# =============================================================================
# Helios Phase 1: Saleor on GKE Deployment Guide
# =============================================================================

This guide walks you through deploying the Saleor e-commerce platform on GKE
as the "customer workload" for Helios to monitor and learn from.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- Terraform >= 1.5.0
- kubectl
- A GCP project with billing enabled
- Domain name (optional, but recommended for SSL)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GKE Autopilot                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │ Saleor API  │  │   Worker    │  │  Dashboard  │                │
│  │  (2+ pods)  │  │  (Celery)   │  │  (nginx)    │                │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘                │
│         │                │                                         │
│         └────────────────┼─────────────────────────────────────────┤
│                          │                                         │
├──────────────────────────┼─────────────────────────────────────────┤
│                          ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Private VPC Network                       │  │
│  │                                                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │  │
│  │  │ Cloud SQL   │  │ Memorystore │  │    GCS      │         │  │
│  │  │ PostgreSQL  │  │   Redis     │  │   Bucket    │         │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Clone and Configure

```bash
cd helios/infra/terraform/environments/dev

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
code terraform.tfvars
```

Update `terraform.tfvars`:
```hcl
project_id  = "your-gcp-project-id"
region      = "us-central1"
environment = "dev"
```

### 2. Deploy Infrastructure with Terraform

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

This creates:
- ✅ VPC with private subnets
- ✅ GKE Autopilot cluster
- ✅ Cloud SQL PostgreSQL instance
- ✅ Memorystore Redis instance
- ✅ GCS bucket for media
- ✅ Service accounts with Workload Identity

### 3. Configure kubectl

```bash
# Get credentials (command is output by Terraform)
gcloud container clusters get-credentials helios-dev-gke \
  --region us-central1 \
  --project your-project-id

# Verify connection
kubectl get nodes
```

### 4. Update Kubernetes Secrets

Get the database password from Secret Manager:

```bash
# Get database password
gcloud secrets versions access latest \
  --secret="helios-dev-db-password" \
  --project=your-project-id

# Get Redis auth string (if enabled)
gcloud secrets versions access latest \
  --secret="helios-dev-redis-auth" \
  --project=your-project-id
```

Update the secrets file:

```bash
# Create a local secrets file (DO NOT COMMIT)
cat > /tmp/saleor-secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: saleor-secrets
  namespace: saleor
type: Opaque
stringData:
  DATABASE_USER: "saleor"
  DATABASE_PASSWORD: "<password-from-secret-manager>"
  DATABASE_URL: "postgresql://saleor:<password>@<cloud-sql-private-ip>:5432/saleor"
  SECRET_KEY: "$(openssl rand -hex 32)"
  REDIS_PASSWORD: "<redis-auth-string>"
  DJANGO_SUPERUSER_EMAIL: "admin@example.com"
  DJANGO_SUPERUSER_PASSWORD: "$(openssl rand -base64 16)"
EOF

# Apply secrets
kubectl apply -f /tmp/saleor-secrets.yaml

# Clean up
rm /tmp/saleor-secrets.yaml
```

### 5. Update ConfigMap with Terraform Outputs

```bash
# Get Cloud SQL private IP
CLOUDSQL_IP=$(terraform output -raw cloudsql_private_ip)

# Get Redis host
REDIS_HOST=$(terraform output -raw redis_host)

# Get Media bucket name
MEDIA_BUCKET=$(terraform output -raw media_bucket_name)

# Update configmap
kubectl create configmap saleor-config \
  --namespace=saleor \
  --from-literal=DATABASE_HOST="$CLOUDSQL_IP" \
  --from-literal=DATABASE_PORT="5432" \
  --from-literal=DATABASE_NAME="saleor" \
  --from-literal=REDIS_URL="redis://:$REDIS_PASSWORD@$REDIS_HOST:6379/0" \
  --from-literal=CELERY_BROKER_URL="redis://:$REDIS_PASSWORD@$REDIS_HOST:6379/1" \
  --from-literal=GS_BUCKET_NAME="$MEDIA_BUCKET" \
  --from-literal=DEFAULT_FILE_STORAGE="storages.backends.gcloud.GoogleCloudStorage" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 6. Deploy Saleor

```bash
# Apply Kustomize overlay for dev
kubectl apply -k infra/kubernetes/saleor/overlays/dev

# Wait for deployments
kubectl rollout status deployment/saleor-api -n saleor
```

### 7. Run Database Migrations

```bash
# Apply migration job
kubectl apply -f infra/kubernetes/saleor/jobs/migration-jobs.yaml

# Watch migration progress
kubectl logs -f job/saleor-migrate -n saleor

# Create superuser
kubectl apply -f - << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: saleor-create-superuser-$(date +%s)
  namespace: saleor
spec:
  template:
    spec:
      serviceAccountName: saleor-api
      restartPolicy: Never
      containers:
        - name: create-superuser
          image: ghcr.io/saleor/saleor:3.20
          command: ["python", "manage.py", "createsuperuser", "--noinput"]
          envFrom:
            - configMapRef:
                name: saleor-config
            - secretRef:
                name: saleor-secrets
EOF
```

### 8. Populate Sample Data (Optional)

```bash
kubectl apply -f - << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: saleor-populate-$(date +%s)
  namespace: saleor
spec:
  template:
    spec:
      serviceAccountName: saleor-api
      restartPolicy: Never
      containers:
        - name: populate
          image: ghcr.io/saleor/saleor:3.20
          command: ["python", "manage.py", "populatedb"]
          envFrom:
            - configMapRef:
                name: saleor-config
            - secretRef:
                name: saleor-secrets
EOF
```

### 9. Access Saleor

#### Port-forward for local access:

```bash
# API (GraphQL Playground)
kubectl port-forward svc/saleor-api 8000:80 -n saleor

# Dashboard
kubectl port-forward svc/saleor-dashboard 9000:80 -n saleor
```

Then open:
- GraphQL Playground: http://localhost:8000/graphql/
- Dashboard: http://localhost:9000/

#### With Ingress (for production-like setup):

1. Create DNS records pointing to the Ingress IP
2. Update the domain placeholders in `ingress.yaml`
3. Wait for the managed certificate to provision (~15 min)

## Verification Checklist

- [ ] Can access GraphQL Playground
- [ ] Can browse products in Dashboard
- [ ] Can create a test order
- [ ] Worker processes tasks (check logs)
- [ ] Media uploads work (product images)

## Troubleshooting

### Pod not starting

```bash
# Check pod status
kubectl get pods -n saleor

# Check pod events
kubectl describe pod <pod-name> -n saleor

# Check logs
kubectl logs <pod-name> -n saleor
```

### Database connection issues

```bash
# Test from a debug pod
kubectl run pg-test --rm -it --restart=Never \
  --image=postgres:15 \
  --command -- psql "postgresql://saleor:<password>@<cloud-sql-ip>:5432/saleor"
```

### Redis connection issues

```bash
# Test Redis connectivity
kubectl run redis-test --rm -it --restart=Never \
  --image=redis:7 \
  --command -- redis-cli -h <redis-host> -a <redis-password> ping
```

## Cost Estimate (Dev Environment)

| Resource | Spec | Monthly Cost (est.) |
|----------|------|---------------------|
| GKE Autopilot | ~2 vCPU, 4GB | ~$50-100 |
| Cloud SQL | db-custom-2-4096 | ~$50-70 |
| Memorystore Redis | 1GB Basic | ~$35 |
| Cloud NAT | Egress | ~$10-30 |
| GCS | <10GB | ~$1 |
| **Total** | | **~$150-240/mo** |

💡 **Tip**: Use `terraform destroy` when not actively testing to minimize costs.

## Next Steps

After Saleor is running:

1. **Phase 2**: Set up Locust for load testing
2. **Phase 3**: Deploy Helios ingestion layer
3. **Phase 4**: Configure metrics collection

---

## Clean Up

```bash
# Delete Kubernetes resources
kubectl delete namespace saleor

# Destroy infrastructure
cd infra/terraform/environments/dev
terraform destroy
```
