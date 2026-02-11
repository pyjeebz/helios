"""Configuration for Helios Inference Service."""

import os
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    """HTTP server configuration."""

    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    reload: bool = False
    log_level: str = "info"


@dataclass
class ModelConfig:
    """Model loading configuration."""

    models_dir: str = "/app/models"
    baseline_enabled: bool = True
    prophet_enabled: bool = True
    xgboost_enabled: bool = True
    cache_predictions: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes


@dataclass
class MetricsConfig:
    """Prometheus metrics configuration."""

    enabled: bool = True
    prefix: str = "helios"
    default_labels: dict = field(
        default_factory=lambda: {"service": "helios-inference", "version": "0.1.0"}
    )


@dataclass
class AnomalyConfig:
    """Anomaly detection configuration."""

    default_threshold_sigma: float = 2.5
    min_data_points: int = 12  # 1 hour of 5-min data
    severity_thresholds: dict = field(
        default_factory=lambda: {"low": 2.0, "medium": 2.5, "high": 3.0, "critical": 4.0}
    )


@dataclass
class AuthConfig:
    """Authentication configuration."""
    
    enabled: bool = False
    api_key: str = ""  # If set, requests must include this key
    exempt_paths: list = field(
        default_factory=lambda: ["/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"]
    )


@dataclass
class RecommendationConfig:
    """Recommendation engine configuration."""

    target_utilization: float = 0.7
    scale_up_threshold: float = 0.85
    scale_down_threshold: float = 0.3
    cooldown_minutes: int = 5
    min_replicas: int = 1
    max_replicas: int = 100



@dataclass
class GcpConfig:
    """Google Cloud Platform configuration."""
    
    project_id: str = ""


@dataclass
class RetrainingConfig:
    """Automated model retraining configuration."""

    enabled: bool = True
    interval_hours: int = 6           # Retrain every N hours
    training_hours: int = 24          # Fetch last N hours from platform
    min_data_points: int = 100        # Skip retrain if < N data points
    auto_deploy: bool = True          # Auto-swap if new model is better
    min_improvement: float = 0.05     # 5% improvement required to deploy
    data_source: str = "gcp"          # "gcp" | "cloudwatch"


@dataclass
class InferenceConfig:
    """Main configuration class."""

    server: ServerConfig = field(default_factory=ServerConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    recommendation: RecommendationConfig = field(default_factory=RecommendationConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    retraining: RetrainingConfig = field(default_factory=RetrainingConfig)
    gcp: GcpConfig = field(default_factory=GcpConfig)

    # Environment
    environment: str = "development"
    debug: bool = False

    @classmethod
    def from_env(cls) -> "InferenceConfig":
        """Load configuration from environment variables."""
        return cls(
            server=ServerConfig(
                host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8080")),
                workers=int(os.getenv("WORKERS", "1")),
                reload=os.getenv("RELOAD", "false").lower() == "true",
                log_level=os.getenv("LOG_LEVEL", "info"),
            ),
            model=ModelConfig(
                models_dir=os.getenv("MODELS_DIR", "/app/models"),
                baseline_enabled=os.getenv("BASELINE_ENABLED", "true").lower() == "true",
                prophet_enabled=os.getenv("PROPHET_ENABLED", "true").lower() == "true",
                xgboost_enabled=os.getenv("XGBOOST_ENABLED", "true").lower() == "true",
                cache_predictions=os.getenv("CACHE_PREDICTIONS", "true").lower() == "true",
                cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
            ),
            metrics=MetricsConfig(
                enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
                prefix=os.getenv("METRICS_PREFIX", "helios"),
            ),
            anomaly=AnomalyConfig(
                default_threshold_sigma=float(os.getenv("ANOMALY_THRESHOLD", "2.5")),
                min_data_points=int(os.getenv("ANOMALY_MIN_POINTS", "12")),
            ),
            recommendation=RecommendationConfig(
                target_utilization=float(os.getenv("TARGET_UTILIZATION", "0.7")),
                scale_up_threshold=float(os.getenv("SCALE_UP_THRESHOLD", "0.85")),
                scale_down_threshold=float(os.getenv("SCALE_DOWN_THRESHOLD", "0.3")),
                cooldown_minutes=int(os.getenv("COOLDOWN_MINUTES", "5")),
                min_replicas=int(os.getenv("MIN_REPLICAS", "1")),
                max_replicas=int(os.getenv("MAX_REPLICAS", "100")),
            ),
            auth=AuthConfig(
                enabled=os.getenv("AUTH_ENABLED", "false").lower() == "true",
                api_key=os.getenv("HELIOS_API_KEY", ""),
            ),
            retraining=RetrainingConfig(
                enabled=os.getenv("RETRAIN_ENABLED", "true").lower() == "true",
                interval_hours=int(os.getenv("RETRAIN_INTERVAL_HOURS", "6")),
                training_hours=int(os.getenv("RETRAIN_TRAINING_HOURS", "24")),
                min_data_points=int(os.getenv("RETRAIN_MIN_DATA_POINTS", "100")),
                auto_deploy=os.getenv("RETRAIN_AUTO_DEPLOY", "true").lower() == "true",
                min_improvement=float(os.getenv("RETRAIN_MIN_IMPROVEMENT", "0.05")),
                data_source=os.getenv("RETRAIN_DATA_SOURCE", "gcp"),
            ),
            gcp=GcpConfig(
                project_id=os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", "")),
            ),
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )


# Global config instance
config = InferenceConfig.from_env()
