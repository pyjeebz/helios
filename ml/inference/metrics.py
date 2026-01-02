"""Prometheus metrics exporter for Helios inference service."""

import time
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY,
)

from .config import config


# =============================================================================
# Service Info
# =============================================================================

SERVICE_INFO = Info(
    f'{config.metrics.prefix}_service',
    'Service information',
    registry=REGISTRY,
)
SERVICE_INFO.info({
    'version': '0.1.0',
    'service': 'helios-inference',
})


# =============================================================================
# Request Metrics
# =============================================================================

REQUEST_COUNT = Counter(
    f'{config.metrics.prefix}_requests_total',
    'Total number of requests',
    ['endpoint', 'method', 'status'],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    f'{config.metrics.prefix}_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint', 'method'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

REQUEST_IN_PROGRESS = Gauge(
    f'{config.metrics.prefix}_requests_in_progress',
    'Number of requests currently being processed',
    ['endpoint'],
    registry=REGISTRY,
)


# =============================================================================
# Prediction Metrics
# =============================================================================

PREDICTIONS_TOTAL = Counter(
    f'{config.metrics.prefix}_predictions_total',
    'Total number of predictions made',
    ['model', 'metric'],
    registry=REGISTRY,
)

PREDICTION_LATENCY = Histogram(
    f'{config.metrics.prefix}_prediction_latency_seconds',
    'Prediction generation latency in seconds',
    ['model'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=REGISTRY,
)

PREDICTION_CACHE_HITS = Counter(
    f'{config.metrics.prefix}_prediction_cache_hits_total',
    'Number of prediction cache hits',
    registry=REGISTRY,
)

PREDICTION_CACHE_MISSES = Counter(
    f'{config.metrics.prefix}_prediction_cache_misses_total',
    'Number of prediction cache misses',
    registry=REGISTRY,
)


# =============================================================================
# Anomaly Detection Metrics
# =============================================================================

ANOMALIES_DETECTED = Counter(
    f'{config.metrics.prefix}_anomalies_detected_total',
    'Total number of anomalies detected',
    ['metric', 'severity'],
    registry=REGISTRY,
)

ANOMALY_DETECTION_LATENCY = Histogram(
    f'{config.metrics.prefix}_anomaly_detection_latency_seconds',
    'Anomaly detection latency in seconds',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=REGISTRY,
)

DATA_POINTS_ANALYZED = Counter(
    f'{config.metrics.prefix}_data_points_analyzed_total',
    'Total number of data points analyzed for anomalies',
    registry=REGISTRY,
)


# =============================================================================
# Recommendation Metrics
# =============================================================================

RECOMMENDATIONS_TOTAL = Counter(
    f'{config.metrics.prefix}_recommendations_total',
    'Total number of recommendations generated',
    ['workload', 'action'],
    registry=REGISTRY,
)

RECOMMENDATION_LATENCY = Histogram(
    f'{config.metrics.prefix}_recommendation_latency_seconds',
    'Recommendation generation latency in seconds',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=REGISTRY,
)

RECOMMENDED_REPLICAS = Gauge(
    f'{config.metrics.prefix}_recommended_replicas',
    'Currently recommended replica count',
    ['workload', 'namespace'],
    registry=REGISTRY,
)


# =============================================================================
# Model Metrics
# =============================================================================

MODELS_LOADED = Gauge(
    f'{config.metrics.prefix}_models_loaded',
    'Number of models currently loaded',
    registry=REGISTRY,
)

MODEL_LOAD_LATENCY = Histogram(
    f'{config.metrics.prefix}_model_load_latency_seconds',
    'Model loading latency in seconds',
    ['model'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=REGISTRY,
)


# =============================================================================
# Health Metrics
# =============================================================================

SERVICE_UP = Gauge(
    f'{config.metrics.prefix}_up',
    'Whether the service is up (1) or down (0)',
    registry=REGISTRY,
)

SERVICE_READY = Gauge(
    f'{config.metrics.prefix}_ready',
    'Whether the service is ready to serve traffic',
    registry=REGISTRY,
)

UPTIME_SECONDS = Gauge(
    f'{config.metrics.prefix}_uptime_seconds',
    'Service uptime in seconds',
    registry=REGISTRY,
)


# =============================================================================
# Helper Functions
# =============================================================================

_start_time: Optional[float] = None


def init_metrics():
    """Initialize metrics on service startup."""
    global _start_time
    _start_time = time.time()
    SERVICE_UP.set(1)
    SERVICE_READY.set(0)


def set_ready(ready: bool = True):
    """Set service readiness state."""
    SERVICE_READY.set(1 if ready else 0)


def update_uptime():
    """Update uptime gauge."""
    if _start_time:
        UPTIME_SECONDS.set(time.time() - _start_time)


def get_uptime() -> float:
    """Get service uptime in seconds."""
    if _start_time:
        return time.time() - _start_time
    return 0.0


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    update_uptime()
    return generate_latest(REGISTRY)


def get_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST


# =============================================================================
# Metric Recording Helpers
# =============================================================================

def record_request(endpoint: str, method: str, status: int, latency: float):
    """Record an HTTP request."""
    REQUEST_COUNT.labels(endpoint=endpoint, method=method, status=str(status)).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(latency)


def record_prediction(model: str, metric: str, latency: float, cache_hit: bool):
    """Record a prediction."""
    PREDICTIONS_TOTAL.labels(model=model, metric=metric).inc()
    PREDICTION_LATENCY.labels(model=model).observe(latency)
    if cache_hit:
        PREDICTION_CACHE_HITS.inc()
    else:
        PREDICTION_CACHE_MISSES.inc()


def record_anomaly(metric: str, severity: str):
    """Record a detected anomaly."""
    ANOMALIES_DETECTED.labels(metric=metric, severity=severity).inc()


def record_detection(data_points: int, latency: float):
    """Record an anomaly detection run."""
    DATA_POINTS_ANALYZED.inc(data_points)
    ANOMALY_DETECTION_LATENCY.observe(latency)


def record_recommendation(workload: str, action: str, latency: float):
    """Record a recommendation."""
    RECOMMENDATIONS_TOTAL.labels(workload=workload, action=action).inc()
    RECOMMENDATION_LATENCY.observe(latency)


def set_recommended_replicas(workload: str, namespace: str, replicas: int):
    """Set recommended replicas gauge."""
    RECOMMENDED_REPLICAS.labels(workload=workload, namespace=namespace).set(replicas)


def record_model_load(model: str, latency: float):
    """Record model loading."""
    MODEL_LOAD_LATENCY.labels(model=model).observe(latency)


def set_models_loaded(count: int):
    """Set number of loaded models."""
    MODELS_LOADED.set(count)
