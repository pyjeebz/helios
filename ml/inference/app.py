"""
Helios Inference Service - FastAPI Application

Real-time ML inference API for infrastructure predictions,
anomaly detection, and scaling recommendations.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    # For now we just log and acknowledge; later this can enqueue into processing pipeline
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
