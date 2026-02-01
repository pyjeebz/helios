# Helios CLI

Command-line interface for Helios - Predictive Infrastructure Intelligence Platform.

## Installation

```bash
pip install helios-cli
```

## Quick Start

```bash
# Configure endpoint
export HELIOS_ENDPOINT="http://helios-inference:8080"

# Get CPU predictions for a deployment
helios predict cpu --deployment my-app --namespace default

# Detect anomalies
helios detect --deployment my-app --namespace default

# Get scaling recommendations
helios recommend --deployment my-app --namespace default --replicas 2
```

## Configuration

### Environment Variables

```bash
export HELIOS_ENDPOINT="http://helios-inference:8080"
```

### Configuration File

```bash
# Set endpoint
helios config set endpoint http://helios-inference:8080

# View current configuration
helios config show
```

## Commands

### `helios predict`

Forecast future resource utilization.

```bash
# Predict CPU for next 12 periods (default)
helios predict cpu --deployment my-app --namespace default

# Predict memory with custom periods
helios predict memory --deployment my-app --namespace default --periods 24

# Short flags
helios predict cpu -d my-app -n default -p 12
```

**Output:**
```
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Period      ┃ Predicted    ┃ Confidence   ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ +5min       │ 45.2%        │ ±5.1%        │
│ +10min      │ 47.8%        │ ±6.2%        │
│ ...         │ ...          │ ...          │
└─────────────┴──────────────┴──────────────┘
Model: baseline | Data points: 228
```

### `helios detect`

Detect anomalies in current metrics.

```bash
# Check for anomalies
helios detect --deployment my-app --namespace default

# Short flags
helios detect -d my-app -n default
```

**Output:**
```
╭─────────────────────────────────────────────╮
│           Anomaly Detection Report          │
├─────────────────────────────────────────────┤
│  Status: HEALTHY                            │
│  Anomaly Rate: 0.0%                         │
│  Data Points: 12                            │
╰─────────────────────────────────────────────╯
```

### `helios recommend`

Get scaling recommendations based on predictions.

```bash
# Get recommendations for current replicas
helios recommend --deployment my-app --namespace default --replicas 2

# Short flags
helios recommend -d my-app -n default -r 2
```

**Output:**
```
╭─────────────────────────────────────────────╮
│          Scaling Recommendations            │
├─────────────────────────────────────────────┤
│  SCALE OUT: 2 → 3 replicas (54%)            │
│  Predicted Utilization: 87.2%               │
│                                             │
│  Resource Adjustments:                      │
│  • CPU: 100m → 150m                         │
│  • Memory: 256Mi (no change)                │
╰─────────────────────────────────────────────╯
```

### `helios status`

Check connection to Helios inference service.

```bash
helios status
```

**Output:**
```
Helios Inference Service
  Endpoint: http://helios-inference:8080
  Status: Connected ✓
  Models: 3 loaded (baseline, prophet, xgboost)
```

## Options

### Global Options

| Option | Description |
|--------|-------------|
| `--endpoint`, `-e` | Override HELIOS_ENDPOINT |
| `--format`, `-f` | Output format: `table`, `json`, `yaml` |
| `--verbose`, `-v` | Enable verbose output |
| `--help` | Show help message |

### Predict Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--deployment` | `-d` | Deployment name | Required |
| `--namespace` | `-n` | Kubernetes namespace | `default` |
| `--periods` | `-p` | Forecast periods | `12` |
| `--model` | `-m` | Model to use | `baseline` |

### Detect Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--deployment` | `-d` | Deployment name | Required |
| `--namespace` | `-n` | Kubernetes namespace | `default` |
| `--threshold` | `-t` | Anomaly threshold | `2.5` sigma |

### Recommend Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--deployment` | `-d` | Deployment name | Required |
| `--namespace` | `-n` | Kubernetes namespace | `default` |
| `--replicas` | `-r` | Current replica count | Required |

## JSON Output

All commands support JSON output for scripting:

```bash
# Get predictions as JSON
helios predict cpu -d my-app -n default -f json

# Parse with jq
helios recommend -d my-app -n default -r 2 -f json | jq '.recommended_replicas'
```

## Examples

### CI/CD Integration

```bash
#!/bin/bash
# Check if scaling is needed before deployment

RECOMMENDATION=$(helios recommend -d my-app -n prod -r 2 -f json)
SCALE_ACTION=$(echo $RECOMMENDATION | jq -r '.action')

if [ "$SCALE_ACTION" = "scale_out" ]; then
  NEW_REPLICAS=$(echo $RECOMMENDATION | jq -r '.recommended_replicas')
  kubectl scale deployment my-app -n prod --replicas=$NEW_REPLICAS
fi
```

### Monitoring Script

```bash
#!/bin/bash
# Alert on anomalies

RESULT=$(helios detect -d my-app -n prod -f json)
STATUS=$(echo $RESULT | jq -r '.status')

if [ "$STATUS" = "ANOMALY" ]; then
  # Send alert
  curl -X POST $SLACK_WEBHOOK -d "{\"text\": \"Anomaly detected in my-app!\"}"
fi
```

## Troubleshooting

### Connection Errors

```bash
# Check endpoint is reachable
curl http://helios-inference:8080/health

# Verify environment variable
echo $HELIOS_ENDPOINT
```

### No Data

If predictions return empty results:

1. Ensure the agent is collecting metrics for the deployment
2. Check the namespace matches
3. Verify metrics are being ingested: `curl http://helios-inference:8080/models`

## License

Apache 2.0
