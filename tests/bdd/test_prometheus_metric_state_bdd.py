from pytest_bdd import scenarios

from tests.bdd.steps.prometheus_metric_state_steps import *  # noqa: F401,F403
from tests.bdd.steps.response_steps import *  # noqa: F401,F403


scenarios("features/prometheus_metric_state.feature")
