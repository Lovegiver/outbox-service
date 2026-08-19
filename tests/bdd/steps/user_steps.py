
from pytest_bdd import given, parsers, then

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


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
