"""Fast, pure-Python unit tests for the state-machine engine.

These run with the standard library only (``python -m unittest``) and need NO
Robot Framework, NO configuration, and NO simulated machine. That is the whole
reason the engine was kept Robot-agnostic: its planning logic — the part most
likely to harbor subtle bugs — can be verified in milliseconds.

Run with:  make unit      (or: python -m unittest discover -s tests_python)
"""

from __future__ import annotations

import os
import sys
import unittest

# Make the custom libraries importable when this file is run directly, without
# relying on the Makefile to set PYTHONPATH. We add <repo>/libraries to the path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "libraries"))

from core.exceptions import (  # noqa: E402  (import after path setup)
    StateTransitionError,
    UnknownStateError,
    UnreachableStateError,
)
from core.state_machine import StateMachine  # noqa: E402
from core.state_model import StateDefinition, SystemState, Transition  # noqa: E402


class _FakeMachine:
    """A trivial stand-in SUT: it just remembers which state it is 'in'.

    Using a fake here (instead of the real simulated backend) keeps these tests
    focused purely on the GRAPH/PLANNING logic. Each transition action simply sets
    ``current`` and each detector compares against it.
    """

    def __init__(self, state: SystemState) -> None:
        self.current = state
        self.calls: list[str] = []

    def mover(self, target: SystemState, label: str):
        def _action() -> None:
            self.calls.append(label)
            self.current = target
        return _action


def _build_linear_machine(sut: _FakeMachine) -> StateMachine:
    """Build A->B->C->D->E forward edges plus a cheap E->C 'shortcut' edge.

    Forward edges cost 1 each. The shortcut lets us prove cost-aware routing:
    going E->C directly (cost 1) must beat any longer alternative.
    """
    machine = StateMachine()
    order = [
        SystemState.POWERED_OFF,
        SystemState.BITLOCKER_PREBOOT,
        SystemState.WINDOWS_LOGON,
        SystemState.USER_LOGGED_IN,
        SystemState.DESKTOP_READY,
    ]
    for priority, state in enumerate(order):
        # Detector: "am I this state?" — compare the fake SUT's current state.
        machine.register_state(StateDefinition(
            state, (lambda s=state: sut.current == s), detection_priority=priority,
        ))
    # Forward chain.
    for src, dst in zip(order, order[1:]):
        machine.register_transition(
            Transition(src, dst, sut.mover(dst, f"{src.name}->{dst.name}"),
                       name=f"{src.name}->{dst.name}", cost=1.0)
        )
    return machine, order


class StateMachinePlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sut = _FakeMachine(SystemState.POWERED_OFF)
        self.machine, self.order = _build_linear_machine(self.sut)

    def test_detects_current_state(self) -> None:
        self.assertEqual(self.machine.detect_current_state(), SystemState.POWERED_OFF)
        self.sut.current = SystemState.WINDOWS_LOGON
        self.assertEqual(self.machine.detect_current_state(), SystemState.WINDOWS_LOGON)

    def test_find_path_returns_forward_chain(self) -> None:
        path = self.machine.find_path(SystemState.POWERED_OFF, SystemState.DESKTOP_READY)
        self.assertEqual(
            [t.name for t in path],
            ["POWERED_OFF->BITLOCKER_PREBOOT", "BITLOCKER_PREBOOT->WINDOWS_LOGON",
             "WINDOWS_LOGON->USER_LOGGED_IN", "USER_LOGGED_IN->DESKTOP_READY"],
        )

    def test_same_source_and_target_is_empty_path(self) -> None:
        self.assertEqual(
            self.machine.find_path(SystemState.WINDOWS_LOGON, SystemState.WINDOWS_LOGON),
            [],
        )

    def test_ensure_state_executes_only_missing_transitions(self) -> None:
        # Start partway through, at the logon screen.
        self.sut.current = SystemState.WINDOWS_LOGON
        executed = self.machine.ensure_state(SystemState.DESKTOP_READY)
        self.assertEqual(
            [t.name for t in executed],
            ["WINDOWS_LOGON->USER_LOGGED_IN", "USER_LOGGED_IN->DESKTOP_READY"],
        )
        self.assertEqual(self.sut.current, SystemState.DESKTOP_READY)

    def test_ensure_state_is_idempotent_when_already_there(self) -> None:
        self.sut.current = SystemState.DESKTOP_READY
        executed = self.machine.ensure_state(SystemState.DESKTOP_READY)
        self.assertEqual(executed, [])
        self.assertEqual(self.sut.calls, [])  # no action ran at all

    def test_cost_aware_routing_prefers_the_cheaper_edge(self) -> None:
        # Add an expensive direct POWERED_OFF->DESKTOP_READY edge (cost 100). The
        # planner must still prefer the four cheap forward hops (total cost 4).
        self.machine.register_transition(Transition(
            SystemState.POWERED_OFF, SystemState.DESKTOP_READY,
            self.sut.mover(SystemState.DESKTOP_READY, "TELEPORT"),
            name="TELEPORT", cost=100.0,
        ))
        path = self.machine.find_path(SystemState.POWERED_OFF, SystemState.DESKTOP_READY)
        self.assertNotIn("TELEPORT", [t.name for t in path])
        self.assertEqual(len(path), 4)

        # Now make the direct edge cheap (cost 1): it must win over the 4-hop route.
        cheap = StateMachine()
        sut = _FakeMachine(SystemState.POWERED_OFF)
        cheap, _ = _build_linear_machine(sut)
        cheap.register_transition(Transition(
            SystemState.POWERED_OFF, SystemState.DESKTOP_READY,
            sut.mover(SystemState.DESKTOP_READY, "TELEPORT"), name="TELEPORT", cost=1.0,
        ))
        path = cheap.find_path(SystemState.POWERED_OFF, SystemState.DESKTOP_READY)
        self.assertEqual([t.name for t in path], ["TELEPORT"])

    def test_unreachable_target_raises(self) -> None:
        # Nothing points back to POWERED_OFF in the linear graph.
        with self.assertRaises(UnreachableStateError):
            self.machine.find_path(SystemState.DESKTOP_READY, SystemState.POWERED_OFF)

    def test_unknown_state_detection_raises(self) -> None:
        self.sut.current = SystemState.UNKNOWN  # no detector matches this
        with self.assertRaises(UnknownStateError):
            self.machine.detect_current_state()

    def test_transition_verification_catches_a_lying_action(self) -> None:
        # An action that fails to actually change the SUT must be caught by the
        # engine's post-transition verification rather than silently "succeeding".
        machine = StateMachine()
        sut = _FakeMachine(SystemState.POWERED_OFF)
        for priority, state in enumerate(
            [SystemState.POWERED_OFF, SystemState.BITLOCKER_PREBOOT]
        ):
            machine.register_state(StateDefinition(
                state, (lambda s=state: sut.current == s), detection_priority=priority,
            ))
        # This action does nothing — a buggy transition.
        machine.register_transition(Transition(
            SystemState.POWERED_OFF, SystemState.BITLOCKER_PREBOOT,
            lambda: None, name="broken",
        ))
        with self.assertRaises(StateTransitionError):
            machine.ensure_state(SystemState.BITLOCKER_PREBOOT)


class StateModelTests(unittest.TestCase):
    def test_state_from_name_is_case_insensitive(self) -> None:
        self.assertEqual(SystemState.from_name("desktop_ready"), SystemState.DESKTOP_READY)
        self.assertEqual(SystemState.from_name("  WINDOWS_LOGON "), SystemState.WINDOWS_LOGON)

    def test_state_from_invalid_name_raises_with_helpful_message(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            SystemState.from_name("on_the_moon")
        self.assertIn("Valid states are", str(ctx.exception))

    def test_self_loop_transition_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Transition(SystemState.WINDOWS_LOGON, SystemState.WINDOWS_LOGON,
                       lambda: None, name="loop")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
