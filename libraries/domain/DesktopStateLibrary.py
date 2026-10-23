"""Robot Framework library for post-login desktop readiness.

Single Responsibility: the moment *after* sign-in — waiting for the shell to
become interactive and asserting the desktop is ready. This is the last link in
the chain that turns a powered-off machine into a usable session, and it is the
precondition the vast majority of application tests actually depend on (State E).
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from backends.system_backend import SystemBackend
from core.context import Context


@library(scope="GLOBAL", auto_keywords=False)
class DesktopStateLibrary:
    """Keywords to wait for and assert the readiness of the Windows desktop."""

    def __init__(self) -> None:
        self._context = Context.instance()

    @property
    def _backend(self) -> SystemBackend:
        return self._context.get_backend()

    @keyword("Wait Until Desktop Is Ready")
    def wait_until_desktop_is_ready(self, timeout_seconds: float | None = None) -> None:
        """Block until the desktop/shell is interactive, or fail on timeout.

        ``timeout_seconds`` defaults to the centrally configured
        ``timeouts.desktop_ready_seconds`` — no test should invent its own magic
        number for "how long a desktop takes to load".
        """
        if timeout_seconds is None:
            timeout_seconds = self._context.configuration.get(
                "timeouts.desktop_ready_seconds", 90
            )
        logger.info(f"Waiting up to {timeout_seconds}s for the desktop to become ready.")
        self._backend.wait_for_desktop(float(timeout_seconds))

    @keyword("Desktop Should Be Ready")
    def desktop_should_be_ready(self) -> None:
        """Fail unless the desktop is fully loaded and interactive."""
        if not self._backend.is_desktop_ready():
            raise AssertionError("Expected the desktop to be ready, but it was not.")

    @keyword("Is Desktop Ready")
    def is_desktop_ready(self) -> bool:
        """Return whether the desktop is fully loaded and interactive."""
        return self._backend.is_desktop_ready()
