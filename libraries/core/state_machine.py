"""The state-machine engine: a pure-Python, Robot-agnostic graph planner.

This is the brain behind "a test asks for a target state and the framework
executes only the missing transitions". It has three jobs:

  1. Hold the registered states (with detectors) and transitions (edges).
  2. Detect the current state by consulting the detectors.
  3. Plan and execute the cheapest sequence of transitions from the current
     state to a requested target — running NOTHING if we are already there.

WHY keep this pure Python (no Robot imports)?
  * Testability — it is covered by fast unit tests (tests_python/) with zero
    Robot or hardware involved.
  * Reusability — the planner has no idea BitLocker exists; it would happily
    drive any other stateful system.
  * Single Responsibility — orchestration logic lives here and ONLY here, so the
    ~800 downstream tests never re-implement navigation.

ALGORITHM: we use Dijkstra's shortest-path over the transition graph, weighted by
each transition's ``cost``. When all costs are equal this degenerates to a
breadth-first search (fewest transitions). We chose cost-aware search because a
real machine has cheap edges (click a button) and very expensive ones (reboot),
and we want the planner to prefer the cheap route automatically.
"""

from __future__ import annotations

import heapq
import logging
from typing import Callable

from core.exceptions import (
    StateTransitionError,
    UnknownStateError,
    UnreachableStateError,
)
from core.state_model import StateDefinition, SystemState, Transition

_LOGGER = logging.getLogger(__name__)


