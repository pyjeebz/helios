"""Tests for Helios Inference Service."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from ml.inference.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "models_loaded" in data
        assert "uptime_seconds" in data

    def test_readiness_check(self, client):
        """Test /ready endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200

        data = response.json()
        assert "ready" in data
        assert "models_ready" in data
        assert "details" in data

    def test_list_models(self, client):
        """Test /models endpoint."""
        response = client.get("/models")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_root_endpoint(self, client):
        """Test / endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "helios-inference"
        assert "version" in data


class TestPredictionEndpoints:
    """Test prediction endpoints."""

    def test_predict_baseline(self, client):
        """Test POST /predict with baseline model."""
        request = {
            "metric": "cpu_utilization",
            "periods": 6,
            "model": "baseline",
            "include_confidence": True
        }

        response = client.post("/predict", json=request)
        # May return 503 if models not loaded in test env, or 200 if loaded
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["metric"] == "cpu_utilization"
            assert data["model"] == "baseline"
            assert data["periods"] == 6
            assert len(data["predictions"]) == 6

            # Check prediction structure
            pred = data["predictions"][0]
            assert "timestamp" in pred
            assert "value" in pred

    def test_predict_invalid_metric(self, client):
        """Test prediction with invalid metric."""
        request = {
            "metric": "invalid_metric",
            "periods": 6,
            "model": "baseline"
        }

        response = client.post("/predict", json=request)
        assert response.status_code == 422  # Validation error

    def test_predict_invalid_periods(self, client):
        """Test prediction with invalid periods."""
        request = {
            "metric": "cpu_utilization",
            "periods": 0,  # Invalid
            "model": "baseline"
        }

        response = client.post("/predict", json=request)
        assert response.status_code == 422

    def test_batch_predict(self, client):
        """Test POST /predict/batch."""
        request = {
            "metrics": ["cpu_utilization", "memory_utilization"],
            "periods": 6,
            "model": "baseline"
        }

        response = client.post("/predict/batch", json=request)
        # May return 503 if models not loaded in test env
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "predictions" in data
            assert "cpu_utilization" in data["predictions"]
            assert "memory_utilization" in data["predictions"]


class TestAnomalyDetection:
    """Test anomaly detection endpoints."""

    def test_detect_anomalies(self, client):
        """Test POST /detect."""
        # Create test data with an obvious anomaly
        base_time = datetime.utcnow()
        data_points = []

        # Normal values
        for i in range(20):
            data_points.append({
                "timestamp": (base_time + timedelta(minutes=i*5)).isoformat(),
                "value": 0.15 + (i % 3) * 0.02  # Values around 0.15-0.19
            })

        # Add anomaly
        data_points.append({
            "timestamp": (base_time + timedelta(minutes=100)).isoformat(),
            "value": 0.95  # Obvious anomaly
        })

        request = {
            "metrics": {
                "cpu_utilization": data_points
            },
            "threshold_sigma": 2.5
        }

        response = client.post("/detect", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "data_points_analyzed" in data
        assert "anomalies_detected" in data
        assert "anomalies" in data
        assert "summary" in data

        # Should detect at least one anomaly
        assert data["anomalies_detected"] >= 1

    def test_detect_no_anomalies(self, client):
        """Test detection with normal data."""
        base_time = datetime.utcnow()
        data_points = []

        # All normal values
        for i in range(20):
            data_points.append({
                "timestamp": (base_time + timedelta(minutes=i*5)).isoformat(),
                "value": 0.15
            })

        request = {
            "metrics": {
                "cpu_utilization": data_points
            },
            "threshold_sigma": 2.5
        }

        response = client.post("/detect", json=request)
        assert response.status_code == 200

        data = response.json()
        assert data["anomalies_detected"] == 0


class TestRecommendations:
    """Test recommendation endpoints."""

    def test_get_recommendation(self, client):
        """Test POST /recommend."""
        request = {
            "workload": "saleor-api",
            "namespace": "saleor",
            "current_state": {
                "replicas": 3,
                "cpu_request": "100m",
                "memory_request": "256Mi",
                "cpu_limit": "500m",
                "memory_limit": "512Mi"
            },
            "target_utilization": 0.7
        }

        response = client.post("/recommend", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) > 0

        rec = data["recommendations"][0]
        assert rec["workload"] == "saleor-api"
        assert rec["namespace"] == "saleor"
        assert "actions" in rec
        assert len(rec["actions"]) > 0

        # Check action structure
        action = rec["actions"][0]
        assert "action" in action
        assert "confidence" in action
        assert "reason" in action

    def test_recommendation_with_predictions(self, client):
        """Test recommendation with prediction data."""
        base_time = datetime.utcnow()
        predictions = [
            {
                "timestamp": (base_time + timedelta(minutes=i*5)).isoformat(),
                "value": 0.85 + i * 0.02,  # Increasing utilization
                "lower_bound": 0.80,
                "upper_bound": 0.95
            }
            for i in range(6)
        ]

        request = {
            "workload": "saleor-api",
            "namespace": "saleor",
            "current_state": {
                "replicas": 2,
                "cpu_request": "100m",
                "memory_request": "256Mi",
                "cpu_limit": "500m",
                "memory_limit": "512Mi"
            },
            "predictions": predictions,
            "target_utilization": 0.7
        }

        response = client.post("/recommend", json=request)
        assert response.status_code == 200


class TestMetrics:
    """Test metrics endpoint."""

    def test_prometheus_metrics(self, client):
        """Test /metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200

        # Check content type
        assert "text/plain" in response.headers["content-type"]

        # Check for expected metrics
        content = response.text
        assert "helios_" in content
        assert "helios_up" in content or "helios_requests_total" in content


class TestStats:
    """Test statistics endpoint."""

    def test_stats_endpoint(self, client):
        """Test /stats endpoint."""
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "uptime_seconds" in data
        assert "models" in data
        assert "predictor" in data
        assert "anomaly_detector" in data
        assert "recommender" in data


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_json(self, client):
        """Test handling of invalid JSON."""
        response = client.post(
            "/predict",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client):
        """Test handling of missing required fields."""
        request = {
            # Missing "metric" field
            "periods": 6,
            "model": "baseline"
        }

        response = client.post("/predict", json=request)
        assert response.status_code == 422

    def test_not_found(self, client):
        """Test 404 handling."""
        response = client.get("/nonexistent")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
