from pytest_bdd import given
from pytest_bdd import scenarios

from tests.bdd.steps.authentication_steps import *  # noqa: F403,F401
from tests.bdd.steps.response_steps import *  # noqa: F403,F401
from tests.bdd.steps.user_steps import *  # noqa: F403,F401


@given('a project exists')
def project_exists() -> None:
    return None


scenarios("features/projects.feature")
