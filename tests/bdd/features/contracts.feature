Feature: Outbox Event contract

  The public contract endpoint exposes the active system schema.

  Scenario: Return 404 when the Outbox contract is absent
    When the latest Outbox contract is requested
    Then the response should have status 404

  Scenario: Return the active Outbox contract
    Given an active Outbox contract schema version "1.0" with schema:
      | field | value |
      | title | Contract v1 |
    When the latest Outbox contract is requested
    Then the response should have status 200
    And the contract response should contain name "outbox-event" and version "1.0"
    And the contract response schema should equal:
      | title | Contract v1 |

  Scenario: Return exactly the persisted active schema
    Given an active Outbox contract schema version "2.0" with schema:
      | title | Persisted contract |
      | type  | object             |
    When the latest Outbox contract is requested
    Then the response should have status 200
    And the contract response schema should equal:
      | title | Persisted contract |
      | type  | object             |

  Scenario: Return only the active schema when several versions exist
    Given an inactive Outbox contract schema version "1.0" with schema:
      | title | Old contract |
    And an active Outbox contract schema version "2.0" with schema:
      | title | Current contract |
    When the latest Outbox contract is requested
    Then the response should have status 200
    And the contract response should contain name "outbox-event" and version "2.0"
    And the contract response schema should equal:
      | title | Current contract |

  Scenario: Return the system contract independently of user Projects
    Given an active Outbox contract schema version "1.0" with schema:
      | title | System contract |
    And a user Project named "Apollo" exists
    When the latest Outbox contract is requested
    Then the response should have status 200
    And the contract response should contain name "outbox-event" and version "1.0"
