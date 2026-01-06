"""Pydantic models for Cost Intelligence API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Resource types for cost calculation."""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


class TimeRange(str, Enum):
    """Time ranges for queries."""
    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"


class OptimizationType(str, Enum):
    """Types of cost optimizations."""
    AUTOSCALING = "autoscaling"
    RIGHTSIZING = "rightsizing"
    SPOT_INSTANCES = "spot_instances"
    SCHEDULING = "scheduling"


# =============================================================================
# Cost Models
# =============================================================================

class ResourceCost(BaseModel):
    """Cost for a specific resource type."""
    resource: ResourceType
    quantity: float = Field(..., description="Resource quantity (cores, GB, etc.)")
    unit_price: float = Field(..., description="Price per unit per hour")
    hourly_cost: float = Field(..., description="Total hourly cost")
    daily_cost: float = Field(..., description="Projected daily cost")
    monthly_cost: float = Field(..., description="Projected monthly cost")


class WorkloadCost(BaseModel):
    """Cost breakdown for a workload."""
    name: str
    namespace: str
    replicas: int
    resources: list[ResourceCost]
    total_hourly: float
    total_daily: float
    total_monthly: float
    efficiency_score: float = Field(..., ge=0, le=1, description="Resource efficiency 0-1")


class NamespaceCost(BaseModel):
    """Cost breakdown for a namespace."""
    namespace: str
    workloads: list[WorkloadCost]
    total_hourly: float
    total_daily: float
    total_monthly: float
    workload_count: int


class CostSummary(BaseModel):
    """Overall cost summary."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    period: TimeRange
    namespaces: list[NamespaceCost]
    total_hourly: float
    total_daily: float
    total_monthly: float
    currency: str = "USD"


# =============================================================================
# Savings Models
# =============================================================================

class SavingsEvent(BaseModel):
    """A single cost savings event."""
    timestamp: datetime
    workload: str
    namespace: str
    optimization_type: OptimizationType
    savings_hourly: float
    savings_monthly: float
    action_taken: str
    before_replicas: Optional[int] = None
    after_replicas: Optional[int] = None
    before_cost: Optional[float] = None
    after_cost: Optional[float] = None


class SavingsSummary(BaseModel):
    """Summary of cost savings."""
    period: TimeRange
    total_savings: float
    savings_by_type: dict[OptimizationType, float]
    savings_by_namespace: dict[str, float]
    events: list[SavingsEvent]
    potential_additional_savings: float
    roi_percent: float = Field(..., description="Return on investment percentage")


class PotentialSaving(BaseModel):
    """A potential savings opportunity."""
    workload: str
    namespace: str
    current_cost_monthly: float
    optimized_cost_monthly: float
    potential_savings_monthly: float
    optimization_type: OptimizationType
    recommendation: str
    confidence: float = Field(..., ge=0, le=1)
    implementation_effort: str = Field(..., description="low/medium/high")


# =============================================================================
# Efficiency Models
# =============================================================================

class ResourceEfficiency(BaseModel):
    """Efficiency metrics for a resource."""
    resource: ResourceType
    requested: float
    used: float
    efficiency: float = Field(..., ge=0, le=1, description="Usage / Requested")
    waste_cost_hourly: float
    recommendation: Optional[str] = None


class WorkloadEfficiency(BaseModel):
    """Efficiency metrics for a workload."""
    name: str
    namespace: str
    resources: list[ResourceEfficiency]
    overall_efficiency: float
    waste_cost_monthly: float
    is_oversized: bool
    is_undersized: bool


class EfficiencySummary(BaseModel):
    """Overall efficiency summary."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    overall_efficiency: float
    total_waste_monthly: float
    workloads: list[WorkloadEfficiency]
    top_opportunities: list[PotentialSaving]


# =============================================================================
# Forecast Models
# =============================================================================

class CostForecastPoint(BaseModel):
    """Single forecast data point."""
    timestamp: datetime
    predicted_cost: float
    lower_bound: float
    upper_bound: float
    confidence: float


class CostForecast(BaseModel):
    """Cost forecast response."""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period: TimeRange
    namespace: Optional[str] = None
    current_daily_cost: float
    forecast_points: list[CostForecastPoint]
    projected_total: float
    trend: str = Field(..., description="increasing/decreasing/stable")
    trend_percent: float


# =============================================================================
# API Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CostResponse(BaseModel):
    """Cost API response."""
    success: bool
    data: CostSummary
    metadata: dict[str, Any] = Field(default_factory=dict)


class SavingsResponse(BaseModel):
    """Savings API response."""
    success: bool
    data: SavingsSummary
    metadata: dict[str, Any] = Field(default_factory=dict)


class EfficiencyResponse(BaseModel):
    """Efficiency API response."""
    success: bool
    data: EfficiencySummary
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForecastResponse(BaseModel):
    """Forecast API response."""
    success: bool
    data: CostForecast
    metadata: dict[str, Any] = Field(default_factory=dict)
