# Helios Inference Service
"""
Real-time ML inference API for infrastructure predictions,
anomaly detection, and scaling recommendations.
"""

__version__ = "0.1.0"


# Lazy imports to avoid circular dependencies
def get_app():
    """Get the FastAPI application."""
    from .app import app

    return app


__all__ = ["__version__", "get_app"]
