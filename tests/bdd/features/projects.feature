Feature: Projects

  Projects allow authenticated users to create, list and disable observable business scopes.

  Scenario: Create a project as an authenticated user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Runtime observability"
    Then the response should have status 200
    And a project should be registered with name "hermes"

  Scenario: Automatically assign OWNER to the project creator
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Runtime observability"
    Then the response should have status 200
    And project "hermes" should have member "alice@example.com" with role "OWNER"

  Scenario: Reject project creation when the project name already exists
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is created with description "Duplicate project"
    Then the response should have status 409
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

  Scenario: OWNER consults an active Project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is consulted
    Then the response should have status 200
    And the response should describe project "Hermes"

  Scenario: An outside user cannot consult a Project
    Given the following users are registered:
      | email               | password          | global role | account status |
      | alice@example.com   | ValidPassword123! | USER        | active         |
      | outsider@example.com | ValidPassword123! | USER       | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "outsider@example.com"
    When project "Hermes" is consulted
    Then the response should have status 403

  Scenario: OWNER can still consult a disabled Project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | inactive       |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is consulted
    Then the response should have status 200
    And the response should describe project "Hermes"

  Scenario: OWNER renames a Project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is renamed to "Apollo"
    Then the response should have status 200
    And project should be stored with name "apollo"
    And no project should be registered with name "Hermes"

  Scenario: OWNER explicitly clears a Project description
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" description is explicitly cleared
    Then the response should have status 200
    And project "Hermes" should have no description

  Scenario: A missing PATCH field stays unchanged
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is renamed to "Apollo"
    Then the response should have status 200
    And project "apollo" should have description "Runtime observability"

  Scenario: A duplicate Project name is refused without partial update
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
      | Apollo | Existing              |                   |            | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is renamed to "Apollo"
    Then the response should have status 409
    And project "Hermes" should have description "Runtime observability"

  Scenario: An empty Project update is refused
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When an empty Project update is submitted
    Then the response should have status 400
    And the response error should contain "PROJECT_UPDATE_EMPTY"

  Scenario: VIEWER cannot modify a Project
    Given the following users are registered:
      | email              | password          | global role | account status |
      | viewer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email        | owner role | project status |
      | Hermes | Runtime observability | viewer@example.com | VIEWER     | active         |
    And the user is authenticated as "viewer@example.com"
    When project "Hermes" is renamed to "Apollo"
    Then the response should have status 403
    And a project should be registered with name "Hermes"

  Scenario: OWNER disables and re-enables a Project without losing relations
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has one EventType
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is disabled
    Then the response should have status 200
    And project "Hermes" should be inactive
    When project "Hermes" is enabled
    Then the response should have status 200
    And project "Hermes" should be active
    And project "Hermes" should still have 1 member
    And project "Hermes" should still have 1 EventType

  Scenario: ADMIN can reactivate an inactive Project
    Given the following users are registered:
      | email             | password          | global role | account status |
      | admin@example.com | ValidPassword123! | ADMIN       | active         |
    And the following projects are registered:
      | name   | description           | owner email | owner role | project status |
      | Hermes | Runtime observability |             |            | inactive       |
    And the user is authenticated as "admin@example.com"
    When project "Hermes" is enabled
    Then the response should have status 200
    And project "Hermes" should be active

  Scenario: DEVELOPER cannot reactivate an inactive Project
    Given the following users are registered:
      | email                 | password          | global role | account status |
      | developer@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email           | owner role | project status |
      | Hermes | Runtime observability | developer@example.com | DEVELOPER  | inactive       |
    And the user is authenticated as "developer@example.com"
    When project "Hermes" is enabled
    Then the response should have status 403
    And project "Hermes" should be inactive

  Scenario: Re-enabling an active Project is idempotent
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When project "Hermes" is enabled
    Then the response should have status 200
    And project "Hermes" should be active
