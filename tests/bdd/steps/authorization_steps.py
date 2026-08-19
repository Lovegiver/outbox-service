from pytest_bdd import given, parsers, then, when

from tests.infrastructure.context import TestContext


@given(parsers.parse('a "{role}" actor for project "{project_name}"'))
def actor_for_project(ctx: TestContext, role: str, project_name: str) -> None:
    global_role = "ADMIN" if role == "ADMIN" else "USER"
    user = ctx.seed.user_registered(
        email=f"{role.lower()}@example.com",
        password="ValidPassword123!",
        global_role=global_role,
    )
    project = ctx.seed.project_registered(project_name)
    if role not in {"ADMIN", "NON_MEMBER"}:
        ctx.seed.project_member_registered(project=project, user=user, role=role)
    ctx.seed.event_type_registered(
        project=project,
        code="article.analyzed",
        name="Article analyzed",
    )
    ctx.request_headers = ctx.auth.as_admin(user) if role == "ADMIN" else ctx.auth.as_user(user)


@given(parsers.parse('project "{project_name}" exists for authorization checks'))
def project_exists_for_authorization(ctx: TestContext, project_name: str) -> None:
    ctx.seed.project_registered(project_name)


@when(parsers.parse('the actor exercises "{permission}" on project "{project_name}"'))
def actor_exercises_permission(
    ctx: TestContext,
    permission: str,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project,
        "article.analyzed",
    )
    headers = ctx.request_headers or {}
    actions = {
        "PROJECT_READ": lambda: ctx.client.get(
            f"/api/admin/projects/{project.id}/members", headers=headers
        ),
        "PROJECT_WRITE": lambda: ctx.client.patch(
            f"/api/admin/projects/{project.id}/disable", headers=headers
        ),
        "EVENT_TYPE_READ": lambda: ctx.client.get(
            f"/api/admin/event-types/by-project/{project.id}", headers=headers
        ),
        "EVENT_TYPE_WRITE": lambda: ctx.client.post(
            "/api/admin/event-types",
            json={"project_id": project.id, "code": "order.created", "name": "Order created"},
            headers=headers,
        ),
        "SCHEMA_READ": lambda: ctx.client.get(
            f"/api/admin/event-types/{event_type.id}/schemas", headers=headers
        ),
        "SCHEMA_WRITE": lambda: ctx.client.post(
            f"/api/admin/event-types/{event_type.id}/schemas",
            json={"json_version_internal": "1.0", "json_schema": {"type": "object"}},
            headers=headers,
        ),
        "ROUTE_READ": lambda: ctx.client.get(
            f"/api/admin/event-types/{event_type.id}/routes", headers=headers
        ),
        "ROUTE_WRITE": lambda: ctx.client.post(
            f"/api/admin/event-types/{event_type.id}/routes",
            json={
                "routing_key": "article.analyzed",
                "destination_name": "audit-target",
                "destination_url": "https://example.test/events",
            },
            headers=headers,
        ),
        "API_KEY_READ": lambda: ctx.client.get(
            f"/api/admin/projects/{project.id}/api-keys", headers=headers
        ),
        "API_KEY_WRITE": lambda: ctx.client.post(
            f"/api/admin/projects/{project.id}/api-keys",
            json={"name": "authorization-key"},
            headers=headers,
        ),
        "METRICS_READ": lambda: ctx.client.get(
            f"/api/admin/event-types/{event_type.id}/metric-definitions", headers=headers
        ),
        "METRICS_WRITE": lambda: ctx.client.post(
            f"/api/admin/event-types/{event_type.id}/metric-definitions",
            json={"code": "event_count", "name": "Event count"},
            headers=headers,
        ),
    }
    ctx.last_response = actions[permission]()


@when(parsers.parse('the actor lists project "{project_name}" members'))
def actor_lists_project_members(ctx: TestContext, project_name: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.get(
        f"/api/admin/projects/{project.id}/members",
        headers=ctx.request_headers or {},
    )


@when(parsers.parse('an unauthenticated actor lists project "{project_name}" members'))
def unauthenticated_actor_lists_project_members(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    ctx.last_response = ctx.client.get(f"/api/admin/projects/{project.id}/members")


@then(parsers.parse('the authorization result should be "{result}"'))
def authorization_result_should_be(ctx: TestContext, result: str) -> None:
    assert ctx.last_response is not None
    if result == "allowed":
        assert 200 <= ctx.last_response.status_code < 300, ctx.last_response.text
    else:
        assert ctx.last_response.status_code == 403, ctx.last_response.text
