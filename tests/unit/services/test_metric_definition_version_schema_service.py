from __future__ import annotations

import pytest

from app.metrics_engine.metric_yaml_validator import MetricYamlValidationError
from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.metric_definition_version_schema import MetricDefinitionVersionSchema
from app.models.schema_definition import SchemaDefinition
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
)
from app.services.metric_definition_version_schema_service import (
    MetricDefinitionVersionSchemaService,
)
from app.services.metric_yaml_service import MetricYamlService


VALID_YAML = """version: "1.0"
observations:
  - code: sales_total
    transform: identity
    value_path: $.amount
"""
SCHEMA = {
    "type": "object",
    "properties": {"amount": {"type": "number"}},
    "required": ["amount"],
}


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


class VersionRepository:
    def __init__(self, version: MetricDefinitionVersion | None) -> None:
        self.version = version

    def find_by_id(self, _version_id: int):
        return self.version


class SchemaRepository:
    def __init__(self, schema: SchemaDefinition | None) -> None:
        self.schema = schema
        self.locked = False

    def find_by_id(self, _schema_id: int, *, for_update: bool = False):
        self.locked = self.locked or for_update
        return self.schema


class CompatibilityRepository:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added: list[MetricDefinitionVersionSchema] = []

    def find_by_version_and_schema(self, **_kwargs):
        return self.existing

    def add(self, compatibility):
        compatibility.id = 41
        self.added.append(compatibility)
        self.existing = compatibility
        return compatibility


def _version(event_type_id: int = 7, yaml_content: str = VALID_YAML):
    definition = MetricDefinition(
        event_type_id=event_type_id,
        code="sales",
        name="Sales",
    )
    definition.id = 10
    version = MetricDefinitionVersion(
        metric_definition_id=definition.id,
        yaml_version_number=1,
        yaml_content=yaml_content,
        metric_definition=definition,
    )
    version.id = 20
    return version


def _schema(event_type_id: int = 7):
    schema = SchemaDefinition(
        event_type_id=event_type_id,
        json_version_internal="1",
        json_schema=SCHEMA,
    )
    schema.id = 30
    return schema


def _service(version=None, schema=None, existing=None, yaml_service=None):
    session = FakeSession()
    compatibilities = CompatibilityRepository(existing)
    schemas = SchemaRepository(schema)
    service = MetricDefinitionVersionSchemaService(
        db=session,  # type: ignore[arg-type]
        compatibility_repository=compatibilities,  # type: ignore[arg-type]
        metric_definition_version_repository=VersionRepository(version),  # type: ignore[arg-type]
        schema_repository=schemas,  # type: ignore[arg-type]
        metric_yaml_service=yaml_service or MetricYamlService(),
    )
    return service, session, compatibilities, schemas


def test_valid_compatibility_is_revalidated_persisted_and_committed() -> None:
    service, session, repository, schemas = _service(_version(), _schema())

    compatibility = service.create_compatibility(7, 20, 30)

    assert compatibility.metric_definition_version_id == 20
    assert compatibility.schema_definition_id == 30
    assert repository.added == [compatibility]
    assert schemas.locked is True
    assert session.commits == 1
    assert session.rollbacks == 0


def test_identical_compatibility_request_is_idempotent() -> None:
    existing = MetricDefinitionVersionSchema(
        metric_definition_version_id=20,
        schema_definition_id=30,
    )
    existing.id = 41
    service, session, repository, _ = _service(
        _version(), _schema(), existing=existing
    )

    assert service.create_compatibility(7, 20, 30) is existing
    assert repository.added == []
    assert session.commits == 1


@pytest.mark.parametrize(
    ("version", "schema", "message"),
    [
        (None, _schema(), "MetricDefinitionVersion 20 not found"),
        (_version(), None, "SchemaDefinition 30 not found"),
    ],
)
def test_unknown_resources_are_explicit(version, schema, message) -> None:
    service, session, _, _ = _service(version, schema)

    with pytest.raises(MetricConfigurationNotFoundError, match=message):
        service.create_compatibility(7, 20, 30)

    assert session.rollbacks == 1


@pytest.mark.parametrize(
    ("version_event_type", "schema_event_type"),
    [(8, 7), (7, 8)],
)
def test_cross_event_type_resources_are_rejected(
    version_event_type: int,
    schema_event_type: int,
) -> None:
    service, session, repository, _ = _service(
        _version(version_event_type),
        _schema(schema_event_type),
    )

    with pytest.raises(MetricConfigurationScopeError):
        service.create_compatibility(7, 20, 30)

    assert repository.added == []
    assert session.rollbacks == 1


def test_incompatible_yaml_is_not_persisted() -> None:
    service, session, repository, schemas = _service(
        _version(
            yaml_content="""version: "1.0"
observations:
  - code: missing_total
    transform: identity
    value_path: $.missing
"""
        ),
        _schema(),
    )

    with pytest.raises(MetricYamlValidationError, match="missing"):
        service.create_compatibility(7, 20, 30)

    assert repository.added == []
    assert schemas.locked is False
    assert session.rollbacks == 1


def test_unexpected_compiler_error_is_visible_and_rolls_back() -> None:
    class BrokenYamlService:
        def compile(self, **_kwargs):
            raise RuntimeError("compiler defect")

    service, session, repository, _ = _service(
        _version(), _schema(), yaml_service=BrokenYamlService()
    )

    with pytest.raises(RuntimeError, match="compiler defect"):
        service.create_compatibility(7, 20, 30)

    assert repository.added == []
    assert session.rollbacks == 1
