Feature: Cross-cutting authorization

  Project roles grant a stable permission matrix across every resource family.

  Scenario Outline: Enforce the project role permission matrix
    Given a "<role>" actor for project "Hermes"
    When the actor exercises "<permission>" on project "Hermes"
    Then the authorization result should be "<result>"

    Examples:
      | role       | permission       | result    |
      | OWNER      | PROJECT_READ     | allowed   |
      | OWNER      | PROJECT_WRITE    | allowed   |
      | OWNER      | EVENT_TYPE_READ  | allowed   |
      | OWNER      | EVENT_TYPE_WRITE | allowed   |
      | OWNER      | SCHEMA_READ      | allowed   |
      | OWNER      | SCHEMA_WRITE     | allowed   |
      | OWNER      | ROUTE_READ       | allowed   |
      | OWNER      | ROUTE_WRITE      | allowed   |
      | OWNER      | API_KEY_READ     | allowed   |
      | OWNER      | API_KEY_WRITE    | allowed   |
      | OWNER      | METRICS_READ     | allowed   |
      | OWNER      | METRICS_WRITE    | allowed   |
      | DEVELOPER  | PROJECT_READ     | allowed   |
      | DEVELOPER  | PROJECT_WRITE    | forbidden |
      | DEVELOPER  | EVENT_TYPE_READ  | allowed   |
      | DEVELOPER  | EVENT_TYPE_WRITE | allowed   |
      | DEVELOPER  | SCHEMA_READ      | allowed   |
      | DEVELOPER  | SCHEMA_WRITE     | allowed   |
      | DEVELOPER  | ROUTE_READ       | allowed   |
      | DEVELOPER  | ROUTE_WRITE      | allowed   |
      | DEVELOPER  | API_KEY_READ     | allowed   |
      | DEVELOPER  | API_KEY_WRITE    | allowed   |
      | DEVELOPER  | METRICS_READ     | allowed   |
      | DEVELOPER  | METRICS_WRITE    | allowed   |
      | VIEWER     | PROJECT_READ     | allowed   |
      | VIEWER     | PROJECT_WRITE    | forbidden |
      | VIEWER     | EVENT_TYPE_READ  | allowed   |
      | VIEWER     | EVENT_TYPE_WRITE | forbidden |
      | VIEWER     | SCHEMA_READ      | allowed   |
      | VIEWER     | SCHEMA_WRITE     | forbidden |
      | VIEWER     | ROUTE_READ       | allowed   |
      | VIEWER     | ROUTE_WRITE      | forbidden |
      | VIEWER     | API_KEY_READ     | allowed   |
      | VIEWER     | API_KEY_WRITE    | forbidden |
      | VIEWER     | METRICS_READ     | allowed   |
      | VIEWER     | METRICS_WRITE    | forbidden |
      | NON_MEMBER | PROJECT_READ     | forbidden |
      | NON_MEMBER | PROJECT_WRITE    | forbidden |
      | NON_MEMBER | EVENT_TYPE_READ  | forbidden |
      | NON_MEMBER | EVENT_TYPE_WRITE | forbidden |
      | NON_MEMBER | SCHEMA_READ      | forbidden |
      | NON_MEMBER | SCHEMA_WRITE     | forbidden |
      | NON_MEMBER | ROUTE_READ       | forbidden |
      | NON_MEMBER | ROUTE_WRITE      | forbidden |
      | NON_MEMBER | API_KEY_READ     | forbidden |
      | NON_MEMBER | API_KEY_WRITE    | forbidden |
      | NON_MEMBER | METRICS_READ     | forbidden |
      | NON_MEMBER | METRICS_WRITE    | forbidden |
      | ADMIN      | PROJECT_READ     | allowed   |
      | ADMIN      | PROJECT_WRITE    | allowed   |
      | ADMIN      | EVENT_TYPE_READ  | allowed   |
      | ADMIN      | EVENT_TYPE_WRITE | allowed   |
      | ADMIN      | SCHEMA_READ      | allowed   |
      | ADMIN      | SCHEMA_WRITE     | allowed   |
      | ADMIN      | ROUTE_READ       | allowed   |
      | ADMIN      | ROUTE_WRITE      | allowed   |
      | ADMIN      | API_KEY_READ     | allowed   |
      | ADMIN      | API_KEY_WRITE    | allowed   |
      | ADMIN      | METRICS_READ     | allowed   |
      | ADMIN      | METRICS_WRITE    | allowed   |

  Scenario: Return 401 when authentication is absent
    Given project "Hermes" exists for authorization checks
    When an unauthenticated actor lists project "Hermes" members
    Then the response should have status 401

  Scenario: Return 401 when authentication is invalid
    Given project "Hermes" exists for authorization checks
    And the user has an invalid authentication token
    When the actor lists project "Hermes" members
    Then the response should have status 401

  Scenario: Return 403 when an authenticated user lacks authorization
    Given a "NON_MEMBER" actor for project "Hermes"
    When the actor lists project "Hermes" members
    Then the response should have status 403
