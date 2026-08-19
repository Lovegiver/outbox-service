Feature: Metric Definitions

  Scenario: A developer creates a MetricDefinition for an EventType
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "developer@example.test"
    When metric definition "article_analysis_count" named "Article analysis count" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And metric definition "article_analysis_count" should be registered for event type "article.analyzed" in project "Hermes"
    And metric definition "article_analysis_count" should be active for event type "article.analyzed" in project "Hermes"
    And the response should contain metric definition "article_analysis_count"

  Scenario: A viewer cannot create a MetricDefinition
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "viewer@example.test"
    When metric definition "article_analysis_count" named "Article analysis count" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403
    And metric definition "article_analysis_count" should not be registered for event type "article.analyzed" in project "Hermes"

  Scenario: Creating a MetricDefinition for an unknown EventType is rejected
    Given user "admin@example.test" exists with global role "ADMIN"
    And the user is authenticated as "admin@example.test"
    When metric definition "article_analysis_count" named "Article analysis count" is created for unknown event type id 999999
    Then the response should have status 404

  Scenario: Duplicate MetricDefinition code is rejected on the same EventType
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And the user is authenticated as "developer@example.test"
    When metric definition "article_analysis_count" named "Article analysis count" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    When metric definition "article_analysis_count" named "Duplicate article analysis count" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 409

  Scenario: Same MetricDefinition code is allowed on different EventTypes
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And project "Hermes" has event type "article.imported" named "Article imported"
    And the user is authenticated as "developer@example.test"
    When metric definition "article_count" named "Article analyzed count" is created for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    When metric definition "article_count" named "Article imported count" is created for event type "article.imported" in project "Hermes"
    Then the response should have status 200
    And metric definition "article_count" should be registered for event type "article.analyzed" in project "Hermes"
    And metric definition "article_count" should be registered for event type "article.imported" in project "Hermes"

  Scenario: MetricDefinitions can be listed for an EventType
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And metric definition "article_analysis_count" exists for event type "article.analyzed" in project "Hermes"
    And metric definition "article_duration_seconds" exists for event type "article.analyzed" in project "Hermes"
    And the user is authenticated as "developer@example.test"
    When metric definitions are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 200
    And the response should contain metric definition "article_analysis_count"
    And the response should contain metric definition "article_duration_seconds"

  Scenario: A non member cannot list MetricDefinitions
    Given project "Hermes" has event type "article.analyzed" named "Article analyzed"
    And metric definition "article_analysis_count" exists for event type "article.analyzed" in project "Hermes"
    And user "outsider@example.test" exists
    And the user is authenticated as "outsider@example.test"
    When metric definitions are listed for event type "article.analyzed" in project "Hermes"
    Then the response should have status 403
