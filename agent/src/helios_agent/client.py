"""Helios API client for sending metrics."""

import asyncio
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .sources.base import MetricSample

logger = logging.getLogger(__name__)


class HeliosClient:
    """Client for sending metrics to Helios API."""
    
    def __init__(
        self,
        endpoint: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_headers(self) -> dict:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "helios-agent/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._get_headers(),
            )
        return self._client
    
    async def send_metrics(self, metrics: list) -> bool:
        """Send metrics to Helios API.
        
        Args:
            metrics: List of metric samples to send
            
        Returns:
            True if successful, False otherwise
        """
        if not metrics:
            return True
        
        payload = {
            "metrics": [m.to_dict() for m in metrics],
            "agent_version": "0.1.0",
            "sent_at": datetime.utcnow().isoformat(),
        }
        
        client = await self._get_client()
        
        for attempt in range(self.retry_attempts):
            try:
                response = await client.post(
                    f"{self.endpoint}/api/v1/ingest",
                    json=payload,
                )
                
                if response.status_code == 200:
                    logger.debug(f"Successfully sent {len(metrics)} metrics")
                    return True
                elif response.status_code == 401:
                    logger.error("Authentication failed - check API key")
                    return False
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = float(response.headers.get("Retry-After", self.retry_delay * 2))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                else:
                    logger.warning(f"Failed to send metrics: {response.status_code}")
                    
            except httpx.TimeoutException:
                logger.warning(f"Timeout sending metrics (attempt {attempt + 1})")
            except httpx.HTTPError as e:
                logger.warning(f"HTTP error sending metrics: {e}")
            
            if attempt < self.retry_attempts - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        logger.error(f"Failed to send {len(metrics)} metrics after {self.retry_attempts} attempts")
        return False
    
    async def check_health(self) -> bool:
        """Check if Helios API is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.endpoint}/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def get_predictions(
        self,
        deployment: str,
        namespace: str = "default",
        metric: str = "cpu_utilization",
        horizon_hours: int = 24,
    ) -> Optional[dict]:
        """Get predictions from Helios API.
        
        Args:
            deployment: Deployment name
            namespace: Kubernetes namespace
            metric: Metric type to predict
            horizon_hours: Prediction horizon
            
        Returns:
            Prediction response or None if failed
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.endpoint}/predict",
                json={
                    "metric": metric,
                    "deployment": deployment,
                    "namespace": namespace,
                    "horizon_hours": horizon_hours,
                },
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get predictions: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting predictions: {e}")
            return None
    
    async def detect_anomalies(
        self,
        deployment: str,
        namespace: str = "default",
        metrics: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Detect anomalies using Helios API.
        
        Args:
            deployment: Deployment name  
            namespace: Kubernetes namespace
            metrics: List of metric types to analyze
            
        Returns:
            Anomaly detection response or None if failed
        """
        try:
            client = await self._get_client()
            payload = {
                "deployment": deployment,
                "namespace": namespace,
            }
            if metrics:
                payload["metrics"] = metrics
            
            response = await client.post(
                f"{self.endpoint}/detect",
                json=payload,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to detect anomalies: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
