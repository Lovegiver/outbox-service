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

  Scenario: Login with valid credentials
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 200
    And the response should contain an access token
  
  #Scenario: Reject login with an invalid password
  #  Given the following users are registered:
  #    | email             | password          | global role | account status |
  #    | alice@example.com | ValidPassword123! | USER        | active         |
  #  When the user logs in with email "alice@example.com" and password "WrongPassword123!"
  #  Then the response should have status 401
  #  And the response error should contain "Invalid credentials"
  #
  #Scenario: Reject login for an unknown user
  #  Given no user is registered with email "unknown@example.com"
  #  When the user logs in with email "unknown@example.com" and password "ValidPassword123!"
  #  Then the response should have status 401
  #  And the response error should contain "Invalid credentials"
  #
  #Scenario: Retrieve the authenticated user identity
  #  Given the following users are registered:
  #    | email             | password          | global role | account status |
  #    | alice@example.com | ValidPassword123! | USER        | active         |
  #  And the user is authenticated as "alice@example.com"
  #  When the authenticated user identity is requested
  #  Then the response should have status 200
  #  And the response should identify user "alice@example.com"
  #  And the response should contain global role "USER"
  #
  #Scenario: Reject identity request without authentication
  #  When the authenticated user identity is requested without authentication
  #  Then the response should have status 403
  #
  #Scenario: Reject identity request with an invalid token
  #  Given the user has an invalid authentication token
  #  When the authenticated user identity is requested
  #  Then the response should have status 401
  #  And the response error should contain "Invalid token"
  #
  #Scenario: Reject identity request with an expired token
  #  Given the following users are registered:
  #    | email             | password          | global role | account status |
  #    | alice@example.com | ValidPassword123! | USER        | active         |
  #  And the user has an expired authentication token for "alice@example.com"
  #  When the authenticated user identity is requested
  #  Then the response should have status 401
  #  And the response error should contain "Token expired"
  #
  #Scenario: Reject identity request for an inactive user
  #  Given the following users are registered:
  #    | email             | password          | global role | account status |
  #    | alice@example.com | ValidPassword123! | USER        | inactive       |
  #  And the user is authenticated as "alice@example.com"
  #  When the authenticated user identity is requested
  #  Then the response should have status 401
  #  And the response error should contain "User not found or inactive"