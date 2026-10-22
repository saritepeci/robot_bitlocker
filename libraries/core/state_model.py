"""State model value objects — the vocabulary of the reusable state machine.

This module defines *what a state and a transition are*, independent of any
particular machine. The actual BitLocker/Windows graph is wired up later in
``StateManager.py`` using these building blocks. Separating the **vocabulary**
(here) from the **graph instance** (StateManager) means the same engine can model
any stateful System-Under-Test.

Mapping to the business requirement (states A–E):

    SystemState.POWERED_OFF         State A  Machine powered off
    SystemState.BITLOCKER_PREBOOT   State B  BitLocker pre-boot auth visible
    SystemState.WINDOWS_LOGON       State C  Windows logon screen visible
    SystemState.USER_LOGGED_IN      State D  User logged in (session starting)
    SystemState.DESKTOP_READY       State E  Desktop fully loaded
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class SystemState(Enum):
    """The discrete, mutually-exclusive states the machine can be observed in.

    WHY an ``Enum`` rather than plain strings?
      * Typos become impossible — ``SystemState.WINDOWS_LOGON`` either exists or
        your code fails to import; ``"windwos_logon"`` would fail silently.
      * The set of legal states is closed and self-documenting.
      * IDEs and refactoring tools understand it.

    The ``.value`` is a stable, human-friendly string used in logs, Robot
    variables, and configuration, so testers can refer to states by name.
    """

    POWERED_OFF = "POWERED_OFF"
    BITLOCKER_PREBOOT = "BITLOCKER_PREBOOT"
    WINDOWS_LOGON = "WINDOWS_LOGON"
    USER_LOGGED_IN = "USER_LOGGED_IN"
    DESKTOP_READY = "DESKTOP_READY"

    # A sentinel used when no detector matches. It is never a navigation target;
    # reaching it signals that the SUT is somewhere the model does not describe.
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_name(cls, name: str) -> "SystemState":
        """Resolve a state from a case-insensitive string (e.g. from Robot).

        Tests and resource files speak strings ("DESKTOP_READY"); the engine
        speaks enum members. This is the single, validated conversion point, so a
        bad state name fails fast with a helpful list of valid options.
        """
        normalized = str(name).strip().upper()
        try:
            return cls[normalized]
        except KeyError:
            valid = ", ".join(member.name for member in cls if member is not cls.UNKNOWN)
            raise ValueError(
                f"Unknown system state '{name}'. Valid states are: {valid}."
            ) from None


# A detector answers the question "is the machine currently in THIS state?".
# It is a zero-argument callable returning a bool. Modeling it as a plain
# callable (not a class) keeps the model lightweight and easy to unit test.
Detector = Callable[[], bool]

# An action performs the side effects that move the machine along one edge of the
# graph (e.g. power on, submit the PIN). It returns nothing; success is verified
# afterwards by re-detecting the state.
TransitionAction = Callable[[], None]


@dataclass(frozen=True)
class StateDefinition:
    """Associates a :class:`SystemState` with the detector that recognizes it.

    ``frozen=True`` makes the object immutable (hashable, safe to share) — a value
    object. The detector is supplied by the domain layer, so this core type stays
    ignorant of *how* a state is recognized (UI probe, API call, simulator query).
    """

    state: SystemState
    detector: Detector
    # Lower numbers are checked first. We probe the most "advanced" states before
    # earlier ones because, on a real machine, later screens are more specific and
    # avoid ambiguous matches (e.g. a loaded desktop also implies "logged in").
    detection_priority: int = 0


@dataclass(frozen=True)
class Transition:
    """A directed edge of the state graph: ``source`` --action--> ``target``.

    Attributes
    ----------
    source, target:
        The states this edge connects.
    action:
        The callable that actually performs the move (wired to a domain keyword).
    name:
        Human-readable label used in logs and in the executed-transition list that
        tests assert on (e.g. ``"Power On Machine"``).
    cost:
        Relative expense of taking this edge. The engine finds the *cheapest*
        path, not merely the shortest. Powering a machine off/on is expensive;
        clicking a button is cheap. Modeling cost lets the planner prefer, say,
        logging out over a full reboot when both reach the target.
    """

    source: SystemState
    target: SystemState
    action: TransitionAction = field(repr=False)
    name: str = ""
    cost: float = 1.0

    def __post_init__(self) -> None:
        # A self-loop is almost certainly a wiring mistake and would pollute the
        # planner, so we reject it early with a clear message.
        if self.source is self.target:
            raise ValueError(
                f"Transition '{self.name or self.source.name}' is a self-loop "
                f"({self.source.name} -> {self.target.name}); that is not allowed."
            )

    def describe(self) -> str:
        """Return a readable 'A -> B (label)' string for logs and assertions."""
        label = self.name or "unnamed"
        return f"{self.source.name} -> {self.target.name} ({label})"
