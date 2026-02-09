"""
Helios Inference Service - FastAPI Application

Real-time ML inference API for infrastructure predictions,
anomaly detection, and scaling recommendations.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Version
__version__ = "0.1.0"

from .anomaly_detector import anomaly_detector_service
from .config import config
from .metrics import (
    get_content_type,
    get_metrics,
    get_uptime,
    init_metrics,
    record_anomaly,
    record_detection,
    record_prediction,
    record_recommendation,
    record_request,
    set_models_loaded,
    set_ready,
    set_recommended_replicas,
)
from .model_manager import model_manager
from .models import (
    AnomalyRequest,
    AnomalyResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ErrorResponse,
    HealthStatus,
    ModelInfo,
    PredictionRequest,
    PredictionResponse,
    ReadyStatus,
    RecommendationRequest,
    RecommendationResponse,
)
from .predictor import predictor_service
from .recommender import recommender_service
from .db import deployment_store, metrics_store, AgentRegister

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.server.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Helios Inference Service...")
    init_metrics()

    # Load models
    start = time.time()
    results = model_manager.load_models()
    load_time = time.time() - start

    loaded_count = sum(1 for v in results.values() if v)
    set_models_loaded(loaded_count)
    logger.info(f"Loaded {loaded_count} models in {load_time:.2f}s")

    if loaded_count > 0:
        set_ready(True)
        logger.info("Service is ready")
    else:
        logger.warning("No models loaded, service may not function correctly")

    yield

    # Shutdown
    logger.info("Shutting down Helios Inference Service...")
    set_ready(False)


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Helios Inference Service",
    description=(
        "Real-time ML inference API for predictive infrastructure intelligence. "
        "Provides time-series forecasting, anomaly detection, and scaling recommendations."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Middleware
# =============================================================================


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Validate API key if authentication is enabled."""
    # Skip if auth is disabled
    if not config.auth.enabled:
        return await call_next(request)
    
    # Skip exempt paths (health, metrics, docs)
    if request.url.path in config.auth.exempt_paths:
        return await call_next(request)
    
    # Check for API key
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not api_key:
        api_key = request.headers.get("X-API-Key", "")
    
    if api_key != config.auth.api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"}
        )
    
    return await call_next(request)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record request metrics."""
    start_time = time.time()

    response = await call_next(request)

    # Record metrics (skip metrics endpoint to avoid recursion)
    if request.url.path != "/metrics":
        latency = time.time() - start_time
        record_request(
            endpoint=request.url.path,
            method=request.method,
            status=response.status_code,
            latency=latency,
        )

    return response


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get(
    "/health",
    response_model=HealthStatus,
    tags=["Health"],
    summary="Health check",
)
async def health_check() -> HealthStatus:
    """Check service health status."""
    return HealthStatus(
        status="healthy",
        version=__version__,
        models_loaded=model_manager.model_count,
        uptime_seconds=get_uptime(),
    )


@app.get(
    "/ready",
    response_model=ReadyStatus,
    tags=["Health"],
    summary="Readiness check",
)
async def readiness_check() -> ReadyStatus:
    """Check if service is ready to receive traffic."""
    models_ready = model_manager.is_loaded

    return ReadyStatus(
        ready=models_ready,
        models_ready=models_ready,
        details={
            "baseline": model_manager.get_model_info("baseline") is not None,
            "prophet": model_manager.get_model_info("prophet") is not None,
            "xgboost": model_manager.get_model_info("xgboost") is not None,
        },
    )


@app.get(
    "/models",
    response_model=list[ModelInfo],
    tags=["Health"],
    summary="List loaded models",
)
async def list_models() -> list[ModelInfo]:
    """List all loaded models and their metadata."""
    return model_manager.list_models()


# =============================================================================
# Prediction Endpoints
# =============================================================================


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Prediction"],
    summary="Generate predictions",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Generate time-series predictions for a metric.

    Forecasts future values based on historical patterns using
    the specified model (baseline, prophet, or xgboost).
    """
    if not model_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Models not loaded, service not ready")

    start = time.time()

    try:
        response = predictor_service.predict(request)

        # Record metrics
        latency = time.time() - start
        record_prediction(
            model=request.model.value,
            metric=request.metric.value,
            latency=latency,
            cache_hit=response.metadata.get("cache_hit", False),
        )

        return response

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    tags=["Prediction"],
    summary="Batch predictions",
)
async def batch_predict(request: BatchPredictionRequest) -> BatchPredictionResponse:
    """Generate predictions for multiple metrics at once."""
    if not model_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Models not loaded, service not ready")

    predictions = {}

    for metric in request.metrics:
        single_request = PredictionRequest(
            metric=metric,
            periods=request.periods,
            model=request.model,
        )
        predictions[metric.value] = predictor_service.predict(single_request)

    return BatchPredictionResponse(predictions=predictions)


# =============================================================================
# Anomaly Detection Endpoints
# =============================================================================


