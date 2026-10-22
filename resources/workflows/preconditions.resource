# =============================================================================
# preconditions.resource — composable, named, higher-level preconditions.
# =============================================================================
# The state facades (Given The Desktop Is Ready, ...) are PRIMITIVES. Real suites
# often need a precondition that is "a state PLUS some extra context" — e.g. a
# logged-in desktop with a specific app open, or a *clean* pre-boot prompt with no
# card inserted. Those richer preconditions are composed here, by name, so that
# dozens of suites can share them without duplicating the setup recipe.
#
# This is the "composable preconditions" requirement made concrete: every keyword
# below builds on the layer beneath it (state facades + domain keywords), never by
# re-implementing navigation. Add a new named precondition here and the whole
# estate can reuse it immediately.
# =============================================================================

*** Settings ***
Documentation       Composable, named preconditions built on the state facades and
...                 domain keywords. Intended for use as `[Setup]` / `Suite Setup`.
Resource            ../states/system_states.resource
Library             domain.SmartCardLibrary


*** Keywords ***
Given A Clean BitLocker Preboot Prompt
    [Documentation]    A *fresh* State B: the machine shows the BitLocker pre-boot
    ...                screen with NO smart card inserted. We first ensure a power
    ...                cycle (via powered-off) so no stale session or card state
    ...                leaks in from a previous test, then remove any card.
    ...                Demonstrates "state + extra setup" composition.
    Given The Machine Is Powered Off
    Given The BitLocker Preboot Screen Is Visible
    Remove Smart Card

Given A Freshly Logged In Desktop Session
    [Documentation]    State E phrased for application suites. Most of the ~800
    ...                application tests will use THIS as their precondition, which
    ...                is exactly why it is named once, here, and reused everywhere.
    Given The Desktop Is Ready

Given The User Has Just Signed In
    [Documentation]    State D (session initializing) phrased for tests that care
    ...                about the brief post-credential, pre-desktop window.
    Given The User Is Logged In
