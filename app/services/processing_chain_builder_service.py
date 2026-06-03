from __future__ import annotations

from app.models.processing_chain import ProcessingChain
from app.models.processing_plan import ProcessingPlan
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository


class ProcessingChainBuilderService:
    def __init__(
        self,
        processing_chain_repository: ProcessingChainRepository,
        processing_plan_repository: ProcessingPlanRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
    ) -> None:
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )

    def build_chain(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> ProcessingChain:
        version_number = self.processing_chain_repository.find_next_version_number(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )

        chain = ProcessingChain(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
            version_number=version_number,
            status="DRAFT",
            is_active=False,
        )

        saved_chain = self.processing_chain_repository.add(chain)

        metric_definition_versions = (
            self.metric_definition_version_repository
            .find_latest_compatible_versions(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )
        )

        plans = [
            ProcessingPlan(
                processing_chain_id=saved_chain.id,
                metric_definition_id=metric_definition_version.metric_definition_id,
                metric_definition_version_id=metric_definition_version.id,
                position=index,
                is_active=True,
            )
            for index, metric_definition_version
            in enumerate(metric_definition_versions)
        ]

        self.processing_plan_repository.add_all(plans)

        return saved_chain