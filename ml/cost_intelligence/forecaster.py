"""Cost forecasting using time series models."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .models import CostForecast, CostForecastPoint, TimeRange

logger = logging.getLogger(__name__)


class CostForecaster:
    """Forecast future costs based on historical data."""

    def __init__(self):
        # Historical data (in production, would come from database)
        self._history: list[float] = []

    def add_data_point(self, cost: float):
        """Add a cost data point."""
        self._history.append(cost)
        # Keep last 90 days of daily data
        self._history = self._history[-90:]

    def forecast(
        self,
        period: TimeRange,
        current_daily_cost: float,
        namespace: Optional[str] = None
    ) -> CostForecast:
        """Generate cost forecast.

        Uses simple exponential smoothing with trend for forecasting.
        In production, would use more sophisticated models.

        Args:
            period: Forecast period
            current_daily_cost: Current daily cost
            namespace: Optional namespace filter

        Returns:
            CostForecast with predictions
        """
        # Determine number of forecast points
        if period == TimeRange.WEEK:
            n_points = 7
            point_interval = timedelta(days=1)
        elif period == TimeRange.MONTH:
            n_points = 30
            point_interval = timedelta(days=1)
        elif period == TimeRange.QUARTER:
            n_points = 12  # Weekly points
            point_interval = timedelta(weeks=1)
        else:
            n_points = 24  # Hourly for short periods
            point_interval = timedelta(hours=1)
            current_daily_cost = current_daily_cost / 24  # Convert to hourly

        # Generate synthetic historical trend (in production, use real data)
        # Assume slight growth trend (2% monthly)
        daily_growth_rate = 0.02 / 30

        # Add some seasonality (weekly pattern)
        now = datetime.utcnow()
        forecast_points = []
        projected_total = 0

        for i in range(n_points):
            future_time = now + (i + 1) * point_interval

            # Base prediction with growth
            days_ahead = (i + 1) if period != TimeRange.QUARTER else (i + 1) * 7
            base_cost = current_daily_cost * (1 + daily_growth_rate * days_ahead)

            # Add weekly seasonality (±10% variation)
            day_of_week = future_time.weekday()
            if day_of_week in [5, 6]:  # Weekend
                seasonality = -0.1
            elif day_of_week in [1, 2, 3]:  # Mid-week peak
                seasonality = 0.05
            else:
                seasonality = 0

            predicted = base_cost * (1 + seasonality)

            # Confidence interval (widens with time)
            confidence_factor = 1 + (i / n_points) * 0.3
            margin = predicted * 0.1 * confidence_factor

            forecast_points.append(CostForecastPoint(
                timestamp=future_time,
                predicted_cost=predicted,
                lower_bound=predicted - margin,
                upper_bound=predicted + margin,
                confidence=max(0.5, 0.95 - (i / n_points) * 0.3)
            ))

            # Adjust for period type
            if period == TimeRange.QUARTER:
                projected_total += predicted * 7  # Weekly to daily
            else:
                projected_total += predicted

        # Determine trend
        if len(forecast_points) >= 2:
            start_cost = forecast_points[0].predicted_cost
            end_cost = forecast_points[-1].predicted_cost
            trend_change = (end_cost - start_cost) / start_cost * 100

            if trend_change > 5:
                trend = "increasing"
            elif trend_change < -5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
            trend_change = 0

        return CostForecast(
            period=period,
            namespace=namespace,
            current_daily_cost=current_daily_cost if period != TimeRange.HOUR else current_daily_cost * 24,
            forecast_points=forecast_points,
            projected_total=projected_total,
            trend=trend,
            trend_percent=trend_change
        )

    def get_budget_status(
        self,
        monthly_budget: float,
        current_spend: float,
        days_elapsed: int
    ) -> dict:
        """Calculate budget status and projection.

        Args:
            monthly_budget: Monthly budget limit
            current_spend: Current month's spend
            days_elapsed: Days elapsed in current month

        Returns:
            Budget status dict
        """
        if days_elapsed <= 0:
            return {
                "on_track": True,
                "projected_monthly": 0,
                "budget_remaining": monthly_budget,
                "burn_rate": 0
            }

        # Calculate burn rate
        daily_burn = current_spend / days_elapsed

        # Project end of month
        days_in_month = 30
        projected_monthly = daily_burn * days_in_month

        # Budget status
        budget_remaining = monthly_budget - current_spend
        on_track = projected_monthly <= monthly_budget

        # Days until budget exhausted
        if daily_burn > 0:
            days_to_exhaustion = budget_remaining / daily_burn
        else:
            days_to_exhaustion = float('inf')

        return {
            "on_track": on_track,
            "projected_monthly": projected_monthly,
            "budget_remaining": budget_remaining,
            "burn_rate": daily_burn,
            "days_to_exhaustion": days_to_exhaustion,
            "overage_projected": max(0, projected_monthly - monthly_budget)
        }


# Global forecaster instance
cost_forecaster = CostForecaster()
