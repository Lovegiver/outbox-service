from pytest_bdd import given, scenarios, then, when

scenarios("metrics/metric_builder.feature")


@given("a demo EventType with a compatible JSON Schema")
def demo_event_type_with_schema() -> None:
    raise NotImplementedError("BDD fixture not implemented yet")


@when("I create a counter metric grouped by provider")
def create_counter_metric_grouped_by_provider() -> None:
    raise NotImplementedError("Builder create step not implemented yet")


@then("the MetricDefinition exists")
def metric_definition_exists() -> None:
    raise NotImplementedError("Assertion not implemented yet")


@then("the MetricDefinitionVersion exists")
def metric_definition_version_exists() -> None:
    raise NotImplementedError("Assertion not implemented yet")


@then("the MetricDefinitionVersion is compatible with the schema")
def metric_definition_version_schema_exists() -> None:
    raise NotImplementedError("Assertion not implemented yet")


@then("the ProcessingPlan contains the generated metric")
def processing_plan_contains_generated_metric() -> None:
    raise NotImplementedError("Assertion not implemented yet")