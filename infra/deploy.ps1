# =============================================================================
# Helper Scripts for Saleor Deployment
# =============================================================================

# Directory for scripts
$ScriptRoot = $PSScriptRoot

function Show-Help {
    Write-Host @"
Helios Saleor Deployment Helper Scripts

Usage: .\deploy.ps1 <command>

Commands:
    init        - Initialize Terraform and create infrastructure
    deploy      - Deploy Saleor to GKE
    migrate     - Run database migrations
    populate    - Populate sample data
    status      - Show deployment status
    logs        - Show logs for a component
    portfwd     - Port-forward services for local access
    destroy     - Destroy all resources

Examples:
    .\deploy.ps1 init
    .\deploy.ps1 deploy
    .\deploy.ps1 logs api
    .\deploy.ps1 portfwd
"@
}

function Initialize-Infrastructure {
    Write-Host "Initializing Terraform..." -ForegroundColor Cyan
    
    Push-Location "$ScriptRoot\terraform\environments\dev"
    
    # Check for tfvars
    if (-not (Test-Path "terraform.tfvars")) {
        Write-Host "ERROR: terraform.tfvars not found. Copy terraform.tfvars.example and update values." -ForegroundColor Red
        Pop-Location
        return
    }
    
    terraform init
    terraform plan -out=tfplan
    
    $confirm = Read-Host "Apply infrastructure? (yes/no)"
    if ($confirm -eq "yes") {
        terraform apply tfplan
    }
    
    Pop-Location
}

function Deploy-Saleor {
    Write-Host "Deploying Saleor to GKE..." -ForegroundColor Cyan
    
    # Get cluster credentials
    Push-Location "$ScriptRoot\terraform\environments\dev"
    $clusterName = terraform output -raw gke_cluster_name
    $region = "us-central1"  # Update if different
    $projectId = terraform output -raw project_id 2>$null
    if (-not $projectId) {
        $projectId = Read-Host "Enter your GCP Project ID"
    }
    Pop-Location
    
    Write-Host "Getting cluster credentials..."
    gcloud container clusters get-credentials $clusterName --region $region --project $projectId
    
    # Apply Kustomize
    Write-Host "Applying Kubernetes manifests..."
    kubectl apply -k "$ScriptRoot\kubernetes\saleor\overlays\dev"
    
    Write-Host "Waiting for deployments..."
    kubectl rollout status deployment/saleor-api -n saleor --timeout=300s
}

function Run-Migrations {
    Write-Host "Running database migrations..." -ForegroundColor Cyan
    
    kubectl apply -f "$ScriptRoot\kubernetes\saleor\jobs\migration-jobs.yaml"
    
    Write-Host "Watching migration logs..."
    Start-Sleep -Seconds 5
    kubectl logs -f job/saleor-migrate -n saleor
}

function Populate-SampleData {
    Write-Host "Populating sample data..." -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    
    kubectl apply -f - << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: saleor-populate-$timestamp
  namespace: saleor
spec:
  ttlSecondsAfterFinished: 300
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
    
    Write-Host "Watching population logs..."
    Start-Sleep -Seconds 10
    kubectl logs -f job/saleor-populate-$timestamp -n saleor
}

function Show-Status {
    Write-Host "`n=== Namespace ===" -ForegroundColor Cyan
    kubectl get namespace saleor
    
    Write-Host "`n=== Pods ===" -ForegroundColor Cyan
    kubectl get pods -n saleor -o wide
    
    Write-Host "`n=== Services ===" -ForegroundColor Cyan
    kubectl get svc -n saleor
    
    Write-Host "`n=== HPA ===" -ForegroundColor Cyan
    kubectl get hpa -n saleor
    
    Write-Host "`n=== Ingress ===" -ForegroundColor Cyan
    kubectl get ingress -n saleor
    
    Write-Host "`n=== Recent Events ===" -ForegroundColor Cyan
    kubectl get events -n saleor --sort-by='.lastTimestamp' | Select-Object -Last 10
}

function Show-Logs {
    param([string]$Component = "api")
    
    $selector = switch ($Component) {
        "api"       { "app.kubernetes.io/name=saleor-api" }
        "worker"    { "app.kubernetes.io/name=saleor-worker" }
        "beat"      { "app.kubernetes.io/name=saleor-beat" }
        "dashboard" { "app.kubernetes.io/name=saleor-dashboard" }
        default     { "app.kubernetes.io/name=saleor-api" }
    }
    
    Write-Host "Showing logs for $Component..." -ForegroundColor Cyan
    kubectl logs -l $selector -n saleor -f --tail=100
}

function Start-PortForward {
    Write-Host "Starting port-forwards..." -ForegroundColor Cyan
    Write-Host "  API (GraphQL):  http://localhost:8000/graphql/"
    Write-Host "  Dashboard:      http://localhost:9000/"
    Write-Host "`nPress Ctrl+C to stop"
    
    # Start background jobs for port-forwarding
    $apiJob = Start-Job -ScriptBlock { kubectl port-forward svc/saleor-api 8000:80 -n saleor }
    $dashJob = Start-Job -ScriptBlock { kubectl port-forward svc/saleor-dashboard 9000:80 -n saleor }
    
    try {
        while ($true) {
            Start-Sleep -Seconds 5
            
            # Check if jobs are still running
            if ($apiJob.State -ne "Running") {
                Write-Host "API port-forward stopped, restarting..." -ForegroundColor Yellow
                $apiJob = Start-Job -ScriptBlock { kubectl port-forward svc/saleor-api 8000:80 -n saleor }
            }
            if ($dashJob.State -ne "Running") {
                Write-Host "Dashboard port-forward stopped, restarting..." -ForegroundColor Yellow
                $dashJob = Start-Job -ScriptBlock { kubectl port-forward svc/saleor-dashboard 9000:80 -n saleor }
            }
        }
    }
    finally {
        Stop-Job $apiJob, $dashJob -ErrorAction SilentlyContinue
        Remove-Job $apiJob, $dashJob -ErrorAction SilentlyContinue
    }
}

function Destroy-Everything {
    $confirm = Read-Host "This will destroy ALL resources. Type 'destroy' to confirm"
    if ($confirm -ne "destroy") {
        Write-Host "Aborted." -ForegroundColor Yellow
        return
    }
    
    Write-Host "Deleting Kubernetes resources..." -ForegroundColor Cyan
    kubectl delete namespace saleor --ignore-not-found
    
    Write-Host "Destroying Terraform infrastructure..." -ForegroundColor Cyan
    Push-Location "$ScriptRoot\terraform\environments\dev"
    terraform destroy -auto-approve
    Pop-Location
    
    Write-Host "Cleanup complete." -ForegroundColor Green
}

# Main script entry
$command = $args[0]
$subarg = $args[1]

switch ($command) {
    "init"      { Initialize-Infrastructure }
    "deploy"    { Deploy-Saleor }
    "migrate"   { Run-Migrations }
    "populate"  { Populate-SampleData }
    "status"    { Show-Status }
    "logs"      { Show-Logs -Component $subarg }
    "portfwd"   { Start-PortForward }
    "destroy"   { Destroy-Everything }
    default     { Show-Help }
}
