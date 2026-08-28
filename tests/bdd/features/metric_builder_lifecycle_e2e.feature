Feature: Metric Builder lifecycle end to end
  BDD-016C keeps creation, rebuild, activation and runtime explicit and isolated.

  Background:
    Given a BDD-016C Builder lifecycle scope exists

  Scenario: A Builder metric enters a DRAFT only after explicit rebuild
    When a count_event metric is previewed and created
    And the lifecycle scope is explicitly rebuilt
    Then the candidate is a DRAFT containing 1 exact plan

  Scenario: Rebuild includes every compatible Builder metric
    Given two compatible Builder metrics exist
    When the lifecycle scope is explicitly rebuilt
    Then the candidate is a DRAFT containing 2 exact plans

  Scenario: Rebuild preserves the current ACTIVE chain
    Given one Builder chain is ACTIVE
    And another compatible Builder metric is created
    When the lifecycle scope is explicitly rebuilt
    Then the previous ACTIVE chain remains unchanged

  Scenario: A Prometheus collision prevents DRAFT creation
    Given colliding historical metric versions are compatible
    When the lifecycle scope rebuild is attempted
    Then the lifecycle request fails with a stable collision
    And no lifecycle DRAFT was persisted

  Scenario: Explicit activation atomically replaces the ACTIVE chain
    Given one Builder chain is ACTIVE
    And another compatible Builder metric is created
    When the lifecycle scope is explicitly rebuilt and activated
    Then exactly one lifecycle chain is ACTIVE

  Scenario: Activation collision preserves the previous ACTIVE chain
    Given an ACTIVE chain and a colliding historical DRAFT exist
    When the colliding lifecycle DRAFT activation is attempted
    Then the lifecycle request fails with a stable collision
    And the previous ACTIVE chain remains unchanged

  Scenario: A future Event executes the newly activated Builder plan
    Given one Builder chain is ACTIVE
    When a future lifecycle Event is ingested and processed
    Then the future Event has one successful observation

  Scenario: Activation does not reprocess an historical Event
    Given an historical lifecycle Event was routed without a chain
    When a Builder chain is created and activated
    And the lifecycle workers run again
    Then the historical Event has no metric execution

  Scenario: The Builder pipeline exposes an exact Counter in Prometheus
    Given one Builder chain is ACTIVE
    When 3 future lifecycle Events are ingested and processed
    Then Prometheus exposes the lifecycle Counter with value 3

  Scenario: An absent optional field produces no measurement
    Given an optional string length Builder chain is ACTIVE
    When a lifecycle Event without the optional field is processed
    Then the lifecycle plan succeeds without observation

  Scenario: An allowed null produces no measurement
    Given an optional string length Builder chain is ACTIVE
    When a lifecycle Event with an allowed null is processed
    Then the lifecycle plan succeeds without observation

  Scenario: An absent label preserves the Counter without exposing the label
    Given an optional label Builder chain is ACTIVE
    When a lifecycle Event without the optional label is processed
    Then the lifecycle contribution has a structural null dimension
    And Prometheus omits the optional lifecycle label

  Scenario: Structurally identical EventTypes remain isolated
    Given two lifecycle EventTypes have structurally identical schemas
    When both lifecycle scopes process one Event
    Then each lifecycle Event uses its exact chain and Prometheus scope

  Scenario: Two metric workers process one durable batch without duplicates
    Given a committed lifecycle batch for 2 metric workers
    When both lifecycle metric workers run concurrently
    Then every lifecycle execution and observation is unique

  Scenario: A permanent plan remains isolated under concurrent workers
    Given a committed lifecycle Event with one permanent metric plan
    When both lifecycle metric workers run concurrently
    Then the permanent lifecycle plan is not retryable and other plans succeed

  Scenario: A second lifecycle cycle has no metric or delivery effect
    Given one Builder chain is ACTIVE
    When a future lifecycle Event is ingested and processed twice
    Then the second lifecycle cycle creates no observation or delivery
