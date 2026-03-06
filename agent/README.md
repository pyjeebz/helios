# Prescale Agent

Metrics collection agent for [Prescale](https://github.com/pyjeebz/prescale) - Predictive Infrastructure Intelligence Platform.

## Installation

```bash
# Base installation (system metrics + Prometheus)
pip install prescale-agent

# With specific backends
pip install prescale-agent[gcp]      # + GCP Cloud Monitoring
pip install prescale-agent[aws]      # + AWS CloudWatch
pip install prescale-agent[azure]    # + Azure Monitor
pip install prescale-agent[datadog]  # + Datadog
pip install prescale-agent[all]      # All backends
```

## Quick Start

```bash
# Generate configuration file
prescale-agent init

# List available metric sources
prescale-agent sources

# Test configured sources
prescale-agent test

# Run the agent
prescale-agent run --config prescale-agent.yaml
```

## Configuration

Create a `prescale-agent.yaml` file:

```yaml
agent:
  collection_interval: 60
  log_level: INFO

sources:
  # System metrics (always available)
  - type: system
    enabled: true
    config:
      collect_cpu: true
      collect_memory: true

  # GCP Cloud Monitoring
  - type: gcp-monitoring
    enabled: true
    config:
      project_id: your-gcp-project
      metrics:
        - kubernetes.io/container/cpu/limit_utilization
        - kubernetes.io/container/memory/limit_utilization

  # Prometheus
  - type: prometheus
    enabled: false
    config:
      url: http://prometheus:9090
      queries:
        - name: cpu_usage
          query: rate(container_cpu_usage_seconds_total[5m])

prescale:
  endpoint: http://prescale-inference:8080
```

## Supported Sources

| Source | Description | Extra Install |
|--------|-------------|---------------|
| `system` | Local CPU, memory, disk via psutil | Built-in |
| `prometheus` | Query Prometheus server | Built-in |
| `gcp-monitoring` | GCP Cloud Monitoring | `[gcp]` |
| `cloudwatch` | AWS CloudWatch | `[aws]` |
| `azure-monitor` | Azure Monitor | `[azure]` |
| `datadog` | Datadog API | `[datadog]` |

## CLI Commands

```bash
prescale-agent init              # Generate config file
prescale-agent run               # Start collecting metrics
prescale-agent run --once        # Single collection (testing)
prescale-agent run --deployment my-deployment  # Associate with deployment
prescale-agent sources           # List available sources
prescale-agent test              # Test source connections
prescale-agent status            # Show agent status
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PRESCALE_CONFIG_FILE` | Path to config file (default: `./prescale-agent.yaml`) |
| `PRESCALE_ENDPOINT` | Prescale inference endpoint |
| `PRESCALE_API_KEY` | API key for authentication |

## License

Apache 2.0 - See [LICENSE](../LICENSE)
