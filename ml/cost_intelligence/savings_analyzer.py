"""Savings analysis from optimizations."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .config import config
from .models import OptimizationType, PotentialSaving, SavingsEvent, SavingsSummary, TimeRange

logger = logging.getLogger(__name__)


class SavingsAnalyzer:
    """Analyze cost savings from optimizations."""

    def __init__(self):
        self.pricing = config.pricing
        self._savings_history: list[SavingsEvent] = []

    def record_scaling_event(
        self,
        workload: str,
        namespace: str,
        before_replicas: int,
        after_replicas: int,
        cpu_per_replica: float,
        memory_per_replica: float,
    ) -> SavingsEvent:
        """Record a scaling event and calculate savings.

        Args:
            workload: Workload name
            namespace: Namespace
            before_replicas: Replica count before scaling
            after_replicas: Replica count after scaling
            cpu_per_replica: CPU cores per replica
            memory_per_replica: Memory GB per replica

        Returns:
            SavingsEvent with calculated savings
        """
        # Calculate hourly cost per replica
        hourly_per_replica = (
            cpu_per_replica * self.pricing.cpu_per_core_hour
            + memory_per_replica * self.pricing.memory_per_gb_hour
        )

        before_cost = before_replicas * hourly_per_replica
        after_cost = after_replicas * hourly_per_replica

        # Savings is positive when scaling down
        savings_hourly = before_cost - after_cost

        if savings_hourly > 0:
            action = f"Scaled down from {before_replicas} to {after_replicas} replicas"
            opt_type = OptimizationType.AUTOSCALING
        elif savings_hourly < 0:
            # Scaling up is negative savings but we track it
            action = f"Scaled up from {before_replicas} to {after_replicas} replicas"
            savings_hourly = 0  # Don't count scale-up as savings
            opt_type = OptimizationType.AUTOSCALING
        else:
            action = "No scaling change"
            opt_type = OptimizationType.AUTOSCALING

        event = SavingsEvent(
            timestamp=datetime.utcnow(),
            workload=workload,
            namespace=namespace,
            optimization_type=opt_type,
            savings_hourly=max(0, savings_hourly),
            savings_monthly=max(0, savings_hourly) * 24 * 30,
            action_taken=action,
            before_replicas=before_replicas,
            after_replicas=after_replicas,
            before_cost=before_cost,
            after_cost=after_cost,
        )

        self._savings_history.append(event)
        return event

    def get_savings_summary(
        self, period: TimeRange = TimeRange.MONTH, namespace: Optional[str] = None
    ) -> SavingsSummary:
        """Get savings summary for a period.

        Args:
            period: Time range
            namespace: Optional namespace filter

        Returns:
            SavingsSummary with totals and breakdown
        """
        # Calculate time cutoff
        now = datetime.utcnow()
        if period == TimeRange.HOUR:
            cutoff = now - timedelta(hours=1)
        elif period == TimeRange.DAY:
            cutoff = now - timedelta(days=1)
        elif period == TimeRange.WEEK:
            cutoff = now - timedelta(weeks=1)
        elif period == TimeRange.MONTH:
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=90)

        # Filter events
        events = [
            e
            for e in self._savings_history
            if e.timestamp >= cutoff and (namespace is None or e.namespace == namespace)
        ]

        # Calculate totals
        total_savings = sum(e.savings_monthly for e in events)

        # Group by type
        savings_by_type: dict[OptimizationType, float] = {}
        for e in events:
            if e.optimization_type not in savings_by_type:
                savings_by_type[e.optimization_type] = 0
            savings_by_type[e.optimization_type] += e.savings_monthly

        # Group by namespace
        savings_by_namespace: dict[str, float] = {}
        for e in events:
            if e.namespace not in savings_by_namespace:
                savings_by_namespace[e.namespace] = 0
            savings_by_namespace[e.namespace] += e.savings_monthly

        # Add simulated historical savings if no real data
        if not events:
            events, total_savings, savings_by_type, savings_by_namespace = (
                self._generate_simulated_savings(period)
            )

        # Calculate potential additional savings
        potential = self._calculate_potential_savings()

        # ROI calculation (savings vs infrastructure cost)
        monthly_infra_cost = 200  # Estimated monthly cost
        roi = (total_savings / monthly_infra_cost * 100) if monthly_infra_cost > 0 else 0

        return SavingsSummary(
            period=period,
            total_savings=total_savings,
            savings_by_type=savings_by_type,
            savings_by_namespace=savings_by_namespace,
            events=events[-20:],  # Last 20 events
            potential_additional_savings=potential,
            roi_percent=roi,
        )

    def _generate_simulated_savings(self, period: TimeRange):
        """Generate simulated savings data for demo purposes."""
        now = datetime.utcnow()

        events = [
            SavingsEvent(
                timestamp=now - timedelta(hours=2),
                workload="saleor-api",
                namespace="saleor",
                optimization_type=OptimizationType.AUTOSCALING,
                savings_hourly=0.02,
                savings_monthly=14.40,
                action_taken="Scaled down from 3 to 2 replicas during low traffic",
                before_replicas=3,
                after_replicas=2,
                before_cost=0.06,
                after_cost=0.04,
            ),
            SavingsEvent(
                timestamp=now - timedelta(hours=8),
                workload="saleor-worker",
                namespace="saleor",
                optimization_type=OptimizationType.AUTOSCALING,
                savings_hourly=0.015,
                savings_monthly=10.80,
                action_taken="Scaled down from 2 to 1 replica during off-peak",
                before_replicas=2,
                after_replicas=1,
                before_cost=0.045,
                after_cost=0.03,
            ),
            SavingsEvent(
                timestamp=now - timedelta(days=1),
                workload="helios-inference",
                namespace="helios",
                optimization_type=OptimizationType.RIGHTSIZING,
                savings_hourly=0.01,
                savings_monthly=7.20,
                action_taken="Reduced CPU request from 200m to 100m",
                before_replicas=2,
                after_replicas=2,
                before_cost=0.03,
                after_cost=0.02,
            ),
        ]

        total_savings = sum(e.savings_monthly for e in events)

        savings_by_type = {OptimizationType.AUTOSCALING: 25.20, OptimizationType.RIGHTSIZING: 7.20}

        savings_by_namespace = {"saleor": 25.20, "helios": 7.20}

        return events, total_savings, savings_by_type, savings_by_namespace

    def _calculate_potential_savings(self) -> float:
        """Calculate potential additional savings from optimization opportunities."""
        # Simulated potential savings based on typical inefficiencies
        return 45.00  # $45/month potential additional savings

    def get_potential_savings(self) -> list[PotentialSaving]:
        """Get list of potential savings opportunities.

        Returns:
            List of potential savings with recommendations
        """
        return [
            PotentialSaving(
                workload="saleor-api",
                namespace="saleor",
                current_cost_monthly=40.00,
                optimized_cost_monthly=30.00,
                potential_savings_monthly=10.00,
                optimization_type=OptimizationType.AUTOSCALING,
                recommendation="Enable predictive autoscaling to reduce replicas during predicted low-traffic periods",
                confidence=0.85,
                implementation_effort="low",
            ),
            PotentialSaving(
                workload="postgresql",
                namespace="saleor",
                current_cost_monthly=60.00,
                optimized_cost_monthly=45.00,
                potential_savings_monthly=15.00,
                optimization_type=OptimizationType.RIGHTSIZING,
                recommendation="Reduce memory request from 1Gi to 768Mi based on actual usage patterns",
                confidence=0.75,
                implementation_effort="medium",
            ),
            PotentialSaving(
                workload="prometheus",
                namespace="monitoring",
                current_cost_monthly=80.00,
                optimized_cost_monthly=60.00,
                potential_savings_monthly=20.00,
                optimization_type=OptimizationType.RIGHTSIZING,
                recommendation="Optimize retention period and use remote storage for older metrics",
                confidence=0.70,
                implementation_effort="high",
            ),
        ]


# Global analyzer instance
savings_analyzer = SavingsAnalyzer()
