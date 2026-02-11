# Helios on GCP: Testing Guide

This guide explains how to configure and test the Helios ML Retraining service with Google Cloud Platform (GCP) Cloud Monitoring.

## Prerequisites

1.  **GCP Project**: You need a Google Cloud Project with Cloud Monitoring enabled.
2.  **Permissions**: Your user/service account needs `Monitoring Viewer` role.
3.  **Data**: The project should have GKE or other metrics available (e.g., `kubernetes.io/container/cpu/limit_utilization`).

## Configuration

The Helios Inference Service uses **Environment Variables** for configuration. It does *not* read `helios-agent.yaml` directly (that is for the Go agent).

### 1. Set Environment Variables

Run these commands in PowerShell before starting the service:

```powershell
# 1. Set your GCP Project ID (REQUIRED)
$env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"

# 2. Authentication (ADC)
# If running locally, you likely don't need to set GOOGLE_APPLICATION_CREDENTIALS 
# if you have run 'gcloud auth application-default login'.
# Otherwise:
# $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account-key.json"

# 3. Configure Retraining
$env:RETRAIN_ENABLED = "true"
$env:RETRAIN_DATA_SOURCE = "gcp"
$env:RETRAIN_INTERVAL_HOURS = "6"
```

### 2. Verify Authentication

Ensure you are authenticated locally:

```bash
gcloud auth application-default login
```

## Running the Service

Start the inference service:

```powershell
# In c:\Users\Windows\Desktop\helios
$env:PORT = "8001"
python -m ml.inference.app
```

You should see logs indicating the scheduler started:
`INFO: Retraining scheduler started: every 6h, source=gcp`

## Triggering a Test

You can manually trigger a retraining cycle to verify data fetching and model training without waiting for the schedule.

### Option A: Using the Dashboard

1.  Start the frontend:
    ```bash
    cd ml/inference/web
    npm run dev
    ```
2.  Open `http://localhost:3000`.
3.  Locate the **Model Training** card.
4.  Click **Retrain Now**.

### Option B: Using PowerShell / curl

```powershell
# Trigger a retrain (fetch last 24h of data)
Invoke-RestMethod -Uri "http://localhost:8001/api/retrain/trigger" -Method Post -Body '{"hours": 24}' -ContentType "application/json"

# Check status
Invoke-RestMethod -Uri "http://localhost:8001/api/retrain/status"
```

## Troubleshooting

-   **"No data returned"**:
    -   Verify your GCP Project ID is correct.
    -   Check if the project actually has metrics for the requested window (`kubernetes.io/container/...`).
    -   Try increasing the window: `{"hours": 168}` (7 days).

-   **Authentication Errors**:
    -   Run `gcloud auth application-default login` again.
    -   Check if `GOOGLE_APPLICATION_CREDENTIALS` is pointing to a valid key file.
