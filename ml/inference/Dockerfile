# Helios Inference Service
# Multi-stage build for smaller image size
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# Production stage
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Helios Inference Service"
LABEL org.opencontainers.image.description="ML-powered resource forecasting and anomaly detection"
LABEL org.opencontainers.image.source="https://github.com/pyjeebz/helios"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# Install runtime dependencies only
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash helios && \
    mkdir -p /app/models && \
    chown -R helios:helios /app

# Copy application code
# Context is ./ml, so paths are relative to ml/
COPY --chown=helios:helios inference/ ./inference/
COPY --chown=helios:helios models/ ./models/

# Switch to non-root user
USER helios

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV MODELS_DIR=/app/models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "inference.app:app", "--host", "0.0.0.0", "--port", "8000"]
