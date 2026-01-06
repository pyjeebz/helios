"""Base interface for all metrics sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MetricType(str, Enum):
    """Types of metrics."""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricSample:
    """A single metric sample from any source."""
    
    name: str
    value: float
    timestamp: datetime
    metric_type: MetricType = MetricType.GAUGE
    labels: dict[str, str] = field(default_factory=dict)
    source: str = ""  # Which source collected this
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "type": self.metric_type.value,
            "labels": self.labels,
            "source": self.source,
        }


@dataclass
class SourceConfig:
    """Configuration for a metrics source."""
    
    name: str
    type: str  # e.g., "prometheus", "datadog", "cloudwatch"
    enabled: bool = True
    interval: int = 15  # Collection interval in seconds
    
    # Connection settings
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    credentials: dict[str, Any] = field(default_factory=dict)
    
    # Query configuration
    queries: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    
    # Filters
    namespaces: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    
    # Extra options specific to the source type
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionResult:
    """Result from a collection operation."""
    
    source: str
    success: bool
    metrics: list[MetricSample] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsSource(ABC):
    """
    Abstract base class for all metrics sources.
    
    Implement this interface to add support for a new monitoring backend.
    
    Example:
        class DatadogSource(MetricsSource):
            source_type = "datadog"
            
            async def collect(self) -> CollectionResult:
                # Fetch metrics from Datadog API
                ...
    """
    
    # Override in subclass - used for registration
    source_type: str = "base"
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.name = config.name
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the source (connect, authenticate, etc.).
        
        Returns:
            True if initialization succeeded
        """
        pass
    
    @abstractmethod
    async def collect(self) -> CollectionResult:
        """
        Collect metrics from this source.
        
        Returns:
            CollectionResult with metrics or error
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the source is healthy and reachable.
        
        Returns:
            True if source is healthy
        """
        pass
    
    async def close(self):
        """Clean up resources. Override if needed."""
        pass
    
    def is_enabled(self) -> bool:
        """Check if this source is enabled."""
        return self.config.enabled
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """
        Return list of required credential fields for this source.
        
        Override to specify required credentials like api_key, secret, etc.
        """
        return []
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """
        Return default queries for this source type.
        
        Override to provide sensible defaults.
        """
        return []
