"""Fetch REAL metrics from Cloud Monitoring for ML training."""
import os
from datetime import datetime, timedelta

import pandas as pd
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()
project_id = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
project_name = f"projects/{project_id}"

end_time = datetime.utcnow()
start_time = end_time - timedelta(hours=6)

interval = monitoring_v3.TimeInterval(
    end_time={"seconds": int(end_time.timestamp())},
    start_time={"seconds": int(start_time.timestamp())},
)

aggregation = monitoring_v3.Aggregation(
    alignment_period={"seconds": 300},  # 5-minute intervals
    per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_MEAN,
    group_by_fields=["resource.labels.namespace_name"],
)

def fetch_metric(metric_type, namespace="saleor"):
    """Fetch a metric and return as list of records."""
    filter_str = f'metric.type = "{metric_type}" AND resource.labels.namespace_name = "{namespace}"'

    request = monitoring_v3.ListTimeSeriesRequest(
        name=project_name,
        filter=filter_str,
        interval=interval,
        aggregation=aggregation,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )

    records = []
    try:
        for ts in client.list_time_series(request=request):
            for point in ts.points:
                timestamp = point.interval.end_time
                if hasattr(timestamp, 'replace'):
                    timestamp = timestamp.replace(tzinfo=None)

                # Extract value - try different fields
                value = 0.0
                try:
                    value = point.value.double_value
                except:
                    try:
                        value = float(point.value.int64_value)
                    except:
                        try:
                            value = point.value.distribution_value.mean
                        except:
                            pass

                records.append({
                    "timestamp": timestamp,
                    "value": value,
                })
    except Exception as e:
        print(f"  Error: {e}")

    return records

# Fetch metrics for saleor namespace
print("=== Fetching Saleor Container Metrics (last 6 hours) ===\n")

all_data = []

# CPU utilization
print("1. CPU limit utilization...")
records = fetch_metric("kubernetes.io/container/cpu/limit_utilization", "saleor")
for r in records:
    r["cpu_utilization"] = r.pop("value")
    all_data.append(r)
print(f"   Found {len(records)} data points")

# Memory utilization
print("2. Memory limit utilization...")
records = fetch_metric("kubernetes.io/container/memory/limit_utilization", "saleor")
if records:
    df_mem = pd.DataFrame(records)
    df_mem = df_mem.rename(columns={"value": "memory_utilization"})
    print(f"   Found {len(records)} data points")

# Memory bytes
print("3. Memory used bytes...")
records = fetch_metric("kubernetes.io/container/memory/used_bytes", "saleor")
if records:
    df_bytes = pd.DataFrame(records)
    df_bytes["memory_mb"] = df_bytes["value"] / (1024 * 1024)
    df_bytes = df_bytes.drop(columns=["value"])
    print(f"   Found {len(records)} data points")

# Uptime
print("4. Container uptime...")
records = fetch_metric("kubernetes.io/container/uptime", "saleor")
print(f"   Found {len(records)} data points")

# Loadtest namespace
print("\n=== Fetching Loadtest Container Metrics ===\n")

print("5. Locust CPU utilization...")
records = fetch_metric("kubernetes.io/container/cpu/limit_utilization", "loadtest")
print(f"   Found {len(records)} data points")

print("6. Locust Memory utilization...")
records = fetch_metric("kubernetes.io/container/memory/limit_utilization", "loadtest")
print(f"   Found {len(records)} data points")

# Combine into DataFrame
print("\n=== Building Training DataFrame ===\n")

# Build combined dataframe
metrics_to_fetch = [
    ("kubernetes.io/container/cpu/limit_utilization", "saleor", "saleor_cpu"),
    ("kubernetes.io/container/memory/limit_utilization", "saleor", "saleor_memory"),
    ("kubernetes.io/container/cpu/limit_utilization", "loadtest", "locust_cpu"),
    ("kubernetes.io/container/memory/limit_utilization", "loadtest", "locust_memory"),
]

dfs = []
for metric, namespace, name in metrics_to_fetch:
    records = fetch_metric(metric, namespace)
    if records:
        df = pd.DataFrame(records)
        df = df.rename(columns={"value": name})
        dfs.append(df)

if dfs:
    # Merge all dataframes
    result = dfs[0]
    for df in dfs[1:]:
        result = pd.merge(result, df, on="timestamp", how="outer")

    result = result.sort_values("timestamp").reset_index(drop=True)

    print(f"Final DataFrame shape: {result.shape}")
    print(f"Columns: {list(result.columns)}")
    print("\nData sample:")
    print(result.head(10))
    print("\nData tail:")
    print(result.tail(5))

    # Save to CSV
    result.to_csv("data/training_data_real.csv", index=False)
    print("\n✓ Saved to data/training_data_real.csv")
else:
    print("No data to combine")
