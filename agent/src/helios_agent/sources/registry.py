"""Source registry - manages available metrics source plugins."""

from typing import Type, Optional
import logging

from .base import MetricsSource, SourceConfig

logger = logging.getLogger(__name__)


class SourceRegistry:
    """
    Registry for metrics source plugins.
    
    Sources register themselves here and can be instantiated by type name.
    """
    
    _sources: dict[str, Type[MetricsSource]] = {}
    
    @classmethod
    def register(cls, source_type: str, source_class: Type[MetricsSource]):
        """Register a metrics source class."""
        cls._sources[source_type] = source_class
        logger.debug(f"Registered metrics source: {source_type}")
    
    @classmethod
    def get(cls, source_type: str) -> Optional[Type[MetricsSource]]:
        """Get a source class by type name."""
        return cls._sources.get(source_type)
    
    @classmethod
    def create(cls, config: SourceConfig) -> Optional[MetricsSource]:
        """Create a source instance from config."""
        source_class = cls._sources.get(config.type)
        if source_class is None:
            logger.error(f"Unknown source type: {config.type}")
            return None
        return source_class(config)
    
    @classmethod
    def list_types(cls) -> list[str]:
        """List all registered source types."""
        return list(cls._sources.keys())
    
    @classmethod
    def is_registered(cls, source_type: str) -> bool:
        """Check if a source type is registered."""
        return source_type in cls._sources


def register_source(source_type: str):
    """
    Decorator to register a metrics source class.
    
    Usage:
        @register_source("datadog")
        class DatadogSource(MetricsSource):
            ...
    """
    def decorator(cls: Type[MetricsSource]):
        cls.source_type = source_type
        SourceRegistry.register(source_type, cls)
        return cls
    return decorator


def get_source(source_type: str) -> Optional[Type[MetricsSource]]:
    """Get a source class by type name."""
    return SourceRegistry.get(source_type)


def list_sources() -> list[str]:
    """List all registered source types."""
    return SourceRegistry.list_types()


# Auto-register built-in sources when this module is imported
def _register_builtin_sources():
    """Import and register all built-in source plugins."""
    try:
        from . import prometheus
    except ImportError as e:
        logger.debug(f"Prometheus source not available: {e}")
    
    try:
        from . import system
    except ImportError as e:
        logger.debug(f"System source not available: {e}")
    
    try:
        from . import datadog
    except ImportError as e:
        logger.debug(f"Datadog source not available: {e}")
    
    try:
        from . import cloudwatch
    except ImportError as e:
        logger.debug(f"CloudWatch source not available: {e}")
    
    try:
        from . import azure_monitor
    except ImportError as e:
        logger.debug(f"Azure Monitor source not available: {e}")
    
    try:
        from . import gcp_monitoring
    except ImportError as e:
        logger.debug(f"GCP Monitoring source not available: {e}")


_register_builtin_sources()
