# =============================================================================
# Storage Module (GCS)
# =============================================================================
# Creates GCS buckets for Saleor media and static files
# =============================================================================

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
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

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "labels" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}

variable "storage_class" {
  description = "Storage class for buckets"
  type        = string
  default     = "STANDARD"
}

variable "versioning_enabled" {
  description = "Enable object versioning"
  type        = bool
  default     = false
}

variable "lifecycle_age_days" {
  description = "Days before objects are moved to cheaper storage (0 to disable)"
  type        = number
  default     = 0
}

# -----------------------------------------------------------------------------
# Random suffix for globally unique bucket names
# -----------------------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# -----------------------------------------------------------------------------
# Media Bucket (user uploads, product images)
# -----------------------------------------------------------------------------
resource "google_storage_bucket" "media" {
  name          = "${var.name_prefix}-media-${random_id.bucket_suffix.hex}"
  project       = var.project_id
  location      = var.region
  storage_class = var.storage_class

  # Prevent accidental deletion
  force_destroy = true # Set to false in production

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  # Versioning
  versioning {
    enabled = var.versioning_enabled
  }

  # CORS configuration for direct browser uploads
  cors {
    origin          = ["*"] # Restrict in production
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  # Lifecycle rules
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_age_days > 0 ? [1] : []
    content {
      condition {
        age = var.lifecycle_age_days
      }
      action {
        type          = "SetStorageClass"
        storage_class = "NEARLINE"
      }
    }
  }

  # Delete incomplete multipart uploads after 7 days
  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }

  labels = var.labels
}

# -----------------------------------------------------------------------------
# Static Bucket (optional - for static assets if not using CDN)
# -----------------------------------------------------------------------------
resource "google_storage_bucket" "static" {
  name          = "${var.name_prefix}-static-${random_id.bucket_suffix.hex}"
  project       = var.project_id
  location      = var.region
  storage_class = var.storage_class

  force_destroy = true

  uniform_bucket_level_access = true

  # Make objects publicly readable
  # Note: Use Cloud CDN in production instead

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 86400 # 24 hours
  }

  labels = var.labels
}

# -----------------------------------------------------------------------------
# Public access for static bucket
# -----------------------------------------------------------------------------
resource "google_storage_bucket_iam_member" "static_public" {
  bucket = google_storage_bucket.static.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "media_bucket_name" {
  description = "Media bucket name"
  value       = google_storage_bucket.media.name
}

output "media_bucket_url" {
  description = "Media bucket URL"
  value       = google_storage_bucket.media.url
}

output "static_bucket_name" {
  description = "Static bucket name"
  value       = google_storage_bucket.static.name
}

output "static_bucket_url" {
  description = "Static bucket URL"
  value       = google_storage_bucket.static.url
}

output "static_bucket_public_url" {
  description = "Static bucket public URL"
  value       = "https://storage.googleapis.com/${google_storage_bucket.static.name}"
}
