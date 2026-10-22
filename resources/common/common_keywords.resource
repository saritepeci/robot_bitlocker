# =============================================================================
# common_keywords.resource — small, generic, cross-cutting keywords.
# =============================================================================
# Keywords here are domain-light helpers reused everywhere (framework bootstrap,
# diagnostics logging). Business/navigation keywords do NOT belong here — those
# live in states/ and workflows/. Keeping this file generic prevents it from
# becoming a dumping ground (a common anti-pattern in large Robot projects).
# =============================================================================

*** Settings ***
Documentation       Generic, cross-cutting helper keywords (bootstrap, logging).
Library             orchestration.StateManager


*** Keywords ***
Initialize Test Framework
    [Documentation]    Root-suite bootstrap. Initializes the framework context and
    ...                records which environment the run targets. Idempotent, so it
    ...                is safe even though libraries self-initialize lazily.
    ...                Intended for use as a root `Suite Setup`.
    ${environment}=    Initialize Framework
    Log    Test framework ready. Environment='${environment}'.    level=INFO

Log Current System State
    [Documentation]    Logs the detected system state. A handy, side-effect-free
    ...                breadcrumb to drop into teardowns while debugging a suite.
    ${state}=    Get Current System State
    Log    Current system state is '${state}'.    level=INFO
