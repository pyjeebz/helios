"""Helios Agent CLI - Unified metrics collection."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from . import __version__
from .agent import Agent
from .config import load_config, AgentConfig
from .sources import SourceRegistry, list_sources

console = Console()


def setup_logging(level: str):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


@click.group()
@click.version_option(version=__version__, prog_name="helios-agent")
def main():
    """Helios Agent - Unified metrics collection for predictive infrastructure intelligence."""
    pass


@main.command()
@click.option("--config", "-c", "config_path", help="Path to config file")
@click.option("--endpoint", "-e", envvar="HELIOS_ENDPOINT", help="Helios API endpoint")
@click.option("--api-key", envvar="HELIOS_API_KEY", help="Helios API key")
@click.option("--interval", default=15, help="Collection interval in seconds")
@click.option("--log-level", default="INFO", help="Log level")
@click.option("--once", is_flag=True, help="Collect once and exit")
def run(
    config_path: Optional[str],
    endpoint: Optional[str],
    api_key: Optional[str],
    interval: int,
    log_level: str,
    once: bool,
):
    """Run the Helios metrics collection agent."""
    setup_logging(log_level)
    
    # Load config
    config = load_config(config_path)
    
    # Override with CLI options
    if endpoint:
        config.endpoint.url = endpoint
    if api_key:
        config.endpoint.api_key = api_key
    if interval:
        for source in config.sources:
            source.interval = interval
    
    config.log_level = log_level
    
    # Create and run agent
    agent = Agent(config)
    
    async def _run():
        await agent.setup()
        
        if once:
            metrics = await agent.collect_once()
            _display_metrics(metrics)
        else:
            source_names = [s.name for s in agent.sources]
            console.print(Panel(
                f"[bold green]Helios Agent v{__version__}[/bold green]\n"
                f"Endpoint: {config.endpoint.url}\n"
                f"Sources: {', '.join(source_names)}\n"
                f"Interval: {interval}s",
                title="Starting",
            ))
            
            try:
                await agent.run()
            except KeyboardInterrupt:
                console.print("\n[yellow]Shutting down...[/yellow]")
                await agent.stop()
    
    asyncio.run(_run())


def _display_metrics(metrics: list):
    """Display collected metrics in a table."""
    if not metrics:
        console.print("[yellow]No metrics collected[/yellow]")
        return
    
    table = Table(title=f"Collected {len(metrics)} Metrics", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Source", style="green")
    table.add_column("Labels", style="dim")
    
    for metric in metrics[:50]:  # Show first 50
        labels_str = ", ".join(f"{k}={v}" for k, v in list(metric.labels.items())[:3])
        if len(metric.labels) > 3:
            labels_str += f" (+{len(metric.labels) - 3})"
        
        # Format value
        if metric.value >= 1_000_000_000:
            value_str = f"{metric.value / 1_000_000_000:.2f}G"
        elif metric.value >= 1_000_000:
            value_str = f"{metric.value / 1_000_000:.2f}M"
        elif metric.value >= 1_000:
            value_str = f"{metric.value / 1_000:.2f}K"
        elif metric.value < 1:
            value_str = f"{metric.value * 100:.1f}%"
        else:
            value_str = f"{metric.value:.4f}"
        
        table.add_row(
            metric.name,
            value_str,
            metric.source,
            labels_str,
        )
    
    console.print(table)
    
    if len(metrics) > 50:
        console.print(f"[dim]... and {len(metrics) - 50} more metrics[/dim]")


@main.command()
@click.option("--config", "-c", "config_path", help="Path to config file")
def test(config_path: Optional[str]):
    """Test configured sources without sending data."""
    config = load_config(config_path)
    
    console.print("[bold]Testing metrics sources...[/bold]\n")
    console.print(f"Available source types: {', '.join(list_sources())}\n")
    
    async def _test():
        from .sources import SourceRegistry
        
        for source_config in config.sources:
            console.print(f"[cyan]{source_config.type.upper()} Source ({source_config.name}):[/cyan]")
            
            source = SourceRegistry.create(source_config)
            if source is None:
                console.print(f"  [red]x Unknown source type: {source_config.type}[/red]")
                continue
            
            # Initialize
            try:
                if not await source.initialize():
                    console.print("  [red]x Failed to initialize[/red]")
                    continue
            except Exception as e:
                console.print(f"  [red]x Init error: {e}[/red]")
                continue
            
            # Health check
            healthy = await source.health_check()
            if healthy:
                console.print("  [green]+ Health check passed[/green]")
            else:
                console.print("  [yellow]! Health check failed (may still work)[/yellow]")
            
            # Collect
            try:
                result = await source.collect()
                
                if result.success:
                    console.print(f"  [green]+ Collected {len(result.metrics)} metrics in {result.duration_ms:.1f}ms[/green]")
                    
                    # Show sample metrics
                    if result.metrics:
                        for m in result.metrics[:3]:
                            if m.value < 1:
                                console.print(f"    - {m.name}: {m.value*100:.1f}%")
                            else:
                                console.print(f"    - {m.name}: {m.value:.2f}")
                        if len(result.metrics) > 3:
                            console.print(f"    ... and {len(result.metrics) - 3} more")
                else:
                    console.print(f"  [red]x Collection failed: {result.error}[/red]")
            except Exception as e:
                console.print(f"  [red]x Collection error: {e}[/red]")
            finally:
                await source.close()
            
            console.print()
        
        # Test Helios connection
        console.print(f"[cyan]Helios API ({config.endpoint.url}):[/cyan]")
        from .client import HeliosClient
        
        client = HeliosClient(
            endpoint=config.endpoint.url,
            api_key=config.endpoint.api_key,
        )
        try:
            healthy = await client.check_health()
            if healthy:
                console.print("  [green]+ Connected successfully[/green]")
            else:
                console.print("  [red]x Could not connect[/red]")
        finally:
            await client.close()
    
    asyncio.run(_test())


@main.command()
def sources():
    """List available metrics source types."""
    console.print("[bold]Available Metrics Sources:[/bold]\n")
    
    table = Table(show_header=True)
    table.add_column("Type", style="cyan")
    table.add_column("Description")
    table.add_column("Required Credentials", style="dim")
    
    source_info = {
        "system": ("Local system metrics via psutil", "None"),
        "prometheus": ("Prometheus server scraping", "endpoint"),
        "datadog": ("Datadog API", "api_key, app_key"),
        "cloudwatch": ("AWS CloudWatch", "aws_access_key_id, aws_secret_access_key, region"),
        "azure_monitor": ("Azure Monitor", "tenant_id, client_id, client_secret, subscription_id"),
        "gcp_monitoring": ("Google Cloud Monitoring", "project_id, credentials_file (optional)"),
    }
    
    registered = list_sources()
    
    for source_type, (desc, creds) in source_info.items():
        status = "[green]+" if source_type in registered else "[red]x"
        table.add_row(f"{status} {source_type}", desc, creds)
    
    console.print(table)
    console.print("\n[dim]+ = registered and available, x = not registered (missing dependencies)[/dim]")


@main.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def init(output: Optional[str]):
    """Generate a sample configuration file."""
    sample_config = """# Helios Agent Configuration
