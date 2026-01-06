"""Resource efficiency analysis."""

import logging
from typing import Optional

from .config import config
from .models import (
    EfficiencySummary,
    OptimizationType,
    PotentialSaving,
    ResourceEfficiency,
    ResourceType,
    WorkloadEfficiency,
)

logger = logging.getLogger(__name__)


class EfficiencyAnalyzer:
    """Analyze resource efficiency of workloads."""

    def __init__(self):
        self.pricing = config.pricing

        # Thresholds for efficiency classification
        self.oversized_threshold = 0.3  # Less than 30% usage = oversized
        self.undersized_threshold = 0.85  # More than 85% usage = undersized

    def calculate_resource_efficiency(
        self,
        resource: ResourceType,
        requested: float,
        used: float,
        unit_price: float
    ) -> ResourceEfficiency:
        """Calculate efficiency for a single resource.

        Args:
            resource: Resource type
            requested: Requested amount
            used: Actually used amount
            unit_price: Price per unit per hour

        Returns:
            ResourceEfficiency metrics
        """
        if requested <= 0:
            efficiency = 0.0
        else:
            efficiency = min(1.0, used / requested)

        # Wasted resources = requested - used
        wasted = max(0, requested - used)
        waste_cost_hourly = wasted * unit_price

        # Generate recommendation
        recommendation = None
        if efficiency < self.oversized_threshold:
            recommendation = f"Consider reducing {resource.value} request by {int((1 - efficiency) * 100)}%"
        elif efficiency > self.undersized_threshold:
            recommendation = f"Consider increasing {resource.value} request to handle peak load"

        return ResourceEfficiency(
            resource=resource,
            requested=requested,
            used=used,
            efficiency=efficiency,
            waste_cost_hourly=waste_cost_hourly,
            recommendation=recommendation
        )

    def analyze_workload(
        self,
        name: str,
        namespace: str,
        cpu_requested: float,
        cpu_used: float,
        memory_requested: float,
        memory_used: float
    ) -> WorkloadEfficiency:
        """Analyze efficiency of a workload.

        Args:
            name: Workload name
            namespace: Namespace
            cpu_requested: CPU cores requested
            cpu_used: CPU cores actually used
            memory_requested: Memory GB requested
            memory_used: Memory GB actually used

        Returns:
            WorkloadEfficiency with metrics
        """
        cpu_efficiency = self.calculate_resource_efficiency(
            ResourceType.CPU,
            cpu_requested,
            cpu_used,
            self.pricing.cpu_per_core_hour
        )

        memory_efficiency = self.calculate_resource_efficiency(
            ResourceType.MEMORY,
            memory_requested,
            memory_used,
            self.pricing.memory_per_gb_hour
        )

        resources = [cpu_efficiency, memory_efficiency]

        # Overall efficiency is weighted average (CPU weighted more)
        overall = (cpu_efficiency.efficiency * 0.6 + memory_efficiency.efficiency * 0.4)

        # Total waste
        waste_hourly = sum(r.waste_cost_hourly for r in resources)

        # Classification
        is_oversized = overall < self.oversized_threshold
        is_undersized = overall > self.undersized_threshold

        return WorkloadEfficiency(
            name=name,
            namespace=namespace,
            resources=resources,
            overall_efficiency=overall,
            waste_cost_monthly=waste_hourly * 24 * 30,
            is_oversized=is_oversized,
            is_undersized=is_undersized
        )

    def get_efficiency_summary(
        self,
        namespace: Optional[str] = None
    ) -> EfficiencySummary:
        """Get efficiency summary for all workloads.

        In production, this would query Prometheus for actual usage.
        Returns simulated data for demo purposes.

        Args:
            namespace: Optional namespace filter

        Returns:
            EfficiencySummary with all workload efficiencies
        """
        # Simulated workload data
        workloads_data = [
            {
                "name": "saleor-api",
                "namespace": "saleor",
                "cpu_requested": 0.5,  # 2 replicas * 0.25 cores
                "cpu_used": 0.225,     # 45% of requested
                "memory_requested": 1.024,  # 2 replicas * 512Mi
                "memory_used": 0.614   # 60% of requested
            },
            {
                "name": "saleor-worker",
                "namespace": "saleor",
                "cpu_requested": 0.25,
                "cpu_used": 0.075,     # 30% usage
                "memory_requested": 0.512,
                "memory_used": 0.282   # 55% usage
            },
            {
                "name": "postgresql",
                "namespace": "saleor",
                "cpu_requested": 0.5,
                "cpu_used": 0.175,     # 35% usage
                "memory_requested": 1.0,
                "memory_used": 0.7     # 70% usage
            },
            {
                "name": "redis",
                "namespace": "saleor",
                "cpu_requested": 0.1,
                "cpu_used": 0.02,      # 20% usage
                "memory_requested": 0.256,
                "memory_used": 0.128   # 50% usage
            },
            {
                "name": "helios-inference",
                "namespace": "helios",
                "cpu_requested": 0.2,  # 2 replicas * 0.1 cores
                "cpu_used": 0.05,      # 25% usage
                "memory_requested": 0.512,
                "memory_used": 0.230   # 45% usage
            },
            {
                "name": "prometheus",
                "namespace": "monitoring",
                "cpu_requested": 0.5,
                "cpu_used": 0.2,       # 40% usage
                "memory_requested": 2.0,
                "memory_used": 1.3     # 65% usage
            },
            {
                "name": "grafana",
                "namespace": "monitoring",
                "cpu_requested": 0.25,
                "cpu_used": 0.0375,    # 15% usage
                "memory_requested": 0.512,
                "memory_used": 0.179   # 35% usage
            },
        ]

        # Filter by namespace if specified
        if namespace:
            workloads_data = [w for w in workloads_data if w["namespace"] == namespace]

        # Analyze each workload
        workloads = [
            self.analyze_workload(**w) for w in workloads_data
        ]

        # Calculate overall metrics
        if workloads:
            overall_efficiency = sum(w.overall_efficiency for w in workloads) / len(workloads)
            total_waste = sum(w.waste_cost_monthly for w in workloads)
        else:
            overall_efficiency = 0
            total_waste = 0

        # Get top opportunities (oversized workloads sorted by waste)
        oversized = [w for w in workloads if w.is_oversized]
        oversized.sort(key=lambda w: w.waste_cost_monthly, reverse=True)

        top_opportunities = [
            PotentialSaving(
                workload=w.name,
                namespace=w.namespace,
                current_cost_monthly=w.waste_cost_monthly / (1 - w.overall_efficiency) if w.overall_efficiency < 1 else 0,
                optimized_cost_monthly=w.waste_cost_monthly / (1 - w.overall_efficiency) * w.overall_efficiency if w.overall_efficiency < 1 else 0,
                potential_savings_monthly=w.waste_cost_monthly,
                optimization_type=OptimizationType.RIGHTSIZING,
                recommendation=f"Right-size resources to match {w.overall_efficiency*100:.0f}% actual usage",
                confidence=0.8,
                implementation_effort="low" if w.waste_cost_monthly < 10 else "medium"
            )
            for w in oversized[:5]
        ]

        return EfficiencySummary(
            overall_efficiency=overall_efficiency,
            total_waste_monthly=total_waste,
            workloads=workloads,
            top_opportunities=top_opportunities
        )


# Global analyzer instance
efficiency_analyzer = EfficiencyAnalyzer()
