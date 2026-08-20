Feature: YAML metric versions, validation and preview

  Background:
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "product.sold" named "Product sold"
    And a sales JSON Schema exists for event type "product.sold" in project "Hermes"
    And metric definition "sales_metrics" is ready for YAML configuration on event type "product.sold" in project "Hermes"
    And the user is authenticated as "developer@example.test"

  Scenario: Create a valid YAML metric version
    When YAML "valid counter" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And YAML version 1 should be persisted exactly for metric definition "sales_metrics"
    And no ProcessingChain or ProcessingPlan should have been created

  Scenario: List the created YAML metric version
    When YAML "valid counter" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    And YAML versions are listed for metric definition "sales_metrics" on event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the version history should contain versions "1"

  Scenario: Reject invalid YAML syntax during creation
    When YAML "invalid syntax" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    Then the response should have status 422
    And no YAML version should be persisted for metric definition "sales_metrics"

  Scenario: Reject a value path absent from the JSON Schema
    When YAML "unknown path" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    Then the response should have status 422
    And the response error should contain "does not exist"
    And no YAML version should be persisted for metric definition "sales_metrics"

  Scenario: Reject a transform incompatible with the JSON type
    When YAML "incompatible transform" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    Then the response should have status 422
    And the response error should contain "does not support"
    And no YAML version should be persisted for metric definition "sales_metrics"

  Scenario: Accept a compatible optional field
    When YAML "optional revenue" is previewed for event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the YAML preview should be valid
    And the compiled value should be marked optional

  Scenario: Validate a valid YAML document
    When YAML "valid counter" is validated for event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the YAML validation should be valid

  Scenario: Validation reports a structural error
    When YAML "unknown transform" is validated for event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the YAML validation should be invalid with error "unsupported transform"

  Scenario: Preview a valid YAML document
    Given the YAML version count is remembered
    When YAML "valid counter" is previewed for event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the YAML preview should be valid
    And the YAML version count should be unchanged

  Scenario: Preview exposes the functional compiled plan
    When YAML "valid counter" is previewed for event type "product.sold" in project "Hermes"
    Then the compiled preview should describe counter "products_sold_total" grouped by "country"

  Scenario: Invalid preview has no persistence effect
    Given the YAML version count is remembered
    When YAML "unknown path" is previewed for event type "product.sold" in project "Hermes"
    Then the YAML preview should be invalid with error "does not exist"
    And the YAML version count should be unchanged

  Scenario: A viewer cannot create a YAML metric version
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And the user is authenticated as "viewer@example.test"
    When YAML "valid counter" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    Then the response should have status 403
    And no YAML version should be persisted for metric definition "sales_metrics"

  Scenario: Reject an unknown MetricDefinition
    When YAML "valid counter" is created for unknown metric definition id 999999 on event type "product.sold" in project "Hermes"
    Then the response should have status 404

  Scenario: Reject a MetricDefinition belonging to another EventType
    Given project "Hermes" has event type "product.returned" named "Product returned"
    And metric definition "return_metrics" is ready for YAML configuration on event type "product.returned" in project "Hermes"
    When YAML "valid counter" is created using metric definition "return_metrics" through event type "product.sold" in project "Hermes"
    Then the response should have status 403
    And no YAML version should be persisted for metric definition "return_metrics"

  Scenario: Reject a SchemaDefinition belonging to another Project
    Given project "Apollo" has event type "order.created" named "Order created"
    And a sales JSON Schema exists for event type "order.created" in project "Apollo"
    When YAML "valid counter" is previewed for event type "product.sold" in project "Hermes" using the schema of "order.created" in project "Apollo"
    Then the response should have status 403

  Scenario: Preserve immutable YAML version history
    When YAML "valid counter" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    And YAML "valid revenue" is created as a version of metric definition "sales_metrics" for event type "product.sold" in project "Hermes"
    And YAML versions are listed for metric definition "sales_metrics" on event type "product.sold" in project "Hermes"
    Then the response should have status 200
    And the version history should contain versions "1,2"
    And YAML version 1 should still contain counter "products_sold_total"
