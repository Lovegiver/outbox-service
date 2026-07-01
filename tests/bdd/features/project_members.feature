Feature: Project Members

  Project members allow authorized users to manage who can access a project.

  Scenario: List project members as authorized member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has member "bob@example.com" with role "VIEWER"
    And the user is authenticated as "alice@example.com"
    When project "Hermes" members are listed
    Then the response should have status 200
    And the response should contain project member "alice@example.com" with role "OWNER"
    And the response should contain project member "bob@example.com" with role "VIEWER"

  Scenario: Reject project members listing without PROJECT_READ
    Given the following users are registered:
      | email             | password          | global role | account status |
      | owner@example.com | ValidPassword123! | USER        | active         |
      | other@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And the user is authenticated as "other@example.com"
    When project "Hermes" members are listed
    Then the response should have status 403

  Scenario: Add an existing user as project member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When user "bob@example.com" is added to project "Hermes" with role "DEVELOPER"
    Then the response should have status 200
    And project "Hermes" should have member "bob@example.com" with role "DEVELOPER"

  Scenario: Reject adding an unknown user as project member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When user "unknown@example.com" is added to project "Hermes" with role "VIEWER"
    Then the response should have status 400
    And the response error should contain "not found"

  Scenario: Reject adding a user who is already project member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has member "bob@example.com" with role "VIEWER"
    And the user is authenticated as "alice@example.com"
    When user "bob@example.com" is added to project "Hermes" with role "DEVELOPER"
    Then the response should have status 400
    And the response error should contain "already"

  Scenario: Update a project member role
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has member "bob@example.com" with role "VIEWER"
    And the user is authenticated as "alice@example.com"
    When user "bob@example.com" role is changed to "DEVELOPER" in project "Hermes"
    Then the response should have status 200
    And project "Hermes" should have member "bob@example.com" with role "DEVELOPER"

  Scenario: Reject project member role update without PROJECT_WRITE
    Given the following users are registered:
      | email              | password          | global role | account status |
      | owner@example.com  | ValidPassword123! | USER        | active         |
      | viewer@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com    | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | owner@example.com | OWNER      | active         |
    And project "Hermes" has member "viewer@example.com" with role "VIEWER"
    And project "Hermes" has member "bob@example.com" with role "VIEWER"
    And the user is authenticated as "viewer@example.com"
    When user "bob@example.com" role is changed to "DEVELOPER" in project "Hermes"
    Then the response should have status 403
    And project "Hermes" should have member "bob@example.com" with role "VIEWER"

  Scenario: Remove a project member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And project "Hermes" has member "bob@example.com" with role "VIEWER"
    And the user is authenticated as "alice@example.com"
    When user "bob@example.com" is removed from project "Hermes"
    Then the response should have status 204
    And project "Hermes" should not have member "bob@example.com"

  Scenario: Reject removing a non-member
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
      | bob@example.com   | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When user "bob@example.com" is removed from project "Hermes"
    Then the response should have status 400
    And the response error should contain "not a member"

  Scenario: Reject removing the last OWNER
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When user "alice@example.com" is removed from project "Hermes"
    Then the response should have status 400
    And the response error should contain "last project OWNER"
    And project "Hermes" should have member "alice@example.com" with role "OWNER"

  Scenario: Reject downgrading the last OWNER
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the following projects are registered:
      | name   | description           | owner email       | owner role | project status |
      | Hermes | Runtime observability | alice@example.com | OWNER      | active         |
    And the user is authenticated as "alice@example.com"
    When user "alice@example.com" role is changed to "VIEWER" in project "Hermes"
    Then the response should have status 400
    And the response error should contain "last project OWNER"
    And project "Hermes" should have member "alice@example.com" with role "OWNER"
