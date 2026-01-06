"""Main CLI entry point for Helios."""

import click
from rich.console import Console

from helios_cli import __version__
from helios_cli.commands import predict, detect, recommend, status, config, agent

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="helios")
@click.option(
    "--endpoint",
    "-e",
    envvar="HELIOS_ENDPOINT",
    default="http://localhost:8000",
    help="Helios API endpoint URL",
)
@click.option(
    "--api-key",
    envvar="HELIOS_API_KEY",
    default=None,
    help="API key for authentication",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
@click.pass_context
def cli(ctx: click.Context, endpoint: str, api_key: str | None, output: str) -> None:
    """Helios CLI - Predictive Infrastructure Intelligence Platform.
    
    ML-powered resource forecasting and anomaly detection for Kubernetes.
    
    Examples:
    
        # Get CPU prediction for a deployment
        helios predict cpu --deployment my-app --namespace default
        
        # Detect anomalies in current metrics
        helios detect --deployment my-app
        
        # Get scaling recommendations
        helios recommend --deployment my-app
        
        # Check Helios service status
        helios status
    """
    ctx.ensure_object(dict)
    ctx.obj["endpoint"] = endpoint
    ctx.obj["api_key"] = api_key
    ctx.obj["output"] = output


# Register commands
cli.add_command(predict.predict)
cli.add_command(detect.detect)
cli.add_command(recommend.recommend)
cli.add_command(status.status)
cli.add_command(config.config)
cli.add_command(agent.agent)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
