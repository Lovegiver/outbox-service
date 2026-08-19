Feature: Runtime metrics dashboard

  The dashboard summary is rebuilt from durable PostgreSQL state.

  Scenario: Return an empty summary when the database is empty
    When the runtime metrics summary is requested
    Then the response should have status 200
    And the runtime summary should contain:
      | field                               | value |
      | events_routed                       | 0     |
      | events_unroutable                   | 0     |
      | events_failed                       | 0     |
      | events_total                        | 0     |
      | deliveries_created                  | 0     |
      | deliveries_pending                  | 0     |
      | deliveries_succeeded                | 0     |
      | deliveries_failed                   | 0     |
      | dead_letters                        | 0     |
      | retry_count                         | 0     |
      | pending_events                      | 0     |
      | pending_deliveries                  | 0     |
      | oldest_received_age_seconds         | null  |
      | oldest_pending_delivery_age_seconds | null  |

  Scenario: Count every durable Event status
    Given Events exist with the following statuses:
      | status     | count |
      | RECEIVED   | 2     |
      | ROUTED     | 3     |
      | UNROUTABLE | 4     |
      | FAILED     | 5     |
    When the runtime metrics summary is requested
    Then the runtime summary should contain:
      | field             | value |
      | pending_events    | 2     |
      | events_routed     | 3     |
      | events_unroutable | 4     |
      | events_failed     | 5     |
      | events_total      | 14    |

  Scenario: Count every durable Delivery status and retry
    Given Deliveries exist with the following states:
      | status      | attempt count |
      | PENDING     | 0             |
      | PENDING     | 2             |
      | DELIVERED   | 1             |
      | FAILED      | 3             |
      | DEAD_LETTER | 4             |
    When the runtime metrics summary is requested
    Then the runtime summary should contain:
      | field                | value |
      | deliveries_created   | 5     |
      | deliveries_pending   | 2     |
      | deliveries_succeeded | 1     |
      | deliveries_failed    | 1     |
      | dead_letters         | 1     |
      | pending_deliveries   | 2     |
      | retry_count          | 6     |

  Scenario: Report the age of the oldest pending work
    Given a received Event created 120 seconds ago
    And a pending Delivery created 90 seconds ago
    When the runtime metrics summary is requested
    Then the oldest received Event age should be at least 120 seconds
    And the oldest pending Delivery age should be at least 90 seconds
