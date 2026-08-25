from pytest_bdd import scenarios

from tests.bdd.steps.metric_runtime_steps import *  # noqa: F401,F403

scenarios("features/metric_runtime_execution.feature")
