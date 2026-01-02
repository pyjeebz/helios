"""Pydantic models for Helios Inference API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class ModelType(str, Enum):
    """Available model types."""
    BASELINE = "baseline"
    PROPHET = "prophet"
    XGBOOST = "xgboost"
    ENSEMBLE = "ensemble"


class MetricName(str, Enum):
    """Supported metric names."""
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    MEMORY_BYTES = "memory_bytes"
    DB_CPU = "db_cpu"
    DB_MEMORY = "db_memory"
    DB_CONNECTIONS = "db_connections"


class Severity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    """Recommendation action types."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_ACTION = "no_action"
    INVESTIGATE = "investigate"


# =============================================================================
# Health & Status
# =============================================================================

class HealthStatus(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status: healthy/unhealthy")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    models_loaded: int = Field(0, description="Number of models loaded")
    uptime_seconds: float = Field(0.0, description="Service uptime in seconds")


class ReadyStatus(BaseModel):
    """Readiness check response."""
    ready: bool = Field(..., description="Whether service is ready")
    models_ready: bool = Field(False, description="Whether models are loaded")
    details: Dict[str, bool] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    """Information about a loaded model."""
    name: str
    type: ModelType
    version: str
    loaded_at: datetime
    metrics: List[str] = Field(default_factory=list)
    performance: Dict[str, float] = Field(default_factory=dict)


# =============================================================================
# Prediction
# =============================================================================

class PredictionRequest(BaseModel):
    """Request for time-series prediction."""
    metric: MetricName = Field(..., description="Metric to predict")
    periods: int = Field(12, ge=1, le=288, description="Number of periods to forecast (5min each)")
    model: ModelType = Field(ModelType.BASELINE, description="Model to use")
    include_confidence: bool = Field(True, description="Include confidence intervals")
    
    model_config = {"json_schema_extra": {
        "example": {
            "metric": "cpu_utilization",
            "periods": 12,
            "model": "baseline",
            "include_confidence": True
        }
    }}


class PredictionPoint(BaseModel):
    """Single prediction point."""
    timestamp: datetime
    value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class PredictionResponse(BaseModel):
    """Response containing predictions."""
    metric: str
    model: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    periods: int
    predictions: List[PredictionPoint]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Anomaly Detection
# =============================================================================

class MetricDataPoint(BaseModel):
    """Single metric data point for anomaly detection."""
    timestamp: datetime
    value: float


class AnomalyRequest(BaseModel):
    """Request for anomaly detection."""
    metrics: Dict[MetricName, List[MetricDataPoint]] = Field(
        ..., 
        description="Dictionary of metric name to list of data points"
    )
    threshold_sigma: float = Field(2.5, ge=1.0, le=5.0, description="Anomaly threshold in std deviations")
    
    model_config = {"json_schema_extra": {
        "example": {
            "metrics": {
                "cpu_utilization": [
                    {"timestamp": "2026-01-02T10:00:00Z", "value": 0.15},
                    {"timestamp": "2026-01-02T10:05:00Z", "value": 0.18},
                    {"timestamp": "2026-01-02T10:10:00Z", "value": 0.85}
                ]
            },
            "threshold_sigma": 2.5
        }
    }}


class Anomaly(BaseModel):
    """Detected anomaly."""
    metric: str
    timestamp: datetime
    value: float
    expected_value: float
    anomaly_score: float
    severity: Severity
    description: str


class AnomalyResponse(BaseModel):
    """Response containing anomaly detection results."""
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    data_points_analyzed: int
    anomalies_detected: int
    anomalies: List[Anomaly]
    summary: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Recommendations
# =============================================================================

class CurrentState(BaseModel):
    """Current infrastructure state."""
    replicas: int = Field(..., ge=0, description="Current replica count")
    cpu_request: str = Field("100m", description="CPU request per pod")
    memory_request: str = Field("256Mi", description="Memory request per pod")
    cpu_limit: str = Field("500m", description="CPU limit per pod")
    memory_limit: str = Field("512Mi", description="Memory limit per pod")


class RecommendationRequest(BaseModel):
    """Request for scaling recommendations."""
    workload: str = Field(..., description="Workload name (e.g., 'saleor-api')")
    namespace: str = Field("saleor", description="Kubernetes namespace")
    current_state: CurrentState
    predictions: Optional[List[PredictionPoint]] = Field(None, description="Optional predictions")
    target_utilization: float = Field(0.7, ge=0.1, le=0.95, description="Target utilization")
    
    model_config = {"json_schema_extra": {
        "example": {
            "workload": "saleor-api",
            "namespace": "saleor",
            "current_state": {
                "replicas": 3,
                "cpu_request": "100m",
                "memory_request": "256Mi",
                "cpu_limit": "500m",
                "memory_limit": "512Mi"
            },
            "target_utilization": 0.7
        }
    }}


class ScalingAction(BaseModel):
    """Recommended scaling action."""
    action: ActionType
    target_replicas: Optional[int] = None
    target_cpu_request: Optional[str] = None
    target_memory_request: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    estimated_savings_percent: Optional[float] = None


class Recommendation(BaseModel):
    """Complete recommendation with context."""
    workload: str
    namespace: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    current_state: CurrentState
    actions: List[ScalingAction]
    predicted_utilization: Optional[float] = None
    time_horizon_minutes: int = Field(60, description="How far ahead this recommendation considers")


class RecommendationResponse(BaseModel):
    """Response containing recommendations."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    recommendations: List[Recommendation]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Batch Operations
# =============================================================================

class BatchPredictionRequest(BaseModel):
    """Batch prediction request for multiple metrics."""
    metrics: List[MetricName] = Field(..., min_length=1)
    periods: int = Field(12, ge=1, le=288)
    model: ModelType = Field(ModelType.BASELINE)


class BatchPredictionResponse(BaseModel):
    """Batch prediction response."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    predictions: Dict[str, PredictionResponse]


# =============================================================================
# Error Response
# =============================================================================

class ErrorDetail(BaseModel):
    """Error detail."""
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    details: List[ErrorDetail] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
