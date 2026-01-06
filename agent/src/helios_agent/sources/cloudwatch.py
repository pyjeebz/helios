"""AWS CloudWatch metrics source."""

import time
from datetime import datetime, timezone, timedelta
import logging

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("cloudwatch")
class CloudWatchSource(MetricsSource):
    """
    Collect metrics from AWS CloudWatch.
    
    Config:
        credentials:
            aws_access_key_id: str
            aws_secret_access_key: str
            region: str - AWS region (default: us-east-1)
        
        metrics: list[str] - Metric specs in format "Namespace/MetricName"
                            e.g., ["AWS/EC2/CPUUtilization", "AWS/RDS/DatabaseConnections"]
        
    Config options:
        period: int - CloudWatch period in seconds (default: 300)
        lookback_minutes: int - How far back to query (default: 10)
        dimensions: dict - Dimensions to filter by
    """
    
    source_type = "cloudwatch"
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._client = None
    
    async def initialize(self) -> bool:
        """Initialize AWS CloudWatch client."""
        try:
            import boto3
            
            region = self.config.credentials.get("region", "us-east-1")
            
            self._client = boto3.client(
                "cloudwatch",
                region_name=region,
                aws_access_key_id=self.config.credentials.get("aws_access_key_id"),
                aws_secret_access_key=self.config.credentials.get("aws_secret_access_key"),
            )
            self._initialized = True
            return True
            
        except ImportError:
            logger.error("boto3 is required for CloudWatch source: pip install boto3")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check CloudWatch connectivity."""
        if not self._client:
            return False
        
        try:
            self._client.list_metrics(Limit=1)
            return True
        except Exception:
            return False
    
    async def collect(self) -> CollectionResult:
        """Query CloudWatch metrics."""
        if not self._client:
            await self.initialize()
        
        start = time.time()
        metrics = []
        
        metric_specs = self.config.metrics or self.get_default_queries()
        
        try:
            lookback = self.config.options.get("lookback_minutes", 10)
            period = self.config.options.get("period", 300)
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=lookback)
            
            for spec in metric_specs:
                result = self._query_metric(spec, start_time, now, period)
                metrics.extend(result)
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            logger.error(f"Error collecting CloudWatch metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    def _query_metric(
        self,
        spec: str,
        start_time: datetime,
        end_time: datetime,
        period: int,
    ) -> list[MetricSample]:
        """Query a single CloudWatch metric."""
        metrics = []
        
        # Parse spec: "Namespace/MetricName" or "Namespace/MetricName:Dim=Val"
        parts = spec.split("/")
        if len(parts) < 2:
            logger.warning(f"Invalid metric spec: {spec}")
            return metrics
        
        namespace = parts[0]
        metric_part = "/".join(parts[1:])
        
        # Parse dimensions
        dimensions = []
        if ":" in metric_part:
            metric_name, dim_str = metric_part.split(":", 1)
            for dim in dim_str.split(","):
                if "=" in dim:
                    name, value = dim.split("=", 1)
                    dimensions.append({"Name": name, "Value": value})
        else:
            metric_name = metric_part
        
        # Add config dimensions
        for name, value in self.config.options.get("dimensions", {}).items():
            dimensions.append({"Name": name, "Value": value})
        
        try:
            response = self._client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average"],
            )
            
            datapoints = response.get("Datapoints", [])
            if datapoints:
                # Sort by timestamp and take the latest
                datapoints.sort(key=lambda x: x["Timestamp"])
                latest = datapoints[-1]
                
                # Build labels from dimensions
                labels = {d["Name"]: d["Value"] for d in dimensions}
                labels["namespace"] = namespace
                
                # Normalize metric name
                normalized = self._normalize_metric_name(namespace, metric_name)
                
                metrics.append(MetricSample(
                    name=normalized,
                    value=latest.get("Average", 0.0),
                    timestamp=latest["Timestamp"].replace(tzinfo=timezone.utc),
                    metric_type=MetricType.GAUGE,
                    labels=labels,
                    source=self.name,
                ))
                
        except Exception as e:
            logger.warning(f"Failed to query CloudWatch metric '{spec}': {e}")
        
        return metrics
    
    def _normalize_metric_name(self, namespace: str, metric_name: str) -> str:
        """Convert CloudWatch metric to standard format."""
        # AWS/EC2/CPUUtilization -> ec2_cpu_utilization
        ns_parts = namespace.lower().split("/")
        if ns_parts[0] == "aws":
            ns_parts = ns_parts[1:]
        
        # Convert CamelCase to snake_case
        import re
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', metric_name).lower()
        
        return f"{'_'.join(ns_parts)}_{name}"
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """CloudWatch requires AWS credentials."""
        return ["aws_access_key_id", "aws_secret_access_key", "region"]
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """Default CloudWatch metrics."""
        return [
            "AWS/EC2/CPUUtilization",
            "AWS/EC2/NetworkIn",
            "AWS/EC2/NetworkOut",
            "AWS/RDS/CPUUtilization",
            "AWS/RDS/DatabaseConnections",
            "AWS/RDS/FreeableMemory",
        ]
