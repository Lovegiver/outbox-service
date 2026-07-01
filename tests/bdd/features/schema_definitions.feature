Feature: Schema Definitions

  Schema Definitions describe the JSON payload accepted for an EventType.

  Scenario: Create a JSON Schema for an EventType
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When schema version "1.0" with client version "v1" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And schema version "1.0" should be registered for event type "article.analyzed"
    And schema version "1.0" should match the submitted JSON Schema for event type "article.analyzed"

  Scenario: The new schema becomes active
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When schema version "2.0" with client version "v2" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And schema version "2.0" should be active for event type "article.analyzed"

  Scenario: Listing returns the active schema
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When schema version "1.0" with client version "v1" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    When schemas are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And the response should contain schema version "1.0"

  Scenario: Listing returns an empty list when no active schema exists
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When schemas are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And the response should be an empty list

  Scenario: Reject schema creation without SCHEMA_WRITE
    Given the following users are registered:
      | email              | password          | global role | account status |
      | owner@example.com  | ValidPassword123! | USER        | active         |
      | viewer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has member "viewer@example.com" with role "VIEWER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "viewer@example.com"
    When schema version "1.0" with client version "v1" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403
    And no schema version "1.0" should be registered for event type "article.analyzed"

  Scenario: Reject schema listing without SCHEMA_READ
    Given the following users are registered:
      | email             | password          | global role | account status |
      | owner@example.com | ValidPassword123! | USER        | active         |
      | other@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "other@example.com"
    When schemas are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403

  Scenario: Reject schema creation when EventType does not exist
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the user is authenticated as "admin@example.com"
    When schema version "1.0" with client version "v1" is created for event type with id 999999
    Then the response should have status 404
    And the response error should contain "not found"
