"""
Cloud Monitoring Data Fetcher

Fetches time-series metrics from GCP Cloud Monitoring API for ML training.
"""

import sys
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from google.cloud import monitoring_v3

sys.path.append("..")
from config import config

# Metric type to aligner mapping
# CUMULATIVE metrics need ALIGN_RATE or ALIGN_DELTA
# GAUGE metrics can use ALIGN_MEAN
METRIC_ALIGNERS = {
    # GKE container metrics
    "kubernetes.io/container/cpu/core_usage_time": "ALIGN_RATE",
    "kubernetes.io/container/memory/used_bytes": "ALIGN_MEAN",
    "kubernetes.io/container/restart_count": "ALIGN_DELTA",
    "kubernetes.io/container/cpu/limit_utilization": "ALIGN_MEAN",
    "kubernetes.io/container/memory/limit_utilization": "ALIGN_MEAN",
    # Cloud SQL
    "cloudsql.googleapis.com/database/cpu/utilization": "ALIGN_MEAN",
    "cloudsql.googleapis.com/database/memory/utilization": "ALIGN_MEAN",
    "cloudsql.googleapis.com/database/postgresql/num_backends": "ALIGN_MEAN",
    # Redis
    "redis.googleapis.com/stats/memory/usage_ratio": "ALIGN_MEAN",
    "redis.googleapis.com/stats/connected_clients": "ALIGN_MEAN",
}


