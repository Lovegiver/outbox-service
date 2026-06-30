from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


scenarios("features/authentication.feature")


@given(parsers.parse('{presence} user is registered with email "{email}"'))
def user_registration_precondition(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    email: str,
) -> None:
    step_registry.user_registration_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        email=email,
    )


@given("the following users are registered:")
def following_users_are_registered(
    ctx: TestContext,
    datatable: list[list[str]],
) -> None:
    headers = datatable[0]
    rows = datatable[1:]

    for row in rows:
        user_data = dict(zip(headers, row))

        ctx.seed.user_registered(
            email=user_data["email"],
            password=user_data["password"],
            global_role=user_data["global role"],
            account_status=user_data["account status"],
        )



@when(parsers.parse('a user registers with email "{email}" and password "{password}"'))
def user_registers(
    ctx: TestContext,
    email: str,
    password: str,
) -> None:
    ctx.last_response = ctx.client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )


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


@then(parsers.parse('{presence} user should be registered with email "{email}"'))
def user_registration_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    email: str,
) -> None:
    step_registry.user_registration_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        email=email,
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