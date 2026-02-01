"""Prediction commands for Helios CLI."""

import json
from datetime import datetime

import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def predict() -> None:
    """Generate resource predictions.
    
    Use these commands to forecast CPU, memory, and other resource usage
    for your Kubernetes deployments.
    
    \b
    Examples:
        helios predict cpu                    # Quick CPU prediction
        helios predict memory -d my-app       # Memory for specific app
    """
    pass


@predict.command()
@click.option("--deployment", "-d", default=None, help="Deployment name (optional)")
@click.option("--namespace", "-n", default="default", help="Kubernetes namespace")
@click.option("--periods", "-p", default=12, type=int, help="Number of prediction periods")
@click.option("--model", "-m", default="baseline", 
              type=click.Choice(["baseline", "prophet", "xgboost"]),
              help="Prediction model to use")
@click.pass_context
def cpu(ctx: click.Context, deployment: str | None, namespace: str, periods: int, model: str) -> None:
    """Predict CPU usage for a deployment.
    
    \b
    Examples:
        helios predict cpu                      # Quick prediction
        helios predict cpu -d my-app -p 24      # 24 periods ahead
        helios predict cpu --model prophet      # Use Prophet model
    """
    _run_prediction(ctx, "cpu_utilization", deployment, namespace, periods, model)


@predict.command()
@click.option("--deployment", "-d", default=None, help="Deployment name (optional)")
@click.option("--namespace", "-n", default="default", help="Kubernetes namespace")
@click.option("--periods", "-p", default=12, type=int, help="Number of prediction periods")
@click.option("--model", "-m", default="baseline",
              type=click.Choice(["baseline", "prophet", "xgboost"]),
              help="Prediction model to use")
@click.pass_context
def memory(ctx: click.Context, deployment: str | None, namespace: str, periods: int, model: str) -> None:
    """Predict memory usage for a deployment.
    
    \b
    Examples:
        helios predict memory                   # Quick prediction
        helios predict memory -d my-app -p 48   # 48 periods ahead
    """
    _run_prediction(ctx, "memory_utilization", deployment, namespace, periods, model)


def _run_prediction(ctx: click.Context, metric: str, deployment: str | None, 
                    namespace: str, periods: int, model: str) -> None:
    """Run prediction request against API."""
    endpoint = ctx.obj["endpoint"]
    api_key = ctx.obj["api_key"]
    output_format = ctx.obj["output"]
    
    metric_display = metric.replace("_", " ").title()
    
    with console.status(f"[bold blue]Fetching {metric_display} predictions..."):
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Build request matching the actual API schema
            request_body = {
                "metric": metric,
                "periods": periods,
                "model": model
            }
            
            response = httpx.post(
                f"{endpoint}/predict",
                json=request_body,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                console.print(Panel(
                    "[yellow]ML models not loaded[/yellow]\n\n"
                    "The prediction service requires trained models.\n"
                    "Run [cyan]python ml/train.py[/cyan] to train models.",
                    title="⚠️ Models Not Ready",
                    border_style="yellow"
                ))
            else:
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
        _display_prediction_table(data, metric_display, deployment or "cluster", namespace, model)


def _display_prediction_table(data: dict, metric_type: str, deployment: str | None, namespace: str, model: str) -> None:
    """Display prediction data in a formatted table."""
    console.print()
    
    info_lines = [f"[bold]{metric_type} Prediction[/bold]"]
    if deployment:
        info_lines.append(f"Deployment: [cyan]{deployment}[/cyan]")
    info_lines.append(f"Namespace: [cyan]{namespace}[/cyan]")
    info_lines.append(f"Model: [cyan]{model}[/cyan]")
    
    console.print(Panel(
        "\n".join(info_lines),
        title="🔮 Helios Prediction",
        border_style="blue",
    ))
    console.print()
    
    predictions = data.get("predictions", [])
    if predictions:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim")
        table.add_column("Predicted", justify="right")
        table.add_column("Lower Bound", justify="right", style="yellow")
        table.add_column("Upper Bound", justify="right", style="yellow")
        table.add_column("Confidence", justify="right")
        
        for pred in predictions[:10]:  # Show first 10
            timestamp = pred.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    pass
            
            value = pred.get('value') or 0
            lower = pred.get('lower_bound') or value * 0.9
            upper = pred.get('upper_bound') or value * 1.1
            confidence = pred.get('confidence') or 0.8
            
            table.add_row(
                timestamp,
                f"{value:.2%}",
                f"{lower:.2%}",
                f"{upper:.2%}",
                f"{confidence * 100:.1f}%",
            )
        
        console.print(table)
        
        if len(predictions) > 10:
            console.print(f"\n[dim]... and {len(predictions) - 10} more predictions[/dim]")
    else:
        console.print("[yellow]No predictions available[/yellow]")
    
    # Show model info
    model_info = data.get("model_info", {})
    summary = data.get("summary", {})
    if model_info or summary:
        console.print()
        console.print(f"[bold]Model:[/bold] {model_info.get('name', model)} (Accuracy: {model_info.get('accuracy', 'N/A')})")
        if summary:
            console.print()
            console.print("[bold]Summary:[/bold]")
            console.print(f"  Peak predicted: [red]{summary.get('peak', 0):.2f}[/red]")
            console.print(f"  Average: [blue]{summary.get('average', 0):.2f}[/blue]")
            console.print(f"  Trend: {summary.get('trend', 'stable')}")
