from pytest_bdd import parsers
from pytest_bdd import then

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


response_status_pattern = parsers.parse("the response should have status {status_code:d}")
response_user_identity_pattern = parsers.parse('the response should identify user "{email}"')
response_error_pattern = parsers.parse('the response error should contain "{message}"')
response_global_role_pattern = parsers.parse('the response should contain global role "{role}"')
response_contains_project_pattern = parsers.parse(
    'the response should contain project "{project_name}"'
)
response_not_contains_project_pattern = parsers.parse(
    'the response should not contain project "{project_name}"'
)


@then(response_status_pattern)
def response_should_have_status(
    ctx: TestContext,
    step_registry: StepRegistry,
    status_code: int,
) -> None:
    step_registry.response_assertion_for("has status")(
        ctx=ctx,
        expected_status=status_code,
    )


@then(response_user_identity_pattern)
def response_should_identify_user(
    ctx: TestContext,
    step_registry: StepRegistry,
    email: str,
) -> None:
    step_registry.response_assertion_for("identifies user")(
        ctx=ctx,
        email=email,
    )


@then(response_error_pattern)
def response_error_should_contain(
    ctx: TestContext,
    step_registry: StepRegistry,
    message: str,
) -> None:
    step_registry.response_assertion_for("contains error")(
        ctx=ctx,
        message=message,
    )


@then("the response should contain an access token")
def response_should_contain_access_token(
    ctx: TestContext,
    step_registry: StepRegistry,
) -> None:
    step_registry.response_assertion_for("contains access token")(
        ctx=ctx,
    )


@then(response_global_role_pattern)
def response_should_contain_global_role(
    ctx: TestContext,
    step_registry: StepRegistry,
    role: str,
) -> None:
    step_registry.response_assertion_for("contains global role")(
        ctx=ctx,
        role=role,
    )


@then(response_contains_project_pattern)
def response_should_contain_project(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
) -> None:
    step_registry.response_assertion_for("contains project")(
        ctx=ctx,
        project_name=project_name,
        expected=True,
    )


@then(response_not_contains_project_pattern)
def response_should_not_contain_project(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
) -> None:
    step_registry.response_assertion_for("contains project")(
        ctx=ctx,
        project_name=project_name,
        expected=False,
    )