class StateMachine:
    """A directed, weighted graph of :class:`SystemState` nodes and transitions.

    The object is built once (states + transitions registered) and then queried
    many times via :meth:`ensure_state`. It is intentionally decoupled from Robot
    Framework; the thin ``StateManager`` library adapts it into keywords.
    """

    def __init__(self) -> None:
        # state -> definition (detector + priority).
        self._definitions: dict[SystemState, StateDefinition] = {}
        # Adjacency list: source state -> list of outgoing transitions.
        self._edges: dict[SystemState, list[Transition]] = {}

    # -- Graph construction ---------------------------------------------------

    def register_state(self, definition: StateDefinition) -> None:
        """Register a state and how to detect it. Idempotent per state."""
        if definition.state in self._definitions:
            raise ValueError(f"State {definition.state.name} is already registered.")
        self._definitions[definition.state] = definition
        self._edges.setdefault(definition.state, [])

    def register_transition(self, transition: Transition) -> None:
        """Register one directed edge. Both endpoints must be known states.

        We validate endpoints eagerly so a wiring mistake fails at setup time
        (loud, with a clear message) rather than mid-test when a path is planned.
        """
        for endpoint in (transition.source, transition.target):
            if endpoint not in self._definitions:
                raise ValueError(
                    f"Cannot register transition '{transition.describe()}': "
                    f"state {endpoint.name} has not been registered."
                )
        self._edges[transition.source].append(transition)

    # -- Introspection --------------------------------------------------------

    @property
    def states(self) -> tuple[SystemState, ...]:
        """All registered states, in registration order."""
        return tuple(self._definitions)

    def detect_current_state(self) -> SystemState:
        """Return the state the system is currently in, using the detectors.

        Detectors are consulted in ascending ``detection_priority`` so that the
        most specific / most advanced screens are recognized first. The first
        detector that returns ``True`` wins.

        Raises :class:`UnknownStateError` if no detector matches — a deliberate,
        loud failure meaning the SUT is somewhere the model does not describe.
        """
        ordered = sorted(
            self._definitions.values(),
            key=lambda definition: definition.detection_priority,
        )
        for definition in ordered:
            try:
                matched = bool(definition.detector())
            except Exception as exc:  # noqa: BLE001 - detectors must never crash planning
                # A flaky probe should not take down the whole run as an
                # unhandled error; treat it as "not this state" but record why.
                _LOGGER.debug("Detector for %s raised %r; treating as no-match.",
                              definition.state.name, exc)
                matched = False
            if matched:
                _LOGGER.debug("Detected current state: %s", definition.state.name)
                return definition.state
        raise UnknownStateError(
            "No registered detector matched the current system state. The SUT is "
            "in an unmodeled state, or a detector is missing."
        )

    # -- Planning -------------------------------------------------------------

    def find_path(self, source: SystemState, target: SystemState) -> list[Transition]:
        """Return the cheapest list of transitions from ``source`` to ``target``.

        Returns an empty list when ``source == target`` (nothing to do — this is
        the idempotency that makes reusable preconditions cheap). Raises
        :class:`UnreachableStateError` when no path exists.

        Implementation: classic Dijkstra with a binary heap. ``best_cost`` tracks
        the cheapest known cost to reach each node; ``came_from`` records the edge
        we arrived by so we can reconstruct the path once the target is popped.
        """
        self._require_known(source)
        self._require_known(target)

        if source == target:
            return []

        best_cost: dict[SystemState, float] = {source: 0.0}
        came_from: dict[SystemState, Transition] = {}
        # The heap holds (cumulative_cost, tiebreaker, state). The monotonically
        # increasing tiebreaker keeps ordering deterministic and stops Python from
        # ever trying to compare two SystemState enum members.
        counter = 0
        frontier: list[tuple[float, int, SystemState]] = [(0.0, counter, source)]
        settled: set[SystemState] = set()

        while frontier:
            cost_so_far, _, current = heapq.heappop(frontier)
            if current in settled:
                continue
            settled.add(current)

            if current == target:
                return self._reconstruct(came_from, source, target)

            for edge in self._edges.get(current, []):
                neighbour = edge.target
                new_cost = cost_so_far + edge.cost
                if new_cost < best_cost.get(neighbour, float("inf")):
                    best_cost[neighbour] = new_cost
                    came_from[neighbour] = edge
                    counter += 1
                    heapq.heappush(frontier, (new_cost, counter, neighbour))

        raise UnreachableStateError(
            f"No transition path exists from {source.name} to {target.name}. "
            f"Check the transition graph wiring in StateManager."
        )

    # -- Orchestration --------------------------------------------------------

    def ensure_state(
        self,
        target: SystemState,
        current: SystemState | None = None,
        on_transition: Callable[[Transition], None] | None = None,
    ) -> list[Transition]:
        """Drive the system to ``target``, executing only the missing steps.

        This is the single method the whole framework is built around.

        Parameters
        ----------
        target:
            The desired state.
        current:
            Optionally the already-known current state (skips a detection probe).
            When ``None`` we detect it.
        on_transition:
            Optional callback invoked just before each transition runs — used by
            the Robot layer to log a nice "Executing: A -> B" line.

        Returns
        -------
        The list of transitions actually executed (empty if already at target),
        which tests assert on to prove the "only missing transitions" behavior.
        """
        self._require_known(target)
        current = current if current is not None else self.detect_current_state()

        if current == target:
            _LOGGER.info("System already in target state %s; no action taken.", target.name)
            return []

        plan = self.find_path(current, target)
        _LOGGER.info(
            "Planned %d transition(s) from %s to %s: %s",
            len(plan), current.name, target.name,
            " | ".join(step.describe() for step in plan),
        )

        executed: list[Transition] = []
        for step in plan:
            if on_transition is not None:
                on_transition(step)
            _LOGGER.info("Executing transition: %s", step.describe())
            step.action()
            executed.append(step)
            self._verify_reached(step)

        return executed

    # -- Internal helpers -----------------------------------------------------

    def _verify_reached(self, step: Transition) -> None:
        """Confirm the system actually reached ``step.target`` after the action.

        Verifying every hop (rather than trusting the action blindly) is what lets
        hundreds of tests rely on a precondition without re-checking it themselves.
        A mismatch raises :class:`StateTransitionError` with full context.
        """
        reached = self.detect_current_state()
        if reached != step.target:
            raise StateTransitionError(
                f"After executing '{step.describe()}' the system should be in "
                f"{step.target.name} but detection reported {reached.name}."
            )

    def _reconstruct(
        self,
        came_from: dict[SystemState, Transition],
        source: SystemState,
        target: SystemState,
    ) -> list[Transition]:
        """Walk ``came_from`` edges backwards from target to source, then reverse."""
        path: list[Transition] = []
        node = target
        while node != source:
            edge = came_from[node]
            path.append(edge)
            node = edge.source
        path.reverse()
        return path

    def _require_known(self, state: SystemState) -> None:
        if state not in self._definitions:
            known = ", ".join(member.name for member in self._definitions)
            raise UnknownStateError(
                f"State {state.name} is not registered. Known states: {known}."
            )
