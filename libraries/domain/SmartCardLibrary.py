"""Robot Framework library for the physical smart card / ID card.

Scope of this library (Single Responsibility): the *card and reader* only —
inserting, removing, and checking presence. It knows nothing about BitLocker,
Windows, or how a card fits into the wider login flow. That orchestration is the
state machine's job. Keeping this boundary crisp is why the same three keywords
serve hundreds of tests without change.

WHAT LIVES HERE vs. IN ROBOT (a recurring teaching theme):
  * Here, in Python: anything that *talks to the SUT* or needs real logic/loops/
    error handling. Card I/O is exactly that.
  * In Robot resources: the readable, business-level *composition* of these
    keywords. See resources/ for the facades that stitch them together.
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from backends.system_backend import SystemBackend
from core.context import Context


@library(scope="GLOBAL", auto_keywords=False)
class SmartCardLibrary:
    """Keywords to operate the smart card reader.

    ``auto_keywords=False`` means ONLY methods explicitly decorated with
    ``@keyword`` become Robot keywords. This is a deliberate best practice: it
    keeps helper methods private and makes the public keyword surface obvious and
    intentional rather than "every public method leaks as a keyword".
    """

    # GLOBAL scope: one instance for the whole run. Safe because all real state
    # lives in the shared backend behind the Context, not in this object.
    def __init__(self) -> None:
        # Resolve collaborators from the composition root. The library depends on
        # the SystemBackend *abstraction*, never on a concrete simulator/driver.
        self._context = Context.instance()

    @property
    def _backend(self) -> SystemBackend:
        # Looked up lazily on each use so a unit test that swaps the backend via
        # Context.set_backend is always honored.
        return self._context.get_backend()

    @keyword("Insert Smart Card")
    def insert_smart_card(self, card_id: str | None = None) -> None:
        """Insert a smart card into the reader.

        ``card_id`` defaults to the configured card (``credentials.smart_card.
        card_id``) so the happy path never hardcodes an identifier. Pass an
        explicit value to drive negative tests (e.g. an unauthorized card).
        """
        card_id = card_id if card_id is not None else self._context.configuration.require(
            "credentials.smart_card.card_id"
        )
        logger.info(f"Inserting smart card '{card_id}'.")
        self._backend.insert_smart_card(card_id)

    @keyword("Remove Smart Card")
    def remove_smart_card(self) -> None:
        """Remove the smart card from the reader (no-op if none is present)."""
        logger.info("Removing smart card.")
        self._backend.remove_smart_card()

    @keyword("Smart Card Should Be Present")
    def smart_card_should_be_present(self) -> None:
        """Fail unless a smart card is currently inserted."""
        if not self._backend.is_smart_card_present():
            raise AssertionError("Expected a smart card to be present, but none was.")

    @keyword("Smart Card Should Not Be Present")
    def smart_card_should_not_be_present(self) -> None:
        """Fail if a smart card is currently inserted."""
        if self._backend.is_smart_card_present():
            raise AssertionError("Expected no smart card, but one was present.")

    @keyword("Is Smart Card Present")
    def is_smart_card_present(self) -> bool:
        """Return ``True``/``False`` whether a card is inserted (for conditionals)."""
        return self._backend.is_smart_card_present()
