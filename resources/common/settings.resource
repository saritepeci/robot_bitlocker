*** Comments ***
# =============================================================================
# settings.resource — the single import hub for every test suite.
# =============================================================================
# A test suite imports ONLY this resource and instantly gets the whole framework:
# all domain libraries, the orchestration facade, configuration variables, and
# the higher-level resource layers. This is the DRY entry point — when the
# framework gains a new library, we add it here ONCE instead of editing hundreds
# of suites.
#
# IMPORT ORDER MATTERS:
#   The `Variables` import is listed FIRST so that `variables/environment.py`
#   runs before any library is imported. That file publishes ${VARIABLES} and
#   exports ROBOT_ENVIRONMENT, guaranteeing every library below initializes
#   against the correct environment. The environment name itself comes from the
#   ROBOT_ENVIRONMENT OS variable (default: "default"), set by the Makefile/CI.
# =============================================================================


*** Settings ***
Documentation       Central import hub: pulls in configuration, domain libraries,
...                 the state-management facade, and the reusable resource layers.
...                 Every suite should import this file and nothing lower-level.

# 1) Configuration variables (must load first — see note above).
Variables           environment.py    %{ROBOT_ENVIRONMENT=default}

# 2) Selected Robot standard libraries (BuiltIn/standard imports come first).
Library             Collections

# 3) The orchestration facade (state-aware navigation) and domain libraries.
Library             orchestration.StateManager
Library             domain.MachineControlLibrary
Library             domain.SmartCardLibrary
Library             domain.BitLockerLibrary
Library             domain.WindowsLoginLibrary
Library             domain.DesktopStateLibrary

# 4) Higher-level, human-readable resource layers built on the above.
Resource            common_keywords.resource
Resource            ../states/system_states.resource
Resource            ../workflows/authentication.resource
Resource            ../workflows/preconditions.resource
