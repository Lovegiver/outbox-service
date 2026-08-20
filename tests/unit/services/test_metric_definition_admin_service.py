from __future__ import annotations

import pytest

from app.metrics_engine.metric_yaml_validator import MetricYamlValidationError
from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.schema_definition import SchemaDefinition
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
    MetricDefinitionAdminService,
)
from app.services.metric_yaml_service import MetricYamlService


VALID_YAML = """version: "1.0"
observations:
  - code: products_sold_total
    transform: constant
"""
JSON_SCHEMA = {"type": "object", "properties": {}}


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed: list[object] = []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, value: object) -> None:
        self.refreshed.append(value)


class FakeMetricDefinitionRepository:
    def __init__(self, metric_definition: MetricDefinition | None) -> None:
        self.metric_definition = metric_definition
        self.lock_requests: list[bool] = []
        self.added: list[MetricDefinition] = []

    def add(self, metric_definition: MetricDefinition) -> MetricDefinition:
        self.added.append(metric_definition)
        metric_definition.id = 100
        return metric_definition

    def find_by_id(
        self,
        _metric_definition_id: int,
        *,
        for_update: bool = False,
    ) -> MetricDefinition | None:
        self.lock_requests.append(for_update)
        return self.metric_definition

    def list_by_event_type(self, _event_type_id: int) -> list[MetricDefinition]:
        return [] if self.metric_definition is None else [self.metric_definition]


class FakeMetricDefinitionVersionRepository:
    def __init__(self, next_version: int = 1, fail_add: bool = False) -> None:
        self.next_version = next_version
        self.fail_add = fail_add
        self.added: list[MetricDefinitionVersion] = []

    def find_next_version_number(self, _metric_definition_id: int) -> int:
        return self.next_version

    def add(self, version: MetricDefinitionVersion) -> MetricDefinitionVersion:
        if self.fail_add:
            raise RuntimeError("database write failed")
        version.id = 200
        self.added.append(version)
        return version

    def list_by_metric_definition(
        self,
        _metric_definition_id: int,
    ) -> list[MetricDefinitionVersion]:
        return list(self.added)


class FakeSchemaRepository:
    def __init__(self, schema_definition: SchemaDefinition | None) -> None:
        self.schema_definition = schema_definition

    def find_by_id(self, _schema_definition_id: int) -> SchemaDefinition | None:
        return self.schema_definition


def _metric_definition(event_type_id: int = 10) -> MetricDefinition:
    value = MetricDefinition(
        event_type_id=event_type_id,
        code="sales_metrics",
        name="Sales metrics",
        is_active=True,
    )
    value.id = 20
    return value


def _schema_definition(event_type_id: int = 10) -> SchemaDefinition:
    value = SchemaDefinition(
        event_type_id=event_type_id,
        json_version_internal="1",
        json_schema=JSON_SCHEMA,
        is_active=True,
    )
    value.id = 30
    return value


def _service(
    *,
    metric_definition: MetricDefinition | None = None,
    schema_definition: SchemaDefinition | None = None,
    next_version: int = 1,
    fail_add: bool = False,
):
    session = FakeSession()
    definition_repository = FakeMetricDefinitionRepository(metric_definition)
    version_repository = FakeMetricDefinitionVersionRepository(
        next_version=next_version,
        fail_add=fail_add,
    )
    service = MetricDefinitionAdminService(
        db=session,  # type: ignore[arg-type]
        metric_definition_repository=definition_repository,  # type: ignore[arg-type]
        metric_definition_version_repository=version_repository,  # type: ignore[arg-type]
        schema_repository=FakeSchemaRepository(schema_definition),  # type: ignore[arg-type]
        metric_yaml_service=MetricYamlService(),
    )
    return service, session, definition_repository, version_repository


def test_preview_compiles_without_writing() -> None:
    service, session, _, versions = _service(
        metric_definition=_metric_definition(),
        schema_definition=_schema_definition(),
    )

    preview = service.preview_metric_yaml(10, 30, VALID_YAML)

    assert preview.compiled_plan_json["compiler_version"] == "1.0"
    assert versions.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


def test_invalid_preview_does_not_write() -> None:
    service, session, _, versions = _service(
        schema_definition=_schema_definition(),
    )

    with pytest.raises(MetricYamlValidationError):
        service.preview_metric_yaml(
            10,
            30,
            "version: '2.0'\nobservations: []\n",
        )

    assert versions.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


def test_create_assigns_next_version_and_preserves_yaml() -> None:
    service, session, definitions, versions = _service(
        metric_definition=_metric_definition(),
        schema_definition=_schema_definition(),
        next_version=3,
    )

    created = service.create_metric_definition_version(
        event_type_id=10,
        metric_definition_id=20,
        schema_definition_id=30,
        yaml_version_label="release",
        yaml_content=VALID_YAML,
    )

    assert created.yaml_version_number == 3
    assert created.yaml_content == VALID_YAML
    assert definitions.lock_requests == [True]
    assert versions.added == [created]
    assert session.commits == 1
    assert session.refreshed == [created]


def test_invalid_creation_has_no_partial_version() -> None:
    service, session, _, versions = _service(
        metric_definition=_metric_definition(),
        schema_definition=_schema_definition(),
    )

    with pytest.raises(MetricYamlValidationError):
        service.create_metric_definition_version(
            event_type_id=10,
            metric_definition_id=20,
            schema_definition_id=30,
            yaml_version_label=None,
            yaml_content="version: '1.0'\nobservations: []\n",
        )

    assert versions.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


def test_database_failure_rolls_back_creation() -> None:
    service, session, _, _ = _service(
        metric_definition=_metric_definition(),
        schema_definition=_schema_definition(),
        fail_add=True,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        service.create_metric_definition_version(
            event_type_id=10,
            metric_definition_id=20,
            schema_definition_id=30,
            yaml_version_label=None,
            yaml_content=VALID_YAML,
        )

    assert session.commits == 0
    assert session.rollbacks == 1


def test_unknown_metric_definition_is_explicit() -> None:
    service, _, _, _ = _service(schema_definition=_schema_definition())

    with pytest.raises(MetricConfigurationNotFoundError, match="not found"):
        service.create_metric_definition_version(
            10, 999, 30, None, VALID_YAML
        )


def test_metric_definition_outside_event_type_is_rejected() -> None:
    service, _, _, _ = _service(
        metric_definition=_metric_definition(event_type_id=11),
        schema_definition=_schema_definition(),
    )

    with pytest.raises(MetricConfigurationScopeError, match="does not belong"):
        service.list_metric_definition_versions(10, 20)


def test_schema_outside_event_type_is_rejected() -> None:
    service, _, _, _ = _service(
        schema_definition=_schema_definition(event_type_id=11),
    )

    with pytest.raises(MetricConfigurationScopeError, match="does not belong"):
        service.preview_metric_yaml(10, 30, VALID_YAML)


def test_unknown_schema_is_explicit() -> None:
    service, _, _, _ = _service()

    with pytest.raises(MetricConfigurationNotFoundError, match="not found"):
        service.preview_metric_yaml(10, 999, VALID_YAML)
