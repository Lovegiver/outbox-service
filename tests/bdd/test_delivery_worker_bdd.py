from pytest_bdd import scenarios

from tests.bdd.steps.delivery_worker_steps import *  # noqa: F403,F401


scenarios("features/delivery_worker.feature")
