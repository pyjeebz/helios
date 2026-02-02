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
            time_since = now - agent.last_seen
            if time_since > offline_threshold:
                agent.status = AgentStatus.OFFLINE
            elif time_since > warning_threshold:
                agent.status = AgentStatus.WARNING
            else:
                agent.status = AgentStatus.ONLINE


# Global store instance
deployment_store = DeploymentStore()
