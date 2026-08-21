Feature: YAML schema compatibility and ProcessingChain activation

  Background:
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "product.sold" named "Product sold"
    And the user is authenticated as "developer@example.test"
    And metric schema "v1" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    And metric YAML version "sales-v1" using "valid amount" exists for definition "sales" on event type "product.sold" in project "Hermes"

  Scenario: Declare and persist a compatible YAML version
    When version "sales-v1" is declared compatible with schema "v1"
    Then the response should have status 200
    And compatibility "sales-v1" to schema "v1" should exist exactly once

  Scenario: Repeating an identical compatibility request is idempotent
    When version "sales-v1" is declared compatible with schema "v1"
    And version "sales-v1" is declared compatible with schema "v1" again
    Then the response should have status 200
    And compatibility "sales-v1" to schema "v1" should exist exactly once

  Scenario: One YAML version can be compatible with multiple schemas
    Given metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    When version "sales-v1" is declared compatible with schema "v1"
    And version "sales-v1" is declared compatible with schema "v2" again
    Then compatibility "sales-v1" to schema "v1" should exist exactly once
    And compatibility "sales-v1" to schema "v2" should exist exactly once

  Scenario: One schema can accept multiple YAML versions
    Given metric YAML version "sales-v2" using "valid counter" exists for definition "sales" on event type "product.sold" in project "Hermes"
    When version "sales-v1" is declared compatible with schema "v1"
    And version "sales-v2" is declared compatible with schema "v1" again
    Then compatibility "sales-v1" to schema "v1" should exist exactly once
    And compatibility "sales-v2" to schema "v1" should exist exactly once

  Scenario: Reject an unknown YAML version
    When unknown YAML version 999999 is declared compatible with schema "v1"
    Then the response should have status 404
    And no metric compatibility should have been persisted

  Scenario: Reject an unknown schema
    When version "sales-v1" is declared compatible with unknown schema 999999
    Then the response should have status 404
    And no metric compatibility should have been persisted

  Scenario: Reject a schema from another EventType
    Given project "Hermes" has event type "product.returned" named "Product returned"
    And metric schema "returns" with shape "complete sales" exists for event type "product.returned" in project "Hermes"
    When version "sales-v1" is declared compatible with schema "returns"
    Then the response should have status 403
    And no metric compatibility should have been persisted

  Scenario: Reject a schema from another Project
    Given project "Apollo" has event type "order.created" named "Order created"
    And metric schema "orders" with shape "complete sales" exists for event type "order.created" in project "Apollo"
    When version "sales-v1" is declared compatible with schema "orders"
    Then the response should have status 403
    And no metric compatibility should have been persisted

  Scenario: Reject a missing path during compatibility validation
    Given metric YAML version "missing-v1" using "unknown path" exists for definition "missing" on event type "product.sold" in project "Hermes"
    When version "missing-v1" is declared compatible with schema "v1"
    Then the response should have status 422
    And the response error should contain "does not exist"
    And no metric compatibility should have been persisted

  Scenario: Reject an incompatible transform during compatibility validation
    Given metric YAML version "country-v1" using "incompatible transform" exists for definition "country" on event type "product.sold" in project "Hermes"
    When version "country-v1" is declared compatible with schema "v1"
    Then the response should have status 422
    And the response error should contain "does not support"
    And no metric compatibility should have been persisted

  Scenario: Accept a statically compatible optional field
    Given metric YAML version "optional-v1" using "optional revenue" exists for definition "optional" on event type "product.sold" in project "Hermes"
    When version "optional-v1" is declared compatible with schema "v1"
    Then the response should have status 200
    And compatibility "optional-v1" to schema "v1" should exist exactly once

  Scenario: A viewer cannot declare compatibility
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And the user is authenticated as "viewer@example.test"
    When version "sales-v1" is declared compatible with schema "v1"
    Then the response should have status 403
    And no metric compatibility should have been persisted

  Scenario: Creating compatibility does not rebuild implicitly
    When version "sales-v1" is declared compatible with schema "v1"
    Then no processing snapshot should exist for schema "v1"

  Scenario: Explicit rebuild creates and activates a complete snapshot
    Given version "sales-v1" is already compatible with schema "v1"
    When the processing chain is explicitly rebuilt for schema "v1"
    Then the response should have status 200
    And active processing chain version 1 should exist for schema "v1"
    And its compiled plans should reference versions "sales-v1"
    And no AnalyticalObservation should have been produced by configuration

  Scenario: A snapshot contains one complete plan per selected definition
    Given metric YAML version "count-v1" using "valid counter" exists for definition "count" on event type "product.sold" in project "Hermes"
    And version "sales-v1" is already compatible with schema "v1"
    And version "count-v1" is already compatible with schema "v1"
    When the processing chain is explicitly rebuilt for schema "v1"
    Then active processing chain version 1 should exist for schema "v1"
    And its compiled plans should reference versions "sales-v1,count-v1"
    And every plan in the active chain should contain a compiled document

  Scenario: An identical explicit rebuild reuses the active snapshot
    Given version "sales-v1" is already compatible with schema "v1"
    When the processing chain is explicitly rebuilt for schema "v1"
    And the active chain identity for schema "v1" is remembered
    And the processing chain is explicitly rebuilt for schema "v1" again
    Then the active chain identity for schema "v1" should be unchanged
    And exactly 1 processing chain should exist for schema "v1"

  Scenario: A changed snapshot creates a new version and preserves audit history
    Given version "sales-v1" is already compatible with schema "v1"
    When the processing chain is explicitly rebuilt for schema "v1"
    Given metric YAML version "count-v1" using "valid counter" exists for definition "count" on event type "product.sold" in project "Hermes"
    And version "count-v1" is already compatible with schema "v1"
    When the processing chain is explicitly rebuilt for schema "v1"
    Then active processing chain version 2 should exist for schema "v1"
    And exactly 2 processing chains should exist for schema "v1"
    And only one processing chain should be active for schema "v1"

  Scenario: Different schemas have independent active snapshots
    Given metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    And version "sales-v1" is already compatible with schema "v1"
    And version "sales-v1" is already compatible with schema "v2"
    When the processing chain is explicitly rebuilt for schema "v1"
    And the processing chain is explicitly rebuilt for schema "v2" again
    Then only one processing chain should be active for schema "v1"
    And only one processing chain should be active for schema "v2"

  Scenario: Rebuild refuses a scope with no compatible metric version
    When the processing chain is explicitly rebuilt for schema "v1"
    Then the response should have status 422
    And no processing snapshot should exist for schema "v1"

  Scenario: Propagate all versions used by the previous active schema
    Given version "sales-v1" is already compatible with schema "v1"
    And the processing chain has been rebuilt for schema "v1"
    And metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    Then the propagation should report 1 compatible and 0 incompatible metrics
    And compatibility "sales-v1" to schema "v1" should exist exactly once
    And compatibility "sales-v1" to schema "v2" should exist exactly once
    And the propagation candidate should be a complete inactive draft
    And no new YAML version should have been created

  Scenario: Propagation reports an incompatible metric without activating a reduced chain
    Given metric YAML version "country-v1" using "valid counter" exists for definition "country" on event type "product.sold" in project "Hermes"
    And version "sales-v1" is already compatible with schema "v1"
    And version "country-v1" is already compatible with schema "v1"
    And the processing chain has been rebuilt for schema "v1"
    And metric schema "v2" with shape "sales without country" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    Then the propagation should report 1 compatible and 1 incompatible metrics
    And the incompatibility reason should contain "does not exist"
    And compatibility "sales-v1" to schema "v2" should exist exactly once
    And compatibility "country-v1" to schema "v2" should not exist
    And the propagation candidate should be incomplete and inactive
    When the propagation candidate is activated for schema "v2"
    Then the response should have status 422
    And no active processing chain should exist for schema "v2"

  Scenario: Propagation does not invent configuration without a previous active chain
    Given metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    Then the propagation should report 0 compatible and 0 incompatible metrics
    And no processing snapshot should exist for schema "v2"

  Scenario: Repeating propagation is idempotent
    Given version "sales-v1" is already compatible with schema "v1"
    And the processing chain has been rebuilt for schema "v1"
    And metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    And compatibilities are propagated from schema "v1" to schema "v2" again
    Then compatibility "sales-v1" to schema "v2" should exist exactly once
    And exactly 1 processing chain should exist for schema "v2"

  Scenario: Propagation calls out optional-field runtime semantics
    Given metric YAML version "optional-v1" using "optional revenue" exists for definition "optional" on event type "product.sold" in project "Hermes"
    And version "optional-v1" is already compatible with schema "v1"
    And the processing chain has been rebuilt for schema "v1"
    And metric schema "v2" with shape "optional discount" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    Then the propagation should report an optional-field runtime warning

  Scenario: A complete propagated candidate is activated explicitly
    Given version "sales-v1" is already compatible with schema "v1"
    And the processing chain has been rebuilt for schema "v1"
    And metric schema "v2" with shape "complete sales" exists for event type "product.sold" in project "Hermes"
    When compatibilities are propagated from schema "v1" to schema "v2"
    And the propagation candidate is activated for schema "v2"
    Then the response should have status 200
    And only one processing chain should be active for schema "v2"
    And the active chain for schema "v1" should remain unchanged
