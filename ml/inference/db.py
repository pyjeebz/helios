"""
Database models for Helios deployments and agents.

Uses in-memory storage for simplicity. Can be replaced with SQLite/PostgreSQL later.
"""

from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import uuid

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class Environment(str, Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AgentStatus(str, Enum):
    """Agent status types."""
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"


# =============================================================================
# Models
# =============================================================================


class Deployment(BaseModel):
    """Deployment configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Deployment name")
    description: str = Field("", description="Deployment description")
    environment: Environment = Field(Environment.DEVELOPMENT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Computed fields (populated by store)
    agents_count: int = 0
    agents_online: int = 0
    metrics_count: int = 0


class DeploymentCreate(BaseModel):
    """Request to create a deployment."""
    name: str = Field(..., min_length=1, max_length=64, pattern=r'^[a-z0-9-]+$')
    description: str = Field("", max_length=256)
    environment: Environment = Field(Environment.DEVELOPMENT)


class DeploymentUpdate(BaseModel):
    """Request to update a deployment."""
    name: Optional[str] = Field(None, min_length=1, max_length=64, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = Field(None, max_length=256)
    environment: Optional[Environment] = None


class Agent(BaseModel):
    """Agent registration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    deployment_id: str = Field(..., description="Parent deployment ID")
    hostname: str = Field(..., description="Agent hostname")
    platform: str = Field("unknown", description="OS platform")
    agent_version: str = Field("unknown", description="Agent version")
    
    # Status
    status: AgentStatus = Field(AgentStatus.ONLINE)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Management controls
    paused: bool = Field(False, description="Whether the agent is paused")
    collection_interval: int = Field(15, description="Collection interval in seconds")
    
    # Metrics info
    metrics: list[str] = Field(default_factory=list)
    metrics_count: int = 0
    
    # Location (optional)
    location: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ip_address: Optional[str] = None


class AgentRegister(BaseModel):
    """Request to register an agent."""
    agent_id: Optional[str] = Field(None, description="Custom agent ID (auto-generated if not provided)")
    hostname: str = Field(..., description="Agent hostname")
    platform: str = Field("unknown", description="OS platform")
    agent_version: str = Field("unknown", description="Agent version")
    metrics: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    region: Optional[str] = None
    ip_address: Optional[str] = None


class AgentHeartbeat(BaseModel):
    """Agent heartbeat request."""
    metrics_count: int = Field(0, description="Total metrics sent")
    metrics: list[str] = Field(default_factory=list, description="Available metrics")


class AgentConfigUpdate(BaseModel):
    """Request to update agent configuration."""
    paused: Optional[bool] = Field(None, description="Pause or resume the agent")
    collection_interval: Optional[int] = Field(None, ge=5, le=3600, description="Collection interval in seconds (5-3600)")


# =============================================================================
# In-Memory Store
# =============================================================================


class DeploymentStore:
    """In-memory storage for deployments and agents."""
    
    def __init__(self):
        self._deployments: dict[str, Deployment] = {}
        self._agents: dict[str, Agent] = {}
        
        # Create a default deployment
        default = Deployment(
            id="default",
            name="default",
            description="Default deployment",
            environment=Environment.DEVELOPMENT
        )
        self._deployments["default"] = default
    
    # -------------------------------------------------------------------------
    # Deployments
    # -------------------------------------------------------------------------
    
    def list_deployments(self) -> list[Deployment]:
        """List all deployments with computed fields."""
        deployments = []
        for dep in self._deployments.values():
            # Compute agent counts
            agents = [a for a in self._agents.values() if a.deployment_id == dep.id]
            dep.agents_count = len(agents)
            dep.agents_online = sum(1 for a in agents if a.status == AgentStatus.ONLINE)
            dep.metrics_count = sum(a.metrics_count for a in agents)
            deployments.append(dep)
        return deployments
    
    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Get a deployment by ID."""
        dep = self._deployments.get(deployment_id)
        if dep:
            agents = [a for a in self._agents.values() if a.deployment_id == dep.id]
            dep.agents_count = len(agents)
            dep.agents_online = sum(1 for a in agents if a.status == AgentStatus.ONLINE)
            dep.metrics_count = sum(a.metrics_count for a in agents)
        return dep
    
    def create_deployment(self, data: DeploymentCreate) -> Deployment:
        """Create a new deployment."""
        # Check for duplicate name
        for dep in self._deployments.values():
            if dep.name == data.name:
                raise ValueError(f"Deployment with name '{data.name}' already exists")
        
        deployment = Deployment(
            name=data.name,
            description=data.description,
            environment=data.environment
        )
        self._deployments[deployment.id] = deployment
        return deployment
    
    def update_deployment(self, deployment_id: str, data: DeploymentUpdate) -> Optional[Deployment]:
        """Update a deployment."""
        dep = self._deployments.get(deployment_id)
        if not dep:
            return None
        
        if data.name is not None:
            # Check for duplicate name
            for other in self._deployments.values():
                if other.id != deployment_id and other.name == data.name:
                    raise ValueError(f"Deployment with name '{data.name}' already exists")
            dep.name = data.name
        
        if data.description is not None:
            dep.description = data.description
        
        if data.environment is not None:
            dep.environment = data.environment
        
        dep.updated_at = datetime.utcnow()
        return dep
    
    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment and its agents."""
        if deployment_id not in self._deployments:
            return False
        
        # Delete associated agents
        agent_ids = [a.id for a in self._agents.values() if a.deployment_id == deployment_id]
        for agent_id in agent_ids:
            del self._agents[agent_id]
        
        del self._deployments[deployment_id]
        return True
    
    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------
    
    def list_agents(self, deployment_id: Optional[str] = None) -> list[Agent]:
        """List agents, optionally filtered by deployment."""
        self._update_agent_statuses()
        
        if deployment_id:
            return [a for a in self._agents.values() if a.deployment_id == deployment_id]
        return list(self._agents.values())
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        self._update_agent_statuses()
        return self._agents.get(agent_id)
    
    def register_agent(self, deployment_id: str, data: AgentRegister) -> Agent:
        """Register a new agent or update existing."""
        # Verify deployment exists
        if deployment_id not in self._deployments:
            raise ValueError(f"Deployment '{deployment_id}' not found")
        
        # Use provided ID or generate one
        agent_id = data.agent_id or f"{data.hostname[:8]}-{str(uuid.uuid4())[:4]}"
        
        # Check if agent already exists
        existing = self._agents.get(agent_id)
        if existing:
            # Update existing agent
            existing.last_seen = datetime.utcnow()
            existing.status = AgentStatus.ONLINE
            existing.hostname = data.hostname
            existing.platform = data.platform
            existing.agent_version = data.agent_version
            existing.metrics = data.metrics
            existing.location = data.location
            existing.region = data.region
            existing.ip_address = data.ip_address
            return existing
        
        # Create new agent
        agent = Agent(
            id=agent_id,
            deployment_id=deployment_id,
            hostname=data.hostname,
            platform=data.platform,
            agent_version=data.agent_version,
            metrics=data.metrics,
            location=data.location,
            region=data.region,
            ip_address=data.ip_address
        )
        self._agents[agent.id] = agent
        return agent
    
    def heartbeat_agent(self, agent_id: str, data: AgentHeartbeat) -> Optional[Agent]:
        """Update agent heartbeat."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        
        agent.last_seen = datetime.utcnow()
        agent.status = AgentStatus.ONLINE
        agent.metrics_count = data.metrics_count
        if data.metrics:
            agent.metrics = data.metrics
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        return True
    
    def get_deployment_metrics(self, deployment_id: str) -> list[str]:
        """Get unique metrics available in a deployment."""
        agents = [a for a in self._agents.values() if a.deployment_id == deployment_id]
        metrics = set()
        for agent in agents:
            metrics.update(agent.metrics)
        return sorted(metrics)
    
    def _update_agent_statuses(self):
        """Update agent statuses based on last_seen time."""
        now = datetime.utcnow()
        warning_threshold = timedelta(minutes=2)
        offline_threshold = timedelta(minutes=5)
        
        for agent in self._agents.values():
            if agent.paused:
                continue
            time_since = now - agent.last_seen
            if time_since > offline_threshold:
                agent.status = AgentStatus.OFFLINE
            elif time_since > warning_threshold:
                agent.status = AgentStatus.WARNING
            else:
                agent.status = AgentStatus.ONLINE

    def update_agent_config(self, agent_id: str, data: AgentConfigUpdate):
        """Update agent configuration."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        if data.paused is not None:
            agent.paused = data.paused
        if data.collection_interval is not None:
            agent.collection_interval = data.collection_interval
        return agent

    def get_agent_config(self, agent_id: str):
        """Get agent control config."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        return {
            "paused": agent.paused,
            "collection_interval": agent.collection_interval,
        }


# =============================================================================
# Metrics Store (Time-series in-memory)
# =============================================================================

class MetricPoint(BaseModel):
    """Single metric data point."""
    name: str
    value: float
    timestamp: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class MetricsStore:
    """In-memory time-series metrics storage."""
    
    def __init__(self, max_points: int = 10000):
        self._metrics: list[MetricPoint] = []
        self._max_points = max_points
    
    def add_metric(self, name: str, value: float, timestamp: datetime, labels: dict[str, str]):
        """Add a metric point."""
        point = MetricPoint(name=name, value=value, timestamp=timestamp, labels=labels)
        self._metrics.append(point)
        
        # Trim old metrics if over limit
        if len(self._metrics) > self._max_points:
            self._metrics = self._metrics[-self._max_points:]
    
    def add_metrics(self, metrics: list[dict]):
        """Add multiple metrics from ingest payload."""
        for m in metrics:
            timestamp = m.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except:
                    timestamp = datetime.utcnow()
            elif timestamp is None:
                timestamp = datetime.utcnow()
            
            self.add_metric(
                name=m.get("name", "unknown"),
                value=float(m.get("value", 0)),
                timestamp=timestamp,
                labels=m.get("labels", {})
            )
    
    def get_metrics(
        self, 
        name: str, 
        deployment_id: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> list[dict]:
        """Get metrics for a specific metric name."""
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        results = []
        for point in reversed(self._metrics):
            if point.name != name:
                continue
            # Handle both naive and aware timestamps
            point_ts = point.timestamp
            if point_ts.tzinfo is None:
                point_ts = point_ts.replace(tzinfo=timezone.utc)
            if point_ts < cutoff:
                continue
            if deployment_id and point.labels.get("deployment") != deployment_id:
                continue
            
            results.append({
                "value": point.value,
                "timestamp": point.timestamp.isoformat(),
                "labels": point.labels
            })
            
            if len(results) >= limit:
                break
        
        return list(reversed(results))
    
    def get_latest(self, name: str, deployment_id: Optional[str] = None) -> Optional[dict]:
        """Get the latest value for a metric."""
        for point in reversed(self._metrics):
            if point.name != name:
                continue
            if deployment_id and point.labels.get("deployment") != deployment_id:
                continue
            return {
                "value": point.value,
                "timestamp": point.timestamp.isoformat(),
                "labels": point.labels
            }
        return None
    
    def get_metric_names(self, deployment_id: Optional[str] = None) -> list[str]:
        """Get unique metric names."""
        names = set()
        for point in self._metrics:
            if deployment_id and point.labels.get("deployment") != deployment_id:
                continue
            names.add(point.name)
        return sorted(names)


# Global store instances — SQLite-backed for persistence
# Falls back to in-memory if SQLite import fails
try:
    from .storage.sqlite_backend import SQLiteDeploymentStore, SQLiteMetricsStore
    deployment_store = SQLiteDeploymentStore()
    metrics_store = SQLiteMetricsStore()
    _storage_backend = "sqlite"
except Exception as _e:
    import logging as _log
    _log.getLogger(__name__).warning(f"SQLite storage unavailable ({_e}), using in-memory")
    deployment_store = DeploymentStore()
    metrics_store = MetricsStore()
    _storage_backend = "memory"
