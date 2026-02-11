# Helios on GCP: Complete Setup Guide

This guide details how to set up Helios to:
1.  **Collect Real-time Metrics** (using the Helios Agent).
2.  **Retrain Models Automatically** (using the Helios Backend).

## Prerequisites

1.  **GCP Project**: A Google Cloud Project with Cloud Monitoring API enabled.
2.  **Credentials**:
    *   **Service Account** with `Monitoring Viewer` role.
    *   **Local Dev**: Run `gcloud auth application-default login`.

---

## Part 1: Real-time Monitoring (The Agent)

The **Helios Agent** runs on your infrastructure (e.g., inside GKE), collects metrics, and pushes them to the Helios Dashboard in real-time.

### 1. Install the Agent

```bash
pip install helios-agent[gcp]
```

### 2. Configure the Agent

Create a `helios-agent.yaml` file:

```yaml
# helios-agent.yaml
endpoint:
  url: "http://localhost:8001"  # Backend URL

sources:
  - name: gcp-cluster-1
    type: gcp_monitoring
    enabled: true
    # Authentication uses ADC (gcloud login) automatically.
    # explicit project_id is optional if ADC has a default project.
    credentials:
      project_id: "your-gcp-project-id" 
    metrics:
      - "kubernetes.io/container/cpu/limit_utilization"
      - "kubernetes.io/container/memory/limit_utilization"
```

### 3. Run the Agent

```bash
helios-agent --config helios-agent.yaml
```

### 4. Verify on Dashboard

1.  Go to the **Dashboard**.
2.  Look at the **Agents** card (Green icon).
3.  You should see **"1 Agents Online"**.

---

## Part 2: Automated Model Retraining (The Backend)

The **Helios Backend** can independently connect to GCP to fetch historical data (e.g., last 24h) to train new ML models.

### 1. Configure the Backend

Set these environment variables for the backend service:

```powershell
# Windows PowerShell
$env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"
$env:RETRAIN_ENABLED = "true"
$env:RETRAIN_DATA_SOURCE = "gcp"
```

### 2. Run the Backend

```powershell
# Ensure you are in the helios root directory
$env:PORT = "8001"
python -m ml.inference.app
```

### 3. Verify on Dashboard

1.  Go to the **Dashboard**.
2.  Look at the **Model Training** card (Purple icon).
3.  It should say **Source: GCP**.
4.  Click **"Retrain Now"** to trigger an immediate fetch-and-train cycle.

---

## Part 3: Running the Dashboard

To see all of this, you need the frontend running:

```bash
cd ml/inference/web
npm run dev
```

Open your browser to `http://localhost:3000`.

## Summary

| Component | Connected To | Purpose | Dashboard Verification |
|-----------|--------------|---------|------------------------|
| **Agent** | `helios-agent.yaml` | Real-time stream | **Agents** Card |
| **Backend** | Env Vars | Historical training | **Model Training** Card |
