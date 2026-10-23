*** Settings ***
Documentation       Executable demonstration of the reusable state model.
...
...                 These tests are the "proof" that the framework drives the machine
...                 to a requested state while running ONLY the missing transitions.
...                 Each test declares its starting point via a `[Setup]` precondition
...                 (so it is independent of execution order) and then asserts exactly
...                 which transitions the engine chose. Read this suite alongside
...                 docs/03_STATE_MODEL.md.
Resource            ../../resources/common/settings.resource
Test Tags           smoke    state-model


*** Test Cases ***
Reaching The Windows Logon Screen From Power Off Runs Two Transitions
    [Documentation]    State A -> State C. From powered off, exactly two transitions
    ...                are required: power on, then BitLocker smart-card unlock.
    [Setup]    Given The Machine Is Powered Off
    ${executed}=    Ensure System State    ${STATE_WINDOWS_LOGON}
    Length Should Be    ${executed}    2
    Lists Should Be Equal    ${executed}
    ...    ${{ ["Power On Machine", "Authenticate BitLocker With Smart Card"] }}
    System Should Be In State    ${STATE_WINDOWS_LOGON}

Reaching The Desktop Runs The Full Transition Chain
    [Documentation]    State A -> State E. The engine walks the entire forward path:
    ...                power on, unlock, sign in, wait for desktop (four transitions).
    [Setup]    Given The Machine Is Powered Off
    ${executed}=    Ensure System State    ${STATE_DESKTOP_READY}
    Length Should Be    ${executed}    4
    System Should Be In State    ${STATE_DESKTOP_READY}

Only The Missing Transitions Run When Partway Through The Flow
    [Documentation]    State C -> State E. Starting already at the logon screen, the
    ...                engine must NOT repeat power-on/unlock; only sign-in and the
    ...                desktop wait remain.
    [Setup]    Given The Windows Logon Screen Is Visible
    ${executed}=    Ensure System State    ${STATE_DESKTOP_READY}
    Lists Should Be Equal    ${executed}
    ...    ${{ ["Log In To Windows", "Wait For Desktop"] }}
    System Should Be In State    ${STATE_DESKTOP_READY}

Requesting The Current State Runs No Transitions At All
    [Documentation]    Idempotency: if the machine is already in the target state,
    ...                `Ensure System State` is a no-op. This is what makes declaring
    ...                a precondition on every one of ~800 tests essentially free.
    [Setup]    Given The Desktop Is Ready
    ${executed}=    Ensure System State    ${STATE_DESKTOP_READY}
    Should Be Empty    ${executed}

The Planner Prefers A Cheap Sign Out Over An Expensive Reboot
    [Documentation]    State E -> State C. Two routes exist: sign out (cheap) or power
    ...                cycle (expensive). Cost-aware planning must pick the single
    ...                sign-out transition.
    [Setup]    Given The Desktop Is Ready
    ${executed}=    Ensure System State    ${STATE_WINDOWS_LOGON}
    Length Should Be    ${executed}    1
    List Should Contain Value    ${executed}    Sign Out Of Windows
    System Should Be In State    ${STATE_WINDOWS_LOGON}

The Model Exposes Exactly The Five Business States
    [Documentation]    Guards the state model against accidental additions/removals;
    ...                the five states map 1:1 onto States A-E in the documentation.
    @{states}=    List Known System States
    Length Should Be    ${states}    5
    List Should Contain Value    ${states}    POWERED_OFF
    List Should Contain Value    ${states}    DESKTOP_READY
