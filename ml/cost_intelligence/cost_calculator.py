"""Cost calculation logic for Kubernetes workloads."""

import logging

from .config import config
from .models import CostSummary, NamespaceCost, ResourceCost, ResourceType, TimeRange, WorkloadCost

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate costs for Kubernetes workloads."""

    def __init__(self):
        self.pricing = config.pricing

    def calculate_resource_cost(
        self,
        resource: ResourceType,
        quantity: float,
        hours: int = 1
    ) -> ResourceCost:
        """Calculate cost for a specific resource.

        Args:
            resource: Type of resource (cpu, memory, storage)
            quantity: Amount (cores for CPU, GB for memory/storage)
            hours: Number of hours

        Returns:
            ResourceCost with calculated costs
        """
        if resource == ResourceType.CPU:
            unit_price = self.pricing.cpu_per_core_hour
        elif resource == ResourceType.MEMORY:
            unit_price = self.pricing.memory_per_gb_hour
        elif resource == ResourceType.STORAGE:
            unit_price = self.pricing.storage_per_gb_hour
        else:
            unit_price = 0.0

        hourly_cost = quantity * unit_price

        return ResourceCost(
            resource=resource,
            quantity=quantity,
            unit_price=unit_price,
            hourly_cost=hourly_cost,
            daily_cost=hourly_cost * 24,
            monthly_cost=hourly_cost * 24 * 30
        )

    def calculate_workload_cost(
        self,
        name: str,
        namespace: str,
        cpu_cores: float,
        memory_gb: float,
        storage_gb: float = 0,
        replicas: int = 1,
        cpu_usage: float = 0.5,
        memory_usage: float = 0.5
    ) -> WorkloadCost:
        """Calculate total cost for a workload.

        Args:
            name: Workload name
            namespace: Kubernetes namespace
            cpu_cores: CPU cores requested per pod
            memory_gb: Memory GB requested per pod
            storage_gb: Ephemeral storage GB per pod
            replicas: Number of replicas
            cpu_usage: Actual CPU usage ratio (0-1)
            memory_usage: Actual memory usage ratio (0-1)

        Returns:
            WorkloadCost with breakdown
        """
        # Calculate per-resource costs (multiply by replicas)
        total_cpu = cpu_cores * replicas
        total_memory = memory_gb * replicas
        total_storage = storage_gb * replicas

        cpu_cost = self.calculate_resource_cost(ResourceType.CPU, total_cpu)
        memory_cost = self.calculate_resource_cost(ResourceType.MEMORY, total_memory)
        storage_cost = self.calculate_resource_cost(ResourceType.STORAGE, total_storage)

        resources = [cpu_cost, memory_cost]
        if storage_gb > 0:
            resources.append(storage_cost)

        total_hourly = sum(r.hourly_cost for r in resources)

        # Calculate efficiency score (average of CPU and memory efficiency)
        efficiency_score = (cpu_usage + memory_usage) / 2

        return WorkloadCost(
            name=name,
            namespace=namespace,
            replicas=replicas,
            resources=resources,
            total_hourly=total_hourly,
            total_daily=total_hourly * 24,
            total_monthly=total_hourly * 24 * 30,
            efficiency_score=efficiency_score
        )

    def calculate_namespace_cost(
        self,
        namespace: str,
        workloads: list[WorkloadCost]
    ) -> NamespaceCost:
        """Calculate total cost for a namespace.

        Args:
            namespace: Namespace name
            workloads: List of workload costs

        Returns:
            NamespaceCost with totals
        """
        total_hourly = sum(w.total_hourly for w in workloads)

        return NamespaceCost(
            namespace=namespace,
            workloads=workloads,
            total_hourly=total_hourly,
            total_daily=total_hourly * 24,
            total_monthly=total_hourly * 24 * 30,
            workload_count=len(workloads)
        )

    def get_current_costs(self, period: TimeRange = TimeRange.DAY) -> CostSummary:
        """Get current cost summary.

        In production, this would query Prometheus for actual resource usage.
        For now, returns simulated data based on typical deployments.

        Args:
            period: Time range for the summary

        Returns:
            CostSummary with all namespace costs
        """
        # Simulated workloads based on our deployment
        saleor_workloads = [
            self.calculate_workload_cost(
                name="saleor-api",
                namespace="saleor",
                cpu_cores=0.25,
                memory_gb=0.512,
                replicas=2,
                cpu_usage=0.45,
                memory_usage=0.60
            ),
            self.calculate_workload_cost(
                name="saleor-worker",
                namespace="saleor",
                cpu_cores=0.25,
                memory_gb=0.512,
                replicas=1,
                cpu_usage=0.30,
                memory_usage=0.55
            ),
            self.calculate_workload_cost(
                name="saleor-dashboard",
                namespace="saleor",
                cpu_cores=0.1,
                memory_gb=0.256,
                replicas=1,
                cpu_usage=0.15,
                memory_usage=0.40
            ),
            self.calculate_workload_cost(
                name="postgresql",
                namespace="saleor",
                cpu_cores=0.5,
                memory_gb=1.0,
                replicas=1,
                cpu_usage=0.35,
                memory_usage=0.70
            ),
            self.calculate_workload_cost(
                name="redis",
                namespace="saleor",
                cpu_cores=0.1,
                memory_gb=0.256,
                replicas=1,
                cpu_usage=0.20,
                memory_usage=0.50
            ),
        ]

        helios_workloads = [
            self.calculate_workload_cost(
                name="helios-inference",
                namespace="helios",
                cpu_cores=0.1,
                memory_gb=0.256,
                replicas=2,
                cpu_usage=0.25,
                memory_usage=0.45
            ),
        ]

        monitoring_workloads = [
            self.calculate_workload_cost(
                name="prometheus",
                namespace="monitoring",
                cpu_cores=0.5,
                memory_gb=2.0,
                replicas=1,
                cpu_usage=0.40,
                memory_usage=0.65
            ),
            self.calculate_workload_cost(
                name="grafana",
                namespace="monitoring",
                cpu_cores=0.25,
                memory_gb=0.512,
                replicas=1,
                cpu_usage=0.15,
                memory_usage=0.35
            ),
        ]

        namespaces = [
            self.calculate_namespace_cost("saleor", saleor_workloads),
            self.calculate_namespace_cost("helios", helios_workloads),
            self.calculate_namespace_cost("monitoring", monitoring_workloads),
        ]

        total_hourly = sum(ns.total_hourly for ns in namespaces)

        return CostSummary(
            period=period,
            namespaces=namespaces,
            total_hourly=total_hourly,
            total_daily=total_hourly * 24,
            total_monthly=total_hourly * 24 * 30
        )

    def parse_resource_string(self, resource_str: str) -> float:
        """Parse Kubernetes resource strings like '100m' or '512Mi'.

        Args:
            resource_str: Resource string (e.g., '100m', '512Mi', '1Gi')

        Returns:
            Value in base units (cores for CPU, GB for memory)
        """
        if not resource_str:
            return 0.0

        resource_str = str(resource_str).strip()

        # CPU: millicores to cores
        if resource_str.endswith('m'):
            return float(resource_str[:-1]) / 1000

        # Memory: various units to GB
        if resource_str.endswith('Ki'):
            return float(resource_str[:-2]) / (1024 * 1024)
        if resource_str.endswith('Mi'):
            return float(resource_str[:-2]) / 1024
        if resource_str.endswith('Gi'):
            return float(resource_str[:-2])
        if resource_str.endswith('Ti'):
            return float(resource_str[:-2]) * 1024

        # Plain number (assume cores for CPU, bytes for memory)
        try:
            return float(resource_str)
        except ValueError:
            return 0.0


# Global calculator instance
cost_calculator = CostCalculator()
