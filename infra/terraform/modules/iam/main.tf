# =============================================================================
# IAM Module
# =============================================================================
# Creates service accounts and IAM bindings for Workload Identity
# =============================================================================

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Input Variables
# -----------------------------------------------------------------------------
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "gke_cluster_name" {
  description = "GKE cluster name"
  type        = string
}

variable "media_bucket_name" {
  description = "Name of the media GCS bucket"
  type        = string
}

variable "saleor_namespace" {
  description = "Kubernetes namespace for Saleor"
  type        = string
  default     = "saleor"
}

variable "saleor_service_account" {
  description = "Kubernetes service account name for Saleor"
  type        = string
  default     = "saleor-api"
}

variable "worker_service_account" {
  description = "Kubernetes service account name for Saleor worker"
  type        = string
  default     = "saleor-worker"
}

# -----------------------------------------------------------------------------
# Service Account for Saleor API
# -----------------------------------------------------------------------------
resource "google_service_account" "saleor_api" {
  account_id   = "${var.name_prefix}-saleor-api"
  display_name = "Saleor API Service Account"
  project      = var.project_id
}

# Grant GCS access for media uploads
resource "google_storage_bucket_iam_member" "saleor_api_media" {
  bucket = var.media_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.saleor_api.email}"
}

# Grant Secret Manager access
resource "google_project_iam_member" "saleor_api_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.saleor_api.email}"
}

# Grant Cloud SQL Client access
resource "google_project_iam_member" "saleor_api_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.saleor_api.email}"
}

# Workload Identity binding for API
resource "google_service_account_iam_member" "saleor_api_workload_identity" {
  service_account_id = google_service_account.saleor_api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.saleor_namespace}/${var.saleor_service_account}]"
}

# -----------------------------------------------------------------------------
# Service Account for Saleor Worker (Celery)
# -----------------------------------------------------------------------------
resource "google_service_account" "saleor_worker" {
  account_id   = "${var.name_prefix}-saleor-worker"
  display_name = "Saleor Worker Service Account"
  project      = var.project_id
}

# Grant GCS access for media processing
resource "google_storage_bucket_iam_member" "saleor_worker_media" {
  bucket = var.media_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.saleor_worker.email}"
}

# Grant Secret Manager access
resource "google_project_iam_member" "saleor_worker_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.saleor_worker.email}"
}

# Grant Cloud SQL Client access
resource "google_project_iam_member" "saleor_worker_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.saleor_worker.email}"
}

# Workload Identity binding for Worker
resource "google_service_account_iam_member" "saleor_worker_workload_identity" {
  service_account_id = google_service_account.saleor_worker.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.saleor_namespace}/${var.worker_service_account}]"
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "saleor_service_account_email" {
  description = "Saleor API service account email"
  value       = google_service_account.saleor_api.email
}

output "saleor_service_account_name" {
  description = "Saleor API service account name"
  value       = google_service_account.saleor_api.name
}

output "worker_service_account_email" {
  description = "Saleor Worker service account email"
  value       = google_service_account.saleor_worker.email
}

output "worker_service_account_name" {
  description = "Saleor Worker service account name"
  value       = google_service_account.saleor_worker.name
}

output "workload_identity_annotation_api" {
  description = "Annotation to add to Kubernetes service account for Saleor API"
  value       = "iam.gke.io/gcp-service-account=${google_service_account.saleor_api.email}"
}

output "workload_identity_annotation_worker" {
  description = "Annotation to add to Kubernetes service account for Worker"
  value       = "iam.gke.io/gcp-service-account=${google_service_account.saleor_worker.email}"
}
