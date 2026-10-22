# =============================================================================
# system_states.resource — the human-readable facade over the state engine.
# =============================================================================
# These keywords are the vocabulary your test cases speak. Each one declares a
# TARGET STATE and lets the StateManager work out (and execute) only the missing
# transitions to get there. This is the mechanism that lets ~800 tests share the
# login flow without copy-pasting a single navigation step.
#
# WHY wrap `Ensure System State` in "Given ..." aliases?
#   * Readability — `Given The Desktop Is Ready` reads like a specification.
#   * A stable contract — if a state is ever renamed, we fix it here once; the
#     suites keep using the same business phrase.
#   * They map 1:1 onto the state model (States A-E), so the docs and the code
#     use identical language.
# =============================================================================

*** Settings ***
Documentation       Facade keywords for requesting system states (the reusable
...                 precondition primitives). Business suites should prefer these
...                 "Given ..." phrases over calling the engine keywords directly.
Library             orchestration.StateManager


*** Keywords ***
Ensure System Is In State
    [Arguments]    ${target_state}
    [Documentation]    Generic facade: drive the machine to ${target_state},
    ...                executing only the transitions that are missing. Returns the
    ...                list of executed transition names (empty if already there).
    ${executed}=    Ensure System State    ${target_state}
    RETURN    ${executed}

# --- State A ------------------------------------------------------------------
Given The Machine Is Powered Off
    [Documentation]    Precondition: the machine is in State A (powered off).
    Ensure System Is In State    ${STATE_POWERED_OFF}

# --- State B ------------------------------------------------------------------
Given The BitLocker Preboot Screen Is Visible
    [Documentation]    Precondition: the machine is in State B (BitLocker pre-boot
    ...                authentication screen visible).
    Ensure System Is In State    ${STATE_BITLOCKER_PREBOOT}

# --- State C ------------------------------------------------------------------
Given The Windows Logon Screen Is Visible
    [Documentation]    Precondition: the machine is in State C (Windows logon
    ...                screen visible).
    Ensure System Is In State    ${STATE_WINDOWS_LOGON}

# --- State D ------------------------------------------------------------------
Given The User Is Logged In
    [Documentation]    Precondition: the machine is in State D (user authenticated,
    ...                session initializing).
    Ensure System Is In State    ${STATE_USER_LOGGED_IN}

# --- State E ------------------------------------------------------------------
Given The Desktop Is Ready
    [Documentation]    Precondition: the machine is in State E (desktop fully
    ...                loaded and interactive). This is the precondition the
    ...                majority of application test suites depend on.
    Ensure System Is In State    ${STATE_DESKTOP_READY}

# --- Assertion helper ---------------------------------------------------------
System Should Be In State
    [Arguments]    ${expected_state}
    [Documentation]    Assert the machine is currently in ${expected_state}.
    System State Should Be    ${expected_state}
