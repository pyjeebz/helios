"""Google Cloud Monitoring metrics source."""

import time
from datetime import datetime, timezone, timedelta
import logging

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("gcp_monitoring")
class GCPMonitoringSource(MetricsSource):
    """
    Collect metrics from Google Cloud Monitoring (Stackdriver).
    
    Config:
        credentials:
            project_id: str - GCP project ID
            credentials_file: str - Path to service account JSON (optional if using ADC)
        
        metrics: list[str] - Metric types to query
                            e.g., ["compute.googleapis.com/instance/cpu/utilization"]
        
    Config options:
        lookback_minutes: int - How far back to query (default: 5)
        alignment_period: int - Alignment period in seconds (default: 60)
    """
    
    source_type = "gcp_monitoring"
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._client = None
    
    async def initialize(self) -> bool:
        """Initialize GCP Monitoring client."""
        try:
            from google.cloud import monitoring_v3
            from google.oauth2 import service_account
            
            credentials = None
            creds_file = self.config.credentials.get("credentials_file")
            
            if creds_file:
                credentials = service_account.Credentials.from_service_account_file(creds_file)
            
            self._client = monitoring_v3.MetricServiceClient(credentials=credentials)
            self._project_id = self.config.credentials.get("project_id")
            self._initialized = True
            return True
            
        except ImportError:
            logger.error("GCP SDK required: pip install google-cloud-monitoring")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize GCP Monitoring: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check GCP Monitoring connectivity."""
        if not self._client or not self._project_id:
            return False
        
        try:
            project_name = f"projects/{self._project_id}"
            # Try to list metric descriptors
            request = {"name": project_name, "page_size": 1}
            list(self._client.list_metric_descriptors(request=request))
            return True
        except Exception:
            return False
    
    async def collect(self) -> CollectionResult:
        """Query GCP Monitoring metrics."""
        if not self._client:
            await self.initialize()
        
        start = time.time()
        metrics = []
        
        metric_types = self.config.metrics or self.get_default_queries()
        
        try:
            lookback = self.config.options.get("lookback_minutes", 5)
            alignment = self.config.options.get("alignment_period", 60)
            
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=lookback)
            
            for metric_type in metric_types:
                result = self._query_metric(metric_type, start_time, now, alignment)
                metrics.extend(result)
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            logger.error(f"Error collecting GCP Monitoring metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    def _query_metric(
        self,
        metric_type: str,
        start_time: datetime,
        end_time: datetime,
        alignment_period: int,
    ) -> list[MetricSample]:
        """Query a single GCP metric type."""
        metrics = []
        
        try:
            from google.cloud.monitoring_v3 import Aggregation, TimeInterval
            from google.protobuf.timestamp_pb2 import Timestamp
            
            project_name = f"projects/{self._project_id}"
            
            # Build time interval
            start_pb = Timestamp()
            start_pb.FromDatetime(start_time)
            end_pb = Timestamp()
            end_pb.FromDatetime(end_time)
            
            interval = TimeInterval(
                start_time=start_pb,
                end_time=end_pb,
            )
            
            # Choose aligner based on metric type
            # Cumulative metrics (counters) need ALIGN_RATE, gauge metrics use ALIGN_MEAN
            aligner = Aggregation.Aligner.ALIGN_RATE
            if any(gauge in metric_type for gauge in ['utilization', 'memory/used', 'limit_utilization']):
                aligner = Aggregation.Aligner.ALIGN_MEAN
            
            # Build aggregation
            aggregation = Aggregation(
                alignment_period={"seconds": alignment_period},
                per_series_aligner=aligner,
            )
            
            results = self._client.list_time_series(
                request={
                    "name": project_name,
                    "filter": f'metric.type = "{metric_type}"',
                    "interval": interval,
                    "view": "FULL",
                    "aggregation": aggregation,
                }
            )
            
            for ts in results:
                # Build labels from metric and resource labels
                labels = dict(ts.metric.labels)
                labels.update({f"resource_{k}": v for k, v in ts.resource.labels.items()})
                labels["resource_type"] = ts.resource.type
                
                # Merge static labels from config (e.g. deployment ID)
                if self.config.labels:
                    labels.update(self.config.labels)
                
                # Get latest point
                points = list(ts.points)
                if points:
                    point = points[0]  # Most recent
                    
                    # Extract value based on type
                    value = self._extract_value(point.value)
                    
                    normalized = self._normalize_metric_name(metric_type)
                    
                    # Handle timestamp - proto-plus returns DatetimeWithNanoseconds which is a datetime subclass
                    ts_value = point.interval.end_time
                    if hasattr(ts_value, 'ToDatetime'):
                        ts_value = ts_value.ToDatetime().replace(tzinfo=timezone.utc)
                    elif not ts_value.tzinfo:
                        ts_value = ts_value.replace(tzinfo=timezone.utc)
                    
                    metrics.append(MetricSample(
                        name=normalized,
                        value=value,
                        timestamp=ts_value,
                        metric_type=MetricType.GAUGE,
                        labels=labels,
                        source=self.name,
                    ))
                    
        except Exception as e:
            logger.warning(f"Failed to query GCP metric '{metric_type}': {e}")
        
        return metrics
    
    def _extract_value(self, typed_value) -> float:
        """Extract numeric value from GCP TypedValue."""
        # The google-cloud-monitoring proto-plus wrapper uses simple attribute access
        # Try each value type in order of likelihood
        try:
            if typed_value.double_value:
                return typed_value.double_value
        except (AttributeError, TypeError):
            pass
        
        try:
            if typed_value.int64_value:
                return float(typed_value.int64_value)
        except (AttributeError, TypeError):
            pass
        
        try:
            if typed_value.bool_value is not None:
                return 1.0 if typed_value.bool_value else 0.0
        except (AttributeError, TypeError):
            pass
        
        try:
            if typed_value.distribution_value:
                return typed_value.distribution_value.mean
        except (AttributeError, TypeError):
            pass
        
        return 0.0
    
    def _normalize_metric_name(self, metric_type: str) -> str:
        """Convert GCP metric type to standard format."""
        # compute.googleapis.com/instance/cpu/utilization -> instance_cpu_utilization
        parts = metric_type.split("/")
        if len(parts) > 1:
            # Remove the domain part
            parts = parts[1:]
        return "_".join(parts).replace("-", "_")
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """GCP requires project ID, credentials optional if using ADC."""
        return ["project_id"]
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """Default GCP Monitoring metrics."""
        return [
            "compute.googleapis.com/instance/cpu/utilization",
            "compute.googleapis.com/instance/memory/balloon/ram_used",
            "compute.googleapis.com/instance/disk/read_bytes_count",
            "compute.googleapis.com/instance/disk/write_bytes_count",
            "compute.googleapis.com/instance/network/received_bytes_count",
            "compute.googleapis.com/instance/network/sent_bytes_count",
            # Kubernetes Engine
            "kubernetes.io/container/cpu/core_usage_time",
            "kubernetes.io/container/memory/used_bytes",
        ]
