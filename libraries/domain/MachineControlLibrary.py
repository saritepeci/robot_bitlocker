"""Robot Framework library for machine power control.

Single Responsibility: the physical power state of the machine — on and off.
Powering a device on/off is a genuine SUT interaction (a relay, an IPMI/Redfish
call, a hypervisor API, or — here — the simulator), so it belongs in Python
behind the backend, not in a .robot file.

It is modeled as its own library (rather than folded into another) because
"turn the machine on" is conceptually independent of smart cards, BitLocker, or
Windows, and keeping it separate honors the Single Responsibility Principle.
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from backends.system_backend import SystemBackend
from core.context import Context


@library(scope="GLOBAL", auto_keywords=False)
class MachineControlLibrary:
    """Keywords to power the machine on and off."""

    def __init__(self) -> None:
        self._context = Context.instance()

    @property
    def _backend(self) -> SystemBackend:
        return self._context.get_backend()

    @keyword("Power On Machine")
    def power_on_machine(self) -> None:
        """Power the machine on; it boots to the BitLocker pre-boot screen."""
        logger.info("Powering the machine on.")
        self._backend.power_on()

    @keyword("Power Off Machine")
    def power_off_machine(self) -> None:
        """Force the machine off, returning it to the powered-off state."""
        logger.info("Powering the machine off.")
        self._backend.power_off()

    @keyword("Machine Should Be Powered Off")
    def machine_should_be_powered_off(self) -> None:
        """Fail unless the machine is currently powered off."""
        if self._backend.is_powered_on():
            raise AssertionError("Expected the machine to be powered off, but it was on.")

    @keyword("Is Machine Powered On")
    def is_machine_powered_on(self) -> bool:
        """Return whether the machine currently has power."""
        return self._backend.is_powered_on()
