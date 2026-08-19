Feature: Event Types

  Event Types describe the business events accepted by a project.

  Scenario: Create an EventType in an active project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When event type "article.analyzed" is created in project "Hermes" with name "Article analyzed"
    Then the response should have status 201
    And event type "article.analyzed" should be registered in project "Hermes"

  Scenario: Reject EventType creation without EVENT_TYPE_WRITE
    Given the following users are registered:
      | email              | password          | global role | account status |
      | owner@example.com  | ValidPassword123! | USER        | active         |
      | viewer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has member "viewer@example.com" with role "VIEWER"
    And the user is authenticated as "viewer@example.com"
    When event type "article.analyzed" is created in project "Hermes" with name "Article analyzed"
    Then the response should have status 403
    And no event type "article.analyzed" should be registered in project "Hermes"

  Scenario: Reject EventType creation when project does not exist
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the user is authenticated as "admin@example.com"
    When event type "article.analyzed" is created in project with id 999999 with name "Article analyzed"
    Then the response should have status 404
    And the response error should contain "not found"

  Scenario: Reject EventType creation in an inactive project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | inactive       |
    And the user is authenticated as "admin@example.com"
    When event type "article.analyzed" is created in project "Hermes" with name "Article analyzed"
    Then the response should have status 409
    And the response error should contain "not active"

  Scenario: Reject EventType creation when code already exists in the project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When event type "article.analyzed" is created in project "Hermes" with name "Duplicate article analyzed"
    Then the response should have status 409
    And the response error should contain "already exists"

  Scenario: List EventTypes of a project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And project "Hermes" has event type "delivery.completed" named "Delivery completed"
    And the user is authenticated as "alice@example.com"
    When event types are listed for project "Hermes"
    Then the response should have status 200
    And the response should contain event type "article.analyzed"
    And the response should contain event type "delivery.completed"

  Scenario: Read an authorized EventType
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When event type "article.analyzed" from project "Hermes" is requested
    Then the response should have status 200
    And the response should identify event type "article.analyzed"

  Scenario: Reject EventType read without permission
    Given the following users are registered:
      | email             | password          | global role | account status |
      | owner@example.com | ValidPassword123! | USER        | active         |
      | other@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "other@example.com"
    When event type "article.analyzed" from project "Hermes" is requested
    Then the response should have status 403

  Scenario: Read an EventType as global admin
    Given the following users are registered:
      | email             | password          | global role | account status |
      | owner@example.com | ValidPassword123! | USER        | active         |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "admin@example.com"
    When event type "article.analyzed" from project "Hermes" is requested
    Then the response should have status 200
    And the response should identify event type "article.analyzed"
