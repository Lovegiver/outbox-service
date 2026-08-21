from __future__ import annotations

import pytest

from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.metric_definition_version_schema import MetricDefinitionVersionSchema
from app.models.schema_definition import SchemaDefinition
from app.services.metric_yaml_service import MetricYamlService
from app.services.processing_chain_builder_service import (
    ProcessingChainBuilderService,
)
from app.services.processing_chain_errors import ProcessingChainSelectionError


SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "country": {"type": "string"},
    },
    "required": ["amount", "country"],
}


class ChainRepository:
    def __init__(self) -> None:
        self.added = []

    def add(self, chain):
        chain.id = 100
        self.added.append(chain)
        return chain


class PlanRepository:
    def __init__(self) -> None:
        self.added = []
        self.by_chain = {}

    def add_all(self, plans):
        for index, plan in enumerate(plans, start=1):
            plan.id = index
        self.added.extend(plans)
        self.by_chain[100] = plans
        return plans

    def list_by_chain_id(self, chain_id):
        return self.by_chain.get(chain_id, [])


class CompatibilityRepository:
    def __init__(self, allowed: set[tuple[int, int]]) -> None:
        self.allowed = allowed

    def find_by_version_and_schema(
        self,
        metric_definition_version_id,
        schema_definition_id,
    ):
        if (metric_definition_version_id, schema_definition_id) in self.allowed:
            return MetricDefinitionVersionSchema(
                metric_definition_version_id=metric_definition_version_id,
                schema_definition_id=schema_definition_id,
            )
        return None


def _schema(event_type_id: int = 7) -> SchemaDefinition:
    value = SchemaDefinition(
        event_type_id=event_type_id,
        json_version_internal="1",
        json_schema=SCHEMA,
    )
    value.id = 30
    return value


def _version(
    version_id: int,
    definition_id: int,
    *,
    event_type_id: int = 7,
    code: str = "sales_total",
    path: str = "$.amount",
) -> MetricDefinitionVersion:
    definition = MetricDefinition(
        event_type_id=event_type_id,
        code=f"definition_{definition_id}",
        name="Metric",
    )
    definition.id = definition_id
    version = MetricDefinitionVersion(
        metric_definition_id=definition_id,
        yaml_version_number=1,
        yaml_content=(
            'version: "1.0"\nobservations:\n'
            f"  - code: {code}\n"
            "    transform: identity\n"
            f"    value_path: {path}\n"
        ),
        metric_definition=definition,
    )
    version.id = version_id
    return version


def _builder(allowed: set[tuple[int, int]]):
    chains = ChainRepository()
    plans = PlanRepository()
    builder = ProcessingChainBuilderService(
        processing_chain_repository=chains,  # type: ignore[arg-type]
        processing_plan_repository=plans,  # type: ignore[arg-type]
        compatibility_repository=CompatibilityRepository(allowed),  # type: ignore[arg-type]
        metric_yaml_service=MetricYamlService(),
    )
    return builder, chains, plans


def test_prepare_chain_is_deterministic_and_uses_canonical_compiler() -> None:
    first = _version(21, 11, code="revenue_total")
    second = _version(20, 10, code="sales_total")
    builder, _, _ = _builder({(20, 30), (21, 30)})

    prepared = builder.prepare_chain(7, _schema(), [first, second])
    repeated = builder.prepare_chain(7, _schema(), [second, first])

    assert [plan.metric_definition_id for plan in prepared.plans] == [10, 11]
    assert prepared.signature == repeated.signature
    assert all(
        plan.compiled_plan_json["compiler_version"] == "1.0"
        for plan in prepared.plans
    )


def test_prepare_chain_rejects_empty_selection() -> None:
    builder, _, _ = _builder(set())

    with pytest.raises(ProcessingChainSelectionError, match="At least one"):
        builder.prepare_chain(7, _schema(), [])


def test_prepare_chain_rejects_duplicate_metric_definition() -> None:
    first = _version(20, 10)
    second = _version(21, 10)
    builder, _, _ = _builder({(20, 30), (21, 30)})

    with pytest.raises(ProcessingChainSelectionError, match="two versions"):
        builder.prepare_chain(7, _schema(), [first, second])


def test_prepare_chain_rejects_missing_compatibility() -> None:
    builder, _, _ = _builder(set())

    with pytest.raises(ProcessingChainSelectionError, match="not compatible"):
        builder.prepare_chain(7, _schema(), [_version(20, 10)])


def test_prepare_chain_rejects_cross_event_type_version() -> None:
    builder, _, _ = _builder({(20, 30)})

    with pytest.raises(ProcessingChainSelectionError, match="another EventType"):
        builder.prepare_chain(
            7,
            _schema(),
            [_version(20, 10, event_type_id=8)],
        )


def test_compile_failure_before_persistence_leaves_no_partial_snapshot() -> None:
    builder, chains, plans = _builder({(20, 30), (21, 30)})

    with pytest.raises(Exception, match="missing"):
        builder.prepare_chain(
            7,
            _schema(),
            [_version(20, 10), _version(21, 11, path="$.missing")],
        )

    assert chains.added == []
    assert plans.added == []


def test_persist_chain_writes_complete_inactive_snapshot() -> None:
    builder, chains, plans = _builder({(20, 30)})
    prepared = builder.prepare_chain(7, _schema(), [_version(20, 10)])

    chain = builder.persist_chain(prepared, version_number=3)

    assert chain.version_number == 3
    assert chain.status == "DRAFT"
    assert chain.is_active is False
    assert chains.added == [chain]
    assert len(plans.added) == 1
    assert plans.added[0].compiled_plan_json is not None
    assert builder.signature_for_chain(chain.id) == prepared.signature
