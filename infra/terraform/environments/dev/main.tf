# =============================================================================
# Helios Phase 1 - Saleor Customer Workload on GKE
# =============================================================================
# This Terraform configuration deploys the complete infrastructure for running
# Saleor e-commerce platform on Google Kubernetes Engine (GKE).
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Uncomment for remote state (recommended for team use)
  # backend "gcs" {
  #   bucket = "helios-terraform-state"
  #   prefix = "dev/saleor"
  # }
}

# -----------------------------------------------------------------------------
# Local Variables
# -----------------------------------------------------------------------------
locals {
  project_id   = var.project_id
  region       = var.region
  zone         = "${var.region}-a"
  environment  = var.environment
  
  # Naming convention
  name_prefix = "helios-${local.environment}"
  
  # Common labels
  common_labels = {
    project     = "helios"
    environment = local.environment
    managed_by  = "terraform"
    component   = "saleor-workload"
  }
}

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------
provider "google" {
  project = local.project_id
  region  = local.region
}

provider "google-beta" {
  project = local.project_id
  region  = local.region
}

# Configure Kubernetes provider after GKE cluster is created
provider "kubernetes" {
  host                   = "https://${module.gke.cluster_endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
}

data "google_client_config" "default" {}

# -----------------------------------------------------------------------------
# Enable Required APIs
# -----------------------------------------------------------------------------
resource "google_project_service" "required_apis" {
  for_each = toset([
    "container.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
  ])

  project            = local.project_id
  service            = each.value
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  project_id  = local.project_id
  region      = local.region
  name_prefix = local.name_prefix
  labels      = local.common_labels

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# GKE Autopilot Cluster
# -----------------------------------------------------------------------------
module "gke" {
  source = "../../modules/gke"

  project_id  = local.project_id
  region      = local.region
  name_prefix = local.name_prefix
  labels      = local.common_labels

  network_id    = module.networking.network_id
  subnet_id     = module.networking.subnet_id
  pods_range    = module.networking.pods_range_name
  services_range = module.networking.services_range_name

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# Cloud SQL PostgreSQL
# -----------------------------------------------------------------------------
module "cloudsql" {
  source = "../../modules/cloudsql"

  project_id  = local.project_id
  region      = local.region
  name_prefix = local.name_prefix
  labels      = local.common_labels

  network_id               = module.networking.network_id
  private_ip_address_range = module.networking.private_services_range

  database_name = "saleor"
  database_user = "saleor"

  # Instance sizing (adjust for load testing)
  tier            = var.cloudsql_tier
  disk_size_gb    = var.cloudsql_disk_size
  disk_autoresize = true

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# Memorystore Redis
# -----------------------------------------------------------------------------
module "redis" {
  source = "../../modules/redis"

  project_id  = local.project_id
  region      = local.region
  name_prefix = local.name_prefix
  labels      = local.common_labels

  network_id = module.networking.network_id

  # Instance sizing
  memory_size_gb = var.redis_memory_size
  tier           = var.redis_tier

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# GCS Bucket for Media
# -----------------------------------------------------------------------------
module "storage" {
  source = "../../modules/storage"

  project_id  = local.project_id
  region      = local.region
  name_prefix = local.name_prefix
  labels      = local.common_labels

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# Workload Identity & IAM
# -----------------------------------------------------------------------------
module "iam" {
  source = "../../modules/iam"

  project_id  = local.project_id
  name_prefix = local.name_prefix

  gke_cluster_name = module.gke.cluster_name
  media_bucket_name = module.storage.media_bucket_name

  depends_on = [module.gke, module.storage]
}

# -----------------------------------------------------------------------------
# Kubernetes Namespace & Base Resources
# -----------------------------------------------------------------------------
resource "kubernetes_namespace" "saleor" {
  metadata {
    name = "saleor"
    labels = merge(local.common_labels, {
      name = "saleor"
    })
  }

  depends_on = [module.gke]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "cloudsql_connection_name" {
  description = "Cloud SQL connection name for proxy"
  value       = module.cloudsql.connection_name
}

output "cloudsql_private_ip" {
  description = "Cloud SQL private IP"
  value       = module.cloudsql.private_ip
  sensitive   = true
}

output "redis_host" {
  description = "Redis host"
  value       = module.redis.host
  sensitive   = true
}

output "redis_port" {
  description = "Redis port"
  value       = module.redis.port
}

output "media_bucket_name" {
  description = "GCS bucket for Saleor media"
  value       = module.storage.media_bucket_name
}

output "saleor_service_account_email" {
  description = "Service account email for Saleor workload identity"
  value       = module.iam.saleor_service_account_email
}

output "kubeconfig_command" {
  description = "Command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --region ${local.region} --project ${local.project_id}"
}
