"""Agent management commands for Helios CLI."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def agent():
    """Manage Helios metrics collection agents."""
    pass


@agent.command("status")
@click.pass_context
def agent_status(ctx: click.Context):
    """Check agent status and metrics sources."""
    import psutil
    import platform
    
    console.print("[bold]Helios Agent Status[/bold]\n")
    
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
    try:
        from helios_agent.sources import list_sources
        sources = list_sources()
        console.print(f"\n[bold]Available Source Types:[/bold] {', '.join(sources)}")
    except ImportError:
        console.print("\n[yellow]helios-agent not installed. Install with:[/yellow]")
        console.print("  pip install helios-agent")


@agent.command("sources")
def agent_sources():
    """List available metrics source types."""
    try:
        from helios_agent.sources import list_sources
        
        console.print("[bold]Available Metrics Sources:[/bold]\n")
        
        table = Table(show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Description")
        table.add_column("Install Extra", style="dim")
        
        source_info = {
            "system": ("Local system metrics via psutil", "included"),
            "prometheus": ("Prometheus server scraping", "included"),
            "datadog": ("Datadog API", "pip install helios-agent[datadog]"),
            "cloudwatch": ("AWS CloudWatch", "pip install helios-agent[aws]"),
            "azure_monitor": ("Azure Monitor", "pip install helios-agent[azure]"),
            "gcp_monitoring": ("Google Cloud Monitoring", "pip install helios-agent[gcp]"),
        }
        
        registered = list_sources()
        
        for source_type, (desc, install) in source_info.items():
            status = "[green]+" if source_type in registered else "[red]x"
            table.add_row(f"{status} {source_type}", desc, install)
        
        console.print(table)
        console.print("\n[dim]+ = available, x = missing dependencies[/dim]")
        
    except ImportError:
        console.print("[yellow]helios-agent not installed. Install with:[/yellow]")
        console.print("  pip install helios-agent")


@agent.command("init")
@click.option("--output", "-o", type=click.Path(), default="helios-agent.yaml", help="Output file path")
def agent_init(output: str):
    """Generate a sample agent configuration file."""
    try:
        from helios_agent.cli_v2 import init as agent_init_cmd
        # Invoke the agent's init command
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "helios_agent.cli_v2", "init", "-o", output],
            capture_output=True,
            text=True,
        )
        console.print(result.stdout)
        if result.stderr:
            console.print(result.stderr)
    except ImportError:
        # Fallback: write config directly
        sample_config = """# Helios Agent Configuration
endpoint:
  url: http://localhost:8000
  api_key: ${HELIOS_API_KEY}

sources:
  - name: local-system
    type: system
    enabled: true
    interval: 15

batch_size: 100
flush_interval: 10
log_level: INFO
"""
        with open(output, "w") as f:
            f.write(sample_config)
        
        console.print(f"[green]+ Created config file: {output}[/green]")
        console.print("\nRun the agent with:")
        console.print(f"  [cyan]helios-agent run -c {output}[/cyan]")


@agent.command("test")
@click.option("--config", "-c", "config_path", help="Path to config file")
def agent_test(config_path: str | None):
    """Test agent collectors without sending data."""
    try:
        import subprocess
        import sys
        
        cmd = [sys.executable, "-m", "helios_agent.cli_v2", "test"]
        if config_path:
            cmd.extend(["-c", config_path])
        
        result = subprocess.run(cmd, capture_output=False)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[yellow]Make sure helios-agent is installed:[/yellow]")
        console.print("  pip install helios-agent")
