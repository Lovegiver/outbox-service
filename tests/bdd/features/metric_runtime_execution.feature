Feature: Execute compiled metric ProcessingPlans at Event runtime
  Metric runtime consumes only the exact active compiled snapshot and remains
  durable, idempotent and independent from routing and delivery.

  Scenario: Execute the exact active chain for the Event schema
    Given a runtime Event with an ACTIVE compiled metric plan
    When the runtime worker routes and processes its metric plans
    Then one durable metric observation is produced from the selected plan

  Scenario: Ignore an Event without an active chain
    Given a runtime Event without a ProcessingChain
    When the runtime worker routes and processes its metric plans
    Then no metric execution or observation is created
    And routing still creates its delivery

  Scenario Outline: Ignore inactive metric chain statuses
    Given a runtime Event with only a <status> metric chain
    When the runtime worker routes and processes its metric plans
    Then no metric execution or observation is created
    And routing still creates its delivery

    Examples:
      | status     |
      | DRAFT      |
      | INCOMPLETE |

  Scenario: Never fall back to another schema chain
    Given a runtime Event whose only ACTIVE metric chain targets another schema
    When the runtime worker routes and processes its metric plans
    Then no metric execution or observation is created

  Scenario: Freeze the first selected snapshot across retries
    Given a runtime Event with an ACTIVE compiled metric plan
    When its metric executions are materialized
    And another ProcessingChain becomes ACTIVE before metric execution
    And the pending metric executions are processed
    Then the observation references the originally materialized chain

  Scenario: Execute several plans independently
    Given a runtime Event with three compiled metric plans
    When the runtime worker routes and processes its metric plans
    Then all three metric plan executions succeed
    And three durable metric observations are produced

  Scenario: Execute several observations from one compiled plan
    Given a runtime Event with one plan containing two compiled observations
    When the runtime worker routes and processes its metric plans
    Then two observations have distinct deterministic occurrence keys

  Scenario Outline: Execute every activable transform
    Given a runtime Event with the compiled transform <transform>
    When the runtime worker routes and processes its metric plans
    Then the metric value is <value>

    Examples:
      | transform | value |
      | constant  | 1     |
      | identity  | 12    |
      | count     | 3     |
      | length    | 4     |
      | to_number | 1     |

  Scenario: Extract deterministic business labels
    Given a runtime Event with two compiled business labels
    When the runtime worker routes and processes its metric plans
    Then the observation dimensions are country FR and premium true

  Scenario: Skip an optional value path that is absent
    Given a runtime Event with an absent optional value path
    When the runtime worker routes and processes its metric plans
    Then the metric plan succeeds without an observation

  Scenario: Preserve an absent optional label structurally
    Given a runtime Event with an absent optional label
    When the runtime worker routes and processes its metric plans
    Then the observation stores a null country dimension
    And metric aggregation preserves the null country partition
    And Prometheus omits the null country label

  Scenario: Preserve a real business label equal to __missing__
    Given a runtime Event whose country label equals __missing__
    When the runtime worker routes and processes its metric plans
    Then the observation stores the literal __missing__ country value
    And Prometheus exposes the literal __missing__ country value

  Scenario: Coalesce internal counter partitions at the Prometheus boundary
    Given a runtime Event with three internally distinct converging counter partitions
    When the runtime worker routes and processes its metric plans
    And the runtime metric observations are aggregated
    Then three distinct MetricState partitions remain
    And the Project scrape exposes one coalesced counter with value 3

  Scenario: Keep successful plans when another plan fails
    Given a runtime Event with a successful failing and successful metric plan
    When the runtime worker routes and processes its metric plans
    Then the two successful plan observations are preserved
    And the failed plan leaves no partial observation
    And routing still creates its delivery

  Scenario: Record an ACTIVE chain without plans as a durable defect
    Given a runtime Event with an ACTIVE chain containing no plan
    When the runtime worker routes and processes its metric plans
    Then a durable metric configuration failure is recorded
    And routing still creates its delivery

  Scenario: Record an unknown compiled operation without runtime repair
    Given a runtime Event with an unknown compiled operation
    When the runtime worker routes and processes its metric plans
    Then the metric plan fails permanently with a unsupported runtime error
    And no metric observation is produced

  Scenario: Record an active plan without compiled JSON durably
    Given a runtime Event with an ACTIVE plan lacking compiled JSON
    When the runtime worker routes and processes its metric plans
    Then the metric plan fails permanently with a no compiled plan error
    And routing still creates its delivery

  Scenario: Technical replay never duplicates observations or deliveries
    Given a runtime Event with an ACTIVE compiled metric plan
    When the runtime worker routes and processes its metric plans twice
    Then exactly one metric execution and observation remain
    And exactly one delivery remains

  Scenario: Metric retry never replays delivery
    Given a runtime Event with a retryable metric plan execution
    When the independent metric retry cycle runs
    Then no additional delivery is created by the metric retry

  Scenario: Aggregation after runtime replay does not double MetricState
    Given a runtime Event with an ACTIVE compiled metric plan
    When the runtime worker routes and processes its metric plans twice
    And runtime observations are aggregated twice
    Then the materialized metric counter value is 1
