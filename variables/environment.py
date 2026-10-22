"""Robot Framework *variable file* — publishes configuration as ``${VARIABLES}``.

A variable file is Python that Robot imports to obtain variables. Using a dynamic
``get_variables(...)`` function (instead of a static ``.py`` with module globals)
lets us take the target environment as an ARGUMENT and compute the variables from
the very same :class:`Configuration` the Python libraries use. One source of
truth, zero drift between Robot ``${VARS}`` and Python config.

Imported from a resource/suite like::

    Variables    environment.py    ${ENVIRONMENT}

SECURITY NOTE (important, and a teaching point):
  We deliberately DO NOT publish the smart-card PIN or the Windows password as
  Robot variables. Robot variables are easy to accidentally ``Log`` and end up in
  log.html, which CI frequently archives. The domain keywords read those secrets
  straight from the configuration internally, so tests never need them as
  variables. Only non-sensitive conveniences (state names, timeouts, identifiers)
  are exposed here.
"""

from __future__ import annotations

import os
from typing import Any

from core.configuration import Configuration
from core.state_model import SystemState


def get_variables(environment: str | None = None) -> dict[str, Any]:
    """Return the dictionary of Robot variables for ``environment``.

    Robot calls this automatically, passing whatever argument the ``Variables``
    import supplies. We source it from the ``ROBOT_ENVIRONMENT`` OS variable with
    a ``default`` fallback (``%{ROBOT_ENVIRONMENT=default}`` in settings.resource),
    which avoids any chicken-and-egg ordering between CLI variables and this file.
    As a side effect we (re)export the resolved environment name to
    ``ROBOT_ENVIRONMENT`` so that the Python :class:`~core.context.Context`, if it
    is created lazily, agrees with Robot on which environment is active.
    """
    environment = environment or os.environ.get("ROBOT_ENVIRONMENT") or "default"
    configuration = Configuration.load(environment)
    os.environ["ROBOT_ENVIRONMENT"] = configuration.environment

    variables: dict[str, Any] = {
        # The active environment, handy for logging and conditional logic.
        "ENVIRONMENT": configuration.environment,

        # --- Centralized timeouts (no test should hardcode a number) ---------
        "DEFAULT_TIMEOUT": configuration.get("timeouts.default_seconds", 30),
        "BITLOCKER_UNLOCK_TIMEOUT": configuration.get("timeouts.bitlocker_unlock_seconds", 45),
        "WINDOWS_LOGIN_TIMEOUT": configuration.get("timeouts.windows_login_seconds", 60),
        "DESKTOP_READY_TIMEOUT": configuration.get("timeouts.desktop_ready_seconds", 90),

        # --- Non-sensitive identifiers ---------------------------------------
        "SMART_CARD_ID": configuration.get("credentials.smart_card.card_id", ""),
        "WINDOWS_USERNAME": configuration.get("credentials.windows.username", ""),
        # NOTE: SMART_CARD_PIN and WINDOWS_PASSWORD are intentionally NOT exported
        # (see the module docstring). Keywords read them from configuration.
    }

    # Export every state name as a variable, e.g. ${STATE_DESKTOP_READY} ==
    # "DESKTOP_READY". Deriving these from the SystemState enum means a new state
    # automatically becomes available to tests with zero duplication, and a typo
    # like ${STATE_DESKTP_READY} fails loudly as an undefined variable.
    for state in SystemState:
        if state is SystemState.UNKNOWN:
            continue
        variables[f"STATE_{state.name}"] = state.name

    return variables
