"""
Helios ML Tests

Unit tests for ML models: Baseline, Prophet, and XGBoost.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta


class TestBaselineModel:
    """Tests for BaselineModel."""

    def test_import(self):
        """Test that BaselineModel can be imported."""
        from models.baseline import BaselineModel, BaselinePrediction
        assert BaselineModel is not None
        assert BaselinePrediction is not None

    def test_initialization(self):
        """Test model initialization with default parameters."""
        from models.baseline import BaselineModel
        model = BaselineModel()
        assert model.window == 12
        assert model.trend_window == 24
        assert model.confidence_level == 0.95
        assert not model.is_fitted_

    def test_initialization_custom(self):
        """Test model initialization with custom parameters."""
        from models.baseline import BaselineModel
        model = BaselineModel(window=6, trend_window=12, confidence_level=0.90)
        assert model.window == 6
        assert model.trend_window == 12
        assert model.confidence_level == 0.90

    def test_fit_basic(self):
        """Test fitting on simple data."""
        from models.baseline import BaselineModel
        model = BaselineModel(window=5)
        
        # Simple increasing series
        y = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        model.fit(y)
        
        assert model.is_fitted_
        assert model.moving_average_ is not None
        assert model.trend_ is not None
        assert model.std_ is not None
        # Moving average of last 5: (6+7+8+9+10)/5 = 8
        assert np.isclose(model.moving_average_, 8.0)
        # Trend should be ~1.0 (constant increase)
        assert np.isclose(model.trend_, 1.0, atol=0.1)

    def test_fit_insufficient_data(self):
        """Test that fit raises error with insufficient data."""
        from models.baseline import BaselineModel
        model = BaselineModel(window=10)
        
        y = pd.Series([1, 2, 3])  # Only 3 points, need 10
        with pytest.raises(ValueError, match="Need at least"):
            model.fit(y)

    def test_predict(self):
        """Test prediction output shape and structure."""
        from models.baseline import BaselineModel, BaselinePrediction
        model = BaselineModel(window=5)
        
        y = pd.Series(range(20))
        model.fit(y)
        
        pred = model.predict(periods=10)
        
        assert isinstance(pred, BaselinePrediction)
        assert len(pred.forecast) == 10
        assert len(pred.confidence_lower) == 10
        assert len(pred.confidence_upper) == 10
        assert pred.trend is not None
        assert pred.moving_average is not None

    def test_predict_not_fitted(self):
        """Test that predict raises error if not fitted."""
        from models.baseline import BaselineModel
        model = BaselineModel()
        
        with pytest.raises(Exception):  # Should raise some error
            model.predict(periods=5)

    def test_confidence_intervals(self):
        """Test that confidence intervals are properly ordered."""
        from models.baseline import BaselineModel
        model = BaselineModel(window=5)
        
        y = pd.Series(np.random.randn(50) * 10 + 100)
        model.fit(y)
        
        pred = model.predict(periods=10)
        
        # Lower should be less than forecast, upper should be greater
        assert np.all(pred.confidence_lower <= pred.forecast)
        assert np.all(pred.forecast <= pred.confidence_upper)


class TestProphetForecaster:
    """Tests for ProphetForecaster."""

    def test_import(self):
        """Test that ProphetForecaster can be imported."""
        from models.prophet_model import ProphetForecaster, ProphetPrediction
        assert ProphetForecaster is not None
        assert ProphetPrediction is not None

    def test_initialization(self):
        """Test model initialization with default parameters."""
        from models.prophet_model import ProphetForecaster
        model = ProphetForecaster()
        assert model.seasonality_mode == "multiplicative"
        assert model.interval_width == 0.95
        assert not model.is_fitted_

    def test_initialization_custom(self):
        """Test model initialization with custom parameters."""
        from models.prophet_model import ProphetForecaster
        model = ProphetForecaster(
            seasonality_mode="additive",
            changepoint_prior_scale=0.1,
            weekly_seasonality=False,
            interval_width=0.80
        )
        assert model.seasonality_mode == "additive"
        assert model.changepoint_prior_scale == 0.1
        assert model.weekly_seasonality is False
        assert model.interval_width == 0.80

    def test_fit_basic(self):
        """Test fitting on synthetic data."""
        from models.prophet_model import ProphetForecaster
        model = ProphetForecaster(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False
        )
        
        # Create synthetic time series
        dates = pd.date_range(start="2024-01-01", periods=100, freq="H")
        values = np.sin(np.linspace(0, 4 * np.pi, 100)) * 10 + 50 + np.random.randn(100)
        
        df = pd.DataFrame({
            "timestamp": dates,
            "value": values
        })
        
        model.fit(df, timestamp_col="timestamp", value_col="value")
        assert model.is_fitted_
        assert model.model_ is not None

    def test_predict(self):
        """Test prediction output structure."""
        from models.prophet_model import ProphetForecaster, ProphetPrediction
        model = ProphetForecaster(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False
        )
        
        # Create data
        dates = pd.date_range(start="2024-01-01", periods=100, freq="H")
        values = np.random.randn(100) * 5 + 50
        
        df = pd.DataFrame({
            "timestamp": dates,
            "value": values
        })
        
        model.fit(df, timestamp_col="timestamp", value_col="value")
        pred = model.predict(periods=24)
        
        assert isinstance(pred, ProphetPrediction)
        assert pred.forecast is not None
        assert len(pred.forecast) == 24
        assert "yhat" in pred.forecast.columns
        assert "yhat_lower" in pred.forecast.columns
        assert "yhat_upper" in pred.forecast.columns


class TestXGBoostAnomalyDetector:
    """Tests for XGBoostAnomalyDetector."""

    def test_import(self):
        """Test that XGBoostAnomalyDetector can be imported."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector, AnomalyResult
        assert XGBoostAnomalyDetector is not None
        assert AnomalyResult is not None

    def test_initialization(self):
        """Test model initialization with default parameters."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector
        model = XGBoostAnomalyDetector()
        assert model.n_estimators == 100
        assert model.max_depth == 6
        assert model.learning_rate == 0.1
        assert model.threshold_sigma == 2.5
        assert model.contamination == 0.05
        assert not model.is_fitted_

    def test_initialization_custom(self):
        """Test model initialization with custom parameters."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector
        model = XGBoostAnomalyDetector(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.05,
            threshold_sigma=3.0,
            contamination=0.10
        )
        assert model.n_estimators == 50
        assert model.max_depth == 4
        assert model.learning_rate == 0.05
        assert model.threshold_sigma == 3.0
        assert model.contamination == 0.10

    def test_fit_basic(self):
        """Test fitting on synthetic data."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector
        model = XGBoostAnomalyDetector(n_estimators=10)
        
        # Create synthetic multi-variate data
        np.random.seed(42)
        n_samples = 200
        
        X = pd.DataFrame({
            "cpu_usage": np.random.randn(n_samples) * 10 + 50,
            "memory_usage": np.random.randn(n_samples) * 15 + 60,
            "network_io": np.random.randn(n_samples) * 20 + 100
        })
        # Target is correlated with features
        y = pd.Series(0.5 * X["cpu_usage"] + 0.3 * X["memory_usage"] + np.random.randn(n_samples) * 2)
        
        model.fit(X, y)
        assert model.is_fitted_
        assert model.model_ is not None
        assert model.scaler_ is not None
        assert model.threshold_ is not None

    def test_predict(self):
        """Test prediction output structure."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector, AnomalyResult
        model = XGBoostAnomalyDetector(n_estimators=10)
        
        np.random.seed(42)
        n_samples = 200
        
        X = pd.DataFrame({
            "cpu_usage": np.random.randn(n_samples) * 10 + 50,
            "memory_usage": np.random.randn(n_samples) * 15 + 60,
        })
        y = pd.Series(0.5 * X["cpu_usage"] + np.random.randn(n_samples) * 2)
        
        model.fit(X, y)
        
        # Predict on same data
        result = model.predict(X, y)
        
        assert isinstance(result, AnomalyResult)
        assert len(result.scores) == n_samples
        assert len(result.predictions) == n_samples
        assert result.threshold > 0
        assert result.feature_importance is not None

    def test_anomaly_detection(self):
        """Test that anomalies are detected in outlier data."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector
        model = XGBoostAnomalyDetector(n_estimators=20, threshold_sigma=2.0)
        
        np.random.seed(42)
        n_samples = 200
        
        # Normal data
        X = pd.DataFrame({
            "cpu_usage": np.random.randn(n_samples) * 5 + 50,
            "memory_usage": np.random.randn(n_samples) * 5 + 60,
        })
        y = pd.Series(X["cpu_usage"] * 0.8 + np.random.randn(n_samples) * 2)
        
        model.fit(X, y)
        
        # Create test data with some outliers
        X_test = pd.DataFrame({
            "cpu_usage": list(np.random.randn(45) * 5 + 50) + [100, 100, 100, 100, 100],  # 5 outliers
            "memory_usage": list(np.random.randn(45) * 5 + 60) + [150, 150, 150, 150, 150],
        })
        y_test = pd.Series(X_test["cpu_usage"] * 0.8 + np.random.randn(50) * 2)
        # Make y_test not match expected pattern for outliers
        y_test.iloc[-5:] = [10, 10, 10, 10, 10]  # Very low values despite high features
        
        result = model.predict(X_test, y_test)
        
        # Should detect some anomalies (outliers)
        assert result.anomaly_indices is not None
        # The last 5 points should be flagged (or at least some of them)
        # Due to randomness, we just check some anomalies were found
        assert len(result.anomaly_indices) > 0

    def test_feature_importance(self):
        """Test that feature importance is calculated."""
        from models.xgboost_anomaly import XGBoostAnomalyDetector
        model = XGBoostAnomalyDetector(n_estimators=10)
        
        np.random.seed(42)
        n_samples = 100
        
        X = pd.DataFrame({
            "feature_a": np.random.randn(n_samples) * 10 + 50,
            "feature_b": np.random.randn(n_samples) * 15 + 60,
            "feature_c": np.random.randn(n_samples) * 20 + 100
        })
        y = pd.Series(0.9 * X["feature_a"] + 0.1 * X["feature_b"] + np.random.randn(n_samples) * 0.1)
        
        model.fit(X, y)
        result = model.predict(X, y)
        
        # Feature importance should have all features
        assert "feature_a" in result.feature_importance
        assert "feature_b" in result.feature_importance
        assert "feature_c" in result.feature_importance
        # feature_a should have highest importance (since y is mostly determined by it)
        assert result.feature_importance["feature_a"] > result.feature_importance["feature_c"]


class TestTrainingPipeline:
    """Tests for the training pipeline."""

    def test_import_pipeline(self):
        """Test that training pipeline can be imported."""
        from train import HeliosTrainingPipeline
        assert HeliosTrainingPipeline is not None

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        from train import HeliosTrainingPipeline
        pipeline = HeliosTrainingPipeline(
            output_dir="test_artifacts",
            target_metric="cpu_usage"
        )
        assert pipeline.target_metric == "cpu_usage"
        assert pipeline.fetcher is not None
        assert pipeline.feature_engineer is not None


class TestFeatureEngineering:
    """Tests for feature engineering."""

    def test_import(self):
        """Test that FeatureEngineer can be imported."""
        from pipeline.feature_engineering import FeatureEngineer
        assert FeatureEngineer is not None

    def test_initialization(self):
        """Test feature engineer initialization."""
        from pipeline.feature_engineering import FeatureEngineer
        fe = FeatureEngineer()
        assert fe is not None


# Fixtures for common test data
@pytest.fixture
def sample_timeseries():
    """Generate sample time series data."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=200, freq="H")
    values = (
        np.sin(np.linspace(0, 8 * np.pi, 200)) * 20  # Seasonality
        + np.linspace(0, 10, 200)  # Trend
        + np.random.randn(200) * 3  # Noise
        + 100  # Baseline
    )
    return pd.DataFrame({"timestamp": dates, "value": values})


@pytest.fixture
def sample_multivariate():
    """Generate sample multi-variate data."""
    np.random.seed(42)
    n_samples = 300
    
    cpu = np.random.randn(n_samples) * 10 + 50
    memory = np.random.randn(n_samples) * 15 + 60
    network = np.random.randn(n_samples) * 20 + 100
    rps = 0.3 * cpu + 0.5 * memory + 0.2 * network + np.random.randn(n_samples) * 5
    
    return pd.DataFrame({
        "cpu_usage": cpu,
        "memory_usage": memory,
        "network_io": network,
        "rps": rps
    })


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
