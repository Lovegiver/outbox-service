Feature: API Keys

  API keys allow project applications to ingest events without using a user JWT.

  Scenario: Create an API key as authorized user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    And the response should contain an API key secret
    And API key "Main ingestion key" should be active for project "Hermes"

  Scenario: Expose the full API key only at creation
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    And the response should contain an API key secret
    When API keys are listed for project "Hermes"
    Then the response should have status 200
    And the response should not expose the API key secret for "Main ingestion key"

  Scenario: List API keys without exposing complete secrets
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API keys are listed for project "Hermes"
    Then the response should have status 200
    And the response should contain API key "Main ingestion key"
    And the listed API keys should not expose complete secrets

  Scenario: Reject API key creation without API_KEY_WRITE
    Given the following users are registered:
      | email              | password          | global role | account status |
      | owner@example.com  | ValidPassword123! | USER        | active         |
      | viewer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has member "viewer@example.com" with role "VIEWER"
    And the user is authenticated as "viewer@example.com"
    When API key "Forbidden key" is created for project "Hermes"
    Then the response should have status 403
    And no API key should be registered with name "Forbidden key" for project "Hermes"

  Scenario: Revoke an active API key
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API key "Main ingestion key" is revoked for project "Hermes"
    Then the response should have status 200
    And API key "Main ingestion key" should be revoked for project "Hermes"

  Scenario: Reject revoking an unknown API key
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key with id 999999 is revoked for project "Hermes"
    Then the response should have status 404
    And the response error should contain "not found"

  Scenario: Reject ingestion with a revoked API key
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has ingestible event type "article.analyzed"
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API key "Main ingestion key" is revoked for project "Hermes"
    Then the response should have status 200
    When an event is ingested for project "Hermes" and event type "article.analyzed" using API key "Main ingestion key"
    Then the response should have status 401

  Scenario: Rotate an API key
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API key "Main ingestion key" is rotated for project "Hermes"
    Then the response should have status 201
    And API key "Main ingestion key" should be revoked for project "Hermes"
    And the latest API key should be active for project "Hermes"

  Scenario: Reject ingestion with the old API key after rotation
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has ingestible event type "article.analyzed"
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API key "Main ingestion key" is rotated for project "Hermes"
    Then the response should have status 201
    When an event is ingested for project "Hermes" and event type "article.analyzed" using the previous API key "Main ingestion key"
    Then the response should have status 401

  Scenario: Accept ingestion with the new API key after rotation
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has ingestible event type "article.analyzed"
    And the user is authenticated as "alice@example.com"
    When API key "Main ingestion key" is created for project "Hermes"
    Then the response should have status 201
    When API key "Main ingestion key" is rotated for project "Hermes"
    Then the response should have status 201
    When an event is ingested for project "Hermes" and event type "article.analyzed" using the latest API key
    Then the response should have status 200
    And an event should be registered for project "Hermes" and event type "article.analyzed"
