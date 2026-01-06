"""Cost Intelligence API - FastAPI Application."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

from .config import config
from .cost_calculator import cost_calculator
from .efficiency import efficiency_analyzer
from .forecaster import cost_forecaster
from .models import (
    CostResponse,
    EfficiencyResponse,
    ForecastResponse,
    HealthResponse,
    SavingsResponse,
    TimeRange,
)
from .savings_analyzer import savings_analyzer

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.server.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "helios_cost_requests_total",
    "Total cost API requests",
    ["endpoint", "method", "status"]
)

COST_GAUGE = Gauge(
    "helios_cost_current",
    "Current costs by namespace and resource",
    ["namespace", "resource"]
)

SAVINGS_GAUGE = Gauge(
    "helios_savings_total",
    "Total savings by type",
    ["type"]
)

EFFICIENCY_GAUGE = Gauge(
    "helios_efficiency",
    "Resource efficiency by namespace",
    ["namespace"]
)

FORECAST_GAUGE = Gauge(
    "helios_cost_forecast",
    "Cost forecast by period",
    ["period"]
)

REQUEST_LATENCY = Histogram(
    "helios_cost_request_latency_seconds",
    "Request latency",
    ["endpoint"]
)


def update_metrics():
    """Update Prometheus gauges with current values."""
    try:
        # Update cost metrics
        costs = cost_calculator.get_current_costs()
        for ns in costs.namespaces:
            for workload in ns.workloads:
                for resource in workload.resources:
                    COST_GAUGE.labels(
                        namespace=ns.namespace,
                        resource=resource.resource.value
                    ).set(resource.hourly_cost)

        # Update savings metrics
        savings = savings_analyzer.get_savings_summary()
        for opt_type, amount in savings.savings_by_type.items():
            SAVINGS_GAUGE.labels(type=opt_type.value).set(amount)

        # Update efficiency metrics
        efficiency = efficiency_analyzer.get_efficiency_summary()
        for workload in efficiency.workloads:
            EFFICIENCY_GAUGE.labels(namespace=workload.namespace).set(
                workload.overall_efficiency
            )

        # Update forecast metrics
        forecast = cost_forecaster.forecast(TimeRange.MONTH, costs.total_daily)
        FORECAST_GAUGE.labels(period="30d").set(forecast.projected_total)

    except Exception as e:
        logger.error(f"Error updating metrics: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Cost Intelligence Service...")
    update_metrics()
    yield
    logger.info("Shutting down Cost Intelligence Service...")


# Create FastAPI app
app = FastAPI(
    title="Helios Cost Intelligence",
    description="Cost analysis and optimization API for Kubernetes infrastructure",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    REQUEST_COUNT.labels(endpoint="/health", method="GET", status="200").inc()
    return HealthResponse(
        status="healthy",
        version="0.1.0"
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness check endpoint."""
    REQUEST_COUNT.labels(endpoint="/ready", method="GET", status="200").inc()
    return {"status": "ready"}


# =============================================================================
# Cost Endpoints
# =============================================================================

@app.get("/costs", response_model=CostResponse, tags=["Costs"])
async def get_costs(
    period: TimeRange = Query(TimeRange.DAY, description="Time period"),
    namespace: Optional[str] = Query(None, description="Filter by namespace")
):
    """Get current cost breakdown."""
    with REQUEST_LATENCY.labels(endpoint="/costs").time():
        try:
            costs = cost_calculator.get_current_costs(period)

            # Filter by namespace if specified
            if namespace:
                costs.namespaces = [
                    ns for ns in costs.namespaces if ns.namespace == namespace
                ]
                costs.total_hourly = sum(ns.total_hourly for ns in costs.namespaces)
                costs.total_daily = costs.total_hourly * 24
                costs.total_monthly = costs.total_daily * 30

            REQUEST_COUNT.labels(endpoint="/costs", method="GET", status="200").inc()
            return CostResponse(
                success=True,
                data=costs,
                metadata={"namespace_filter": namespace}
            )
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="/costs", method="GET", status="500").inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/costs/summary", tags=["Costs"])
async def get_cost_summary():
    """Get simplified cost summary."""
    costs = cost_calculator.get_current_costs()
    return {
        "total_hourly": round(costs.total_hourly, 2),
        "total_daily": round(costs.total_daily, 2),
        "total_monthly": round(costs.total_monthly, 2),
        "currency": "USD",
        "namespace_count": len(costs.namespaces),
        "top_namespace": max(costs.namespaces, key=lambda x: x.total_monthly).namespace
        if costs.namespaces else None
    }


# =============================================================================
# Savings Endpoints
# =============================================================================

