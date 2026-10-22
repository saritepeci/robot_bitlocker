*** Settings ***
Documentation       BitLocker pre-boot authentication (State B) behavior.
...
...                 Every test starts from a *clean* pre-boot prompt via a shared,
...                 composable precondition — no test repeats the power-on/navigation
...                 steps. The suite covers the happy path plus the two important
...                 negative paths (wrong PIN, unauthorized card), proving the
...                 machine stays locked on failure.
Resource            ../../resources/common/settings.resource
Test Setup          Given A Clean BitLocker Preboot Prompt
Test Tags           bitlocker    authentication


*** Test Cases ***
BitLocker Preboot Screen Is Shown With No Card Inserted
    [Documentation]    Sanity check of the precondition itself: State B is visible
    ...                and no smart card is present.
    BitLocker Preboot Should Be Visible
    Smart Card Should Not Be Present

Correct Smart Card And Pin Unlocks BitLocker
    [Documentation]    Happy path: inserting the configured card and submitting the
    ...                correct PIN advances the machine to the Windows logon screen.
    Insert Smart Card And Unlock BitLocker
    Windows Logon Should Be Visible

An Incorrect Pin Leaves BitLocker Locked
    [Documentation]    Negative path: a wrong PIN is rejected and the machine remains
    ...                on the pre-boot screen (it does NOT advance).
    Insert Smart Card
    Run Keyword And Expect Error    *Incorrect smart-card PIN*
    ...    Unlock BitLocker With Smart Card    999999
    BitLocker Preboot Should Be Visible

An Unauthorized Smart Card Is Rejected
    [Documentation]    Negative path: a card that is not provisioned for this machine
    ...                cannot unlock it, even before a PIN is considered.
    Insert Smart Card    UNAUTHORIZED-CARD-9999
    Run Keyword And Expect Error    *not authorized*
    ...    Unlock BitLocker With Smart Card
    BitLocker Preboot Should Be Visible
