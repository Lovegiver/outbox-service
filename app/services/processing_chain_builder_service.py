"""Build immutable ProcessingChain snapshots without owning transactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.processing_chain import ProcessingChain
from app.models.processing_plan import ProcessingPlan
from app.models.schema_definition import SchemaDefinition
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.services.metric_yaml_service import MetricYamlService
from app.services.processing_chain_errors import ProcessingChainSelectionError


@dataclass(frozen=True)
class PreparedProcessingPlan:
    """One deterministic, validated plan ready for persistence."""

    metric_definition_id: int
    metric_definition_version_id: int
    compiled_plan_json: dict[str, Any]


@dataclass(frozen=True)
class PreparedProcessingChain:
    """A complete in-memory snapshot prepared before the critical section."""

    event_type_id: int
    schema_definition_id: int
    plans: tuple[PreparedProcessingPlan, ...]

    @property
    def signature(self) -> tuple[tuple[int, int, str], ...]:
        """Return a stable functional identity for idempotent rebuilds."""
        import json

        return tuple(
            (
                plan.metric_definition_id,
                plan.metric_definition_version_id,
                json.dumps(
                    plan.compiled_plan_json,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            for plan in self.plans
        )


class ProcessingChainBuilderService:
    """Validate, compile, and persist complete inactive snapshots."""

    def __init__(
        self,
        processing_chain_repository: ProcessingChainRepository,
        processing_plan_repository: ProcessingPlanRepository,
        compatibility_repository: MetricDefinitionVersionSchemaRepository,
        metric_yaml_service: MetricYamlService,
    ) -> None:
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository
        self.compatibility_repository = compatibility_repository
        self.metric_yaml_service = metric_yaml_service

    def prepare_chain(
        self,
        event_type_id: int,
        schema_definition: SchemaDefinition,
        metric_definition_versions: list[MetricDefinitionVersion],
    ) -> PreparedProcessingChain:
        """Compile an explicit compatible selection without writing data."""
        if schema_definition.event_type_id != event_type_id:
            raise ProcessingChainSelectionError(
                "SchemaDefinition belongs to another EventType"
            )
        if not metric_definition_versions:
            raise ProcessingChainSelectionError(
                "At least one compatible metric definition version is required"
            )

        plans: list[PreparedProcessingPlan] = []
        seen_metric_definitions: set[int] = set()
        ordered_versions = sorted(
            metric_definition_versions,
            key=lambda version: (
                version.metric_definition_id,
                version.yaml_version_number,
                version.id,
            ),
        )

        for metric_version in ordered_versions:
            metric_definition = metric_version.metric_definition
            if metric_definition.event_type_id != event_type_id:
                raise ProcessingChainSelectionError(
                    f"MetricDefinitionVersion {metric_version.id} belongs "
                    "to another EventType"
                )
            if metric_version.metric_definition_id in seen_metric_definitions:
                raise ProcessingChainSelectionError(
                    "A ProcessingChain cannot contain two versions of the same "
                    "MetricDefinition"
                )
            compatibility = self.compatibility_repository.find_by_version_and_schema(
                metric_definition_version_id=metric_version.id,
                schema_definition_id=schema_definition.id,
            )
            if compatibility is None:
                raise ProcessingChainSelectionError(
                    f"MetricDefinitionVersion {metric_version.id} is not compatible "
                    f"with SchemaDefinition {schema_definition.id}"
                )

            compilation = self.metric_yaml_service.compile(
                yaml_content=metric_version.yaml_content,
                json_schema=schema_definition.json_schema,
            )
            plans.append(
                PreparedProcessingPlan(
                    metric_definition_id=metric_version.metric_definition_id,
                    metric_definition_version_id=metric_version.id,
                    compiled_plan_json=compilation.compiled_plan_json,
                )
            )
            seen_metric_definitions.add(metric_version.metric_definition_id)

        return PreparedProcessingChain(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition.id,
            plans=tuple(plans),
        )

    def persist_chain(
        self,
        prepared: PreparedProcessingChain,
        version_number: int,
        *,
        status: str = "DRAFT",
    ) -> ProcessingChain:
        """Persist a fully prepared inactive snapshot in the caller transaction."""
        if status not in {"DRAFT", "INCOMPLETE"}:
            raise ProcessingChainSelectionError(
                f"Unsupported inactive ProcessingChain status: {status}"
            )
        if not prepared.plans or any(
            plan.compiled_plan_json is None for plan in prepared.plans
        ):
            raise ProcessingChainSelectionError(
                "A persisted ProcessingChain candidate requires complete plans"
            )
        chain = self.processing_chain_repository.add(
            ProcessingChain(
                event_type_id=prepared.event_type_id,
                schema_definition_id=prepared.schema_definition_id,
                version_number=version_number,
                status=status,
                is_active=False,
            )
        )
        self.processing_plan_repository.add_all(
            [
                ProcessingPlan(
                    processing_chain_id=chain.id,
                    metric_definition_id=plan.metric_definition_id,
                    metric_definition_version_id=plan.metric_definition_version_id,
                    position=position,
                    is_active=True,
                    compiled_plan_json=plan.compiled_plan_json,
                )
                for position, plan in enumerate(prepared.plans)
            ]
        )
        return chain

    def matches_complete_snapshot(
        self,
        processing_chain_id: int,
        prepared: PreparedProcessingChain,
    ) -> bool:
        """Return whether a stored chain is a complete copy of ``prepared``."""
        plans = self.processing_plan_repository.list_by_chain_id(
            processing_chain_id
        )
        if not plans or any(
            not plan.is_active or plan.compiled_plan_json is None
            for plan in plans
        ):
            return False
        return self.signature_for_chain(processing_chain_id) == prepared.signature

    def signature_for_chain(
        self,
        processing_chain_id: int,
    ) -> tuple[tuple[int, int, str], ...]:
        """Load the stable functional identity of a persisted snapshot."""
        import json

        plans = self.processing_plan_repository.list_by_chain_id(
            processing_chain_id
        )
        return tuple(
            (
                plan.metric_definition_id,
                plan.metric_definition_version_id,
                json.dumps(
                    plan.compiled_plan_json,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            for plan in plans
        )
