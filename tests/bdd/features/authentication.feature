
Feature: Authentication

  Authentication allows users to register and authenticate themselves.

  Scenario: Register a new user
    Given no user is registered with email "alice@example.com"
    When a user registers with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 200
    And a user should be registered with email "alice@example.com"
    And the response should identify user "alice@example.com"

  Scenario: Reject registration with an already used email
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When a user registers with email "alice@example.com" and password "AnotherPassword123!"
    Then the response should have status 400
    And the response error should contain "already exists"

  Scenario Outline: Reject registration with a malformed email
    When a user registers with email "<email>" and password "ValidPassword123!"
    Then the response should have status 422
    And no user should be registered with email "<email>"

    Examples:
      | email   |
      | foo     |
      | foo@    |
      | bar.com |
      | foo@bar |

  Scenario: Reject registration with an empty email
    When a user registers with an empty email
    Then the response should have status 422
    And no user should be registered with email ""

  Scenario: Normalize email when registering
    When a user registers with email "  Alice@Example.COM  " and password "ValidPassword123!"
    Then the response should have status 200
    And a user should be registered with email "alice@example.com"

  Scenario: Reject an email already registered with different casing
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When a user registers with email "ALICE@EXAMPLE.COM" and password "AnotherPassword123!"
    Then the response should have status 400
    And the response error should contain "already exists"

  Scenario Outline: Reject a password outside the length policy
    When a user registers with email "alice@example.com" and password "<password>"
    Then the response should have status 422
    And no user should be registered with email "alice@example.com"

    Examples:
      | password                          |
      | Short1!                           |
      | ValidPassword123!ValidPassword12! |

  Scenario: Reject registration with an empty password
    When a user registers with an empty password
    Then the response should have status 422
    And no user should be registered with email "alice@example.com"

  Scenario Outline: Reject a password missing a required character class
    When a user registers with email "alice@example.com" and password "<password>"
    Then the response should have status 422
    And no user should be registered with email "alice@example.com"

    Examples:
      | password          |
      | validpassword123! |
      | VALIDPASSWORD123! |
      | ValidPassword!!!  |
      | ValidPassword123  |

  Scenario: Login with valid credentials
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 200
    And the response should contain an access token

  Scenario: Reject login with an invalid password
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "alice@example.com" and password "WrongPassword123!"
    Then the response should have status 401
    And the response error should contain "Invalid credentials"

  Scenario: Reject login for an unknown user
    Given no user is registered with email "unknown@example.com"
    When the user logs in with email "unknown@example.com" and password "ValidPassword123!"
    Then the response should have status 401
    And the response error should contain "Invalid credentials"

  Scenario: Reject login for an inactive user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | inactive       |
    When the user logs in with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 401
    And the response error should contain "Invalid credentials"

  Scenario: Normalize email when logging in
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "  ALICE@EXAMPLE.COM  " and password "ValidPassword123!"
    Then the response should have status 200
    And the response should contain an access token

  Scenario: Retrieve the authenticated user identity
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 200
    And the response should identify user "alice@example.com"
    And the response should contain global role "USER"

  Scenario: Reject identity request without authentication
    When the authenticated user identity is requested without authentication
    Then the response should have status 401

  Scenario: Reject identity request with an invalid token
    Given the user has an invalid authentication token
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Invalid token"

  Scenario: Reject identity request with an expired token
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user has an expired authentication token for "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Token expired"

  Scenario: Reject identity request for an inactive user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | inactive       |
    And the user is authenticated as "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "User not found or inactive"

  Scenario: Reject identity request with a token signed by another secret
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user has an authentication token signed with the wrong secret for "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Invalid token"

  Scenario: Reject identity request with a token without subject
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user has an authentication token without subject for "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Invalid token"

  Scenario: Reject identity request with a token for an unknown user
    Given the user has an authentication token for an unknown user
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "User not found or inactive"

  Scenario: Reject identity request with an unexpected token type
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user has a "refresh" token for "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Invalid token"
