"""Unit tests for the in-memory simulated backend.

The simulator is the executable specification of the SUT contract, so we verify
both the happy path (the full authentication flow) and that it REJECTS illegal
commands for the current state — which is exactly the behavior real negative
tests rely upon.
"""

from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "libraries"))

from backends.simulated_backend import SimulatedSystemBackend  # noqa: E402
from core.exceptions import BackendError  # noqa: E402


def _make_backend() -> SimulatedSystemBackend:
    return SimulatedSystemBackend(
        valid_card_id="CARD-1",
        valid_pin="123456",
        valid_username="user",
        valid_password="pw",
        action_delay_seconds=0.0,
    )


class HappyPathTests(unittest.TestCase):
    def test_full_authentication_flow(self) -> None:
        b = _make_backend()
        self.assertFalse(b.is_powered_on())

        b.power_on()
        self.assertTrue(b.is_bitlocker_preboot_visible())

        b.insert_smart_card("CARD-1")
        b.submit_bitlocker_pin("123456")
        self.assertTrue(b.is_windows_logon_visible())

        b.submit_windows_credentials("user", "pw")
        self.assertTrue(b.is_user_logged_in())
        self.assertFalse(b.is_desktop_ready())

        b.wait_for_desktop(timeout_seconds=1)
        self.assertTrue(b.is_desktop_ready())

    def test_sign_out_returns_to_logon(self) -> None:
        b = _make_backend()
        b.power_on()
        b.insert_smart_card("CARD-1")
        b.submit_bitlocker_pin("123456")
        b.submit_windows_credentials("user", "pw")
        b.wait_for_desktop(timeout_seconds=1)
        b.sign_out()
        self.assertTrue(b.is_windows_logon_visible())


class IllegalCommandTests(unittest.TestCase):
    def test_cannot_submit_pin_while_powered_off(self) -> None:
        b = _make_backend()
        with self.assertRaises(BackendError):
            b.submit_bitlocker_pin("123456")

    def test_wrong_pin_keeps_machine_locked(self) -> None:
        b = _make_backend()
        b.power_on()
        b.insert_smart_card("CARD-1")
        with self.assertRaises(BackendError):
            b.submit_bitlocker_pin("000000")
        self.assertTrue(b.is_bitlocker_preboot_visible())  # unchanged

    def test_unauthorized_card_is_rejected(self) -> None:
        b = _make_backend()
        b.power_on()
        b.insert_smart_card("ROGUE")
        with self.assertRaises(BackendError):
            b.submit_bitlocker_pin("123456")

    def test_pin_without_card_is_rejected(self) -> None:
        b = _make_backend()
        b.power_on()
        with self.assertRaises(BackendError):
            b.submit_bitlocker_pin("123456")

    def test_invalid_windows_credentials_are_rejected(self) -> None:
        b = _make_backend()
        b.power_on()
        b.insert_smart_card("CARD-1")
        b.submit_bitlocker_pin("123456")
        with self.assertRaises(BackendError):
            b.submit_windows_credentials("user", "WRONG")
        self.assertTrue(b.is_windows_logon_visible())  # unchanged

    def test_double_insert_is_rejected(self) -> None:
        b = _make_backend()
        b.power_on()
        b.insert_smart_card("CARD-1")
        with self.assertRaises(BackendError):
            b.insert_smart_card("CARD-1")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
