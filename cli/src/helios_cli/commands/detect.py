"""Anomaly detection commands for Helios CLI."""

import json
from datetime import datetime, timedelta, timezone
import random

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def generate_sample_metrics(lookback_hours: int = 1):
    """Generate sample metrics data for anomaly detection."""
    now = datetime.now(timezone.utc)
    points = []
    
    # Generate realistic time-series with possible anomaly
    base_cpu = 0.45
    for i in range(lookback_hours * 12):  # 5-min intervals
        timestamp = now - timedelta(minutes=(lookback_hours * 60) - (i * 5))
        # Normal variation with occasional spike
        noise = random.uniform(-0.05, 0.05)
        value = base_cpu + noise
        
        # Add a spike at 70% through the data
        if 0.68 <= i / (lookback_hours * 12) <= 0.72:
            value = random.uniform(0.85, 0.95)
        
        points.append({
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "value": round(value, 3)
        })
    
    return points


@click.command()
@click.option("--deployment", "-d", default=None, help="Deployment name (optional, for labeling)")
@click.option("--namespace", "-n", default=None, help="Kubernetes namespace (optional, for labeling)")
@click.option("--lookback", "-l", default=1, type=int, help="Hours of data to analyze")
@click.option("--sensitivity", "-s", default="medium", 
              type=click.Choice(["low", "medium", "high"]),
              help="Detection sensitivity (low=3σ, medium=2.5σ, high=2σ)")
@click.option("--metric", "-m", default="cpu_utilization",
              type=click.Choice(["cpu_utilization", "memory_utilization", "request_latency", "error_rate"]),
              help="Metric to analyze")
@click.pass_context
def detect(ctx: click.Context, deployment: str | None, namespace: str | None, lookback: int, 
           sensitivity: str, metric: str) -> None:
    """Detect anomalies in resource metrics.
    
    Analyzes metrics to identify unusual patterns that may indicate issues.
    
    \b
    Examples:
        helios detect                           # Quick detect with defaults
        helios detect -d my-app -n production   # Specific deployment
        helios detect --sensitivity high        # More sensitive detection
        helios detect -m memory_utilization     # Check memory instead
    """
    endpoint = ctx.obj["endpoint"]
    api_key = ctx.obj["api_key"]
    output_format = ctx.obj["output"]
    
    # Map sensitivity to threshold sigma
    threshold_map = {"low": 3.0, "medium": 2.5, "high": 2.0}
    threshold_sigma = threshold_map[sensitivity]
    
    # Generate sample metrics data
    metrics_data = generate_sample_metrics(lookback)
    
    with console.status(f"[bold blue]Analyzing {metric} for anomalies..."):
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Build request matching the actual API schema
            request_body = {
                "metrics": {
                    metric: metrics_data
                },
                "threshold_sigma": threshold_sigma
            }
            
            response = httpx.post(
                f"{endpoint}/detect",
                json=request_body,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Error:[/red] API returned {e.response.status_code}: {e.response.text}")
            raise SystemExit(1)
        except httpx.HTTPError as e:
            console.print(f"[red]Error:[/red] Failed to connect to Helios: {e}")
            raise SystemExit(1)
    
    if output_format == "json":
        console.print(json.dumps(data, indent=2))
    elif output_format == "yaml":
        import yaml
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        _display_anomalies(data, deployment, namespace, metric, sensitivity)


def _display_anomalies(data: dict, deployment: str | None, namespace: str | None, metric: str, sensitivity: str) -> None:
    """Display anomaly detection results."""
    console.print()
    
    anomalies = data.get("anomalies", [])
    summary = data.get("summary", {})
    status = summary.get("status", "unknown")
    
    status_color = {"healthy": "green", "attention": "yellow", "warning": "red", "critical": "bold red"}.get(status, "white")
    
    info_lines = ["[bold]Anomaly Detection Results[/bold]"]
    if deployment:
        info_lines.append(f"Deployment: [cyan]{deployment}[/cyan]")
    if namespace:
        info_lines.append(f"Namespace: [cyan]{namespace}[/cyan]")
    info_lines.extend([
        f"Metric: [cyan]{metric}[/cyan]",
        f"Sensitivity: [cyan]{sensitivity}[/cyan]",
        f"Data Points: [cyan]{data.get('data_points_analyzed', 0)}[/cyan]",
    ])
    
    console.print(Panel(
        "\n".join(info_lines) + "\n"
        f"Status: [{status_color}]{status.upper()}[/{status_color}]",
        title="🔍 Helios Anomaly Detection",
        border_style=status_color.split()[-1] if " " in status_color else status_color,
    ))
    console.print()
    
    if anomalies:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim")
        table.add_column("Metric")
        table.add_column("Severity", justify="center")
        table.add_column("Value", justify="right")
        table.add_column("Expected", justify="right")
        table.add_column("Score", justify="right")
        
        for anomaly in anomalies:
            timestamp = anomaly.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = dt.strftime("%H:%M:%S")
                except ValueError:
                    pass
            
            severity = anomaly.get("severity", "medium")
            severity_style = {
                "low": "yellow",
                "medium": "orange1",
                "high": "red",
                "critical": "bold red",
            }.get(severity, "white")
            
            table.add_row(
                timestamp,
                anomaly.get("metric", "unknown"),
                f"[{severity_style}]{severity.upper()}[/{severity_style}]",
                f"{anomaly.get('value', 0):.2%}",
                f"{anomaly.get('expected_value', 0):.2%}",
                f"{anomaly.get('anomaly_score', 0):.2f}σ",
            )
        
        console.print(table)
        console.print()
        
        # Summary by severity
        by_severity = summary.get("by_severity", {})
        if by_severity:
            console.print("[bold]Summary:[/bold]")
            for sev, count in by_severity.items():
                console.print(f"  • {sev.capitalize()}: {count}")
    else:
        console.print("[green]✓ All metrics are within normal ranges[/green]")
    
    # Show anomaly rate
    rate = summary.get("anomaly_rate", 0)
    console.print()
    console.print(f"[bold]Anomaly Rate:[/bold] {rate:.1%}")
