"""Recommendation service for scaling decisions."""

import logging
import math
from datetime import datetime
from typing import Any, Optional

from .config import config
from .models import (
    ActionType,
    CurrentState,
    PredictionPoint,
    Recommendation,
    RecommendationRequest,
    RecommendationResponse,
    ScalingAction,
)

logger = logging.getLogger(__name__)


class RecommenderService:
    """Service for generating scaling recommendations."""

    def __init__(self):
        self._recommendation_count = 0
        self._last_recommendations: dict[str, tuple[datetime, Recommendation]] = {}

    @property
    def recommendation_count(self) -> int:
        """Total recommendations generated."""
        return self._recommendation_count

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """Generate scaling recommendations for a workload.

        Args:
            request: Request with current state and optional predictions

        Returns:
            RecommendationResponse with scaling actions
        """
        self._recommendation_count += 1

        # Check cooldown
        workload_key = f"{request.namespace}/{request.workload}"
        if not self._check_cooldown(workload_key):
            # Return no-action recommendation during cooldown
            return RecommendationResponse(
                recommendations=[self._create_cooldown_recommendation(request)],
                metadata={"cooldown_active": True},
            )

        # Analyze current state and predictions
        actions = self._analyze_and_recommend(request)

        # Build recommendation
        recommendation = Recommendation(
            workload=request.workload,
            namespace=request.namespace,
            current_state=request.current_state,
            actions=actions,
            predicted_utilization=self._get_predicted_utilization(request.predictions),
            time_horizon_minutes=60,
        )

        # Store for cooldown tracking
        self._last_recommendations[workload_key] = (datetime.utcnow(), recommendation)

        return RecommendationResponse(
            recommendations=[recommendation],
            metadata={
                "cooldown_active": False,
                "target_utilization": request.target_utilization,
            },
        )

    def _check_cooldown(self, workload_key: str) -> bool:
        """Check if workload is in cooldown period."""
        if workload_key not in self._last_recommendations:
            return True

        last_time, _ = self._last_recommendations[workload_key]
        elapsed = (datetime.utcnow() - last_time).total_seconds() / 60

        return elapsed >= config.recommendation.cooldown_minutes

    def _create_cooldown_recommendation(self, request: RecommendationRequest) -> Recommendation:
        """Create a no-action recommendation during cooldown."""
        return Recommendation(
            workload=request.workload,
            namespace=request.namespace,
            current_state=request.current_state,
            actions=[
                ScalingAction(
                    action=ActionType.NO_ACTION,
                    confidence=1.0,
                    reason="In cooldown period, no action recommended",
                )
            ],
            time_horizon_minutes=config.recommendation.cooldown_minutes,
        )

    def _analyze_and_recommend(self, request: RecommendationRequest) -> list[ScalingAction]:
        """Analyze state and generate recommendations."""
        actions = []

        # Get current and predicted utilization
        current_util = self._estimate_current_utilization(request.current_state)
        predicted_util = self._get_predicted_utilization(request.predictions)

        # Use the higher of current or predicted for scaling decisions
        effective_util = max(current_util, predicted_util or 0.0)

        # Check for scale-up need
        if effective_util > config.recommendation.scale_up_threshold:
            scale_up_action = self._recommend_scale_up(
                request, effective_util, request.target_utilization
            )
            actions.append(scale_up_action)

        # Check for scale-down opportunity
        elif effective_util < config.recommendation.scale_down_threshold:
            scale_down_action = self._recommend_scale_down(
                request, effective_util, request.target_utilization
            )
            actions.append(scale_down_action)

        # Otherwise, no scaling needed
        else:
            actions.append(
                ScalingAction(
                    action=ActionType.NO_ACTION,
                    confidence=0.9,
                    reason=f"Utilization ({effective_util:.1%}) is within target range",
                )
            )

        # Check for resource optimization
        resource_action = self._recommend_resource_optimization(request)
        if resource_action:
            actions.append(resource_action)

        return actions

    def _recommend_scale_up(
        self,
        request: RecommendationRequest,
        current_util: float,
        target_util: float,
    ) -> ScalingAction:
        """Generate scale-up recommendation."""
        current_replicas = request.current_state.replicas

        # Calculate target replicas to achieve target utilization
        target_replicas = math.ceil(current_replicas * (current_util / target_util))

        # Respect max replicas
        target_replicas = min(target_replicas, config.recommendation.max_replicas)

        # Calculate confidence based on how far over threshold
        excess = current_util - config.recommendation.scale_up_threshold
        confidence = min(0.5 + excess * 2, 0.95)

        return ScalingAction(
            action=ActionType.SCALE_OUT,
            target_replicas=target_replicas,
            confidence=confidence,
            reason=(
                f"Current utilization ({current_util:.1%}) exceeds threshold "
                f"({config.recommendation.scale_up_threshold:.1%}). "
                f"Recommend scaling from {current_replicas} to {target_replicas} replicas."
            ),
        )

    def _recommend_scale_down(
        self,
        request: RecommendationRequest,
        current_util: float,
        target_util: float,
    ) -> ScalingAction:
        """Generate scale-down recommendation."""
        current_replicas = request.current_state.replicas

        # Calculate target replicas
        target_replicas = max(
            math.ceil(current_replicas * (current_util / target_util)),
            config.recommendation.min_replicas,
        )

        # Calculate potential savings
        if current_replicas > target_replicas:
            savings = (current_replicas - target_replicas) / current_replicas * 100
        else:
            savings = 0.0

        # Calculate confidence (lower for scale-down to be conservative)
        deficit = config.recommendation.scale_down_threshold - current_util
        confidence = min(0.4 + deficit, 0.85)

        return ScalingAction(
            action=ActionType.SCALE_IN,
            target_replicas=target_replicas,
            confidence=confidence,
            reason=(
                f"Current utilization ({current_util:.1%}) is below threshold "
                f"({config.recommendation.scale_down_threshold:.1%}). "
                f"Recommend scaling from {current_replicas} to {target_replicas} replicas."
            ),
            estimated_savings_percent=savings,
        )

    def _recommend_resource_optimization(
        self, request: RecommendationRequest
    ) -> Optional[ScalingAction]:
        """Check for vertical scaling opportunities."""
        # Parse current resource requests
        cpu_request = self._parse_cpu(request.current_state.cpu_request)
        self._parse_memory(request.current_state.memory_request)

        # Simple heuristics for resource optimization
        # In production, this would analyze actual usage vs requests

        # Check if CPU limit is much higher than request (potential right-sizing)
        cpu_limit = self._parse_cpu(request.current_state.cpu_limit)
        if cpu_limit > cpu_request * 3:
            return ScalingAction(
                action=ActionType.SCALE_DOWN,
                target_cpu_request=request.current_state.cpu_request,
                confidence=0.6,
                reason=(
                    f"CPU limit ({request.current_state.cpu_limit}) is significantly higher "
                    f"than request ({request.current_state.cpu_request}). "
                    "Consider right-sizing based on actual usage."
                ),
            )

        return None

    def _estimate_current_utilization(self, state: CurrentState) -> float:
        """Estimate current utilization from state.

        In production, this would query actual metrics.
        For now, returns a placeholder.
        """
        # This would normally come from metrics
        # Returning a moderate value for demonstration
        return 0.5

    def _get_predicted_utilization(
        self, predictions: Optional[list[PredictionPoint]]
    ) -> Optional[float]:
        """Get max predicted utilization from predictions."""
        if not predictions:
            return None

        # Return max predicted value in the forecast window
        return max(p.value for p in predictions)

    def _parse_cpu(self, cpu_str: str) -> float:
        """Parse CPU string to millicores."""
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1])
        else:
            return float(cpu_str) * 1000

    def _parse_memory(self, mem_str: str) -> float:
        """Parse memory string to bytes."""
        units = {
            "Ki": 1024,
            "Mi": 1024**2,
            "Gi": 1024**3,
            "K": 1000,
            "M": 1000**2,
            "G": 1000**3,
        }

        for unit, multiplier in units.items():
            if mem_str.endswith(unit):
                return float(mem_str[: -len(unit)]) * multiplier

        return float(mem_str)

    def get_stats(self) -> dict[str, Any]:
        """Get recommender statistics."""
        return {
            "total_recommendations": self._recommendation_count,
            "active_cooldowns": len(self._last_recommendations),
        }


# Global recommender instance
recommender_service = RecommenderService()
