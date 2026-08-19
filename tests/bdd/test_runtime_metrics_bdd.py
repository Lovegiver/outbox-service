from pytest_bdd import scenarios

from tests.bdd.steps.response_steps import *  # noqa: F403,F401
from tests.bdd.steps.runtime_metrics_steps import *  # noqa: F403,F401


scenarios("features/runtime_metrics.feature")
