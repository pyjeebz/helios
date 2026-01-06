"""Prometheus metrics source - scrapes metrics from Prometheus server."""

import time
from datetime import datetime, timezone
from typing import Any
import logging

import httpx

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("prometheus")
class PrometheusSource(MetricsSource):
    """
    Collect metrics from a Prometheus server.
    
    This source executes PromQL queries and converts results to MetricSamples.
    
    Config:
        endpoint: str - Prometheus server URL (e.g., "http://prometheus:9090")
        queries: list[str] - PromQL queries to execute
        
    Config options:
        timeout: int - Query timeout in seconds (default: 30)
        step: str - Query step for range queries (default: "1m")
    """
    
    source_type = "prometheus"
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
    
    async def initialize(self) -> bool:
        """Initialize HTTP client for Prometheus."""
        timeout = self.config.options.get("timeout", 30)
        self._client = httpx.AsyncClient(
            base_url=self.config.endpoint,
            timeout=timeout,
        )
        self._initialized = True
        return True
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> bool:
        """Check Prometheus connectivity."""
        if not self._client:
            return False
        
        try:
            response = await self._client.get("/-/healthy")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Prometheus health check failed: {e}")
            return False
    
    async def collect(self) -> CollectionResult:
        """Execute PromQL queries and collect metrics."""
        if not self._client:
            await self.initialize()
        
        start = time.time()
        metrics = []
        
        # Use configured queries or defaults
        queries = self.config.queries or self.get_default_queries()
        
        try:
            for query in queries:
                result = await self._execute_query(query)
                metrics.extend(result)
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            logger.error(f"Error collecting Prometheus metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    async def _execute_query(self, query: str) -> list[MetricSample]:
        """Execute a PromQL query and parse results."""
        metrics = []
        
        try:
            response = await self._client.get(
                "/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                logger.warning(f"Prometheus query failed: {data.get('error', 'unknown')}")
                return metrics
            
            result = data.get("data", {})
            result_type = result.get("resultType")
            
            if result_type == "vector":
                metrics.extend(self._parse_vector(result.get("result", []), query))
            elif result_type == "matrix":
                metrics.extend(self._parse_matrix(result.get("result", []), query))
            
        except Exception as e:
            logger.warning(f"Failed to execute query '{query}': {e}")
        
        return metrics
    
    def _parse_vector(self, results: list[dict], query: str) -> list[MetricSample]:
        """Parse instant vector results."""
        metrics = []
        
        for item in results:
            metric_labels = item.get("metric", {})
            timestamp_val, value = item.get("value", [0, "0"])
            
            # Extract metric name from labels or query
            name = metric_labels.pop("__name__", self._query_to_name(query))
            
            try:
                metrics.append(MetricSample(
                    name=name,
                    value=float(value),
                    timestamp=datetime.fromtimestamp(timestamp_val, tz=timezone.utc),
                    metric_type=MetricType.GAUGE,
                    labels=metric_labels,
                    source=self.name,
                ))
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse metric value: {e}")
        
        return metrics
    
    def _parse_matrix(self, results: list[dict], query: str) -> list[MetricSample]:
        """Parse range vector (matrix) results - take latest value."""
        metrics = []
        
        for item in results:
            metric_labels = item.get("metric", {})
            values = item.get("values", [])
            
            if not values:
                continue
            
            # Take the most recent value
            timestamp_val, value = values[-1]
            name = metric_labels.pop("__name__", self._query_to_name(query))
            
            try:
                metrics.append(MetricSample(
                    name=name,
                    value=float(value),
                    timestamp=datetime.fromtimestamp(timestamp_val, tz=timezone.utc),
                    metric_type=MetricType.GAUGE,
                    labels=metric_labels,
                    source=self.name,
                ))
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse metric value: {e}")
        
        return metrics
    
    def _query_to_name(self, query: str) -> str:
        """Convert a PromQL query to a metric name."""
        # Simple heuristic: extract first word before parens or brackets
        clean = query.strip()
        for char in "({[":
            if char in clean:
                clean = clean.split(char)[0]
        return clean.strip().replace(" ", "_").lower()
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """Prometheus may need basic auth."""
        return []  # Optional: ["username", "password"]
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """Default Prometheus queries for Kubernetes metrics."""
        return [
            # CPU usage by pod
            'sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (namespace, pod)',
            # Memory usage by pod
            'sum(container_memory_usage_bytes{container!=""}) by (namespace, pod)',
            # Network I/O
            'sum(rate(container_network_receive_bytes_total[5m])) by (namespace, pod)',
            'sum(rate(container_network_transmit_bytes_total[5m])) by (namespace, pod)',
        ]