class CloudMonitoringFetcher:
    """
    Fetches metrics from GCP Cloud Monitoring.

    Supports:
    - GKE container metrics (CPU, memory)
    - Cloud SQL metrics
    - Redis/Memorystore metrics
    - Prometheus metrics via GKE Managed Prometheus
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the fetcher.

        Args:
            project_id: GCP project ID. Defaults to config value.
        """
        self.project_id = project_id or config.gcp.project_id
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{self.project_id}"

    def _get_aligner(self, metric_type: str) -> monitoring_v3.Aggregation.Aligner:
        """Get the appropriate aligner for a metric type."""
        aligner_name = METRIC_ALIGNERS.get(metric_type, "ALIGN_MEAN")
        return getattr(monitoring_v3.Aggregation.Aligner, aligner_name)

    def _timestamp_to_datetime(self, ts) -> datetime:
        """Convert protobuf timestamp or DatetimeWithNanoseconds to datetime."""
        try:
            # If it has a replace method, it's datetime-like
            if hasattr(ts, 'replace'):
                return ts.replace(tzinfo=None)
            # If it has seconds attribute, convert from epoch
            elif hasattr(ts, 'seconds'):
                return datetime.utcfromtimestamp(ts.seconds)
            else:
                return ts
        except Exception:
            return datetime.utcnow()

    def fetch_metric(
        self,
        metric_type: str,
        hours: int = 6,
        aggregation_minutes: int = 5,
        filters: Optional[dict[str, str]] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch a single metric type as a DataFrame.

        Args:
            metric_type: Full metric type (e.g., "kubernetes.io/container/cpu/core_usage_time")
            hours: Hours of historical data to fetch
            aggregation_minutes: Aggregation window in minutes
            filters: Additional metric filters (e.g., {"resource.labels.namespace_name": "saleor"})
            end_time: End time for the query. Defaults to now.

        Returns:
            DataFrame with columns: timestamp, value, and any label columns
        """
        now = datetime.utcnow()
        end_time = end_time or now
        start_time = end_time - timedelta(hours=hours)

        # Build the filter string
        filter_parts = [f'metric.type = "{metric_type}"']
        if filters:
            for key, value in filters.items():
                filter_parts.append(f'{key} = "{value}"')
        filter_str = " AND ".join(filter_parts)

        # Create time interval using seconds since epoch
        interval = monitoring_v3.TimeInterval(
            end_time={"seconds": int(end_time.timestamp())},
            start_time={"seconds": int(start_time.timestamp())},
        )

        # Get appropriate aligner for this metric type
        aligner = self._get_aligner(metric_type)

        # Create aggregation
        aggregation = monitoring_v3.Aggregation(
            alignment_period={"seconds": aggregation_minutes * 60},
            per_series_aligner=aligner,
        )

        # Make the request
        request = monitoring_v3.ListTimeSeriesRequest(
            name=self.project_name,
            filter=filter_str,
            interval=interval,
            aggregation=aggregation,
            view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        )

        # Parse results into DataFrame
        records = []
        try:
            results = self.client.list_time_series(request=request)
            for ts in results:
                labels = dict(ts.metric.labels)
                labels.update({f"resource_{k}": v for k, v in ts.resource.labels.items()})

                for point in ts.points:
                    timestamp = self._timestamp_to_datetime(point.interval.end_time)
                    record = {
                        "timestamp": timestamp,
                        "value": self._extract_value(point.value),
                        "metric_type": metric_type,
                        **labels
                    }
                    records.append(record)
        except Exception as e:
            print(f"Warning: Failed to fetch {metric_type}: {e}")
            return pd.DataFrame()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def _extract_value(self, typed_value) -> float:
        """Extract numeric value from TypedValue."""
        # Try different value fields (proto3 doesn't have HasField for scalars)
        try:
            return typed_value.double_value
        except:
            pass
        try:
            return float(typed_value.int64_value)
        except:
            pass
        try:
            return typed_value.distribution_value.mean
        except:
            pass
        return 0.0

    def fetch_container_metrics(
        self,
        namespace: str = "saleor",
        hours: int = 6,
    ) -> pd.DataFrame:
        """
        Fetch GKE container metrics for a namespace.

        Returns DataFrame with CPU and memory usage.
        """
        filters = {"resource.labels.namespace_name": namespace}

        # Use GAUGE metrics that work with ALIGN_MEAN
        metrics_to_fetch = [
            ("kubernetes.io/container/memory/used_bytes", "memory_bytes"),
            ("kubernetes.io/container/cpu/limit_utilization", "cpu_utilization"),
            ("kubernetes.io/container/memory/limit_utilization", "memory_utilization"),
        ]

        dfs = []
        for metric, name in metrics_to_fetch:
            df = self.fetch_metric(metric, hours=hours, filters=filters)
            if not df.empty:
                # Aggregate across containers (take mean per timestamp)
                df_agg = df.groupby("timestamp")["value"].mean().reset_index()
                df_agg = df_agg.rename(columns={"value": name})
                dfs.append(df_agg)

        if not dfs:
            return pd.DataFrame()

        # Merge on timestamp
        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on="timestamp", how="outer")

        return result.sort_values("timestamp").reset_index(drop=True)

    def fetch_locust_metrics(self, hours: int = 6) -> pd.DataFrame:
        """
        Fetch Locust load testing metrics from GKE Managed Prometheus.

        Returns DataFrame with RPS, latency, user counts.
        """
        # Try different Prometheus metric patterns
        prometheus_metrics = [
            ("prometheus.googleapis.com/locust_requests_current_rps/gauge", "rps"),
            ("prometheus.googleapis.com/locust_users/gauge", "users"),
            ("prometheus.googleapis.com/locust_response_times/histogram", "latency"),
        ]

        dfs = []
        for metric, name in prometheus_metrics:
            df = self.fetch_metric(metric, hours=hours)
            if not df.empty:
                df_agg = df.groupby("timestamp")["value"].mean().reset_index()
                df_agg = df_agg.rename(columns={"value": name})
                dfs.append(df_agg)

        if not dfs:
            return pd.DataFrame()

        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on="timestamp", how="outer")

        return result.sort_values("timestamp").reset_index(drop=True)

    def fetch_cloudsql_metrics(self, hours: int = 6) -> pd.DataFrame:
        """Fetch Cloud SQL database metrics."""
        metrics_to_fetch = [
            ("cloudsql.googleapis.com/database/cpu/utilization", "db_cpu"),
            ("cloudsql.googleapis.com/database/memory/utilization", "db_memory"),
            ("cloudsql.googleapis.com/database/postgresql/num_backends", "db_connections"),
        ]

        dfs = []
        for metric, name in metrics_to_fetch:
            df = self.fetch_metric(metric, hours=hours)
            if not df.empty:
                df_agg = df.groupby("timestamp")["value"].mean().reset_index()
                df_agg = df_agg.rename(columns={"value": name})
                dfs.append(df_agg)

        if not dfs:
            return pd.DataFrame()

        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on="timestamp", how="outer")

        return result.sort_values("timestamp").reset_index(drop=True)

    def fetch_all_metrics(
        self,
        hours: int = 6,
        namespace: str = "saleor"
    ) -> pd.DataFrame:
        """
        Fetch all relevant metrics and combine into a single DataFrame.

        This is the main method for ML training data.
        """
        print(f"Fetching {hours} hours of metrics for namespace '{namespace}'...")

        # Fetch each metric category
        container_df = self.fetch_container_metrics(namespace, hours)
        locust_df = self.fetch_locust_metrics(hours)
        db_df = self.fetch_cloudsql_metrics(hours)

        # Round timestamps to nearest minute for better merging
        def round_timestamps(df):
            if df.empty or "timestamp" not in df.columns:
                return df
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.floor("5min")
            # Aggregate if multiple rows per rounded timestamp
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                df = df.groupby("timestamp")[numeric_cols].mean().reset_index()
            return df

        container_df = round_timestamps(container_df)
        locust_df = round_timestamps(locust_df)
        db_df = round_timestamps(db_df)

        # Collect all non-empty dataframes
        all_dfs = []
        if not container_df.empty:
            all_dfs.append(("container", container_df))
            print(f"  ✓ Container metrics: {len(container_df)} points")
        if not locust_df.empty:
            all_dfs.append(("locust", locust_df))
            print(f"  ✓ Locust metrics: {len(locust_df)} points")
        if not db_df.empty:
            all_dfs.append(("db", db_df))
            print(f"  ✓ Database metrics: {len(db_df)} points")

        if not all_dfs:
            print("Warning: No metrics found from Cloud Monitoring")
            return pd.DataFrame()

        # Start with first dataframe
        result = all_dfs[0][1].copy()

        # Merge remaining dataframes
        for name, df in all_dfs[1:]:
            result = pd.merge(result, df, on="timestamp", how="outer")

        result = result.sort_values("timestamp").reset_index(drop=True)
        print(f"Fetched {len(result)} data points with {len(result.columns)} features")

        return result


def fetch_training_data(hours: int = 6, namespace: str = "saleor") -> pd.DataFrame:
    """
    Fetch training data for ML models.

    Args:
        hours: Hours of historical data
        namespace: Kubernetes namespace to focus on

    Returns:
        DataFrame ready for feature engineering
    """
    fetcher = CloudMonitoringFetcher()
    return fetcher.fetch_all_metrics(hours=hours, namespace=namespace)


if __name__ == "__main__":
    # Test the fetcher
    print("Testing Cloud Monitoring Fetcher...")
    df = fetch_training_data(hours=1)

    if df.empty:
        print("\nNo data from Cloud Monitoring. This could mean:")
        print("  1. GKE cluster has no recent activity")
        print("  2. Metrics haven't propagated yet (wait 5-10 min)")
        print("  3. Authentication issue (check gcloud auth)")
    else:
        print(f"\nData shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
