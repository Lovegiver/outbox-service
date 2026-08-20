from __future__ import annotations

from app.metrics_engine.compiled_processing_plan import CompiledProcessingPlan
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository


class ProcessingPlanConfigurationError(RuntimeError):
    """Raised when an active ProcessingPlan is not executable as persisted."""


class ProcessingPlanProvider:
    """
    Provides runtime-ready analytical processing plans.

    This provider is the boundary between persisted ProcessingChain /
    ProcessingPlan configuration and the runtime metrics extraction engine.
    Runtime execution only reads ``compiled_plan_json``. It never rebuilds or
    recompiles a plan implicitly.
    """

    def __init__(
        self,
        processing_chain_repository: ProcessingChainRepository,
        processing_plan_repository: ProcessingPlanRepository,
    ) -> None:
        """
        Initialize the provider.

        Args:
            processing_chain_repository: Repository used to find the active
                ProcessingChain for an EventType and SchemaDefinition.
            processing_plan_repository: Repository used to list active plans
                attached to a ProcessingChain.
        """
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository

    def get_active_plans(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> list[CompiledProcessingPlan]:
        """
        Return compiled analytical plans for an active processing chain.

        Args:
            event_type_id: EventType identifier of the incoming event.
            schema_definition_id: SchemaDefinition identifier used to validate
                the incoming event.

        Returns:
            A list of compiled plans. Returns an empty list when no active chain
            exists for the provided scope.
        """
        active_chain = self.processing_chain_repository.find_active(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )

        if active_chain is None:
            return []

        plans = self.processing_plan_repository.list_active_by_chain_id(
            processing_chain_id=active_chain.id,
        )

        compiled_plans: list[CompiledProcessingPlan] = []

        for plan in plans:
            if plan.compiled_plan_json is None:
                raise ProcessingPlanConfigurationError(
                    f"Active ProcessingPlan {plan.id} has no compiled plan."
                )

            compiled_plans.append(
                CompiledProcessingPlan(
                    processing_chain_id=active_chain.id,
                    metric_definition_id=plan.metric_definition_id,
                    metric_definition_version_id=plan.metric_definition_version_id,
                    compiled_plan_json=plan.compiled_plan_json,
                )
            )

        return compiled_plans
