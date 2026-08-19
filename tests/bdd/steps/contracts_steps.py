from pytest_bdd import given, parsers, then, when

from tests.domain.record import EventTypeRecord, ProjectRecord, SchemaDefinitionRecord
from tests.infrastructure.context import TestContext


def _contract_context(ctx: TestContext):
    context = getattr(ctx, "contract_context", None)
    if context is None:
        project = ctx.factory.project(ProjectRecord(name="OUTBOX"))
        event_type = ctx.factory.event_type(
            EventTypeRecord(project=project, code="OUTBOX_EVENT", name="Outbox Event Contract")
        )
        context = (project, event_type)
        setattr(ctx, "contract_context", context)
    return context


def _schema_from_table(datatable: list[list[str]]) -> dict:
    rows = datatable[1:] if datatable and datatable[0] == ["field", "value"] else datatable
    return {row[0]: row[1] for row in rows}


@given(parsers.parse('an {state} Outbox contract schema version "{version}" with schema:'))
def outbox_contract_schema(ctx: TestContext, state: str, version: str, datatable: list[list[str]]) -> None:
    _, event_type = _contract_context(ctx)
    ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_version_internal=version,
            json_schema=_schema_from_table(datatable),
            is_active=state == "active",
        )
    )


@given(parsers.parse('a user Project named "{name}" exists'))
def user_project_exists(ctx: TestContext, name: str) -> None:
    ctx.seed.project_registered(name)


@when("the latest Outbox contract is requested")
def latest_outbox_contract_requested(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.get("/contracts/outbox-event/latest")


@then(parsers.parse('the contract response should contain name "{name}" and version "{version}"'))
def contract_response_identity(ctx: TestContext, name: str, version: str) -> None:
    payload = ctx.last_response.json()
    assert payload["contract_name"] == name
    assert payload["version"] == version


@then("the contract response schema should equal:")
def contract_response_schema(ctx: TestContext, datatable: list[list[str]]) -> None:
    assert ctx.last_response.json()["schema"] == _schema_from_table(datatable), (
        ctx.last_response.json()["schema"],
        _schema_from_table(datatable),
    )
