Feature: Analyze JSON Schema fields for Counter metrics
  The Metrics Builder exposes only conservative, deterministic choices and its
  preview never persists configuration.

  Background:
    Given an authorized Metrics Builder schema exists

  Scenario: Inspect required optional and nullable fields
    When the Builder schema fields are inspected
    Then the Builder exposes required optional and nullable independently

  Scenario: Inspect the active schema without an explicit schema identifier
    When the active Builder schema fields are inspected
    Then the Builder exposes required optional and nullable independently

  Scenario: A nested field requires every ancestor
    When the Builder schema fields are inspected
    Then the nested Builder field is optional when an ancestor is optional

  Scenario: A complex construction is not supported
    When the Builder schema fields are inspected
    Then the complex Builder field is UNSUPPORTED

  Scenario: Counter intents depend on field type and bounds
    When the Builder schema fields are inspected
    Then only Counter-safe intents are proposed

  Scenario: Preview every supported intent
    When each supported Builder intent is previewed
    Then all six Builder previews use the expected transforms
    And no metric configuration is persisted by preview

  Scenario: Refuse sum_value without a non-negative bound
    When sum_value is previewed on the unbounded amount
    Then the Builder preview is invalid with code "BUILDER_COUNTER_UNSAFE"
    And no metric configuration is persisted by preview

  Scenario: count_event rejects a selected field
    When count_event is previewed with a value path
    Then the Builder preview is invalid with code "BUILDER_CONTRACT_INVALID"

  Scenario: count_by_label requires one safe label
    When count_by_label is previewed without a label
    Then the Builder preview is invalid with code "BUILDER_CONTRACT_INVALID"

  Scenario: A boolean can be a label
    When count_by_label is previewed with the boolean label
    Then the Builder preview is valid

  Scenario: A small scalar enum can be a label
    When count_by_label is previewed with the enum label
    Then the Builder preview is valid

  Scenario: A bounded label explains its static series contribution
    When a safe Builder metric is previewed with a bounded label
    Then the Builder preview exposes explainable cardinality safeguards

  Scenario: A free string cannot be a label
    When count_by_label is previewed with the free string label
    Then the Builder preview is invalid with code "BUILDER_COUNTER_UNSAFE"

  Scenario: An identifier cannot be a label
    When count_by_label is previewed with the identifier label
    Then the Builder preview is invalid with code "BUILDER_COUNTER_UNSAFE"

  Scenario: A JSONPath expression is rejected before compilation
    When a Builder preview uses an interpreted JSONPath expression
    Then the Builder preview is invalid with code "BUILDER_CONTRACT_INVALID"

  Scenario: A SQL injection attempt is inert
    When a Builder preview uses a SQL injection as metric code
    Then the Builder preview is invalid with code "BUILDER_CONTRACT_INVALID"
    And no metric configuration is persisted by preview

  Scenario: Apostrophes and markup remain inert free text
    When a Builder metric is created with apostrophes and markup in free text
    Then the Builder free text is stored exactly as inert data

  Scenario: A Prometheus name collision is refused
    Given an existing metric normalizes to the requested Prometheus name
    When the colliding metric code is previewed
    Then the Builder preview is invalid with code "BUILDER_PROMETHEUS_NAME_COLLISION"
    And no metric configuration is persisted by preview

  Scenario: Unknown request properties are refused
    When a Builder preview contains an unknown property
    Then the Builder API responds with status 422

  Scenario: A label collection exceeding the configured limit is refused
    When a Builder preview contains too many labels
    Then the Builder API responds with status 422
    And no metric configuration is persisted by preview

  Scenario: Functional errors do not expose internal details
    When sum_value is previewed on the unbounded amount
    Then the Builder error contains no internal technical detail

  Scenario: A schema from another Project is not disclosed
    Given another Project owns a Builder schema
    When the other Project Builder schema is inspected
    Then the Builder API responds with status 403

  Scenario: An unknown explicit schema is reported as missing
    When an unknown explicit Builder schema is inspected
    Then the Builder API responds with status 404
