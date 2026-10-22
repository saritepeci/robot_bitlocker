"""Robot Framework library for the Windows logon (sign-in) screen.

Single Responsibility: the Windows logon screen — detecting it, signing a user
in, and signing them back out. It begins where BitLocker ends (logon screen
visible) and ends the instant Windows accepts the credentials and starts the
session (desktop readiness is ``DesktopStateLibrary``'s concern).
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from backends.system_backend import SystemBackend
from core.context import Context


@library(scope="GLOBAL", auto_keywords=False)
class WindowsLoginLibrary:
    """Keywords to authenticate against the Windows logon screen."""

    def __init__(self) -> None:
        self._context = Context.instance()

    @property
    def _backend(self) -> SystemBackend:
        return self._context.get_backend()

    @keyword("Windows Logon Should Be Visible")
    def windows_logon_should_be_visible(self) -> None:
        """Fail unless the Windows logon screen is currently displayed."""
        if not self._backend.is_windows_logon_visible():
            raise AssertionError(
                "Expected the Windows logon screen to be visible, but it was not."
            )

    @keyword("Is Windows Logon Visible")
    def is_windows_logon_visible(self) -> bool:
        """Return whether the Windows logon screen is currently displayed."""
        return self._backend.is_windows_logon_visible()

    @keyword("Log In To Windows")
    def log_in_to_windows(
        self, username: str | None = None, password: str | None = None
    ) -> None:
        """Sign in at the Windows logon screen.

        ``username``/``password`` default to the configured test account so the
        reusable transition carries no hardcoded credentials. Provide explicit
        values from a test to drive negative sign-in scenarios.

        On success the session begins initializing; use ``DesktopStateLibrary`` to
        wait until the desktop is interactive.
        """
        configuration = self._context.configuration
        # ``is None`` (not truthiness): an explicitly empty username/password is a
        # real, invalid credential that must be sent to the SUT and rejected — it
        # must NOT silently fall back to the configured account.
        username = username if username is not None else configuration.require(
            "credentials.windows.username"
        )
        password = password if password is not None else configuration.require(
            "credentials.windows.password"
        )
        logger.info(f"Signing in to Windows as '{username}'.")
        # The password is intentionally never written to the log.
        self._backend.submit_windows_credentials(username, password)

    @keyword("Is User Logged In")
    def is_user_logged_in(self) -> bool:
        """Return whether a user session is active (logging in or desktop ready)."""
        return self._backend.is_user_logged_in()

    @keyword("Sign Out Of Windows")
    def sign_out_of_windows(self) -> None:
        """Sign the current user out, returning to the Windows logon screen."""
        logger.info("Signing out of Windows.")
        self._backend.sign_out()
