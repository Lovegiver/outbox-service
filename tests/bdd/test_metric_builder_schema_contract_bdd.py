from pytest_bdd import scenarios

from tests.bdd.steps.metric_builder_steps import *  # noqa: F401,F403


scenarios("features/metric_builder_schema_contract.feature")
