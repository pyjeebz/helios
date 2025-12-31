# =============================================================================
# Memorystore Redis Module
# =============================================================================
# Creates a Memorystore Redis instance for Saleor caching and Celery broker
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

variable "network_id" {
  description = "VPC network ID"
  type        = string
}

variable "memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "tier" {
  description = "Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "REDIS_7_0"
}

variable "auth_enabled" {
  description = "Enable AUTH for Redis"
  type        = bool
  default     = true
}

variable "transit_encryption_mode" {
  description = "Transit encryption mode (DISABLED or SERVER_AUTHENTICATION)"
  type        = string
  default     = "DISABLED"
}

# -----------------------------------------------------------------------------
# Memorystore Redis Instance
# -----------------------------------------------------------------------------
resource "google_redis_instance" "main" {
  name           = "${var.name_prefix}-redis"
  project        = var.project_id
  region         = var.region
  
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  redis_version  = var.redis_version

  # Network configuration
  authorized_network = var.network_id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  # Authentication
  auth_enabled = var.auth_enabled

  # Transit encryption
  transit_encryption_mode = var.transit_encryption_mode

  # Redis configuration
  redis_configs = {
    maxmemory-policy = "volatile-lru"
    notify-keyspace-events = "Ex"  # For Celery task expiration
  }

  # Maintenance window (Sunday 5-6 AM)
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 5
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = false
  }
}

# -----------------------------------------------------------------------------
# Store auth string in Secret Manager (if auth enabled)
# -----------------------------------------------------------------------------
resource "google_secret_manager_secret" "redis_auth" {
  count = var.auth_enabled ? 1 : 0

  secret_id = "${var.name_prefix}-redis-auth"
  project   = var.project_id

  labels = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_auth" {
  count = var.auth_enabled ? 1 : 0

  secret      = google_secret_manager_secret.redis_auth[0].id
  secret_data = google_redis_instance.main.auth_string
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "instance_name" {
  description = "Redis instance name"
  value       = google_redis_instance.main.name
}

output "host" {
  description = "Redis host IP"
  value       = google_redis_instance.main.host
  sensitive   = true
}

output "port" {
  description = "Redis port"
  value       = google_redis_instance.main.port
}

output "auth_string" {
  description = "Redis AUTH string"
  value       = google_redis_instance.main.auth_string
  sensitive   = true
}

output "auth_secret_id" {
  description = "Secret Manager secret ID for Redis AUTH"
  value       = var.auth_enabled ? google_secret_manager_secret.redis_auth[0].secret_id : null
}

output "redis_url" {
  description = "Redis connection URL (without auth)"
  value       = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}"
  sensitive   = true
}

output "current_location_id" {
  description = "Current zone where Redis is located"
  value       = google_redis_instance.main.current_location_id
}
