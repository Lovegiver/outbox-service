Feature: Prometheus business metric state

  Prometheus scrapes counters already materialized by OB1 for one Project.

  Scenario: Return an empty document for a Project without materialized counters
    Given Prometheus project "empty-shop" exists
    When Prometheus business state is requested for project "empty-shop"
    Then the response should have status 200
    And the Prometheus business response should be empty

  Scenario: Return 404 for an unknown Project
    When Prometheus business state is requested for unknown project id 999999999
    Then the response should have status 404

  Scenario: Never derive exposed counters during a scrape
    Given project "observation-only" has pending counter observations:
      | event_type    | metric_code         | value | labels           |
      | product.sold  | products_sold_total | 12    | {"country":"FR"} |
    When Prometheus business state is requested for project "observation-only"
    Then the response should have status 200
    And the Prometheus business response should be empty
    And project "observation-only" should have 0 materialized counters
    And the aggregation checkpoint for project "observation-only" event type "product.sold" should not exist

  Scenario: Expose one cumulative counter after aggregation
    Given project "shop-counter" has pending counter observations:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 7     | {"country":"FR"} |
      | product.sold | products_sold_total | 5     | {"country":"FR"} |
    When all pending counter observations are aggregated
    And Prometheus business state is requested for project "shop-counter"
    Then the response should have status 200
    And metric "ob1_products_sold_total" with label "country" equal to "FR" should expose value 12

  Scenario: Aggregation is idempotent without new observations
    Given project "shop-idempotent" has pending counter observations:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 3     | {"country":"FR"} |
      | product.sold | products_sold_total | 4     | {"country":"FR"} |
    When all pending counter observations are aggregated twice
    And Prometheus business state is requested for project "shop-idempotent"
    Then metric "ob1_products_sold_total" with label "country" equal to "FR" should expose value 7
    And the aggregation checkpoint for project "shop-idempotent" event type "product.sold" should equal the last observation

  Scenario: Keep dimension sets as distinct series
    Given project "shop-series" has pending counter observations:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 12    | {"country":"FR"} |
      | product.sold | products_sold_total | 4     | {"country":"BE"} |
    When all pending counter observations are aggregated
    And Prometheus business state is requested for project "shop-series"
    Then metric "ob1_products_sold_total" should expose 2 series
    And metric "ob1_products_sold_total" with label "country" equal to "FR" should expose value 12
    And metric "ob1_products_sold_total" with label "country" equal to "BE" should expose value 4

  Scenario: Expose all EventTypes of one Project
    Given project "multi-events" has materialized counters:
      | event_type       | metric_code        | value | labels |
      | product.sold     | business_total     | 8     | {}     |
      | product.returned | business_total     | 2     | {}     |
    When Prometheus business state is requested for project "multi-events"
    Then the Prometheus response should contain platform EventType "product.sold"
    And the Prometheus response should contain platform EventType "product.returned"

  Scenario: Isolate counters between Projects
    Given project "visible-shop" has materialized counters:
      | event_type   | metric_code    | value | labels |
      | product.sold | visible_total  | 5     | {}     |
    And project "other-shop" has materialized counters:
      | event_type   | metric_code   | value | labels |
      | product.sold | secret_total | 99    | {}     |
    When Prometheus business state is requested for project "visible-shop"
    Then the Prometheus business response should contain metric "ob1_visible_total"
    And the Prometheus business response should not contain metric "ob1_secret_total"
    And the Prometheus response should not contain platform Project "other-shop"

  Scenario: Add stable platform labels at exposition time
    Given project "platform-shop" has materialized counters:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 1     | {"country":"FR"} |
    When Prometheus business state is requested for project "platform-shop"
    Then the Prometheus response should contain platform Project "platform-shop"
    And the Prometheus response should contain platform EventType "product.sold"
    And persisted business labels for project "platform-shop" should not contain platform labels

  Scenario: Reject a business label reserved by OB1
    Given project "collision-shop" has pending counter observations:
      | event_type   | metric_code         | value | labels                   |
      | product.sold | products_sold_total | 1     | {"ob1_project":"forged"} |
    When aggregation is attempted atomically
    Then aggregation should fail with "reserved prefix"
    And project "collision-shop" should have 0 materialized counters
    And the aggregation checkpoint for project "collision-shop" event type "product.sold" should not exist

  Scenario: Emit TYPE once for several series in one family
    Given project "type-shop" has materialized counters:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 12    | {"country":"FR"} |
      | product.sold | products_sold_total | 4     | {"country":"BE"} |
    When Prometheus business state is requested for project "type-shop"
    Then type "counter" for metric "ob1_products_sold_total" should appear once

  Scenario: Escape label values in text exposition
    Given project "escape-shop" has a materialized counter with special label characters
    When Prometheus business state is requested for project "escape-shop"
    Then the Prometheus business response should contain escaped special label characters

  Scenario: Normalize an incompatible business metric code
    Given project "name-shop" has materialized counters:
      | event_type   | metric_code          | value | labels |
      | product.sold | 9products.sold-total | 1     | {}     |
    When Prometheus business state is requested for project "name-shop"
    Then the Prometheus business response should contain metric "ob1_9products_sold_total"

  Scenario: Produce deterministic family and series ordering
    Given project "ordered-shop" has materialized counters:
      | event_type   | metric_code | value | labels           |
      | product.sold | z.total     | 1     | {"country":"FR"} |
      | product.sold | a.total     | 2     | {"country":"FR"} |
      | product.sold | a.total     | 3     | {"country":"BE"} |
    When Prometheus business state is requested twice for project "ordered-shop"
    Then both Prometheus business responses should be identical
    And Prometheus families and series should be sorted

  Scenario: Advertise Prometheus text format
    Given Prometheus project "content-type-shop" exists
    When Prometheus business state is requested for project "content-type-shop"
    Then the Prometheus business Content-Type should be "text/plain; version=0.0.4; charset=utf-8"

  Scenario: Roll back state and checkpoint when aggregation fails
    Given project "atomic-shop" has materialized counters:
      | event_type   | metric_code         | value | labels           |
      | product.sold | products_sold_total | 5     | {"country":"FR"} |
    And project "atomic-shop" has pending counter observations:
      | event_type   | metric_code         | value | labels                   |
      | product.sold | products_sold_total | 2     | {"country":"FR"}         |
      | product.sold | products_sold_total | 1     | {"ob1_event_type":"bad"} |
    When aggregation is attempted atomically
    Then aggregation should fail with "reserved prefix"
    And materialized metric "products_sold_total" in project "atomic-shop" should still have value 5
    And the aggregation checkpoint for project "atomic-shop" event type "product.sold" should not exist
