from pytest_bdd import scenarios

from tests.bdd.steps.legacy_metrics_steps import *  # noqa: F403,F401
from tests.bdd.steps.response_steps import *  # noqa: F403,F401


scenarios("features/legacy_metrics.feature")
