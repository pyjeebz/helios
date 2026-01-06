"""Azure Monitor metrics source."""

import time
from datetime import datetime, timezone, timedelta
import logging

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("azure_monitor")
class AzureMonitorSource(MetricsSource):
    """
    Collect metrics from Azure Monitor.
    
    Config:
        credentials:
            tenant_id: str - Azure AD tenant ID
            client_id: str - Service principal client ID
            client_secret: str - Service principal secret
            subscription_id: str - Azure subscription ID
        
        metrics: list[str] - Metric specs in format "ResourceType/MetricName"
                            e.g., ["Microsoft.Compute/virtualMachines/Percentage CPU"]
        
    Config options:
        resource_group: str - Filter by resource group
        timespan: str - ISO8601 duration (default: PT5M)
        interval: str - Aggregation interval (default: PT1M)
    """
    
    source_type = "azure_monitor"
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._credential = None
        self._client = None
    
    async def initialize(self) -> bool:
        """Initialize Azure Monitor client."""
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
            
            self._credential = ClientSecretCredential(
                tenant_id=self.config.credentials.get("tenant_id"),
                client_id=self.config.credentials.get("client_id"),
                client_secret=self.config.credentials.get("client_secret"),
            )
            
            self._client = MonitorManagementClient(
                credential=self._credential,
                subscription_id=self.config.credentials.get("subscription_id"),
            )
            
            self._initialized = True
            return True
            
        except ImportError:
            logger.error("Azure SDK required: pip install azure-identity azure-mgmt-monitor")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Azure Monitor: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check Azure Monitor connectivity."""
        if not self._client:
            return False
        
        try:
            # Try to list metric definitions for a known resource type
            list(self._client.metric_definitions.list(
                resource_uri=f"/subscriptions/{self.config.credentials.get('subscription_id')}",
            ))
            return True
        except Exception:
            return False
    
    async def collect(self) -> CollectionResult:
        """Query Azure Monitor metrics."""
        if not self._client:
            await self.initialize()
        
        start = time.time()
        metrics = []
        
        metric_specs = self.config.metrics or self.get_default_queries()
        
        try:
            timespan = self.config.options.get("timespan", "PT5M")
            interval = self.config.options.get("interval", "PT1M")
            
            for spec in metric_specs:
                result = self._query_metric(spec, timespan, interval)
                metrics.extend(result)
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            logger.error(f"Error collecting Azure Monitor metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    def _query_metric(
        self,
        spec: str,
        timespan: str,
        interval: str,
    ) -> list[MetricSample]:
        """Query a single Azure Monitor metric."""
        metrics = []
        
        # Parse spec: "ResourceUri/MetricName" or simplified format
        # For simplicity, we'll query all resources of a type
        
        try:
            # This is a simplified implementation
            # In production, you'd iterate over resources
            response = self._client.metrics.list(
                resource_uri=spec,
                timespan=timespan,
                interval=interval,
                metricnames=None,  # All metrics
                aggregation="Average",
            )
            
            for metric in response.value:
                for ts in metric.timeseries:
                    for data in ts.data:
                        if data.average is not None:
                            # Build labels from dimensions
                            labels = {}
                            if ts.metadatavalues:
                                for mv in ts.metadatavalues:
                                    labels[mv.name.value] = mv.value
                            
                            normalized = self._normalize_metric_name(metric.name.value)
                            
                            metrics.append(MetricSample(
                                name=normalized,
                                value=data.average,
                                timestamp=data.time_stamp.replace(tzinfo=timezone.utc),
                                metric_type=MetricType.GAUGE,
                                labels=labels,
                                source=self.name,
                            ))
                            break  # Take first (most recent) value
                            
        except Exception as e:
            logger.warning(f"Failed to query Azure metric '{spec}': {e}")
        
        return metrics
    
    def _normalize_metric_name(self, name: str) -> str:
        """Convert Azure metric name to standard format."""
        # Percentage CPU -> cpu_percentage
        import re
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        name = name.replace(" ", "_").replace("%", "pct")
        return name
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """Azure requires service principal credentials."""
        return ["tenant_id", "client_id", "client_secret", "subscription_id"]
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """Default Azure metrics."""
        return [
            # These would be resource URIs in production
            "Percentage CPU",
            "Available Memory Bytes",
            "Disk Read Bytes",
            "Disk Write Bytes",
            "Network In Total",
            "Network Out Total",
        ]
