from pytest_bdd import scenarios

from tests.bdd.steps.authentication_steps import *  # noqa: F401,F403
from tests.bdd.steps.metric_definition_steps import *  # noqa: F401,F403
from tests.bdd.steps.processing_chain_steps import *  # noqa: F401,F403
from tests.bdd.steps.response_steps import *  # noqa: F401,F403


scenarios("features/processing_chain_activation.feature")
