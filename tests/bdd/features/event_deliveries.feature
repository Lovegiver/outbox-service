Feature: Event Deliveries

  Scenario: A single active Route creates one pending EventDelivery
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "article.analyzed" and URL "https://blackhole.example.test/webhook"
    And project "Hermes" has a received Event of type "article.analyzed"
    When received Events are routed into deliveries
    Then the received Event should have status "ROUTED"
    And the received Event should have 1 delivery
    And delivery "blackhole-webhook" should be created for the received Event
    And delivery "blackhole-webhook" should have status "PENDING"
    And delivery "blackhole-webhook" should have destination type "webhook"
    And delivery "blackhole-webhook" should target URL "https://blackhole.example.test/webhook"
    And delivery "blackhole-webhook" should have attempt count 0
    And delivery "blackhole-webhook" should have no last error

  Scenario: Multiple active Routes create multiple EventDeliveries
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "article.analyzed" and URL "https://blackhole.example.test/webhook"
    And event type "article.analyzed" in project "Hermes" has route "audit-webhook" with routing key "article.analyzed.audit" and URL "https://audit.example.test/webhook"
    And project "Hermes" has a received Event of type "article.analyzed"
    When received Events are routed into deliveries
    Then the received Event should have status "ROUTED"
    And the received Event should have 2 deliveries
    And delivery "blackhole-webhook" should be created for the received Event
    And delivery "audit-webhook" should be created for the received Event

  Scenario: No active Route makes the Event unroutable and creates no EventDelivery
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And project "Hermes" has a received Event of type "article.analyzed"
    When received Events are routed into deliveries
    Then the received Event should have status "UNROUTABLE"
    And the received Event should have 0 deliveries

  Scenario: Routing an already routed Event does not create duplicate deliveries
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "article.analyzed" and URL "https://blackhole.example.test/webhook"
    And project "Hermes" has a received Event of type "article.analyzed"
    When received Events are routed into deliveries
    And received Events are routed into deliveries
    Then the received Event should have status "ROUTED"
    And the received Event should have 1 delivery

  Scenario: An EventDelivery always belongs to the routed Event
    Given the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And event type "article.analyzed" in project "Hermes" has route "blackhole-webhook" with routing key "article.analyzed" and URL "https://blackhole.example.test/webhook"
    And project "Hermes" has a received Event of type "article.analyzed"
    When received Events are routed into deliveries
    Then delivery "blackhole-webhook" should be linked to the received Event
