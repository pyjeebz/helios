"""
Locust load testing for Helios Inference Service.

Run with:
    locust -f locustfile.py --host=http://localhost:8080

Or headless:
    locust -f locustfile.py --host=http://localhost:8080 --headless -u 50 -r 10 -t 60s
"""

import random

from locust import HttpUser, between, task


class HeliosInferenceUser(HttpUser):
    """Simulates user behavior against the inference service."""

    wait_time = between(0.1, 0.5)  # Fast requests for load testing

    @task(10)
    def health_check(self):
        """High frequency health checks (simulates k8s probes)."""
        self.client.get("/health")

    @task(5)
    def ready_check(self):
        """Readiness checks."""
        self.client.get("/ready")

    @task(20)
    def predict_cpu(self):
        """CPU utilization predictions - most common request."""
        payload = {
            "metric": "cpu_utilization",
            "model": "baseline",
            "periods": random.choice([6, 12, 24])
        }
        self.client.post("/predict", json=payload)

    @task(15)
    def predict_memory(self):
        """Memory utilization predictions."""
        payload = {
            "metric": "memory_utilization",
            "model": "baseline",
            "periods": random.choice([6, 12, 24])
        }
        self.client.post("/predict", json=payload)

    @task(10)
    def batch_predict(self):
        """Batch predictions for multiple metrics."""
        payload = {
            "metrics": ["cpu_utilization", "memory_utilization"],
            "model": "baseline",
            "periods": 12
        }
        self.client.post("/predict/batch", json=payload)

    @task(8)
    def detect_anomalies(self):
        """Anomaly detection requests."""
        # Generate synthetic time series with occasional anomaly
        data_points = []
        base_value = random.uniform(0.1, 0.3)
        for i in range(20):
            value = base_value + random.uniform(-0.05, 0.05)
            # 10% chance of anomaly
            if random.random() < 0.1:
                value = random.uniform(0.8, 1.0)
            data_points.append({
                "timestamp": f"2026-01-02T{10+i//6:02d}:{(i%6)*10:02d}:00Z",
                "value": value
            })

        payload = {
            "metrics": {
                "cpu_utilization": data_points
            },
            "threshold_sigma": 2.5
        }
        self.client.post("/detect", json=payload)

    @task(5)
    def get_recommendations(self):
        """Scaling recommendations."""
        payload = {
            "workload": random.choice(["saleor-api", "saleor-worker", "helios-inference"]),
            "namespace": random.choice(["saleor", "helios"]),
            "current_state": {
                "replicas": random.randint(1, 5),
                "cpu_request": random.choice(["100m", "250m", "500m"]),
                "memory_request": random.choice(["256Mi", "512Mi", "1Gi"]),
                "cpu_limit": "1000m",
                "memory_limit": "2Gi"
            },
            "target_utilization": 0.7
        }
        self.client.post("/recommend", json=payload)

    @task(2)
    def list_models(self):
        """List loaded models."""
        self.client.get("/models")


class HighLoadUser(HttpUser):
    """Aggressive user for stress testing."""

    wait_time = between(0.01, 0.1)  # Very fast

    @task
    def rapid_predictions(self):
        """Rapid-fire prediction requests."""
        payload = {
            "metric": random.choice(["cpu_utilization", "memory_utilization"]),
            "model": "baseline",
            "periods": 6
        }
        self.client.post("/predict", json=payload)
