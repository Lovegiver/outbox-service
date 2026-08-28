"""Unit proofs for atomic and idempotent Builder creation orchestration."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.event_type import EventType
from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)
from app.models.schema_definition import SchemaDefinition
from app.services.metric_builder_errors import (
    MetricBuilderAlreadyExistsError,
    MetricBuilderCreationConflictError,
    MetricBuilderNameCollisionError,
    MetricBuilderNotFoundError,
    MetricBuilderUnsafeError,
)
from app.services.metric_builder_schema_analyzer import (
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalyzer,
)
from app.services.metric_builder_service import MetricBuilderService
from app.services.metric_yaml_service import MetricYamlService

SCHEMA = {
    "type": "object",
    "required": ["amount", "status", "active"],
    "properties": {
        "amount": {"type": ["number", "null"], "minimum": 0},
        "unsafe_amount": {"type": "number"},
        "status": {"type": "string", "enum": ["new", "done"]},
        "active": {"type": "boolean"},
    },
}


def _assign_id(identifier: int):
    def assign(entity):
        entity.id = identifier
        return entity

    return assign


def _service() -> tuple[MetricBuilderService, dict[str, Mock]]:
    db = Mock()
    event_repository = Mock()
    event_repository.find_by_id.return_value = EventType(
        id=12,
        project_id=4,
        code="order.created",
        name="Order created",
    )
    schema_repository = Mock()
    schema_repository.find_by_id.return_value = SchemaDefinition(
        id=7,
        event_type_id=12,
        json_version_internal="1",
        json_schema=deepcopy(SCHEMA),
        is_active=True,
    )
    definition_repository = Mock()
    definition_repository.list_by_event_type.return_value = []
    definition_repository.find_by_event_type_and_code.return_value = None
    definition_repository.add.side_effect = _assign_id(101)
    version_repository = Mock()
    version_repository.add.side_effect = _assign_id(201)
    compatibility_repository = Mock()
    compatibility_repository.add.side_effect = _assign_id(301)
    limits = MetricBuilderAnalysisLimits(max_enum_values=5, max_labels=3)
    service = MetricBuilderService(
        db=db,
        event_type_repository=event_repository,
        schema_repository=schema_repository,
        metric_definition_repository=definition_repository,
        metric_definition_version_repository=version_repository,
        compatibility_repository=compatibility_repository,
        metric_yaml_service=MetricYamlService(),
        schema_analyzer=MetricBuilderSchemaAnalyzer(limits),
        limits=limits,
    )
    return service, {
        "db": db,
        "event": event_repository,
        "schema": schema_repository,
        "definition": definition_repository,
        "version": version_repository,
        "compatibility": compatibility_repository,
    }


def _create(service: MetricBuilderService, **overrides):
    request = {
        "event_type_id": 12,
        "code": "sales_total",
        "name": "Sales total",
        "description": "Count sales",
        "intent": "sum_value",
        "value_path": "$.amount",
        "labels": {"status": "$.status"},
        "schema_definition_id": 7,
        "yaml_version_label": "initial",
    }
    request.update(overrides)
    return service.create_metric_from_builder(**request)


def test_create_persists_exact_triplet_with_one_commit_and_flush_ids() -> None:
    service, dependencies = _service()

    result = _create(service)

    assert result.created is True
    assert result.metric_definition.id == 101
    assert result.metric_definition_version.id == 201
    assert result.compatibility.id == 301
    assert result.compatibility.metric_definition_version_id == 201
    assert result.compatibility.schema_definition_id == 7
    assert result.metric_definition_version.metric_definition_id == 101
    assert result.metric_definition_version.yaml_version_number == 1
    assert result.metric_definition_version.yaml_content == result.yaml_content
    assert result.compiled_plan_json["compiler_version"] == "1.1"
    assert result.compiled_plan_json["observations"][0]["value"]["nullable"] is True
    dependencies["db"].commit.assert_called_once_with()
    dependencies["db"].rollback.assert_not_called()
    dependencies["event"].find_by_id.assert_called_once_with(12, for_update=True)
    dependencies["schema"].find_by_id.assert_called_once_with(7, for_update=True)


@pytest.mark.parametrize(
    "failing_dependency", ["definition", "version", "compatibility"]
)
def test_any_persistence_failure_rolls_back_without_intermediate_commit(
    failing_dependency: str,
) -> None:
    service, dependencies = _service()
    dependencies[failing_dependency].add.side_effect = RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        _create(service)

    dependencies["db"].commit.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_compilation_failure_happens_before_first_write_and_rolls_back() -> None:
    service, dependencies = _service()
    service.metric_yaml_service.compile = Mock(side_effect=RuntimeError("compiler"))

    with pytest.raises(RuntimeError, match="compiler"):
        _create(service)

    dependencies["definition"].add.assert_not_called()
    dependencies["version"].add.assert_not_called()
    dependencies["compatibility"].add.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_create_revalidates_counter_safety_before_any_write() -> None:
    service, dependencies = _service()

    with pytest.raises(MetricBuilderUnsafeError):
        _create(service, value_path="$.unsafe_amount")

    dependencies["definition"].add.assert_not_called()
    dependencies["version"].add.assert_not_called()
    dependencies["compatibility"].add.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_missing_locked_event_type_is_a_narrow_error_and_rolls_back() -> None:
    service, dependencies = _service()
    dependencies["event"].find_by_id.return_value = None

    with pytest.raises(MetricBuilderNotFoundError):
        _create(service)

    dependencies["definition"].add.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_identical_replay_returns_same_triplet_without_new_rows() -> None:
    service, dependencies = _service()
    preview = service.preview_metric(
        12,
        "sales_total",
        "sum_value",
        "$.amount",
        {"status": "$.status"},
        7,
    )
    definition = MetricDefinition(
        id=101,
        event_type_id=12,
        code="sales_total",
        name="Sales total",
        description="Count sales",
        is_active=True,
    )
    version = MetricDefinitionVersion(
        id=201,
        metric_definition_id=101,
        yaml_version_number=1,
        yaml_version_label="initial",
        yaml_content=preview.yaml_content,
        is_active=True,
    )
    compatibility = MetricDefinitionVersionSchema(
        id=301,
        metric_definition_version_id=201,
        schema_definition_id=7,
    )
    dependencies["definition"].list_by_event_type.return_value = [definition]
    dependencies["definition"].find_by_event_type_and_code.return_value = definition
    dependencies["version"].find_by_metric_definition_and_number.return_value = version
    dependencies[
        "compatibility"
    ].find_by_version_and_schema.return_value = compatibility

    result = _create(service)

    assert result.created is False
    assert result.metric_definition.id == 101
    assert result.metric_definition_version.id == 201
    assert result.compatibility.id == 301
    dependencies["definition"].add.assert_not_called()
    dependencies["version"].add.assert_not_called()
    dependencies["compatibility"].add.assert_not_called()
    dependencies["db"].commit.assert_called_once_with()


def test_same_code_with_different_content_is_a_stable_conflict() -> None:
    service, dependencies = _service()
    definition = MetricDefinition(
        id=101,
        event_type_id=12,
        code="sales_total",
        name="Different",
        description="Count sales",
        is_active=True,
    )
    dependencies["definition"].list_by_event_type.return_value = [definition]
    dependencies["definition"].find_by_event_type_and_code.return_value = definition
    dependencies["version"].find_by_metric_definition_and_number.return_value = None

    with pytest.raises(MetricBuilderAlreadyExistsError) as raised:
        _create(service)

    assert raised.value.public_message().startswith("BUILDER_METRIC_ALREADY_EXISTS")
    dependencies["db"].rollback.assert_called_once_with()
    dependencies["definition"].add.assert_not_called()


def test_existing_code_without_exact_compatibility_is_not_repaired() -> None:
    service, dependencies = _service()
    preview = service.preview_metric(
        12,
        "sales_total",
        "sum_value",
        "$.amount",
        {"status": "$.status"},
        7,
    )
    definition = MetricDefinition(
        id=101,
        event_type_id=12,
        code="sales_total",
        name="Sales total",
        description="Count sales",
        is_active=True,
    )
    dependencies["definition"].list_by_event_type.return_value = [definition]
    dependencies["definition"].find_by_event_type_and_code.return_value = definition
    dependencies[
        "version"
    ].find_by_metric_definition_and_number.return_value = MetricDefinitionVersion(
        id=201,
        metric_definition_id=101,
        yaml_version_number=1,
        yaml_version_label="initial",
        yaml_content=preview.yaml_content,
        is_active=True,
    )
    dependencies["compatibility"].find_by_version_and_schema.return_value = None

    with pytest.raises(MetricBuilderAlreadyExistsError):
        _create(service)

    dependencies["definition"].add.assert_not_called()
    dependencies["version"].add.assert_not_called()
    dependencies["compatibility"].add.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_normalized_name_collision_is_checked_under_scope_lock() -> None:
    service, dependencies = _service()
    dependencies["definition"].list_by_event_type.return_value = [
        MetricDefinition(
            id=99,
            event_type_id=12,
            code="sales-total",
            name="Existing",
        )
    ]

    with pytest.raises(MetricBuilderNameCollisionError):
        _create(service)

    dependencies["event"].find_by_id.assert_called_once_with(12, for_update=True)
    dependencies["definition"].add.assert_not_called()
    dependencies["db"].rollback.assert_called_once_with()


def test_integrity_error_is_rolled_back_and_translated() -> None:
    service, dependencies = _service()
    dependencies["compatibility"].add.side_effect = IntegrityError(
        "statement",
        {},
        RuntimeError("duplicate"),
    )

    with pytest.raises(MetricBuilderCreationConflictError) as raised:
        _create(service)

    assert raised.value.public_message().startswith("BUILDER_CREATION_CONFLICT")
    dependencies["db"].rollback.assert_called_once_with()
    dependencies["db"].commit.assert_not_called()


def test_label_order_and_request_input_do_not_change_canonical_yaml() -> None:
    service, _ = _service()
    first_labels = {"status": "$.status", "active": "$.active"}
    second_labels = {"active": "$.active", "status": "$.status"}
    original = deepcopy(first_labels)

    first = service.preview_metric(
        12,
        "sales_total",
        "sum_value",
        "$.amount",
        first_labels,
        7,
    )
    second = service.preview_metric(
        12,
        "sales_total",
        "sum_value",
        "$.amount",
        second_labels,
        7,
    )

    assert first.valid is True
    assert first.yaml_content == second.yaml_content
    assert first.compiled_plan_json == second.compiled_plan_json
    assert first_labels == original
