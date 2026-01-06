"""Datadog metrics source - fetches metrics from Datadog API."""

import time
from datetime import datetime, timezone, timedelta
import logging

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("datadog")
class DatadogSource(MetricsSource):
    """
    Collect metrics from Datadog API.
    
    Config:
        endpoint: str - Datadog API endpoint (default: "https://api.datadoghq.com")
        api_key: str - Datadog API key
        credentials:
            app_key: str - Datadog application key
        
        metrics: list[str] - Metric names to query (e.g., ["system.cpu.user", "system.mem.used"])
        
    Config options:
        site: str - Datadog site (us1, us3, us5, eu1, ap1)
        lookback_minutes: int - How far back to query (default: 5)
    """
    
    source_type = "datadog"
    
    SITE_ENDPOINTS = {
        "us1": "https://api.datadoghq.com",
        "us3": "https://api.us3.datadoghq.com",
        "us5": "https://api.us5.datadoghq.com",
        "eu1": "https://api.datadoghq.eu",
        "ap1": "https://api.ap1.datadoghq.com",
    }
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._client = None
    
    async def initialize(self) -> bool:
        """Initialize Datadog client."""
        try:
            import httpx
            
            # Determine endpoint
            site = self.config.options.get("site", "us1")
            endpoint = self.config.endpoint or self.SITE_ENDPOINTS.get(site, self.SITE_ENDPOINTS["us1"])
            
            self._client = httpx.AsyncClient(
                base_url=endpoint,
                headers={
                    "DD-API-KEY": self.config.api_key or "",
                    "DD-APPLICATION-KEY": self.config.credentials.get("app_key", ""),
                },
                timeout=30,
            )
            self._initialized = True
            return True
            
        except ImportError:
            logger.error("httpx is required for Datadog source")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Datadog source: {e}")
            return False
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> bool:
        """Check Datadog API connectivity."""
        if not self._client:
            return False
        
        try:
            response = await self._client.get("/api/v1/validate")
            return response.status_code == 200
        except Exception:
            return False
    
    async def collect(self) -> CollectionResult:
        """Query Datadog metrics API."""
        if not self._client:
            await self.initialize()
        
        start = time.time()
        metrics = []
        
        # Get metrics to query
        metric_names = self.config.metrics or self.get_default_queries()
        
        try:
            lookback = self.config.options.get("lookback_minutes", 5)
            now = datetime.now(timezone.utc)
            from_ts = int((now - timedelta(minutes=lookback)).timestamp())
            to_ts = int(now.timestamp())
            
            for metric_name in metric_names:
                result = await self._query_metric(metric_name, from_ts, to_ts)
                metrics.extend(result)
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            logger.error(f"Error collecting Datadog metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    async def _query_metric(self, metric_name: str, from_ts: int, to_ts: int) -> list[MetricSample]:
        """Query a single metric from Datadog."""
        metrics = []
        
        try:
            response = await self._client.get(
                "/api/v1/query",
                params={
                    "query": metric_name,
                    "from": from_ts,
                    "to": to_ts,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            for series in data.get("series", []):
                scope = series.get("scope", "")
                pointlist = series.get("pointlist", [])
                
                # Parse scope into labels
                labels = self._parse_scope(scope)
                
                # Take the most recent point
                if pointlist:
                    timestamp_ms, value = pointlist[-1]
                    
                    # Normalize metric name
                    normalized_name = self._normalize_metric_name(series.get("metric", metric_name))
                    
                    metrics.append(MetricSample(
                        name=normalized_name,
                        value=value if value is not None else 0.0,
                        timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
                        metric_type=MetricType.GAUGE,
                        labels=labels,
                        source=self.name,
                    ))
            
        except Exception as e:
            logger.warning(f"Failed to query Datadog metric '{metric_name}': {e}")
        
        return metrics
    
    def _parse_scope(self, scope: str) -> dict[str, str]:
        """Parse Datadog scope string into labels dict."""
        labels = {}
        if scope:
            for part in scope.split(","):
                if ":" in part:
                    key, value = part.split(":", 1)
                    labels[key.strip()] = value.strip()
        return labels
    
    def _normalize_metric_name(self, name: str) -> str:
        """Convert Datadog metric name to standard format."""
        # system.cpu.user -> cpu_user
        parts = name.split(".")
        if len(parts) > 1 and parts[0] in ("system", "aws", "azure", "gcp"):
            parts = parts[1:]
        return "_".join(parts)
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """Datadog requires API key and app key."""
        return ["api_key", "app_key"]
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """Default Datadog metrics to collect."""
        return [
            "system.cpu.user",
            "system.cpu.system",
            "system.mem.used",
            "system.mem.total",
            "system.disk.used",
            "system.net.bytes_rcvd",
            "system.net.bytes_sent",
        ]
