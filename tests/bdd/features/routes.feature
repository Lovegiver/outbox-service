Feature: Routes

  Routes define where events of an EventType must be delivered.

  Scenario: Create an active route for an EventType
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When route "blackhole-webhook" with routing key "default" and URL "https://blackhole.example.test/webhook" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And route "blackhole-webhook" should be active for event type "article.analyzed" in project "Hermes"

  Scenario: List routes of an EventType
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "default" and URL "https://blackhole.example.test/webhook"
    And the user is authenticated as "alice@example.com"
    When routes are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And the response should contain route "blackhole-webhook"

  Scenario: Update a route
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "default" and URL "https://blackhole.example.test/webhook"
    And the user is authenticated as "alice@example.com"
    When route "blackhole-webhook" for event type "article.analyzed" in project "Hermes" is updated to routing key "priority" and URL "https://blackhole.example.test/priority"
    Then the response should have status 200
    And route "blackhole-webhook" should target URL "https://blackhole.example.test/priority" for event type "article.analyzed" in project "Hermes"

  Scenario: Reject route creation without ROUTE_WRITE
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
    When route "forbidden-webhook" with routing key "default" and URL "https://forbidden.example.test/webhook" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403
    And no route "forbidden-webhook" should be registered for event type "article.analyzed" in project "Hermes"

  Scenario: Reject route listing without ROUTE_READ
    Given the following users are registered:
      | email             | password          | global role | account status |
      | owner@example.com | ValidPassword123! | USER        | active         |
      | other@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "other@example.com"
    When routes are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403

  Scenario: Reject route creation when EventType does not exist
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the user is authenticated as "admin@example.com"
    When route "missing-event-type-route" with routing key "default" and URL "https://missing.example.test/webhook" is created for event type with id 999999
    Then the response should have status 404
    And the response error should contain "not found"

  Scenario: Reject route update when route does not exist
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "alice@example.com"
    When route with id 999999 for event type "article.analyzed" in project "Hermes" is updated to URL "https://missing.example.test/webhook"
    Then the response should have status 404
    And the response error should contain "not found"

  Scenario: A created route influences deliveries created by the worker
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "default" and URL "https://blackhole.example.test/webhook"
    And project "Hermes" has a received event for event type "article.analyzed"
    When received events are routed by the worker
    Then a delivery should be created for destination "blackhole-webhook"

  Scenario: A modified route influences deliveries created after modification
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "default" and URL "https://blackhole.example.test/webhook"
    And the user is authenticated as "alice@example.com"
    When route "blackhole-webhook" for event type "article.analyzed" in project "Hermes" is updated to routing key "priority" and URL "https://blackhole.example.test/priority"
    Then the response should have status 200
    Given project "Hermes" has a received event for event type "article.analyzed"
    When received events are routed by the worker
    Then a delivery should be created for destination "blackhole-webhook" with URL "https://blackhole.example.test/priority"
