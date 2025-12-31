# Helios Load Testing with Locust

Load testing suite for generating realistic e-commerce traffic patterns that Helios can learn from.

## Quick Start

### Local Development

```powershell
# Install dependencies
cd loadtest
pip install -r requirements.txt

# Run with web UI (interactive)
cd locustfiles
locust -f locustfile.py --host=http://localhost:8000

# Open http://localhost:8089 in browser
```

### Kubernetes Deployment

```powershell
# Deploy Locust to cluster
kubectl apply -k infra/kubernetes/locust/base

# Port forward the web UI
kubectl port-forward -n loadtest svc/locust-master 8089:8089

# Open http://localhost:8089
```

## Traffic Patterns

### 1. Mixed Traffic (Default)
Realistic mix of user personas:
- **Browsers (50%)**: Casual browsing, category views, product listing
- **Searchers (25%)**: Heavy search, filtering, sorting
- **Buyers (20%)**: Add to cart, checkout flow
- **Admins (5%)**: Product management (write-heavy)

```powershell
locust -f locustfile.py --host=http://localhost:8000
```

### 2. Read-Heavy Mode
For testing cache effectiveness and read scaling:

```powershell
locust -f read_heavy.py --host=http://localhost:8000
```

### 3. Write-Heavy Mode
For testing database write scaling:

```powershell
locust -f write_heavy.py --host=http://localhost:8000
```

## Load Shapes (ML Training Patterns)

### Ramp Pattern (Trend Detection)
Gradual growth followed by plateau and decline:

```powershell
locust -f ramp_pattern.py --host=http://localhost:8000 --headless -t 20m
```

Pattern: `0 → 100 users (5min) → hold (10min) → 0 users (5min)`

### Wave Pattern (Seasonality Detection)
Sinusoidal oscillation simulating daily cycles:

```powershell
locust -f wave_pattern.py --host=http://localhost:8000 --headless -t 30m
```

Pattern: `10 ↔ 100 users, 5-minute cycles, 6 cycles total`

### Spike Pattern (Anomaly Detection)
Flash-sale bursts with recovery periods:

```powershell
locust -f spike_pattern.py --host=http://localhost:8000 --headless -t 20m
```

Pattern: `baseline(20) → spike(200) → recovery, 3 cycles`

## Headless Mode (CI/CD)

Run without web UI for automated testing:

```powershell
# 50 users, 5/sec spawn rate, 10 minute duration
locust -f locustfile.py --host=http://localhost:8000 \
    --headless -u 50 -r 5 -t 10m \
    --csv=results/test
```

## Metrics Output

Locust generates metrics in multiple formats:

### CSV Reports
```
--csv=results/test
```
Generates:
- `test_stats.csv` - Request statistics
- `test_failures.csv` - Failed requests
- `test_stats_history.csv` - Time-series data
- `test_exceptions.csv` - Exceptions

### JSON Report (Single File)
```
--json
```

### Prometheus Metrics
The Locust web UI exposes metrics at `/metrics` in Prometheus format.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCUST_HOST` | - | Target API URL |
| `ADMIN_EMAIL` | admin@example.com | Admin user email |
| `ADMIN_PASSWORD` | admin123456 | Admin user password |
| `LOCUST_USERS` | 50 | Number of simulated users |
| `LOCUST_SPAWN_RATE` | 5 | Users spawned per second |
| `LOCUST_RUN_TIME` | 30m | Test duration |

## Project Structure

```
loadtest/
├── Dockerfile              # Container image
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── locustfiles/
    ├── locustfile.py      # Combined (default)
    ├── read_heavy.py      # Read-focused
    ├── write_heavy.py     # Write-focused
    ├── ramp_pattern.py    # Ramp shape
    ├── wave_pattern.py    # Wave shape
    ├── spike_pattern.py   # Spike shape
    ├── common/
    │   ├── __init__.py
    │   ├── utils.py       # Helpers
    │   └── graphql_client.py  # Saleor queries
    ├── personas/
    │   ├── __init__.py
    │   ├── browser.py     # Casual browsing
    │   ├── searcher.py    # Search-heavy
    │   ├── buyer.py       # Purchase flow
    │   └── admin.py       # Admin ops
    └── shapes/
        ├── __init__.py
        └── load_shapes.py  # Custom shapes
```

## Scaling Workers (Kubernetes)

For higher load, scale the worker pods:

```powershell
kubectl scale deployment locust-worker -n loadtest --replicas=5
```

Each worker can simulate ~500-1000 users depending on resources.

## Integration with Helios

The generated traffic produces:
1. **QPS metrics** - Requests per second by endpoint
2. **Latency distributions** - p50, p95, p99 response times
3. **Error rates** - Failed request percentages
4. **Throughput patterns** - Time-series data for ML training

These metrics feed into Helios for:
- Trend detection and forecasting
- Anomaly detection
- Capacity planning predictions
- Auto-scaling decisions
