from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.container.service_factory import ServiceFactory
from app.main import app
from app.metrics_engine.metric_yaml_parser import MetricYamlParseError
from app.metrics_engine.metric_yaml_validator import MetricYamlValidationError
from tests.domain.record import EventTypeRecord, ProjectRecord, UserAccountRecord
from tests.infrastructure.context import TestContext


@dataclass(frozen=True)
class AuthorizedMetricRoute:
    """HTTP route coordinates for one administrator and EventType."""

    event_type_id: int
    headers: dict[str, str]


class FailingMetricDefinitionAdminService:
    """Raise one selected error from either YAML administration operation."""

    def __init__(self, error: Exception) -> None:
        """Store the error that each exercised service operation must raise."""
        self.error = error

    def create_metric_definition_version(self, **_kwargs: object) -> NoReturn:
        """Fail version creation at the service boundary."""
        raise self.error

    def preview_metric_yaml(self, **_kwargs: object) -> NoReturn:
        """Fail validation or preview at the service boundary."""
        raise self.error


@pytest.fixture
def authorized_metric_route(ctx: TestContext) -> AuthorizedMetricRoute:
    """Create the minimum persisted scope needed by the permission dependency."""
    suffix = uuid4().hex
    project = ctx.factory.project(ProjectRecord(name=f"router-errors-{suffix}"))
    event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=project,
            code=f"router.errors.{suffix}",
            name="Router error contract",
        )
    )
    user = ctx.factory.user_account(
        UserAccountRecord(
            email=f"router-errors-{suffix}@example.test",
            role="ADMIN",
        )
    )
    return AuthorizedMetricRoute(
        event_type_id=event_type.id,
        headers=ctx.auth.as_admin(user),
    )


def _install_failing_service(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    service = FailingMetricDefinitionAdminService(error)
    monkeypatch.setattr(
        ServiceFactory,
        "create_metric_definition_admin_service",
        classmethod(lambda _cls, _db: service),
    )


def _post_with_server_errors_captured(
    path: str,
    *,
    payload: dict[str, object],
    headers: dict[str, str],
) -> Response:
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post(path, json=payload, headers=headers)


def test_parse_error_remains_a_yaml_creation_error(
    ctx: TestContext,
    authorized_metric_route: AuthorizedMetricRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_service(
        monkeypatch,
        MetricYamlParseError("Metric YAML syntax is invalid"),
    )

    response = ctx.client.post(
        "/api/admin/event-types/"
        f"{authorized_metric_route.event_type_id}/metric-definitions/20/versions",
        json={"schema_definition_id": 30, "yaml_content": "invalid: ["},
        headers=authorized_metric_route.headers,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Metric YAML syntax is invalid"}


def test_validation_error_remains_an_invalid_preview(
    ctx: TestContext,
    authorized_metric_route: AuthorizedMetricRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_service(
        monkeypatch,
        MetricYamlValidationError("Unknown metric value path '$.missing'"),
    )

    response = ctx.client.post(
        "/api/admin/event-types/"
        f"{authorized_metric_route.event_type_id}/metric-definitions/yaml/preview",
        json={"schema_definition_id": 30, "yaml_content": "version: '1.0'"},
        headers=authorized_metric_route.headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "errors": ["Unknown metric value path '$.missing'"],
        "compiled_plan_json": None,
    }


@pytest.mark.parametrize("operation", ["validate", "preview"])
def test_unexpected_value_error_is_not_returned_as_invalid_yaml(
    ctx: TestContext,
    authorized_metric_route: AuthorizedMetricRoute,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    _install_failing_service(monkeypatch, ValueError("compiler invariant failed"))
    path = (
        "/api/admin/event-types/"
        f"{authorized_metric_route.event_type_id}/metric-definitions/yaml/"
        f"{operation}"
    )

    response = _post_with_server_errors_captured(
        path,
        payload={"schema_definition_id": 30, "yaml_content": "version: '1.0'"},
        headers=authorized_metric_route.headers,
    )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_unexpected_value_error_is_not_returned_as_yaml_422(
    ctx: TestContext,
    authorized_metric_route: AuthorizedMetricRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_service(monkeypatch, ValueError("service invariant failed"))

    response = _post_with_server_errors_captured(
        "/api/admin/event-types/"
        f"{authorized_metric_route.event_type_id}/metric-definitions/20/versions",
        payload={"schema_definition_id": 30, "yaml_content": "version: '1.0'"},
        headers=authorized_metric_route.headers,
    )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
