"""Helios Agent - Main agent runner with unified metrics sources."""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

from .client import HeliosClient
from .sources import MetricsSource, MetricSample, SourceRegistry
from .config import AgentConfig

logger = logging.getLogger(__name__)


class Agent:
    """
    Main Helios metrics collection agent.
    
    Uses a unified source interface to collect metrics from any backend:
    - system: Local host metrics via psutil
    - prometheus: Prometheus server
    - datadog: Datadog API
    - cloudwatch: AWS CloudWatch
    - azure_monitor: Azure Monitor
    - gcp_monitoring: Google Cloud Monitoring
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.sources: list[MetricsSource] = []
        self.client: Optional[HeliosClient] = None
        self._running = False
        self._paused = False
        self._interval_override: Optional[int] = None  # Server-controlled interval
        self._metrics_buffer: list[MetricSample] = []
        self._last_flush = datetime.now(timezone.utc)
    
    async def setup(self):
        """Initialize sources and client."""
        # Setup Helios client
        self.client = HeliosClient(
            endpoint=self.config.endpoint.url,
            api_key=self.config.endpoint.api_key,
            timeout=self.config.endpoint.timeout,
            retry_attempts=self.config.endpoint.retry_attempts,
            retry_delay=self.config.endpoint.retry_delay,
        )
        
        # Setup sources from config
        for source_config in self.config.sources:
            if not source_config.enabled:
                continue
            
            source = SourceRegistry.create(source_config)
            if source is None:
                logger.warning(f"Unknown source type: {source_config.type}")
                continue
            
            # Initialize the source
            try:
                if await source.initialize():
                    self.sources.append(source)
                    logger.info(f"Initialized source: {source.name} (type: {source_config.type})")
                else:
                    logger.warning(f"Failed to initialize source: {source.name}")
            except Exception as e:
                logger.error(f"Error initializing source {source.name}: {e}")
        
        logger.info(f"Agent initialized with {len(self.sources)} sources")
        logger.info(f"Available source types: {SourceRegistry.list_types()}")
    
    async def run(self):
        """Run the agent main loop."""
        self._running = True
        logger.info("Starting Helios Agent...")
        
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass
        
        # Check Helios API health
        if self.client:
            healthy = await self.client.check_health()
            if healthy:
                logger.info(f"Connected to Helios at {self.config.endpoint.url}")
            else:
                logger.warning(f"Could not connect to Helios at {self.config.endpoint.url}")
        
        # Start source collection tasks
        tasks = []
        for source in self.sources:
            if source.is_enabled():
                task = asyncio.create_task(self._run_source(source))
                tasks.append(task)
        
        # Start flush task
        flush_task = asyncio.create_task(self._flush_loop())
        tasks.append(flush_task)
        
        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Agent tasks cancelled")
    
    async def stop(self):
        """Stop the agent gracefully."""
        logger.info("Stopping Helios Agent...")
        self._running = False
        
        # Flush remaining metrics
        await self._flush_metrics()
        
        # Close sources
        for source in self.sources:
            try:
                await source.close()
            except Exception as e:
                logger.warning(f"Error closing source {source.name}: {e}")
        
        # Close client
        if self.client:
            await self.client.close()
    
    async def _run_source(self, source: MetricsSource):
        """Run a source collection loop."""
        while self._running:
            # Check if paused
            if self._paused:
                logger.debug(f"Agent paused, skipping collection from {source.name}")
                await asyncio.sleep(5)  # Check pause state every 5s
                continue
            
            try:
                result = await source.collect()
                
                if result.success:
                    # Convert source metrics to buffer format
                    self._metrics_buffer.extend(result.metrics)
                    logger.debug(
                        f"Collected {len(result.metrics)} metrics from {source.name} "
                        f"in {result.duration_ms:.1f}ms"
                    )
                else:
                    logger.warning(f"Source {source.name} error: {result.error}")
                
            except Exception as e:
                logger.error(f"Error running source {source.name}: {e}")
            
            # Use server-controlled interval if available, else source default
            interval = self._interval_override or source.config.interval
            await asyncio.sleep(interval)
    
    async def _flush_loop(self):
        """Periodically flush metrics to Helios."""
        while self._running:
            await asyncio.sleep(self.config.flush_interval)
            await self._flush_metrics()
    
    async def _flush_metrics(self):
        """Flush buffered metrics to Helios."""
        if not self._metrics_buffer:
            return
        
        if not self.client:
            logger.warning("No Helios client configured, discarding metrics")
            self._metrics_buffer.clear()
            return
        
        # Get metrics to send
        metrics_to_send = self._metrics_buffer[:self.config.batch_size]
        self._metrics_buffer = self._metrics_buffer[self.config.batch_size:]
        
        # Send metrics
        result = await self.client.send_metrics(metrics_to_send)
        
        if result is not None:
            logger.info(f"Sent {len(metrics_to_send)} metrics to Helios")
            
            # Apply control commands from server
            commands = result.get("commands")
            if commands:
                self._apply_commands(commands)
        else:
            # Re-add failed metrics to buffer (at the front)
            self._metrics_buffer = metrics_to_send + self._metrics_buffer
            # Trim buffer if too large
            max_buffer = self.config.batch_size * 10
            if len(self._metrics_buffer) > max_buffer:
                dropped = len(self._metrics_buffer) - max_buffer
                self._metrics_buffer = self._metrics_buffer[:max_buffer]
                logger.warning(f"Buffer full, dropped {dropped} oldest metrics")
    
    def _apply_commands(self, commands: dict):
        """Apply control commands received from the server."""
        if "paused" in commands:
            new_paused = bool(commands["paused"])
            if new_paused != self._paused:
                self._paused = new_paused
                state = "PAUSED" if new_paused else "RESUMED"
                logger.info(f"Agent {state} by server command")
        
        if "collection_interval" in commands:
            new_interval = int(commands["collection_interval"])
            if new_interval != self._interval_override:
                old = self._interval_override or "default"
                self._interval_override = new_interval
                logger.info(f"Collection interval changed: {old} -> {new_interval}s")
    
    async def collect_once(self) -> list[MetricSample]:
        """Run all sources once and return metrics."""
        all_metrics = []
        
        for source in self.sources:
            if source.is_enabled():
                result = await source.collect()
                if result.success:
                    all_metrics.extend(result.metrics)
        
        return all_metrics
    
    async def health_check(self) -> dict:
        """Check health of all sources and client."""
        status = {
            "sources": {},
            "client": False,
            "metrics_buffered": len(self._metrics_buffer),
        }
        
        for source in self.sources:
            try:
                status["sources"][source.name] = await source.health_check()
            except Exception:
                status["sources"][source.name] = False
        
        if self.client:
            status["client"] = await self.client.check_health()
        
        return status
