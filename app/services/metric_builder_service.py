"""Business Metrics Builder orchestration for Counter previews."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar, Optional

import yaml
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.metrics_engine.metric_yaml_parser import MetricYamlParseError
from app.metrics_engine.metric_yaml_validator import MetricYamlValidationError
from app.metrics_engine.prometheus_renderer import (
    PrometheusRenderingError,
    normalize_prometheus_metric_name,
    validate_prometheus_business_label_name,
)
from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)
from app.models.schema_definition import SchemaDefinition
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.metric_definition_repository import MetricDefinitionRepository
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_builder_errors import (
    MetricBuilderAlreadyExistsError,
    MetricBuilderCardinalityBudgetError,
    MetricBuilderCardinalityUnboundedError,
    MetricBuilderContractError,
    MetricBuilderCreationConflictError,
    MetricBuilderError,
    MetricBuilderNameCollisionError,
    MetricBuilderNotFoundError,
    MetricBuilderScopeError,
    MetricBuilderUnsafeError,
    MetricBuilderUnsupportedError,
)
from app.services.metric_builder_schema_analyzer import (
    AnalyzedBuilderField,
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalysisError,
    MetricBuilderSchemaAnalyzer,
    SchemaAnalysisStatus,
)
from app.services.metric_cardinality_service import (
    CardinalityAssessment,
    CardinalityDecision,
    CardinalityPlan,
    MetricCardinalityService,
)
from app.services.metric_yaml_service import MetricYamlCompilation, MetricYamlService


@dataclass(frozen=True)
class BuilderPreview:
    """Result of a non-persisting Builder preview."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    yaml_content: Optional[str]
    compiled_plan_json: Optional[dict[str, Any]]
    prometheus_metric_name: Optional[str]
    safeguards: Optional[CardinalityAssessment]


@dataclass(frozen=True)
class BuilderCreateResult:
    """Result of one atomic or idempotently reused Builder creation."""

    metric_definition: MetricDefinition
    metric_definition_version: MetricDefinitionVersion
    compatibility: MetricDefinitionVersionSchema
    schema_definition: SchemaDefinition
    yaml_content: str
    compiled_plan_json: dict[str, Any]
    prometheus_metric_name: str
    created: bool
    warnings: list[str]
    safeguards: Optional[CardinalityAssessment]


@dataclass(frozen=True)
class _PreparedBuilderMetric:
    """Canonical non-persisted content used by preview and creation."""

    schema_definition: SchemaDefinition
    yaml_content: str
    compilation: MetricYamlCompilation
    prometheus_metric_name: str


_METRIC_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


