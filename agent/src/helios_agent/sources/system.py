"""System metrics source - collects host-level metrics via psutil."""

import time
from datetime import datetime, timezone
import logging

import psutil

from .base import MetricsSource, MetricSample, MetricType, SourceConfig, CollectionResult
from .registry import register_source

logger = logging.getLogger(__name__)


@register_source("system")
class SystemSource(MetricsSource):
    """
    Collect system metrics from the local host using psutil.
    
    This source collects:
    - CPU utilization (overall and per-core)
    - Memory usage
    - Disk usage
    - Network I/O
    
    Config options:
        collect_cpu: bool - Collect CPU metrics (default: True)
        collect_memory: bool - Collect memory metrics (default: True)
        collect_disk: bool - Collect disk metrics (default: True)
        collect_network: bool - Collect network metrics (default: True)
        per_cpu: bool - Collect per-CPU core metrics (default: False)
    """
    
    source_type = "system"
    
    async def initialize(self) -> bool:
        """Initialize system metrics collection."""
        # psutil doesn't need initialization
        self._initialized = True
        return True
    
    async def health_check(self) -> bool:
        """System source is always healthy if psutil is available."""
        try:
            psutil.cpu_percent(interval=None)
            return True
        except Exception:
            return False
    
    async def collect(self) -> CollectionResult:
        """Collect system metrics."""
        start = time.time()
        metrics = []
        now = datetime.now(timezone.utc)
        
        options = self.config.options
        
        try:
            # CPU metrics
            if options.get("collect_cpu", True):
                metrics.extend(self._collect_cpu(now, options.get("per_cpu", False)))
            
            # Memory metrics
            if options.get("collect_memory", True):
                metrics.extend(self._collect_memory(now))
            
            # Disk metrics
            if options.get("collect_disk", True):
                metrics.extend(self._collect_disk(now))
            
            # Network metrics
            if options.get("collect_network", True):
                metrics.extend(self._collect_network(now))
            
            # Merge config-level labels (like deployment) into each metric
            if self.config.labels:
                for metric in metrics:
                    metric.labels.update(self.config.labels)
            
            duration = (time.time() - start) * 1000
            
            return CollectionResult(
                source=self.name,
                success=True,
                metrics=metrics,
                duration_ms=duration,
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return CollectionResult(
                source=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
    
    def _collect_cpu(self, timestamp: datetime, per_cpu: bool = False) -> list[MetricSample]:
        """Collect CPU metrics."""
        metrics = []
        
        # Overall CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        metrics.append(MetricSample(
            name="cpu_utilization",
            value=cpu_percent / 100.0,
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            labels={"host": self._get_hostname()},
            source=self.name,
        ))
        
        # Per-CPU if requested
        if per_cpu:
            per_cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
            for i, pct in enumerate(per_cpu_percent):
                metrics.append(MetricSample(
                    name="cpu_utilization",
                    value=pct / 100.0,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    labels={"host": self._get_hostname(), "cpu": str(i)},
                    source=self.name,
                ))
        
        return metrics
    
    def _collect_memory(self, timestamp: datetime) -> list[MetricSample]:
        """Collect memory metrics."""
        metrics = []
        mem = psutil.virtual_memory()
        host = self._get_hostname()
        
        metrics.append(MetricSample(
            name="memory_utilization",
            value=mem.percent / 100.0,
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            labels={"host": host},
            source=self.name,
        ))
        
        metrics.append(MetricSample(
            name="memory_bytes",
            value=float(mem.used),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            labels={"host": host, "type": "used"},
            source=self.name,
        ))
        
        metrics.append(MetricSample(
            name="memory_bytes",
            value=float(mem.total),
            timestamp=timestamp,
            metric_type=MetricType.GAUGE,
            labels={"host": host, "type": "total"},
            source=self.name,
        ))
        
        return metrics
    
    def _collect_disk(self, timestamp: datetime) -> list[MetricSample]:
        """Collect disk metrics."""
        metrics = []
        host = self._get_hostname()
        
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                metrics.append(MetricSample(
                    name="disk_utilization",
                    value=usage.percent / 100.0,
                    timestamp=timestamp,
                    metric_type=MetricType.GAUGE,
                    labels={
                        "host": host,
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                    },
                    source=self.name,
                ))
            except (PermissionError, OSError):
                continue
        
        return metrics
    
    def _collect_network(self, timestamp: datetime) -> list[MetricSample]:
        """Collect network metrics."""
        metrics = []
        host = self._get_hostname()
        net = psutil.net_io_counters()
        
        metrics.append(MetricSample(
            name="network_bytes_recv",
            value=float(net.bytes_recv),
            timestamp=timestamp,
            metric_type=MetricType.COUNTER,
            labels={"host": host},
            source=self.name,
        ))
        
        metrics.append(MetricSample(
            name="network_bytes_sent",
            value=float(net.bytes_sent),
            timestamp=timestamp,
            metric_type=MetricType.COUNTER,
            labels={"host": host},
            source=self.name,
        ))
        
        return metrics
    
    def _get_hostname(self) -> str:
        """Get the hostname."""
        import socket
        return socket.gethostname()
    
    @classmethod
    def get_required_credentials(cls) -> list[str]:
        """System source doesn't need credentials."""
        return []
    
    @classmethod
    def get_default_queries(cls) -> list[str]:
        """System source doesn't use queries."""
        return []