# Unified metrics collection from any monitoring backend

# Helios API endpoint
endpoint:
  url: http://localhost:8000
  api_key: ${HELIOS_API_KEY}  # Or set via environment
  timeout: 30
  retry_attempts: 3

# Metrics sources - add any combination of backends
sources:
  # Local system metrics (always available)
  - name: local-system
    type: system
    enabled: true
    interval: 15
    options:
      collect_cpu: true
      collect_memory: true
      collect_disk: true
      collect_network: true

  # Prometheus (if you have a Prometheus server)
  # - name: prometheus
  #   type: prometheus
  #   enabled: false
  #   endpoint: http://prometheus:9090
  #   interval: 15
  #   queries:
  #     - 'sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (namespace, pod)'
  #     - 'sum(container_memory_usage_bytes{container!=""}) by (namespace, pod)'

  # Datadog (requires API key)
  # - name: datadog
  #   type: datadog
  #   enabled: false
  #   api_key: ${DATADOG_API_KEY}
  #   credentials:
  #     app_key: ${DATADOG_APP_KEY}
  #   options:
  #     site: us1  # us1, us3, us5, eu1, ap1
  #   metrics:
  #     - system.cpu.user
  #     - system.mem.used

  # AWS CloudWatch (requires AWS credentials)
  # - name: cloudwatch
  #   type: cloudwatch
  #   enabled: false
  #   credentials:
  #     aws_access_key_id: ${AWS_ACCESS_KEY_ID}
  #     aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  #     region: us-east-1
  #   metrics:
  #     - AWS/EC2/CPUUtilization
  #     - AWS/RDS/DatabaseConnections

  # Azure Monitor (requires service principal)
  # - name: azure-monitor
  #   type: azure_monitor
  #   enabled: false
  #   credentials:
  #     tenant_id: ${AZURE_TENANT_ID}
  #     client_id: ${AZURE_CLIENT_ID}
  #     client_secret: ${AZURE_CLIENT_SECRET}
  #     subscription_id: ${AZURE_SUBSCRIPTION_ID}

  # Google Cloud Monitoring (requires service account)
  # - name: gcp-monitoring
  #   type: gcp_monitoring
  #   enabled: false
  #   credentials:
  #     project_id: ${GCP_PROJECT_ID}
  #     credentials_file: /path/to/service-account.json

# Agent settings
batch_size: 100
flush_interval: 10
log_level: INFO
"""
    
    output_path = output or "helios-agent.yaml"
    
    with open(output_path, "w") as f:
        f.write(sample_config)
    
    console.print(f"[green]+ Created config file: {output_path}[/green]")
    console.print("\nEdit the file to enable your monitoring sources, then run:")
    console.print(f"  [cyan]helios-agent run -c {output_path}[/cyan]")


@main.command()
def status():
    """Show agent status and system info."""
    import psutil
    import platform
    
    console.print(Panel(
        f"[bold]Helios Agent v{__version__}[/bold]",
        title="Status",
    ))
    
    # System info
    table = Table(title="System Information", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    
    table.add_row("Platform", platform.platform())
    table.add_row("Python", platform.python_version())
    table.add_row("CPU Cores", str(psutil.cpu_count()))
    table.add_row("CPU Usage", f"{psutil.cpu_percent():.1f}%")
    
    mem = psutil.virtual_memory()
    table.add_row("Memory Total", f"{mem.total / 1024**3:.1f} GB")
    table.add_row("Memory Used", f"{mem.percent:.1f}%")
    
    console.print(table)
    
    # Available sources
    console.print(f"\n[bold]Available Source Types:[/bold] {', '.join(list_sources())}")


if __name__ == "__main__":
    main()
