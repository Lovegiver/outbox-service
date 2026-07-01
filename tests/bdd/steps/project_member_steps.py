from pytest_bdd import given
from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


project_has_member_pattern = parsers.parse(
    'project "{project_name}" has member "{email}" with role "{role}"'
)
project_members_listed_pattern = parsers.parse(
    'project "{project_name}" members are listed'
)
project_member_added_pattern = parsers.parse(
    'user "{email}" is added to project "{project_name}" with role "{role}"'
)
project_member_role_changed_pattern = parsers.parse(
    'user "{email}" role is changed to "{role}" in project "{project_name}"'
)
project_member_removed_pattern = parsers.parse(
    'user "{email}" is removed from project "{project_name}"'
)
project_should_have_member_pattern = parsers.parse(
    'project "{project_name}" should have member "{email}" with role "{role}"'
)
project_should_not_have_member_pattern = parsers.parse(
    'project "{project_name}" should not have member "{email}"'
)


@given(project_has_member_pattern)
def project_has_member(
    ctx: TestContext,
    project_name: str,
    email: str,
    role: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    user = ctx.probe.user_account.get_by_email(email)

    ctx.seed.project_member_registered(
        project=project,
        user=user,
        role=role,
    )


@when(project_members_listed_pattern)
def project_members_are_listed(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.get(
        f"/api/admin/projects/{project.id}/members",
        headers=ctx.request_headers or {},
    )


@when(project_member_added_pattern)
def project_member_is_added(
    ctx: TestContext,
    project_name: str,
    email: str,
    role: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.post(
        f"/api/admin/projects/{project.id}/members",
        json={
            "email": email,
            "role": role,
        },
        headers=ctx.request_headers or {},
    )


@when(project_member_role_changed_pattern)
def project_member_role_is_changed(
    ctx: TestContext,
    project_name: str,
    email: str,
    role: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    user = ctx.probe.user_account.get_by_email(email)

    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}/members/{user.id}/role",
        json={
            "role": role,
        },
        headers=ctx.request_headers or {},
    )


@when(project_member_removed_pattern)
def project_member_is_removed(
    ctx: TestContext,
    project_name: str,
    email: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    user = ctx.probe.user_account.get_by_email(email)

    ctx.last_response = ctx.client.delete(
        f"/api/admin/projects/{project.id}/members/{user.id}",
        headers=ctx.request_headers or {},
    )


@then(project_should_have_member_pattern)
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


@then(project_should_not_have_member_pattern)
def project_member_absence_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    email: str,
) -> None:
    step_registry.project_member_assertion_for("is absent")(
        ctx=ctx,
        project_name=project_name,
        email=email,
    )
