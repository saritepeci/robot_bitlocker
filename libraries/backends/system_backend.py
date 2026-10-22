"""The ``SystemBackend`` port — the only contract the framework has with the SUT.

Everything above this line (domain libraries, state machine, tests) depends on
this *abstraction*; nothing depends on a concrete driver. That is the Dependency
Inversion Principle, and it is what makes the whole framework hardware-optional:

    domain libraries ---> SystemBackend (abstract) <--- SimulatedSystemBackend
                                                   <--- WinAppDriverBackend (future)

The interface is split into two kinds of methods, which is a useful discipline:

  * QUERIES ("is_*") — read-only probes. They must never change the SUT. The
    state detectors are built exclusively from these.
  * COMMANDS ("power_on", "submit_*", ...) — actions with side effects that move
    the machine between states. The transitions are built from these.

Keeping queries and commands apart (a nod to Command-Query Separation) makes the
state model predictable: detecting a state can never accidentally change it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SystemBackend(ABC):
    """Abstract adapter to a BitLocker + Smart Card protected Windows machine.

    Concrete subclasses translate these calls into real automation (UI drivers,
    power control, smart-card middleware) or, for the reference project, into an
    in-memory simulation. Methods raise :class:`core.exceptions.BackendError` when
    a command is invalid for the current machine state.
    """

    # -- Queries (read-only; safe to call at any time) ------------------------

    @abstractmethod
    def is_powered_on(self) -> bool:
        """True if the machine has power and has begun booting."""

    @abstractmethod
    def is_bitlocker_preboot_visible(self) -> bool:
        """True if the BitLocker pre-boot authentication screen is displayed."""

    @abstractmethod
    def is_windows_logon_visible(self) -> bool:
        """True if the Windows logon (sign-in) screen is displayed."""

    @abstractmethod
    def is_user_logged_in(self) -> bool:
        """True once credentials were accepted and the session is initializing."""

    @abstractmethod
    def is_desktop_ready(self) -> bool:
        """True once the desktop/shell has fully loaded and is interactive."""

    @abstractmethod
    def is_smart_card_present(self) -> bool:
        """True if a smart card is currently inserted in the reader."""

    # -- Commands (side effects; may raise BackendError) ----------------------

    @abstractmethod
    def power_on(self) -> None:
        """Power the machine on; it should boot to the BitLocker pre-boot screen."""

    @abstractmethod
    def power_off(self) -> None:
        """Force the machine off, returning it to the powered-off state."""

    @abstractmethod
    def insert_smart_card(self, card_id: str) -> None:
        """Insert the smart card identified by ``card_id`` into the reader."""

    @abstractmethod
    def remove_smart_card(self) -> None:
        """Remove the smart card from the reader."""

    @abstractmethod
    def submit_bitlocker_pin(self, pin: str) -> None:
        """Submit the smart-card PIN to unlock BitLocker pre-boot authentication.

        Requires a card to be present and the pre-boot screen to be visible. On
        success the machine advances to the Windows logon screen.
        """

    @abstractmethod
    def submit_windows_credentials(self, username: str, password: str) -> None:
        """Submit Windows sign-in credentials at the logon screen.

        On success the machine advances to the logged-in (session starting) state.
        """

    @abstractmethod
    def wait_for_desktop(self, timeout_seconds: float) -> None:
        """Block until the desktop is interactive, or raise on timeout."""

    @abstractmethod
    def sign_out(self) -> None:
        """Sign the user out, returning the machine to the Windows logon screen."""

    # -- Diagnostics ----------------------------------------------------------

    @abstractmethod
    def capture_diagnostics(self, destination_path: str) -> str:
        """Persist evidence (screenshot/state snapshot) and return the file path.

        Called by the DiagnosticsListener on failure. Real backends save a PNG;
        the simulator writes a textual snapshot. Returning the path lets the
        listener attach it to the Robot log.
        """