class MetricBuilderService:
    """Analyze schemas and validate business Counter intents before preview."""

    INTENT_TO_TRANSFORM: ClassVar[dict[str, str]] = {
        "count_event": "constant",
        "count_by_label": "constant",
        "sum_value": "identity",
        "count_array_items": "count",
        "measure_string_length": "length",
        "count_boolean_true": "to_number",
    }

    def __init__(
        self,
        db: Session,
        event_type_repository: EventTypeRepository,
        schema_repository: SchemaRepository,
        metric_definition_repository: MetricDefinitionRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        compatibility_repository: MetricDefinitionVersionSchemaRepository,
        metric_yaml_service: MetricYamlService,
        schema_analyzer: MetricBuilderSchemaAnalyzer,
        limits: MetricBuilderAnalysisLimits,
        processing_chain_repository: Optional[ProcessingChainRepository] = None,
        processing_plan_repository: Optional[ProcessingPlanRepository] = None,
        cardinality_service: Optional[MetricCardinalityService] = None,
    ) -> None:
        """Initialize the Builder with read and canonical compilation services."""
        self.db = db
        self.event_type_repository = event_type_repository
        self.schema_repository = schema_repository
        self.metric_definition_repository = metric_definition_repository
        self.metric_definition_version_repository = metric_definition_version_repository
        self.compatibility_repository = compatibility_repository
        self.metric_yaml_service = metric_yaml_service
        self.schema_analyzer = schema_analyzer
        self.limits = limits
        self.processing_chain_repository = processing_chain_repository
        self.processing_plan_repository = processing_plan_repository
        self.cardinality_service = cardinality_service or MetricCardinalityService(
            schema_analyzer,
            limits,
        )

    def list_schema_fields(
        self,
        event_type_id: int,
        schema_definition_id: Optional[int] = None,
    ) -> tuple[SchemaDefinition, list[AnalyzedBuilderField]]:
        """Return conservative descriptors for the exact requested schema."""
        schema_definition = self._resolve_schema_definition(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )
        return schema_definition, self._analyze(schema_definition.json_schema)

    def preview_metric(
        self,
        event_type_id: int,
        metric_code: str,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        schema_definition_id: Optional[int] = None,
    ) -> BuilderPreview:
        """Validate and compile a Counter draft without persisting data."""
        try:
            prepared = self._prepare_metric(
                event_type_id=event_type_id,
                metric_code=metric_code,
                intent=intent,
                value_path=value_path,
                labels=labels,
                schema_definition_id=schema_definition_id,
            )
            safeguards = self._assess_candidate(
                event_type_id=event_type_id,
                prepared=prepared,
            )
            return BuilderPreview(
                valid=safeguards.accepted,
                errors=[item.message for item in safeguards.errors],
                warnings=[item.message for item in safeguards.warnings],
                yaml_content=prepared.yaml_content,
                compiled_plan_json=prepared.compilation.compiled_plan_json,
                prometheus_metric_name=prepared.prometheus_metric_name,
                safeguards=safeguards,
            )
        except (
            MetricBuilderContractError,
            MetricBuilderNameCollisionError,
            MetricBuilderUnsafeError,
            MetricBuilderUnsupportedError,
            MetricYamlParseError,
            MetricYamlValidationError,
        ) as exc:
            message = (
                exc.public_message()
                if isinstance(exc, MetricBuilderError)
                else str(exc)
            )
            return BuilderPreview(
                valid=False,
                errors=[message],
                warnings=[],
                yaml_content=None,
                compiled_plan_json=None,
                prometheus_metric_name=None,
                safeguards=None,
            )

    def create_metric_from_builder(
        self,
        event_type_id: int,
        code: str,
        name: str,
        description: Optional[str],
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        schema_definition_id: Optional[int] = None,
        yaml_version_label: Optional[str] = None,
    ) -> BuilderCreateResult:
        """Persist definition, first version, and exact compatibility atomically."""
        try:
            event_type = self.event_type_repository.find_by_id(
                event_type_id,
                for_update=True,
            )
            if event_type is None:
                raise MetricBuilderNotFoundError("EventType not found")

            prepared = self._prepare_metric(
                event_type_id=event_type_id,
                metric_code=code,
                intent=intent,
                value_path=value_path,
                labels=labels,
                schema_definition_id=schema_definition_id,
                lock_schema=True,
                allow_existing_code=True,
            )
            existing = self.metric_definition_repository.find_by_event_type_and_code(
                event_type_id=event_type_id,
                code=code,
            )
            safeguards = self._assess_candidate(
                event_type_id=event_type_id,
                prepared=prepared,
                replacing_metric_code=code if existing is not None else None,
            )
            self._require_safe_cardinality(safeguards)
            if existing is not None:
                result = self._reuse_identical_creation(
                    existing=existing,
                    prepared=prepared,
                    name=name,
                    description=description,
                    yaml_version_label=yaml_version_label,
                )
                self.db.commit()
                return BuilderCreateResult(
                    **{**result.__dict__, "safeguards": safeguards}
                )

            metric_definition = self.metric_definition_repository.add(
                MetricDefinition(
                    event_type_id=event_type_id,
                    code=code,
                    name=name,
                    description=description,
                    is_active=True,
                )
            )
            metric_definition_version = self.metric_definition_version_repository.add(
                MetricDefinitionVersion(
                    metric_definition_id=metric_definition.id,
                    yaml_version_number=1,
                    yaml_version_label=yaml_version_label,
                    yaml_content=prepared.yaml_content,
                    is_active=True,
                )
            )
            compatibility = self.compatibility_repository.add(
                MetricDefinitionVersionSchema(
                    metric_definition_version_id=metric_definition_version.id,
                    schema_definition_id=prepared.schema_definition.id,
                )
            )
            self.db.commit()
            return BuilderCreateResult(
                metric_definition=metric_definition,
                metric_definition_version=metric_definition_version,
                compatibility=compatibility,
                schema_definition=prepared.schema_definition,
                yaml_content=prepared.yaml_content,
                compiled_plan_json=prepared.compilation.compiled_plan_json,
                prometheus_metric_name=prepared.prometheus_metric_name,
                created=True,
                warnings=[item.message for item in safeguards.warnings],
                safeguards=safeguards,
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise MetricBuilderCreationConflictError(
                "Concurrent Builder creation conflicts with persisted state"
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def _prepare_metric(
        self,
        *,
        event_type_id: int,
        metric_code: str,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        schema_definition_id: Optional[int],
        lock_schema: bool = False,
        allow_existing_code: bool = False,
    ) -> _PreparedBuilderMetric:
        """Reanalyze, generate, and canonically compile one Builder request."""
        schema_definition = self._resolve_schema_definition(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
            for_update=lock_schema,
        )
        fields = self._analyze(schema_definition.json_schema)
        prometheus_name = self._validate_metric_code_and_collision(
            event_type_id=event_type_id,
            metric_code=metric_code,
            allow_existing_code=allow_existing_code,
        )
        self._validate_intent(
            intent=intent,
            value_path=value_path,
            labels=labels,
            fields=fields,
        )
        metric_yaml = self._build_metric_yaml(
            metric_code=metric_code,
            intent=intent,
            value_path=value_path,
            labels=labels,
        )
        yaml_content = yaml.safe_dump(
            metric_yaml,
            sort_keys=False,
            allow_unicode=True,
        )
        compilation = self.metric_yaml_service.compile(
            yaml_content=yaml_content,
            json_schema=schema_definition.json_schema,
        )
        return _PreparedBuilderMetric(
            schema_definition=schema_definition,
            yaml_content=yaml_content,
            compilation=compilation,
            prometheus_metric_name=prometheus_name,
        )

    def _reuse_identical_creation(
        self,
        *,
        existing: MetricDefinition,
        prepared: _PreparedBuilderMetric,
        name: str,
        description: Optional[str],
        yaml_version_label: Optional[str],
    ) -> BuilderCreateResult:
        """Return an exact persisted triplet or reject conflicting content."""
        version = self.metric_definition_version_repository.find_by_metric_definition_and_number(
            existing.id, 1
        )
        if version is None:
            raise MetricBuilderAlreadyExistsError(
                "Existing metric has no coherent first Builder version"
            )
        compatibility = self.compatibility_repository.find_by_version_and_schema(
            metric_definition_version_id=version.id,
            schema_definition_id=prepared.schema_definition.id,
        )
        if compatibility is None:
            raise MetricBuilderAlreadyExistsError(
                "Existing metric targets different schema compatibility"
            )

        existing_compilation = self.metric_yaml_service.compile(
            yaml_content=version.yaml_content,
            json_schema=prepared.schema_definition.json_schema,
        )
        is_identical = (
            existing.name == name
            and existing.description == description
            and existing.is_active is True
            and version.yaml_version_label == yaml_version_label
            and version.is_active is True
            and existing_compilation.metric_yaml == prepared.compilation.metric_yaml
            and existing_compilation.compiled_plan_json
            == prepared.compilation.compiled_plan_json
        )
        if not is_identical:
            raise MetricBuilderAlreadyExistsError(
                "Metric code already exists with different functional content"
            )
        return BuilderCreateResult(
            metric_definition=existing,
            metric_definition_version=version,
            compatibility=compatibility,
            schema_definition=prepared.schema_definition,
            yaml_content=version.yaml_content,
            compiled_plan_json=existing_compilation.compiled_plan_json,
            prometheus_metric_name=prepared.prometheus_metric_name,
            created=False,
            warnings=[],
            safeguards=None,
        )

    def _assess_candidate(
        self,
        *,
        event_type_id: int,
        prepared: _PreparedBuilderMetric,
        replacing_metric_code: Optional[str] = None,
    ) -> CardinalityAssessment:
        """Estimate a candidate plus the active EventType snapshot, read-only."""
        candidate = CardinalityPlan(
            compiled_plan_json=prepared.compilation.compiled_plan_json,
            schema_definition_id=prepared.schema_definition.id,
            json_schema=prepared.schema_definition.json_schema,
        )
        current: list[CardinalityPlan] = []
        replaced: list[CardinalityPlan] = []
        if (
            self.processing_chain_repository is not None
            and self.processing_plan_repository is not None
        ):
            for chain in self.processing_chain_repository.list_active_by_event_type(
                event_type_id
            ):
                schema = self.schema_repository.find_by_id(chain.schema_definition_id)
                if schema is None:
                    continue
                for plan in self.processing_plan_repository.list_active_by_chain_id(
                    chain.id
                ):
                    if isinstance(plan.compiled_plan_json, dict):
                        entry = CardinalityPlan(
                            compiled_plan_json=plan.compiled_plan_json,
                            schema_definition_id=schema.id,
                            json_schema=schema.json_schema,
                        )
                        current.append(entry)
                        if (
                            replacing_metric_code is not None
                            and self._plan_has_metric_code(
                                entry.compiled_plan_json, replacing_metric_code
                            )
                        ):
                            replaced.append(entry)
        return self.cardinality_service.assess(
            current_plans=current,
            candidate_plans=[candidate],
            replaced_plans=replaced,
        )

    @staticmethod
    def _plan_has_metric_code(plan: dict[str, Any], metric_code: str) -> bool:
        """Return whether one historical plan belongs to a replaced metric code."""
        observations = plan.get("observations", [])
        return isinstance(observations, list) and any(
            isinstance(item, dict) and item.get("metric_code") == metric_code
            for item in observations
        )

    @staticmethod
    def _require_safe_cardinality(assessment: CardinalityAssessment) -> None:
        """Translate static safety diagnostics into narrow create errors."""
        if assessment.decision is not CardinalityDecision.ERROR:
            return
        codes = {item.code for item in assessment.errors}
        message = assessment.errors[0].message
        if "BUILDER_CARDINALITY_BUDGET_EXCEEDED" in codes:
            raise MetricBuilderCardinalityBudgetError(message)
        raise MetricBuilderCardinalityUnboundedError(message)

    def _analyze(self, schema: dict[str, Any]) -> list[AnalyzedBuilderField]:
        """Translate bounded-analysis errors into one public Builder error."""
        try:
            return self.schema_analyzer.analyze(schema)
        except MetricBuilderSchemaAnalysisError as exc:
            raise MetricBuilderUnsupportedError(str(exc)) from exc

    def _resolve_schema_definition(
        self,
        event_type_id: int,
        schema_definition_id: Optional[int],
        *,
        for_update: bool = False,
    ) -> SchemaDefinition:
        """Resolve an active or explicit schema and enforce exact scope."""
        if schema_definition_id is None:
            schema_definition = self.schema_repository.find_active_by_event_type(
                event_type_id,
                for_update=for_update,
            )
        else:
            schema_definition = self.schema_repository.find_by_id(
                schema_definition_id,
                for_update=for_update,
            )
        if schema_definition is None:
            raise MetricBuilderNotFoundError("SchemaDefinition not found")
        if schema_definition.event_type_id != event_type_id:
            raise MetricBuilderScopeError(
                "SchemaDefinition belongs to another EventType"
            )
        return schema_definition

    def _validate_metric_code_and_collision(
        self,
        *,
        event_type_id: int,
        metric_code: str,
        allow_existing_code: bool = False,
    ) -> str:
        """Validate a bounded business code and its final Prometheus identity."""
        if (
            not metric_code
            or len(metric_code) > 150
            or _CONTROL_CHARACTER.search(metric_code)
            or _METRIC_CODE.fullmatch(metric_code) is None
        ):
            raise MetricBuilderContractError(
                "Metric code must be 1..150 characters from [A-Za-z0-9_.:-]"
            )
        final_name = normalize_prometheus_metric_name(metric_code)
        for existing in self.metric_definition_repository.list_by_event_type(
            event_type_id
        ):
            if allow_existing_code and existing.code == metric_code:
                continue
            if normalize_prometheus_metric_name(existing.code) == final_name:
                raise MetricBuilderNameCollisionError(
                    f"Metric code collides with an existing Prometheus name '{final_name}'"
                )
        return final_name

    def _validate_intent(
        self,
        *,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        fields: list[AnalyzedBuilderField],
    ) -> None:
        """Enforce intent arity, schema membership, Counter, and label safety."""
        if intent not in self.INTENT_TO_TRANSFORM:
            raise MetricBuilderContractError(f"Unknown metric intent '{intent}'")
        if len(labels) > self.limits.max_labels:
            raise MetricBuilderContractError(
                f"At most {self.limits.max_labels} labels are allowed"
            )
        by_path = {field.path: field for field in fields}

        if intent == "count_event":
            if value_path is not None or labels:
                raise MetricBuilderContractError(
                    "count_event accepts neither value_path nor labels"
                )
            return
        if intent == "count_by_label":
            if value_path is not None or len(labels) != 1:
                raise MetricBuilderContractError(
                    "count_by_label requires exactly one label and no value_path"
                )
        elif value_path is None:
            raise MetricBuilderContractError(f"{intent} requires one value_path")

        if value_path is not None:
            field = self._require_field(value_path, by_path)
            if field.analysis_status is SchemaAnalysisStatus.UNSUPPORTED:
                raise MetricBuilderUnsupportedError(field.analysis_reason)
            if intent not in field.value_intents:
                if intent == "sum_value" and field.json_type in {"number", "integer"}:
                    raise MetricBuilderUnsafeError(field.analysis_reason)
                raise MetricBuilderContractError(
                    f"Intent '{intent}' is incompatible with '{field.json_type}'"
                )

        normalized_label_names: set[str] = set()
        for label_name, label_path in labels.items():
            self._validate_label_name(label_name)
            if label_name in normalized_label_names:
                raise MetricBuilderContractError("Label names must be unique")
            normalized_label_names.add(label_name)
            field = self._require_field(label_path, by_path)
            if not field.label_allowed:
                error_type = (
                    MetricBuilderUnsupportedError
                    if field.analysis_status is SchemaAnalysisStatus.UNSUPPORTED
                    else MetricBuilderUnsafeError
                )
                raise error_type(
                    field.label_rejection_reason or "Selected label is unsafe"
                )

    def _require_field(
        self,
        path: str,
        fields: dict[str, AnalyzedBuilderField],
    ) -> AnalyzedBuilderField:
        """Require exact membership in the canonical schema field inventory."""
        if (
            len(path) > self.limits.max_path_length
            or _CONTROL_CHARACTER.search(path)
            or path not in fields
        ):
            raise MetricBuilderContractError(
                "Selected path is not a canonical field of this SchemaDefinition"
            )
        segments = path[2:].replace("[*]", "").split(".")
        if len(segments) > self.limits.max_path_segments:
            raise MetricBuilderContractError("Selected path has too many segments")
        return fields[path]

    def _validate_label_name(self, label_name: str) -> None:
        """Validate a bounded, non-reserved Prometheus label name."""
        if len(
            label_name
        ) > self.limits.max_label_name_length or _CONTROL_CHARACTER.search(label_name):
            raise MetricBuilderContractError("Label name is invalid or too long")
        try:
            validate_prometheus_business_label_name(label_name)
        except PrometheusRenderingError as exc:
            raise MetricBuilderContractError(str(exc)) from exc

    def _build_metric_yaml(
        self,
        metric_code: str,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
    ) -> dict[str, Any]:
        """Map the six closed intents to the five executable transforms."""
        transform = self.INTENT_TO_TRANSFORM[intent]
        observation: dict[str, Any] = {
            "code": metric_code,
            "transform": transform,
            "labels": dict(sorted(labels.items())),
        }
        if transform != "constant":
            observation["value_path"] = value_path
        return {"version": "1.0", "observations": [observation]}
