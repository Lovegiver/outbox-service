Feature: Delivery Worker

  The delivery worker executes persisted EventDeliveries and updates their
  lifecycle according to the delivery result.

  Scenario: A pending webhook delivery succeeds
    Given project "Hermes" has a routed Event with pending delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And webhook deliveries will succeed
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DELIVERED"
    And delivery "blackhole-webhook" should have attempt count 1
    And delivery "blackhole-webhook" should have no last error

  Scenario: A pending webhook delivery failure is persisted
    Given project "Hermes" has a routed Event with pending delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And webhook deliveries will fail with "HTTP 503 Service Unavailable"
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "FAILED"
    And delivery "blackhole-webhook" should have attempt count 1
    And delivery "blackhole-webhook" should have last error containing "HTTP 503 Service Unavailable"

  Scenario: A delivered delivery is not processed again
    Given project "Hermes" has a routed Event with delivered delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And webhook deliveries will fail with "should not be called"
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DELIVERED"
    And delivery "blackhole-webhook" should have attempt count 1
    And webhook delivery should not have been called

  Scenario: A dead-letter delivery is not processed again
    Given project "Hermes" has a routed Event with dead-letter delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And webhook deliveries will fail with "should not be called"
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DEAD_LETTER"
    And webhook delivery should not have been called

  Scenario: A failed retryable delivery is processed again
    Given project "Hermes" has a routed Event with failed delivery "blackhole-webhook" to "https://blackhole.example.test/webhook" after 1 attempt
    And webhook deliveries will succeed
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DELIVERED"
    And delivery "blackhole-webhook" should have attempt count 2
    And delivery "blackhole-webhook" should have no last error

Scenario: Unsupported destination type fails the delivery
    Given project "Hermes" has a routed Event with pending delivery "kafka-target" to "https://blackhole.example.test/webhook"
    And delivery "kafka-target" has destination type "kafka"
    When pending deliveries are processed by the delivery worker
    Then delivery "kafka-target" should have status "FAILED"
    And delivery "kafka-target" should have attempt count 1
    And delivery "kafka-target" should have last error containing "Unsupported destination type"

  Scenario: Missing destination URL fails the delivery
    Given project "Hermes" has a routed Event with pending delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And delivery "blackhole-webhook" has no destination URL
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "FAILED"
    And delivery "blackhole-webhook" should have attempt count 1
    And delivery "blackhole-webhook" should have last error containing "No destination URL"

  Scenario: Final failed attempt moves the delivery to dead letter
    Given max delivery attempts is 3
    And project "Hermes" has a routed Event with failed delivery "blackhole-webhook" to "https://blackhole.example.test/webhook" after 2 attempt
    And webhook deliveries will fail with "HTTP 503 Service Unavailable"
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DEAD_LETTER"
    And delivery "blackhole-webhook" should have attempt count 3
    And delivery "blackhole-webhook" should have last error containing "HTTP 503 Service Unavailable"

  Scenario: Non retryable failed delivery is not processed again
    Given max delivery attempts is 3
    And project "Hermes" has a routed Event with failed delivery "blackhole-webhook" to "https://blackhole.example.test/webhook" after 3 attempt
    And webhook deliveries will fail with "should not be called"
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "FAILED"
    And delivery "blackhole-webhook" should have attempt count 3
    And webhook delivery should not have been called

  Scenario: Multiple pending deliveries are processed in the same worker pass
    Given project "Hermes" has a routed Event with pending delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And the same routed Event has pending delivery "audit-webhook" to "https://audit.example.test/webhook"
    And webhook deliveries will succeed
    When pending deliveries are processed by the delivery worker
    Then delivery "blackhole-webhook" should have status "DELIVERED"
    And delivery "audit-webhook" should have status "DELIVERED"
    And webhook delivery should have been called 2 times

  Scenario: Successful webhook delivery sends the Event payload to the destination URL
    Given project "Hermes" has a routed Event with pending delivery "blackhole-webhook" to "https://blackhole.example.test/webhook"
    And webhook deliveries will record successful calls
    When pending deliveries are processed by the delivery worker
    Then the last webhook call should target URL "https://blackhole.example.test/webhook"
    And the last webhook call payload should contain number "duration_seconds" equal to 12.3

  Scenario: Processing a missing delivery id is ignored safely
    When missing delivery id 999999 is processed by the delivery worker
    Then missing delivery processing should not fail