@app.post(
    "/detect",
    response_model=AnomalyResponse,
    tags=["Anomaly Detection"],
    summary="Detect anomalies",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def detect_anomalies(request: AnomalyRequest) -> AnomalyResponse:
    """Detect anomalies in provided metrics data.

    Analyzes the provided data points and identifies values
    that deviate significantly from expected patterns.
    """
    start = time.time()

    try:
        response = anomaly_detector_service.detect(request)

        # Record metrics
        latency = time.time() - start
        record_detection(response.data_points_analyzed, latency)

        for anomaly in response.anomalies:
            record_anomaly(anomaly.metric, anomaly.severity.value)

        return response

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Recommendation Endpoints
# =============================================================================


@app.post(
    "/recommend",
    response_model=RecommendationResponse,
    tags=["Recommendations"],
    summary="Get scaling recommendations",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """Generate scaling recommendations for a workload.

    Analyzes current state and predictions to provide
    proactive scaling recommendations.
    """
    start = time.time()

    try:
        response = recommender_service.recommend(request)

        # Record metrics
        latency = time.time() - start
        for rec in response.recommendations:
            for action in rec.actions:
                record_recommendation(
                    workload=request.workload,
                    action=action.action.value,
                    latency=latency,
                )

                if action.target_replicas is not None:
                    set_recommended_replicas(
                        workload=request.workload,
                        namespace=request.namespace,
                        replicas=action.target_replicas,
                    )

        return response

    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Metrics Endpoint
# =============================================================================


@app.get(
    "/metrics",
    tags=["Observability"],
    summary="Prometheus metrics",
    response_class=Response,
)
async def prometheus_metrics():
    """Expose Prometheus metrics for scraping."""
    return Response(
        content=get_metrics(),
        media_type=get_content_type(),
    )


# =============================================================================
# Ingestion Endpoint (from helios-agent)
# =============================================================================


@app.post(
    "/api/v1/ingest",
    tags=["Ingest"],
    summary="Ingest metrics from agents",
)
async def ingest_metrics(request: Request) -> dict:
    """Receive metrics from helios-agent and acknowledge receipt.

    The agent posts a JSON payload like:
    {
      "metrics": [ { ...metric sample... }, ... ],
      "agent_version": "0.1.0",
      "sent_at": "..."
    }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    metrics = payload.get("metrics") if isinstance(payload, dict) else None
    if not isinstance(metrics, list):
        raise HTTPException(status_code=400, detail="Missing or invalid 'metrics' field")

    # Store metrics in time-series store
    metrics_store.add_metrics(metrics)
    
    # Auto-register agent based on metric labels
    if metrics:
        first_metric = metrics[0]
        labels = first_metric.get("labels", {})
        deployment_id = labels.get("deployment")
        hostname = labels.get("host") or labels.get("hostname", "unknown")
        
        if deployment_id:
            try:
                import platform as plat
                agent_data = AgentRegister(
                    hostname=hostname,
                    platform=labels.get("platform", plat.system()),
                    agent_version=payload.get("agent_version", "unknown"),
                    metrics=list(set(m.get("name", "") for m in metrics)),
                    agent_id=f"{hostname[:8]}-{deployment_id[:4]}"
                )
                deployment_store.register_agent(deployment_id, agent_data)
            except Exception as e:
                logger.warning(f"Failed to auto-register agent: {e}")

    received = len(metrics)
    logger.info(f"Ingest received {received} metrics from agent")

    # Optionally record an internal stat (if metric helpers are available)
    try:
        record_request(endpoint="/api/v1/ingest", method="POST", status=200, latency=0)
    except Exception:
        # ignore if metrics helper isn't available or fails
        pass

    return {"received": received}


# =============================================================================
# Metrics API (for Web UI)
# =============================================================================


@app.get(
    "/api/metrics",
    tags=["Metrics API"],
    summary="Get available metric names",
)
async def get_metric_names(deployment_id: Optional[str] = None) -> dict:
    """Get list of available metric names."""
    names = metrics_store.get_metric_names(deployment_id)
    return {"metrics": names}


@app.get(
    "/api/metrics/{metric_name}",
    tags=["Metrics API"],
    summary="Get metric time-series data",
)
async def get_metric_data(
    metric_name: str,
    deployment_id: Optional[str] = None,
    hours: int = 1,
    limit: int = 100
) -> dict:
    """Get time-series data for a specific metric."""
    data = metrics_store.get_metrics(metric_name, deployment_id, hours, limit)
    latest = metrics_store.get_latest(metric_name, deployment_id)
    return {
        "metric": metric_name,
        "data": data,
        "latest": latest,
        "count": len(data)
    }


@app.get(
    "/api/metrics/{metric_name}/latest",
    tags=["Metrics API"],
    summary="Get latest metric value",
)
async def get_metric_latest(
    metric_name: str,
    deployment_id: Optional[str] = None
) -> dict:
    """Get the latest value for a metric."""
    latest = metrics_store.get_latest(metric_name, deployment_id)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No data for metric '{metric_name}'")
    return latest


# =============================================================================
# Info Endpoints
# =============================================================================


@app.get(
    "/",
    tags=["Info"],
    summary="Service info",
)
async def root() -> dict[str, Any]:
    """Get service information."""
    return {
        "service": "helios-inference",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "metrics": "/metrics",
    }


@app.get(
    "/stats",
    tags=["Info"],
    summary="Service statistics",
)
async def get_stats() -> dict[str, Any]:
    """Get service statistics."""
    return {
        "uptime_seconds": get_uptime(),
        "models": model_manager.get_status(),
        "predictor": predictor_service.get_stats(),
        "anomaly_detector": anomaly_detector_service.get_stats(),
        "recommender": recommender_service.get_stats(),
    }


# =============================================================================
# Deployment & Agent Endpoints (Web UI)
# =============================================================================

from .db import (
    deployment_store,
    Deployment,
    DeploymentCreate,
    DeploymentUpdate,
    Agent,
    AgentRegister,
    AgentHeartbeat,
)


@app.get(
    "/api/deployments",
    response_model=list[Deployment],
    tags=["Deployments"],
    summary="List all deployments",
)
async def list_deployments() -> list[Deployment]:
    """Get all deployments."""
    return deployment_store.list_deployments()


@app.post(
    "/api/deployments",
    response_model=Deployment,
    tags=["Deployments"],
    summary="Create a deployment",
)
async def create_deployment(data: DeploymentCreate) -> Deployment:
    """Create a new deployment."""
    try:
        return deployment_store.create_deployment(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/deployments/{deployment_id}",
    response_model=Deployment,
    tags=["Deployments"],
    summary="Get a deployment",
)
async def get_deployment(deployment_id: str) -> Deployment:
    """Get a deployment by ID."""
    deployment = deployment_store.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


@app.patch(
    "/api/deployments/{deployment_id}",
    response_model=Deployment,
    tags=["Deployments"],
    summary="Update a deployment",
)
async def update_deployment(deployment_id: str, data: DeploymentUpdate) -> Deployment:
    """Update a deployment."""
    try:
        deployment = deployment_store.update_deployment(deployment_id, data)
        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found")
        return deployment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete(
    "/api/deployments/{deployment_id}",
    tags=["Deployments"],
    summary="Delete a deployment",
)
async def delete_deployment(deployment_id: str) -> dict[str, str]:
    """Delete a deployment and its agents."""
    if not deployment_store.delete_deployment(deployment_id):
        raise HTTPException(status_code=404, detail="Deployment not found")
    return {"status": "deleted"}


@app.get(
    "/api/deployments/{deployment_id}/metrics",
    response_model=list[str],
    tags=["Deployments"],
    summary="Get available metrics for a deployment",
)
async def get_deployment_metrics(deployment_id: str) -> list[str]:
    """Get unique metrics available in a deployment."""
    if not deployment_store.get_deployment(deployment_id):
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment_store.get_deployment_metrics(deployment_id)


@app.get(
    "/api/deployments/{deployment_id}/agents",
    response_model=list[Agent],
    tags=["Agents"],
    summary="List agents in a deployment",
)
async def list_deployment_agents(deployment_id: str) -> list[Agent]:
    """Get all agents in a deployment."""
    if not deployment_store.get_deployment(deployment_id):
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment_store.list_agents(deployment_id)


@app.post(
    "/api/deployments/{deployment_id}/agents/register",
    response_model=Agent,
    tags=["Agents"],
    summary="Register an agent",
)
async def register_agent(deployment_id: str, data: AgentRegister) -> Agent:
    """Register a new agent or update existing."""
    try:
        return deployment_store.register_agent(deployment_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/agents/{agent_id}",
    response_model=Agent,
    tags=["Agents"],
    summary="Get an agent",
)
async def get_agent(agent_id: str) -> Agent:
    """Get an agent by ID."""
    agent = deployment_store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post(
    "/api/agents/{agent_id}/heartbeat",
    response_model=Agent,
    tags=["Agents"],
    summary="Agent heartbeat",
)
async def agent_heartbeat(agent_id: str, data: AgentHeartbeat) -> Agent:
    """Update agent heartbeat."""
    agent = deployment_store.heartbeat_agent(agent_id, data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete(
    "/api/agents/{agent_id}",
    tags=["Agents"],
    summary="Delete an agent",
)
async def delete_agent(agent_id: str) -> dict[str, str]:
    """Delete an agent."""
    if not deployment_store.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}


# =============================================================================
# Static Files (Web UI)
# =============================================================================

# Serve static files if they exist (production build)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
    
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve the Vue.js SPA for all non-API routes."""
        # Don't serve for API routes
        if full_path.startswith("api/") or full_path in ["docs", "redoc", "openapi.json", "health", "ready", "metrics"]:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Try to serve the requested file
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Fallback to index.html for SPA routing
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Not found")


# =============================================================================
# Error Handlers
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the service."""
    import uvicorn

    uvicorn.run(
        "ml.inference.app:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        reload=config.server.reload,
        log_level=config.server.log_level,
    )


if __name__ == "__main__":
    main()
