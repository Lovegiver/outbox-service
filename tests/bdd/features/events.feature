Feature: Events

  Events are accepted through the public ingestion API and persisted only when
  their payload complies with the active JSON Schema.

  Scenario: Ingest a valid Event with a valid API key
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json"
    Then the response should have status 200
    And an event should be persisted for project "Hermes" and event type "article.analyzed"
    And the persisted event should have status "RECEIVED"
    And the persisted event should use schema version "1.0"

  Scenario: Reject Event ingestion without API key
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json" without API key
    Then the response should have status 401

  Scenario: Reject Event ingestion with invalid API key
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json" and invalid API key
    Then the response should have status 401

  Scenario: Reject Event ingestion with revoked API key
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has revoked API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json"
    Then the response should have status 401

  Scenario: Reject Event ingestion when payload misses a required JSON field
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.invalid.missing_required.json"
    Then the response should have status 400
    And no event should be persisted for project "Hermes" and event type "article.analyzed"

  Scenario: Reject Event ingestion when payload has an invalid JSON type
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.invalid.bad_type.json"
    Then the response should have status 400
    And no event should be persisted for project "Hermes" and event type "article.analyzed"

  Scenario: Reject null when the active JSON Schema forbids it
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.invalid.null_required.json"
    Then the response should have status 400
    And no event should be persisted for project "Hermes" and event type "article.analyzed"

  Scenario: Reject Event ingestion when no active schema exists
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json"
    Then the response should have status 400
    And no event should be persisted for project "Hermes" and event type "article.analyzed"

  Scenario: Generate an Event UUID when absent
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json"
    Then the response should have status 200
    And the response should contain an event UUID

  Scenario: Preserve a provided Event UUID and correlation ID
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json", event UUID "11111111-1111-4111-8111-111111111111" and correlation ID "corr-process-0001"
    Then the response should have status 200
    And event UUID "11111111-1111-4111-8111-111111111111" should be persisted
    And correlation ID "corr-process-0001" should be persisted

  Scenario: Reject duplicate Event UUID
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json", event UUID "22222222-2222-4222-8222-222222222222" and correlation ID "corr-duplicate"
    Then the response should have status 200
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json", event UUID "22222222-2222-4222-8222-222222222222" and correlation ID "corr-duplicate"
    Then the response should have status 409

  Scenario: Ingestion does not execute worker routing
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has active schema "article_analyzed.schema.v1.json"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "article.analyzed" and URL "https://blackhole.example.test/webhook"
    And project "Hermes" has active API key "ingestion-key"
    When event "article.analyzed" is submitted for project "Hermes" with payload "article_analyzed.valid.json"
    Then the response should have status 200
    And the persisted event should have status "RECEIVED"
    And no delivery should be created for the persisted event
