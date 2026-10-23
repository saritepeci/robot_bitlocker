"""Robot Framework library for BitLocker pre-boot authentication.

Single Responsibility: the BitLocker pre-boot screen — detecting it and
unlocking it with the smart card + PIN. It assumes a card is already inserted
(that is ``SmartCardLibrary``'s job) and stops the moment BitLocker hands control
to the Windows boot manager (the logon screen is ``WindowsLoginLibrary``'s job).

This crisp boundary is deliberate: each library owns exactly one screen/concept,
so when the real pre-boot UI changes you touch exactly one file.
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from backends.system_backend import SystemBackend
from core.context import Context


@library(scope="GLOBAL", auto_keywords=False)
class BitLockerLibrary:
    """Keywords to detect and clear the BitLocker pre-boot gate."""

    def __init__(self) -> None:
        self._context = Context.instance()

    @property
    def _backend(self) -> SystemBackend:
        return self._context.get_backend()

    @keyword("BitLocker Preboot Should Be Visible")
    def bitlocker_preboot_should_be_visible(self) -> None:
        """Fail unless the BitLocker pre-boot authentication screen is showing."""
        if not self._backend.is_bitlocker_preboot_visible():
            raise AssertionError(
                "Expected the BitLocker pre-boot screen to be visible, but it was not."
            )

    @keyword("Is BitLocker Preboot Visible")
    def is_bitlocker_preboot_visible(self) -> bool:
        """Return whether the BitLocker pre-boot screen is currently visible."""
        return self._backend.is_bitlocker_preboot_visible()

    @keyword("Unlock BitLocker With Smart Card")
    def unlock_bitlocker_with_smart_card(self, pin: str | None = None) -> None:
        """Submit the smart-card PIN to unlock BitLocker pre-boot authentication.

        ``pin`` defaults to the configured PIN so the reusable happy-path
        transition stays free of hardcoded secrets. Supply an explicit (wrong)
        PIN from a test to exercise the lock-out / rejection behavior.

        Precondition: a smart card must already be inserted. On success the
        machine proceeds to the Windows logon screen.
        """
        # Use ``is None`` (not a truthiness test) so an explicitly supplied empty
        # PIN is treated as a real — invalid — value, not as "use the default".
        pin = pin if pin is not None else self._context.configuration.require(
            "credentials.smart_card.pin"
        )
        logger.info("Submitting smart-card PIN to unlock BitLocker.")
        # NOTE: we never log the PIN value itself — secrets must not leak into the
        # Robot log/report, which are frequently archived as CI artifacts.
        self._backend.submit_bitlocker_pin(pin)
