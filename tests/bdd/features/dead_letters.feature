Feature: Dead Letters

  Dead Letters expose deliveries that reached a terminal failure state and allow
  authorized users to manually requeue them.

  Scenario: A project viewer can list project dead letters
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503 Service Unavailable" after 3 attempts
    And the user is authenticated as "viewer@example.test"
    When dead letters are listed for project "Hermes"
    Then the response should have status 200
    And the response should contain dead letter "blackhole-webhook"
    And the dead letter "blackhole-webhook" should expose attempt count 3
    And the dead letter "blackhole-webhook" should expose last error "HTTP 503 Service Unavailable"
    And the dead letter "blackhole-webhook" should expose an event UUID

  Scenario: Dead letter listing is scoped to the requested project
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503 Service Unavailable" after 3 attempts
    And project "Atlas" has dead letter delivery "atlas-webhook" with error "HTTP 500" after 3 attempts
    And the user is authenticated as "viewer@example.test"
    When dead letters are listed for project "Hermes"
    Then the response should have status 200
    And the response should contain dead letter "blackhole-webhook"
    And the response should not contain dead letter "atlas-webhook"

  Scenario: A non member cannot list project dead letters
    Given project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503 Service Unavailable" after 3 attempts
    And user "outsider@example.test" exists
    And the user is authenticated as "outsider@example.test"
    When dead letters are listed for project "Hermes"
    Then the response should have status 403

  Scenario: A developer can retry a project dead letter
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503 Service Unavailable" after 3 attempts
    And the user is authenticated as "developer@example.test"
    When dead letter "blackhole-webhook" is retried for project "Hermes"
    Then the response should have status 200
    And delivery "blackhole-webhook" should have status "PENDING"
    And delivery "blackhole-webhook" should have attempt count 0
    And delivery "blackhole-webhook" should have no last error

  Scenario: A viewer cannot retry a project dead letter
    Given project "Hermes" has user "viewer@example.test" with role "VIEWER"
    And project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503 Service Unavailable" after 3 attempts
    And the user is authenticated as "viewer@example.test"
    When dead letter "blackhole-webhook" is retried for project "Hermes"
    Then the response should have status 403
    And delivery "blackhole-webhook" should have status "DEAD_LETTER"

  Scenario: Retrying an unknown dead letter returns not found
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And the user is authenticated as "developer@example.test"
    When dead letter id 999999 is retried for project "Hermes"
    Then the response should have status 404

  Scenario: Retrying a non dead-letter delivery is rejected
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has failed delivery "blackhole-webhook" with error "Previous failure" after 1 attempts
    And the user is authenticated as "developer@example.test"
    When dead letter "blackhole-webhook" is retried for project "Hermes"
    Then the response should have status 404
    And delivery "blackhole-webhook" should have status "FAILED"

  Scenario: Retry all dead letters requeues all project dead letters only
    Given project "Hermes" has user "developer@example.test" with role "DEVELOPER"
    And project "Hermes" has dead letter delivery "blackhole-webhook" with error "HTTP 503" after 3 attempts
    And project "Hermes" has dead letter delivery "audit-webhook" with error "HTTP 500" after 3 attempts
    And project "Atlas" has dead letter delivery "atlas-webhook" with error "HTTP 500" after 3 attempts
    And the user is authenticated as "developer@example.test"
    When all dead letters are retried for project "Hermes"
    Then the response should have status 200
    And the retry-all response should report 2 retried dead letters
    And delivery "blackhole-webhook" should have status "PENDING"
    And delivery "audit-webhook" should have status "PENDING"
    And delivery "atlas-webhook" should have status "DEAD_LETTER"
