from typing import Optional

from pytest_bdd import given, parsers, then, when

from tests.bdd.registry import StepRegistry
from tests.domain.record import EventTypeRecord
from tests.infrastructure.context import TestContext


def _optional_cell(value: str) -> Optional[str]:
    normalized = value.strip()
    return normalized or None


project_registered_pattern = parsers.parse(
    '{presence} project is registered with name "{project_name}"'
)
project_created_pattern = parsers.parse(
    'project "{project_name}" is created with description "{description}"'
)
project_disabled_pattern = parsers.parse('project "{project_name}" is disabled')
project_disabled_by_id_pattern = parsers.parse(
    "project with id {project_id:d} is disabled"
)
project_should_be_registered_pattern = parsers.parse(
    '{presence} project should be registered with name "{project_name}"'
)
project_member_role_pattern = parsers.parse(
    'project "{project_name}" should have member "{email}" with role "{role}"'
)
project_status_pattern = parsers.parse('project "{project_name}" should be {status}')
project_consulted_pattern = parsers.parse('project "{project_name}" is consulted')
project_renamed_pattern = parsers.parse(
    'project "{project_name}" is renamed to "{new_name}"'
)
project_description_updated_pattern = parsers.parse(
    'project "{project_name}" description is changed to "{description}"'
)
project_description_cleared_pattern = parsers.parse(
    'project "{project_name}" description is explicitly cleared'
)
project_enabled_pattern = parsers.parse('project "{project_name}" is enabled')
project_name_assertion_pattern = parsers.parse(
    'project should be stored with name "{project_name}"'
)
project_description_assertion_pattern = parsers.parse(
    'project "{project_name}" should have description "{description}"'
)


@given(project_registered_pattern)
def project_registration_precondition(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    project_name: str,
) -> None:
    step_registry.project_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        project_name=project_name,
    )


@given("the following projects are registered:")
def following_projects_are_registered(
    ctx: TestContext,
    datatable: list[list[str]],
) -> None:
    headers = datatable[0]
    rows = datatable[1:]

    for row in rows:
        project_data = dict(zip(headers, row))

        project = ctx.seed.project_registered(
            name=project_data["name"],
            description=_optional_cell(project_data.get("description", "")),
            project_status=project_data.get("project status", "active"),
        )

        owner_email = _optional_cell(project_data.get("owner email", ""))
        owner_role = _optional_cell(project_data.get("owner role", ""))

        if owner_email is not None and owner_role is not None:
            user = ctx.probe.user_account.get_by_email(owner_email)
            ctx.seed.project_member_registered(
                project=project,
                user=user,
                role=owner_role,
            )


@when(project_created_pattern)
def project_is_created_with_description(
    ctx: TestContext,
    project_name: str,
    description: str,
) -> None:
    ctx.last_response = ctx.client.post(
        "/api/admin/projects",
        json={
            "name": project_name,
            "description": description,
        },
        headers=ctx.request_headers or {},
    )


@when("projects are listed")
def projects_are_listed(
    ctx: TestContext,
) -> None:
    ctx.last_response = ctx.client.get(
        "/api/admin/projects",
        headers=ctx.request_headers or {},
    )


@when(project_disabled_pattern)
def project_is_disabled(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}/disable",
        headers=ctx.request_headers or {},
    )


@when(project_disabled_by_id_pattern)
def project_with_id_is_disabled(
    ctx: TestContext,
    project_id: int,
) -> None:
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project_id}/disable",
        headers=ctx.request_headers or {},
    )


@when(project_consulted_pattern)
def project_is_consulted(ctx: TestContext, project_name: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.get(
        f"/api/admin/projects/{project.id}",
        headers=ctx.request_headers or {},
    )


@when(project_renamed_pattern)
def project_is_renamed(
    ctx: TestContext,
    project_name: str,
    new_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}",
        json={"name": new_name},
        headers=ctx.request_headers or {},
    )


@when(project_description_updated_pattern)
def project_description_is_updated(
    ctx: TestContext,
    project_name: str,
    description: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}",
        json={"description": description},
        headers=ctx.request_headers or {},
    )


@when(project_description_cleared_pattern)
def project_description_is_cleared(ctx: TestContext, project_name: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}",
        json={"description": None},
        headers=ctx.request_headers or {},
    )


@when(project_enabled_pattern)
def project_is_enabled(ctx: TestContext, project_name: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}/enable",
        headers=ctx.request_headers or {},
    )


@when("an empty Project update is submitted")
def empty_project_update_is_submitted(ctx: TestContext) -> None:
    project = ctx.probe.project.get_by_name("Hermes")
    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}",
        json={},
        headers=ctx.request_headers or {},
    )


@given(parsers.parse('project "{project_name}" has one EventType'))
def project_has_one_event_type(ctx: TestContext, project_name: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.factory.event_type(
        EventTypeRecord(
            project=project,
            code="project.lifecycle.test",
            name="Project lifecycle test",
        )
    )


@then(project_should_be_registered_pattern)
def project_registration_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    project_name: str,
) -> None:
    step_registry.project_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        project_name=project_name,
    )


@then(project_member_role_pattern)
def project_member_role_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    email: str,
    role: str,
) -> None:
    step_registry.project_member_assertion_for("has role")(
        ctx=ctx,
        project_name=project_name,
        email=email,
        role=role,
    )


@then(project_status_pattern)
def project_status_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    status: str,
) -> None:
    step_registry.project_assertion_for("has status")(
        ctx=ctx,
        project_name=project_name,
        status=status,
    )


@then(project_name_assertion_pattern)
def project_name_is_stored(ctx: TestContext, project_name: str) -> None:
    assert ctx.probe.project.exists_by_name(project_name)


@then(project_description_assertion_pattern)
def project_description_is_stored(
    ctx: TestContext,
    project_name: str,
    description: str,
) -> None:
    details = ctx.probe.project.get_details_by_name(project_name)
    assert details["description"] == description


@then(parsers.parse('project "{project_name}" should have no description'))
def project_has_no_description(ctx: TestContext, project_name: str) -> None:
    details = ctx.probe.project.get_details_by_name(project_name)
    assert details["description"] is None


@then(parsers.parse('project "{project_name}" should still have {count:d} member'))
def project_keeps_members(ctx: TestContext, project_name: str, count: int) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    assert ctx.probe.project.count_members(project.id) == count


@then(parsers.parse('project "{project_name}" should still have {count:d} EventType'))
def project_keeps_event_types(ctx: TestContext, project_name: str, count: int) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    assert ctx.probe.project.count_event_types(project.id) == count


@then(parsers.parse('the response should describe project "{project_name}"'))
def response_describes_project(ctx: TestContext, project_name: str) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.json()["name"] == project_name
