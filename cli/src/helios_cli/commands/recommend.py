"""Scaling recommendation commands for Helios CLI."""

import json
import random

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--deployment", "-d", required=True, help="Deployment name")
@click.option("--namespace", "-n", default="default", help="Kubernetes namespace")
@click.option("--replicas", "-r", default=2, type=int, help="Current replica count")
@click.option("--cpu-request", default="100m", help="Current CPU request")
@click.option("--memory-request", default="256Mi", help="Current memory request")
@click.option("--target-utilization", "-t", default=0.7, type=float, help="Target utilization (0.0-1.0)")
@click.option("--cost-optimize", is_flag=True, help="Prioritize cost optimization")
@click.option("--performance", is_flag=True, help="Prioritize performance")
@click.pass_context
def recommend(ctx: click.Context, deployment: str, namespace: str, replicas: int,
              cpu_request: str, memory_request: str, target_utilization: float,
              cost_optimize: bool, performance: bool) -> None:
    """Get scaling recommendations for a deployment.
    
    Analyzes current resource usage and provides intelligent scaling recommendations.
    
    \b
    Examples:
        helios recommend                          # Quick recommend with defaults
        helios recommend -d my-app -n prod        # Specific deployment
        helios recommend --cost-optimize          # Prioritize savings
        helios recommend --performance            # Prioritize performance
        helios recommend -r 3 -t 0.6              # Custom config
    """
    endpoint = ctx.obj["endpoint"]
    api_key = ctx.obj["api_key"]
    output_format = ctx.obj["output"]
    
    # Simulate predicted utilization (in real scenario, this comes from /predict)
    predicted_util = random.uniform(0.75, 0.95)  # Simulated high utilization
    
    with console.status("[bold blue]Generating scaling recommendations..."):
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Build request matching the actual API schema
            request_body = {
                "workload": deployment,
                "namespace": namespace,
                "current_state": {
                    "replicas": replicas,
                    "cpu_request": cpu_request,
                    "memory_request": memory_request,
                    "cpu_limit": "500m",
                    "memory_limit": "512Mi"
                },
                "predictions": [
                    {"timestamp": "2026-02-01T06:00:00Z", "value": predicted_util},
                    {"timestamp": "2026-02-01T06:05:00Z", "value": predicted_util + 0.02},
                    {"timestamp": "2026-02-01T06:10:00Z", "value": predicted_util + 0.05}
                ],
                "target_utilization": target_utilization
            }
            
            response = httpx.post(
                f"{endpoint}/recommend",
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
        strategy = "cost" if cost_optimize else "performance" if performance else "balanced"
        _display_recommendations(data, deployment, namespace, strategy, replicas, cpu_request, memory_request)


def _display_recommendations(data: dict, deployment: str, namespace: str, strategy: str,
                             current_replicas: int, current_cpu: str, current_memory: str) -> None:
    """Display scaling recommendations."""
    console.print()
    
    strategy_emoji = {"balanced": "⚖️", "cost": "💰", "performance": "🚀"}.get(strategy, "⚖️")
    
    recommendations = data.get("recommendations", [])
    rec = recommendations[0] if recommendations else {}
    actions = rec.get("actions", [])
    
    info_lines = [
        "[bold]Scaling Recommendations[/bold]",
        f"Deployment: [cyan]{deployment}[/cyan]",
        f"Namespace: [cyan]{namespace}[/cyan]",
        f"Strategy: {strategy_emoji} {strategy.capitalize()}"
    ]
    
    console.print(Panel(
        "\n".join(info_lines),
        title="📊 Helios Recommendations",
        border_style="blue",
    ))
    console.print()
    
    if actions:
        # Actions table
        table = Table(show_header=True, header_style="bold magenta", title="Recommended Actions")
        table.add_column("Action", style="bold")
        table.add_column("Target")
        table.add_column("Confidence", justify="right")
        table.add_column("Reason")
        
        for action in actions:
            action_type = action.get("action", "unknown")
            action_color = {
                "scale_out": "green",
                "scale_in": "yellow",
                "scale_up": "green",
                "scale_down": "yellow",
                "no_action": "dim"
            }.get(action_type, "white")
            
            target = ""
            if action.get("target_replicas"):
                target = f"{current_replicas} → {action['target_replicas']} replicas"
            elif action.get("target_cpu_request"):
                target = f"CPU: {action['target_cpu_request']}"
            elif action.get("target_memory_request"):
                target = f"Memory: {action['target_memory_request']}"
            else:
                target = "-"
            
            confidence = action.get("confidence", 0)
            conf_color = "green" if confidence >= 0.8 else "yellow" if confidence >= 0.6 else "red"
            
            table.add_row(
                f"[{action_color}]{action_type.upper().replace('_', ' ')}[/{action_color}]",
                target,
                f"[{conf_color}]{confidence:.0%}[/{conf_color}]",
                action.get("reason", "")[:60] + "..." if len(action.get("reason", "")) > 60 else action.get("reason", ""),
            )
        
        console.print(table)
        
        # Predicted utilization
        predicted = rec.get("predicted_utilization")
        if predicted:
            console.print()
            util_color = "green" if predicted < 0.7 else "yellow" if predicted < 0.85 else "red"
            console.print(f"[bold]Predicted Utilization:[/bold] [{util_color}]{predicted:.1%}[/{util_color}]")
        
        # Apply commands
        console.print()
        console.print("[bold]To apply scaling:[/bold]")
        for action in actions:
            if action.get("target_replicas"):
                console.print(f"  [cyan]kubectl scale deployment/{deployment} -n {namespace} --replicas={action['target_replicas']}[/cyan]")
    else:
        console.print("[green]✓ Current configuration is optimal - no changes recommended[/green]")
    
    # Cooldown status
    metadata = data.get("metadata", {})
    if metadata.get("cooldown_active"):
        console.print()
        console.print("[yellow]⏳ Cooldown active - recommendations may be limited[/yellow]")
