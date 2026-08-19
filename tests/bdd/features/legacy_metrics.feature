Feature: Legacy system metrics

  Legacy metrics are read from persisted SystemMetric records.

  Scenario: Return an empty list when no system metric exists
    When all system metrics are requested
    Then the response should have status 200
    And the system metric list should be empty

  Scenario: List all persisted system metrics
    Given system metrics exist:
      | metric_code           | value |
      | delivery.failed.total | 2     |
      | event.routed.total    | 7     |
    When all system metrics are requested
    Then the response should have status 200
    And the system metric list should contain 2 entries
    And the system metric "delivery.failed.total" should have value 2

  Scenario: List only the latest value for each metric
    Given an old system metric "event.routed.total" with value 3
    And a latest system metric "event.routed.total" with value 9
    When latest system metrics are requested
    Then the response should have status 200
    And the latest system metric "event.routed.total" should have value 9

  Scenario: Expose an empty Prometheus response coherently
    When legacy Prometheus metrics are requested
    Then the response should have status 200
    And the Prometheus response should end with a newline
    And the Prometheus response should not contain metric "outbox_event_routed_total"

  Scenario: Expose metrics using Prometheus-safe names and numeric values
    Given system metrics exist:
      | metric_code        | value |
      | event.routed.total | 7.5   |
    When legacy Prometheus metrics are requested
    Then the response should have status 200
    And the Prometheus response should contain type "outbox_event_routed_total" as "gauge"
    And the Prometheus response should contain metric "outbox_event_routed_total" with value "7.5"

  Scenario: Keep system metrics separate from business MetricState
    Given system metrics exist:
      | metric_code        | value |
      | event.routed.total | 7     |
    When all system metrics are requested
    Then the response should have status 200
    And the system metric list should not contain metric "business_counter"