@app.get("/savings", response_model=SavingsResponse, tags=["Savings"])
async def get_savings(
    period: TimeRange = Query(TimeRange.MONTH, description="Time period"),
    namespace: Optional[str] = Query(None, description="Filter by namespace")
):
    """Get savings summary from optimizations."""
    with REQUEST_LATENCY.labels(endpoint="/savings").time():
        try:
            savings = savings_analyzer.get_savings_summary(period, namespace)

            REQUEST_COUNT.labels(endpoint="/savings", method="GET", status="200").inc()
            return SavingsResponse(
                success=True,
                data=savings,
                metadata={"namespace_filter": namespace}
            )
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="/savings", method="GET", status="500").inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/savings/potential", tags=["Savings"])
async def get_potential_savings():
    """Get potential savings opportunities."""
    opportunities = savings_analyzer.get_potential_savings()
    total_potential = sum(o.potential_savings_monthly for o in opportunities)

    return {
        "total_potential_monthly": round(total_potential, 2),
        "opportunities_count": len(opportunities),
        "opportunities": [o.model_dump() for o in opportunities]
    }


# =============================================================================
# Efficiency Endpoints
# =============================================================================

@app.get("/efficiency", response_model=EfficiencyResponse, tags=["Efficiency"])
async def get_efficiency(
    namespace: Optional[str] = Query(None, description="Filter by namespace")
):
    """Get resource efficiency analysis."""
    with REQUEST_LATENCY.labels(endpoint="/efficiency").time():
        try:
            efficiency = efficiency_analyzer.get_efficiency_summary(namespace)

            REQUEST_COUNT.labels(endpoint="/efficiency", method="GET", status="200").inc()
            return EfficiencyResponse(
                success=True,
                data=efficiency,
                metadata={"namespace_filter": namespace}
            )
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="/efficiency", method="GET", status="500").inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/efficiency/summary", tags=["Efficiency"])
async def get_efficiency_summary():
    """Get simplified efficiency summary."""
    efficiency = efficiency_analyzer.get_efficiency_summary()

    # Count workloads by status
    oversized = sum(1 for w in efficiency.workloads if w.is_oversized)
    undersized = sum(1 for w in efficiency.workloads if w.is_undersized)
    optimal = len(efficiency.workloads) - oversized - undersized

    return {
        "overall_efficiency": round(efficiency.overall_efficiency * 100, 1),
        "total_waste_monthly": round(efficiency.total_waste_monthly, 2),
        "workload_count": len(efficiency.workloads),
        "oversized_count": oversized,
        "undersized_count": undersized,
        "optimal_count": optimal,
        "top_opportunity": efficiency.top_opportunities[0].workload
            if efficiency.top_opportunities else None
    }


# =============================================================================
# Forecast Endpoints
# =============================================================================

@app.get("/forecast", response_model=ForecastResponse, tags=["Forecast"])
async def get_forecast(
    period: TimeRange = Query(TimeRange.MONTH, description="Forecast period"),
    namespace: Optional[str] = Query(None, description="Filter by namespace")
):
    """Get cost forecast."""
    with REQUEST_LATENCY.labels(endpoint="/forecast").time():
        try:
            # Get current costs for base
            costs = cost_calculator.get_current_costs()
            current_daily = costs.total_daily

            # Filter by namespace if specified
            if namespace:
                ns_costs = [ns for ns in costs.namespaces if ns.namespace == namespace]
                if ns_costs:
                    current_daily = ns_costs[0].total_daily
                else:
                    current_daily = 0

            forecast = cost_forecaster.forecast(period, current_daily, namespace)

            REQUEST_COUNT.labels(endpoint="/forecast", method="GET", status="200").inc()
            return ForecastResponse(
                success=True,
                data=forecast,
                metadata={"namespace_filter": namespace}
            )
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="/forecast", method="GET", status="500").inc()
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast/budget", tags=["Forecast"])
async def get_budget_status(
    monthly_budget: float = Query(500.0, description="Monthly budget in USD"),
    days_elapsed: int = Query(15, description="Days elapsed in current month")
):
    """Get budget status and projections."""
    costs = cost_calculator.get_current_costs()
    current_spend = costs.total_daily * days_elapsed

    status = cost_forecaster.get_budget_status(
        monthly_budget=monthly_budget,
        current_spend=current_spend,
        days_elapsed=days_elapsed
    )

    return {
        "monthly_budget": monthly_budget,
        "current_spend": round(current_spend, 2),
        "days_elapsed": days_elapsed,
        **{k: round(v, 2) if isinstance(v, float) else v for k, v in status.items()}
    }


# =============================================================================
# Metrics Endpoint
# =============================================================================

@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Prometheus metrics endpoint."""
    update_metrics()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        log_level=config.server.log_level
    )
