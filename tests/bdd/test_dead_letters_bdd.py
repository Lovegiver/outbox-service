from pytest_bdd import scenarios

from tests.bdd.steps.authentication_steps import *  # noqa: F403,F401
from tests.bdd.steps.dead_letter_steps import *  # noqa: F403,F401
from tests.bdd.steps.response_steps import *  # noqa: F403,F401

scenarios("features/dead_letters.feature")
