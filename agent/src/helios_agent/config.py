"""Configuration management for Helios Agent."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .sources import SourceConfig


@dataclass
class HeliosEndpoint:
    """Helios API endpoint configuration."""
    
    url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass 
class AgentConfig:
    """Main agent configuration."""
    
    # Helios endpoint
    endpoint: HeliosEndpoint = field(default_factory=HeliosEndpoint)
    
    # Metrics sources (unified)
    sources: list[SourceConfig] = field(default_factory=list)
    
    # Agent settings
    batch_size: int = 100
    flush_interval: int = 10  # seconds
    log_level: str = "INFO"
    
    @classmethod
    def from_file(cls, path: str | Path) -> "AgentConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})
    
    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        """Create config from dictionary."""
        config = cls()
        
        # Endpoint
        if "endpoint" in data:
            ep = data["endpoint"]
            config.endpoint = HeliosEndpoint(
                url=ep.get("url", config.endpoint.url),
                api_key=ep.get("api_key") or os.environ.get("HELIOS_API_KEY"),
                timeout=ep.get("timeout", config.endpoint.timeout),
                retry_attempts=ep.get("retry_attempts", config.endpoint.retry_attempts),
                retry_delay=ep.get("retry_delay", config.endpoint.retry_delay),
            )
        
        # Override API key from env
        if not config.endpoint.api_key:
            config.endpoint.api_key = os.environ.get("HELIOS_API_KEY")
        
        # Override URL from env  
        if os.environ.get("HELIOS_ENDPOINT"):
            config.endpoint.url = os.environ["HELIOS_ENDPOINT"]
        
        # Parse sources
        config.sources = []
        for source_data in data.get("sources", []):
            source_config = SourceConfig(
                name=source_data.get("name", source_data.get("type", "unknown")),
                type=source_data.get("type"),
                enabled=source_data.get("enabled", True),
                interval=source_data.get("interval", 15),
                endpoint=source_data.get("endpoint"),
                api_key=source_data.get("api_key") or os.environ.get(f"{source_data.get('type', '').upper()}_API_KEY"),
                credentials=source_data.get("credentials", {}),
                queries=source_data.get("queries", []),
                metrics=source_data.get("metrics", []),
                namespaces=source_data.get("namespaces", []),
                labels=source_data.get("labels", {}),
                options=source_data.get("options", {}),
            )
            config.sources.append(source_config)
        
        # Default to system source if no sources configured
        if not config.sources:
            config.sources.append(SourceConfig(
                name="local-system",
                type="system",
                enabled=True,
                interval=15,
                options={
                    "collect_cpu": True,
                    "collect_memory": True,
                    "collect_disk": True,
                    "collect_network": True,
                },
            ))
        
        # Agent settings
        config.batch_size = data.get("batch_size", config.batch_size)
        config.flush_interval = data.get("flush_interval", config.flush_interval)
        config.log_level = data.get("log_level", config.log_level)
        
        return config
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables."""
        config = cls()
        
        # Endpoint
        config.endpoint.url = os.environ.get("HELIOS_ENDPOINT", config.endpoint.url)
        config.endpoint.api_key = os.environ.get("HELIOS_API_KEY")
        
        # Default system source
        config.sources = [
            SourceConfig(
                name="local-system",
                type="system",
                enabled=True,
                interval=15,
            )
        ]
        
        # Add Prometheus if configured
        prom_url = os.environ.get("PROMETHEUS_URL")
        if prom_url:
            config.sources.append(SourceConfig(
                name="prometheus",
                type="prometheus",
                enabled=True,
                endpoint=prom_url,
                interval=15,
            ))
        
        # Add Datadog if configured
        dd_api_key = os.environ.get("DATADOG_API_KEY")
        if dd_api_key:
            config.sources.append(SourceConfig(
                name="datadog",
                type="datadog",
                enabled=True,
                api_key=dd_api_key,
                credentials={"app_key": os.environ.get("DATADOG_APP_KEY", "")},
                interval=15,
            ))
        
        return config


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Load configuration from file or environment."""
    # Try config file first
    if config_path and Path(config_path).exists():
        return AgentConfig.from_file(config_path)
    
    # Try default locations
    default_paths = [
        Path("helios-agent.yaml"),
        Path("helios-agent.yml"),
        Path.home() / ".helios" / "agent.yaml",
        Path("/etc/helios/agent.yaml"),
    ]
    
    for path in default_paths:
        if path.exists():
            return AgentConfig.from_file(path)
    
    # Fall back to environment
    return AgentConfig.from_env()
