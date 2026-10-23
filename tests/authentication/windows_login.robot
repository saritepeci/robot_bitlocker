*** Settings ***
Documentation       Windows logon (State C) — DATA-DRIVEN example.
...
...                 Demonstrates Robot's `Test Template`: every test case below is a
...                 single data row fed to the same template keyword, so adding a new
...                 credential scenario is a one-line change — not a new test body.
...                 `Test Setup` re-establishes State C before each row, so a
...                 successful sign-in in one row never contaminates the next.
Resource            ../../resources/common/settings.resource
Test Setup          Given The Windows Logon Screen Is Visible
Test Template       Verify Windows Login Outcome
Test Tags           authentication    windows-login    data-driven


*** Test Cases ***                  USERNAME                PASSWORD              EXPECTED
Configured Account Signs In         USE_CONFIGURED          USE_CONFIGURED        SUCCESS
Wrong Password Is Rejected          ${WINDOWS_USERNAME}     definitely-wrong      FAILURE
Unknown User Is Rejected            intruder                any-password          FAILURE
Empty Credentials Are Rejected      ${EMPTY}                ${EMPTY}              FAILURE


*** Keywords ***
Verify Windows Login Outcome
    [Documentation]    Template keyword shared by every data row.
    ...
    ...                The sentinel ``USE_CONFIGURED`` is translated to ${None} so the
    ...                domain keyword falls back to the configured secret — this is how
    ...                the happy-path row signs in WITHOUT the password ever appearing
    ...                in the test data or the log (see variables/environment.py).
    [Arguments]    ${username}    ${password}    ${expected_outcome}
    ${user}=    Set Variable If    '${username}' == 'USE_CONFIGURED'    ${None}    ${username}
    ${pass}=    Set Variable If    '${password}' == 'USE_CONFIGURED'    ${None}    ${password}
    IF    '${expected_outcome}' == 'SUCCESS'
        Log In To Windows    ${user}    ${pass}
        ${logged_in}=    Is User Logged In
        Should Be True    ${logged_in}    Expected the user to be logged in after valid credentials.
    ELSE
        Run Keyword And Expect Error    *    Log In To Windows    ${user}    ${pass}
        Windows Logon Should Be Visible
    END
