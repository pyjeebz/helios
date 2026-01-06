"""Configuration for Cost Intelligence Service."""

import os
from dataclasses import dataclass, field


@dataclass
class GKEPricing:
    """GKE Autopilot pricing (us-central1)."""

    # Per hour pricing
    cpu_per_core_hour: float = 0.0445  # USD per vCPU hour
    memory_per_gb_hour: float = 0.0049  # USD per GB hour
    storage_per_gb_hour: float = 0.0001  # USD per GB hour (ephemeral)

    # Spot/Preemptible discounts
    spot_discount: float = 0.60  # 60% discount

    # Committed use discounts
    committed_1yr_discount: float = 0.37  # 37% discount
    committed_3yr_discount: float = 0.55  # 55% discount


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = field(default_factory=lambda: os.environ.get("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "8081")))
    workers: int = field(default_factory=lambda: int(os.environ.get("WORKERS", "1")))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "info"))


@dataclass
class PrometheusConfig:
    """Prometheus connection configuration."""

    url: str = field(
        default_factory=lambda: os.environ.get(
            "PROMETHEUS_URL", "http://prometheus-server.monitoring.svc.cluster.local"
        )
    )
    timeout: int = field(default_factory=lambda: int(os.environ.get("PROMETHEUS_TIMEOUT", "30")))


@dataclass
class InferenceConfig:
    """Inference service connection configuration."""

    url: str = field(
        default_factory=lambda: os.environ.get(
            "INFERENCE_URL", "http://helios-inference.helios.svc.cluster.local"
        )
    )
    timeout: int = field(default_factory=lambda: int(os.environ.get("INFERENCE_TIMEOUT", "10")))


@dataclass
class GCPConfig:
    """GCP configuration."""

    project_id: str = field(
        default_factory=lambda: os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
    )
    region: str = field(default_factory=lambda: os.environ.get("GCP_REGION", "us-central1"))
    billing_dataset: str = field(
        default_factory=lambda: os.environ.get("BILLING_DATASET", "billing_export")
    )


@dataclass
class Config:
    """Main configuration."""

    server: ServerConfig = field(default_factory=ServerConfig)
    pricing: GKEPricing = field(default_factory=GKEPricing)
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    gcp: GCPConfig = field(default_factory=GCPConfig)
    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "development"))


# Global config instance
config = Config()
