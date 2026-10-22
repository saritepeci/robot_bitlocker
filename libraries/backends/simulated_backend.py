"""In-memory implementation of :class:`SystemBackend` used for the demo and CI.

This simulator is the reference project's "machine". It models the real
authentication flow as a tiny internal state machine and validates every command
against the current state, exactly as a real device would reject, say, a PIN
entry while powered off.

WHY ship a simulator at all?
  * The framework (state engine, keywords, tests, CI) can be exercised end-to-end
    with zero hardware, so this repository stays a runnable teaching artifact.
  * It documents, in executable form, the exact contract a *real* backend must
    satisfy — a new ``WinAppDriverBackend`` just has to make these same queries
    and commands behave against a physical machine.

The simulator is the ONLY place that knows the "true" machine state. The domain
libraries and detectors learn about it solely through the boolean query methods,
mirroring how, on real hardware, you can only infer state by probing the UI.
"""

from __future__ import annotations

import enum
import time
from pathlib import Path

from backends.system_backend import SystemBackend
from core.exceptions import BackendError


class _SimState(enum.Enum):
    """The simulator's private notion of the machine's physical state.

    Deliberately NOT the public ``SystemState`` enum: the backend promises only
    the boolean queries of the port, not an enum, which keeps the port decoupled
    from the core model. The mapping to the public states is expressed purely
    through which queries return True.
    """

    OFF = enum.auto()
    PREBOOT = enum.auto()
    LOGON = enum.auto()
    LOGGING_IN = enum.auto()
    DESKTOP = enum.auto()


class SimulatedSystemBackend(SystemBackend):
    """A faithful, in-memory stand-in for the BitLocker/Windows machine.

    All "valid" credentials are injected via the constructor (Dependency
    Injection) — the simulator has no hardcoded secrets of its own; it simply
    compares what it is given against what the configuration supplied.
    """

    def __init__(
        self,
        *,
        valid_card_id: str,
        valid_pin: str,
        valid_username: str,
        valid_password: str,
        action_delay_seconds: float = 0.0,
        tpm_auto_unlock: bool = False,
    ) -> None:
        self._valid_card_id = valid_card_id
        self._valid_pin = valid_pin
        self._valid_username = valid_username
        self._valid_password = valid_password
        self._action_delay_seconds = max(0.0, float(action_delay_seconds))
        self._tpm_auto_unlock = bool(tpm_auto_unlock)

        # The "true" machine state and whether a card is inserted.
        self._state = _SimState.OFF
        self._card_id: str | None = None

    # -- Queries --------------------------------------------------------------
    # Each maps the internal state onto one public, observable fact. Note how a
    # "later" state does NOT report earlier screens as visible: the machine is in
    # exactly one place at a time, which keeps detection unambiguous.

    def is_powered_on(self) -> bool:
        return self._state is not _SimState.OFF

    def is_bitlocker_preboot_visible(self) -> bool:
        return self._state is _SimState.PREBOOT

    def is_windows_logon_visible(self) -> bool:
        return self._state is _SimState.LOGON

    def is_user_logged_in(self) -> bool:
        # Both the transient "logging in" and the fully loaded desktop count as
        # "logged in"; the desktop-ready probe below is the more specific one.
        return self._state in (_SimState.LOGGING_IN, _SimState.DESKTOP)

    def is_desktop_ready(self) -> bool:
        return self._state is _SimState.DESKTOP

    def is_smart_card_present(self) -> bool:
        return self._card_id is not None

    # -- Commands -------------------------------------------------------------

    def power_on(self) -> None:
        self._require_state(_SimState.OFF, action="power on")
        self._sleep()
        # A TPM-only machine would auto-unlock BitLocker and boot straight to the
        # logon screen; a smart-card-protected machine stops at pre-boot auth.
        self._state = _SimState.LOGON if self._tpm_auto_unlock else _SimState.PREBOOT

    def power_off(self) -> None:
        # Powering off is always valid — it is the universal "reset" edge.
        self._sleep()
        self._state = _SimState.OFF
        # A reboot does not physically eject the card, so card presence persists.

    def insert_smart_card(self, card_id: str) -> None:
        if self._card_id is not None:
            raise BackendError(
                f"A smart card ({self._card_id}) is already inserted; remove it first."
            )
        self._sleep()
        self._card_id = str(card_id)

    def remove_smart_card(self) -> None:
        self._sleep()
        self._card_id = None

    def submit_bitlocker_pin(self, pin: str) -> None:
        self._require_state(_SimState.PREBOOT, action="submit the BitLocker PIN")
        if self._card_id is None:
            raise BackendError("Cannot authenticate BitLocker: no smart card inserted.")
        if self._card_id != self._valid_card_id:
            raise BackendError(
                f"Smart card '{self._card_id}' is not authorized for this machine."
            )
        self._sleep()
        if str(pin) != self._valid_pin:
            # Wrong PIN leaves the machine on the pre-boot screen, exactly like
            # real hardware — so negative tests can assert the state is unchanged.
            raise BackendError("Incorrect smart-card PIN; BitLocker remains locked.")
        self._state = _SimState.LOGON

    def submit_windows_credentials(self, username: str, password: str) -> None:
        self._require_state(_SimState.LOGON, action="submit Windows credentials")
        self._sleep()
        if str(username) != self._valid_username or str(password) != self._valid_password:
            raise BackendError("Invalid Windows credentials; sign-in rejected.")
        self._state = _SimState.LOGGING_IN

    def wait_for_desktop(self, timeout_seconds: float) -> None:
        if self._state is _SimState.DESKTOP:
            return
        if self._state is not _SimState.LOGGING_IN:
            raise BackendError(
                "Cannot wait for the desktop: the user is not signing in "
                f"(current internal state: {self._state.name})."
            )
        # A real backend would poll the shell until it is responsive or the
        # timeout elapses; the simulator just honors the configured delay.
        self._sleep(min(self._action_delay_seconds, max(0.0, timeout_seconds)))
        self._state = _SimState.DESKTOP

    def sign_out(self) -> None:
        if self._state not in (_SimState.LOGGING_IN, _SimState.DESKTOP):
            raise BackendError("Cannot sign out: no interactive user session is active.")
        self._sleep()
        self._state = _SimState.LOGON

    # -- Diagnostics ----------------------------------------------------------

    def capture_diagnostics(self, destination_path: str) -> str:
        """Write a textual state snapshot (the simulator's "screenshot")."""
        path = Path(destination_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = (
            "=== Simulated System Diagnostics ===\n"
            f"internal_state : {self._state.name}\n"
            f"card_present   : {self._card_id is not None}\n"
            f"card_id        : {self._card_id or '(none)'}\n"
        )
        path.write_text(snapshot, encoding="utf-8")
        return str(path)

    # -- Internal helpers -----------------------------------------------------

    def _require_state(self, expected: _SimState, *, action: str) -> None:
        if self._state is not expected:
            raise BackendError(
                f"Cannot {action}: machine must be in {expected.name} but is in "
                f"{self._state.name}."
            )

    def _sleep(self, seconds: float | None = None) -> None:
        delay = self._action_delay_seconds if seconds is None else seconds
        if delay > 0:
            time.sleep(delay)
