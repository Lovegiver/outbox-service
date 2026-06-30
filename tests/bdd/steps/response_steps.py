
from pytest_bdd import parsers, then

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


@then(parsers.parse("the response should have status {status_code:d}"))
def response_should_have_status(
    ctx: TestContext,
    step_registry: StepRegistry,
    status_code: int,
) -> None:
    step_registry.response_assertion_for("has status")(
        ctx=ctx,
        expected_status=status_code,
    )


@then(parsers.parse('the response should identify user "{email}"'))
def response_should_identify_user(
    ctx: TestContext,
    step_registry: StepRegistry,
    email: str,
) -> None:
    step_registry.response_assertion_for("identifies user")(
        ctx=ctx,
        email=email,
    )


@then(parsers.parse('the response error should contain "{message}"'))
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


@then(parsers.parse('the response should contain global role "{role}"'))
def response_should_contain_global_role(
    ctx: TestContext,
    step_registry: StepRegistry,
    role: str,
) -> None:
    step_registry.response_assertion_for("contains global role")(
        ctx=ctx,
        role=role,
    )
