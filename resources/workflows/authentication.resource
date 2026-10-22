# =============================================================================
# authentication.resource — reusable, business-level authentication actions.
# =============================================================================
# These "facade" keywords bundle several low-level domain keywords into one
# readable business step (e.g. "insert the card AND submit the PIN"). They are the
# right tool when a test wants to DRIVE an authentication step explicitly — for
# example to verify the step's own behavior (wrong PIN, wrong password).
#
# HOW THIS DIFFERS FROM THE STATE FACADES (important design distinction):
#   * states/system_states.resource  -> "put the machine in state X" (a reusable
#     PRECONDITION; the engine figures out the steps). Use it to GET somewhere.
#   * authentication.resource (here)  -> "perform this specific auth action now"
#     (an explicit ACTION on known inputs). Use it to TEST the action itself.
#   Both reuse the same underlying domain keywords, so there is no duplicated
#   logic — only two intention-revealing entry points.
# =============================================================================

*** Settings ***
Documentation       Reusable, business-level authentication actions composed from
...                 the domain libraries. Use these to exercise an auth step
...                 directly; use the state facades to reach a precondition.
Library             domain.SmartCardLibrary
Library             domain.BitLockerLibrary
Library             domain.WindowsLoginLibrary
Library             domain.DesktopStateLibrary


*** Keywords ***
Insert Smart Card And Unlock BitLocker
    [Arguments]    ${pin}=${None}    ${card_id}=${None}
    [Documentation]    Insert the smart card (if not already inserted) and submit
    ...                the PIN to clear BitLocker pre-boot. With no arguments it
    ...                uses the configured card and PIN (the happy path); pass an
    ...                explicit ${pin}/${card_id} to drive negative scenarios.
    ${present}=    Is Smart Card Present
    IF    not ${present}
        Insert Smart Card    ${card_id}
    END
    Unlock BitLocker With Smart Card    ${pin}

Sign In To Windows And Wait For Desktop
    [Arguments]    ${username}=${None}    ${password}=${None}
    [Documentation]    Submit Windows credentials and block until the desktop is
    ...                interactive. Defaults to the configured test account.
    Log In To Windows    ${username}    ${password}
    Wait Until Desktop Is Ready
