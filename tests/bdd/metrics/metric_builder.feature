Feature: Metrics Builder

  Scenario: Create a metric ready for Prometheus runtime
    Given a demo EventType with a compatible JSON Schema
    When I create a counter metric grouped by provider
    Then the MetricDefinition exists
    And the MetricDefinitionVersion exists
    And the MetricDefinitionVersion is compatible with the schema
    And the ProcessingPlan contains the generated metric
    When I ingest a matching event
    Then an AnalyticalObservation is produced for the generated metric
    And MetricState is updated for the generated metric
    And the Prometheus endpoint exposes the generated metric