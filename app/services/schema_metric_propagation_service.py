"""Controlled propagation of active metric snapshots to a new JSON schema."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.metrics_engine.metric_yaml_parser import MetricYamlParseError
from app.metrics_engine.metric_yaml_validator import MetricYamlValidationError
from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
)
from app.services.metric_yaml_service import MetricYamlService
from app.services.processing_chain_builder_service import (
    PreparedProcessingChain,
    PreparedProcessingPlan,
    ProcessingChainBuilderService,
)
from app.services.processing_chain_errors import ProcessingChainSelectionError


OPTIONAL_RUNTIME_WARNING = (
    "Statically compatible; missing optional-field runtime behavior is deferred "
    "to BDD-015C"
)


@dataclass(frozen=True)
class PropagatedMetricResult:
    """Compatibility outcome for one version from the source snapshot."""

    metric_definition_id: int
    metric_definition_version_id: int
    compatible: bool
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SchemaMetricPropagationResult:
    """Complete analysis and optional persisted candidate for one propagation."""

    source_schema_definition_id: int
    target_schema_definition_id: int
    evaluated_count: int
    compatible_count: int
    incompatible_count: int
    results: list[PropagatedMetricResult]
    proposed_metric_definition_version_ids: list[int]
    candidate_processing_chain_id: int | None
    activation_allowed: bool


class SchemaMetricPropagationService:
    """Revalidate exactly the versions used by a previous active chain."""

    def __init__(
        self,
        db: Session,
        schema_repository: SchemaRepository,
        processing_chain_repository: ProcessingChainRepository,
        processing_plan_repository: ProcessingPlanRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        compatibility_repository: MetricDefinitionVersionSchemaRepository,
        metric_yaml_service: MetricYamlService,
        processing_chain_builder_service: ProcessingChainBuilderService,
    ) -> None:
        self.db = db
        self.schema_repository = schema_repository
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )
        self.compatibility_repository = compatibility_repository
        self.metric_yaml_service = metric_yaml_service
        self.processing_chain_builder_service = processing_chain_builder_service

    def propagate(
        self,
        event_type_id: int,
        source_schema_definition_id: int,
        target_schema_definition_id: int,
    ) -> SchemaMetricPropagationResult:
        """Analyze all source plans, then atomically persist proven results."""
        try:
            return self._propagate(
                event_type_id=event_type_id,
                source_schema_definition_id=source_schema_definition_id,
                target_schema_definition_id=target_schema_definition_id,
            )
        except Exception:
            self.db.rollback()
            raise

    def _propagate(
        self,
        event_type_id: int,
        source_schema_definition_id: int,
        target_schema_definition_id: int,
    ) -> SchemaMetricPropagationResult:
        """Implement propagation under the public rollback boundary."""
        source_schema = self._resolve_schema(
            source_schema_definition_id, event_type_id
        )
        target_schema = self._resolve_schema(
            target_schema_definition_id, event_type_id
        )
        if source_schema.id == target_schema.id:
            raise ProcessingChainSelectionError(
                "Source and target SchemaDefinition must be different"
            )

        source_chain = self.processing_chain_repository.find_active(
            event_type_id=event_type_id,
            schema_definition_id=source_schema.id,
        )
        if source_chain is None:
            self.db.commit()
            return SchemaMetricPropagationResult(
                source_schema_definition_id=source_schema.id,
                target_schema_definition_id=target_schema.id,
                evaluated_count=0,
                compatible_count=0,
                incompatible_count=0,
                results=[],
                proposed_metric_definition_version_ids=[],
                candidate_processing_chain_id=None,
                activation_allowed=False,
            )

        source_plans = self.processing_plan_repository.list_by_chain_id(
            source_chain.id
        )
        version_ids = [plan.metric_definition_version_id for plan in source_plans]
        versions = self.metric_definition_version_repository.find_by_ids(version_ids)
        versions_by_id = {version.id: version for version in versions}
        if len(versions_by_id) != len(set(version_ids)):
            raise ProcessingChainSelectionError(
                "The source ProcessingChain references a missing metric version"
            )

        results: list[PropagatedMetricResult] = []
        compatible_prepared_plans: list[PreparedProcessingPlan] = []
        for source_plan in source_plans:
            metric_version = versions_by_id[source_plan.metric_definition_version_id]
            try:
                compilation = self.metric_yaml_service.compile(
                    yaml_content=metric_version.yaml_content,
                    json_schema=target_schema.json_schema,
                )
            except (MetricYamlParseError, MetricYamlValidationError) as exc:
                results.append(
                    PropagatedMetricResult(
                        metric_definition_id=metric_version.metric_definition_id,
                        metric_definition_version_id=metric_version.id,
                        compatible=False,
                        reason=str(exc),
                    )
                )
                continue

            warnings = (
                [OPTIONAL_RUNTIME_WARNING]
                if _compiled_plan_uses_optional_path(
                    compilation.compiled_plan_json
                )
                else []
            )
            results.append(
                PropagatedMetricResult(
                    metric_definition_id=metric_version.metric_definition_id,
                    metric_definition_version_id=metric_version.id,
                    compatible=True,
                    warnings=warnings,
                )
            )
            compatible_prepared_plans.append(
                PreparedProcessingPlan(
                    metric_definition_id=metric_version.metric_definition_id,
                    metric_definition_version_id=metric_version.id,
                    compiled_plan_json=compilation.compiled_plan_json,
                )
            )

        prepared = (
            PreparedProcessingChain(
                event_type_id=event_type_id,
                schema_definition_id=target_schema.id,
                plans=tuple(compatible_prepared_plans),
            )
            if compatible_prepared_plans
            else None
        )

        try:
            self.schema_repository.lock_by_ids(
                [source_schema.id, target_schema.id]
            )
            locked_source_chain = self.processing_chain_repository.find_active(
                event_type_id=event_type_id,
                schema_definition_id=source_schema.id,
            )
            if locked_source_chain is None or locked_source_chain.id != source_chain.id:
                raise ProcessingChainSelectionError(
                    "Source ProcessingChain changed during schema propagation"
                )

            for result in results:
                if not result.compatible:
                    continue
                if self.compatibility_repository.find_by_version_and_schema(
                    metric_definition_version_id=(
                        result.metric_definition_version_id
                    ),
                    schema_definition_id=target_schema.id,
                ) is None:
                    self.compatibility_repository.add(
                        MetricDefinitionVersionSchema(
                            metric_definition_version_id=(
                                result.metric_definition_version_id
                            ),
                            schema_definition_id=target_schema.id,
                        )
                    )

            candidate_id = None
            if prepared is not None:
                candidate_status = (
                    "DRAFT"
                    if all(result.compatible for result in results)
                    else "INCOMPLETE"
                )
                candidate = self._find_equivalent_candidate(
                    event_type_id=event_type_id,
                    schema_definition_id=target_schema.id,
                    prepared=prepared,
                    candidate_status=candidate_status,
                )
                if candidate is None:
                    candidate = self.processing_chain_builder_service.persist_chain(
                        prepared=prepared,
                        version_number=(
                            self.processing_chain_repository
                            .find_next_version_number(
                                event_type_id=event_type_id,
                                schema_definition_id=target_schema.id,
                            )
                        ),
                        status=candidate_status,
                    )
                candidate_id = candidate.id

            self.db.commit()
            return SchemaMetricPropagationResult(
                source_schema_definition_id=source_schema.id,
                target_schema_definition_id=target_schema.id,
                evaluated_count=len(results),
                compatible_count=sum(result.compatible for result in results),
                incompatible_count=sum(
                    not result.compatible for result in results
                ),
                results=results,
                proposed_metric_definition_version_ids=[
                    result.metric_definition_version_id
                    for result in results
                    if result.compatible
                ],
                candidate_processing_chain_id=candidate_id,
                activation_allowed=(
                    bool(results) and all(result.compatible for result in results)
                ),
            )
        except Exception:
            self.db.rollback()
            raise

    def _find_equivalent_candidate(
        self,
        event_type_id: int,
        schema_definition_id: int,
        prepared: PreparedProcessingChain,
        candidate_status: str,
    ):
        for chain in self.processing_chain_repository.list_by_scope(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        ):
            reusable_statuses = (
                {"ACTIVE", "DRAFT"}
                if candidate_status == "DRAFT"
                else {"INCOMPLETE"}
            )
            if chain.status not in reusable_statuses:
                continue
            if self.processing_chain_builder_service.matches_complete_snapshot(
                chain.id,
                prepared,
            ):
                return chain
        return None

    def _resolve_schema(self, schema_definition_id: int, event_type_id: int):
        schema = self.schema_repository.find_by_id(schema_definition_id)
        if schema is None:
            raise MetricConfigurationNotFoundError(
                f"SchemaDefinition {schema_definition_id} not found"
            )
        if schema.event_type_id != event_type_id:
            raise MetricConfigurationScopeError(
                "SchemaDefinition belongs to another EventType"
            )
        return schema


def _compiled_plan_uses_optional_path(value) -> bool:
    """Return whether a compiled document contains a statically optional path."""
    if isinstance(value, dict):
        if value.get("required") is False and "path" in value:
            return True
        return any(_compiled_plan_uses_optional_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_compiled_plan_uses_optional_path(item) for item in value)
    return False
