Feature: Create Builder Counter metrics atomically
  A valid Builder request creates exactly one immutable metric triplet and
  leaves ProcessingChains and Event runtime state unchanged.

  Background:
    Given an authorized Metrics Builder schema exists

  Scenario: Create a Counter metric from the Builder
    When the user creates an atomic Counter metric
    Then the exact Builder triplet is persisted atomically

  Scenario: Replay an identical Builder creation
    When the same atomic Counter creation is replayed
    Then the replay returns the same Builder resources without new rows

  Scenario: Reject different content under the same metric code
    When the same metric code is created with different content
    Then the Builder creation conflicts with code "BUILDER_METRIC_ALREADY_EXISTS"
    And only the winning Builder triplet exists

  Scenario: Reject a normalized Prometheus name collision
    When two metric codes converging to one Prometheus name are created
    Then the Builder creation conflicts with code "BUILDER_PROMETHEUS_NAME_COLLISION"
    And only the winning Builder triplet exists

  Scenario: Create compatibility only for the selected schema
    Given another schema exists for the Builder EventType
    When the metric is created for the explicit inactive schema
    Then the compatibility targets only the explicitly selected schema

  Scenario: Builder creation performs no rebuild or runtime work
    When the user creates an atomic Counter metric
    Then the Builder creation creates no chain plan or runtime data

  Scenario: Builder creation does not activate a chain
    When the user creates an atomic Counter metric
    Then the Builder creation creates no chain plan or runtime data

  Scenario: Builder creation preserves the ACTIVE chain
    Given an ACTIVE ProcessingChain already exists for the Builder scope
    When the user creates an atomic Counter metric
    Then the exact Builder triplet is persisted atomically
    And the existing ACTIVE ProcessingChain remains unchanged

  Scenario: Hostile free text remains inert during atomic creation
    When a hostile description is used in an atomic Builder creation
    Then the hostile description remains inert and the database is intact

  Scenario: A conflict response reveals no internal detail
    When the same metric code is created with different content
    Then the Builder creation conflicts with code "BUILDER_METRIC_ALREADY_EXISTS"
    And the Builder error contains no internal technical detail
