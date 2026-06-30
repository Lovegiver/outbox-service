Feature: Projects

  Projects allow authenticated users to create, list and disable observable business scopes.

  Scenario: Create a project as an authenticated user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Runtime observability"
    Then the response should have status 200
    And a project should be registered with name "Hermes"

  Scenario: Automatically assign OWNER to the project creator
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Runtime observability"
    Then the response should have status 200
    And project "Hermes" should have member "alice@example.com" with role "OWNER"

  Scenario: Reject project creation when the project name already exists
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Duplicate project"
    Then the response should have status 400
    And the response error should contain "already exists"

  Scenario: List only projects visible to the authenticated user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
      | Apollo | Delivery monitoring   | bob@example.com   | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When projects are listed
    Then the response should have status 200
    And the response should contain project "Hermes"
    And the response should not contain project "Apollo"

  Scenario: List all projects as global admin
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
      | Apollo | Delivery monitoring   | bob@example.com   | OWNER      | active         |
    And the user is authenticated as "admin@example.com"
    When projects are listed
    Then the response should have status 200
    And the response should contain project "Hermes"
    And the response should contain project "Apollo"

  Scenario: Disable a project as authorized user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is disabled
    Then the response should have status 200
    And project "Hermes" should be inactive

  Scenario: Reject project disable without PROJECT_WRITE permission
    Given the following users are registered:
      | email              | password          | global role | account status |
      | viewer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email        | owner role | project status |
      | Hermes | Runtime observability | viewer@example.com | VIEWER     | active         |
    And the user is authenticated as "viewer@example.com"
    When project "Hermes" is disabled
    Then the response should have status 403
    And project "Hermes" should be active

  Scenario: Reject project disable when the project does not exist
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the user is authenticated as "admin@example.com"
    When project with id 999999 is disabled
    Then the response should have status 404
    And the response error should contain "not found"
