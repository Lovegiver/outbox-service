"""Collect the BDD-016C lifecycle scenarios."""

from pytest_bdd import scenarios

from tests.bdd.steps.metric_builder_lifecycle_steps import *

scenarios("features/metric_builder_lifecycle_e2e.feature")
