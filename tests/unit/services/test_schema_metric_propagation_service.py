from __future__ import annotations

import pytest

from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.processing_chain import ProcessingChain
from app.models.processing_plan import ProcessingPlan
from app.models.schema_definition import SchemaDefinition
from app.services.schema_metric_propagation_service import (
    SchemaMetricPropagationService,
    _compiled_plan_uses_optional_path,
)


class Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _schema(schema_id: int):
    schema = SchemaDefinition(
        event_type_id=7,
        json_version_internal=str(schema_id),
        json_schema={"type": "object", "properties": {}},
    )
    schema.id = schema_id
    return schema


def _version():
    definition = MetricDefinition(event_type_id=7, code="sales", name="Sales")
    definition.id = 10
    version = MetricDefinitionVersion(
        metric_definition_id=10,
        yaml_version_number=1,
        yaml_content="version: '1.0'\nobservations: [{code: x, transform: constant}]\n",
        metric_definition=definition,
    )
    version.id = 20
    return version


def _active_chain():
    chain = ProcessingChain(
        event_type_id=7,
        schema_definition_id=30,
        version_number=1,
        status="ACTIVE",
        is_active=True,
    )
    chain.id = 40
    return chain


def _plan():
    plan = ProcessingPlan(
        processing_chain_id=40,
        metric_definition_id=10,
        metric_definition_version_id=20,
        position=0,
        compiled_plan_json={"compiler_version": "1.0"},
    )
    plan.id = 50
    return plan


def test_unexpected_analysis_error_rolls_back_and_is_not_an_incompatibility() -> None:
    session = Session()
    schemas = {30: _schema(30), 31: _schema(31)}
    version = _version()

    class Schemas:
        def find_by_id(self, schema_id):
            return schemas.get(schema_id)

    class Chains:
        def find_active(self, **_kwargs):
            return _active_chain()

    class Plans:
        def list_by_chain_id(self, _chain_id):
            return [_plan()]

    class Versions:
        def find_by_ids(self, _ids):
            return [version]

    class BrokenCompiler:
        def compile(self, **_kwargs):
            raise RuntimeError("unexpected compiler defect")

    service = SchemaMetricPropagationService(
        db=session,  # type: ignore[arg-type]
        schema_repository=Schemas(),  # type: ignore[arg-type]
        processing_chain_repository=Chains(),  # type: ignore[arg-type]
        processing_plan_repository=Plans(),  # type: ignore[arg-type]
        metric_definition_version_repository=Versions(),  # type: ignore[arg-type]
        compatibility_repository=object(),  # type: ignore[arg-type]
        metric_yaml_service=BrokenCompiler(),  # type: ignore[arg-type]
        processing_chain_builder_service=object(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="unexpected compiler defect"):
        service.propagate(7, 30, 31)

    assert session.commits == 0
    assert session.rollbacks == 1


def test_optional_path_detection_is_recursive_and_precise() -> None:
    assert _compiled_plan_uses_optional_path(
        {"observations": [{"value": {"path": "$.discount", "required": False}}]}
    )
    assert not _compiled_plan_uses_optional_path(
        {"observations": [{"value": {"path": "$.amount", "required": True}}]}
    )
    assert not _compiled_plan_uses_optional_path({"required": False})
