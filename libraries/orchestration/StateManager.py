"""``StateManager`` — the Robot Framework facade over the state engine.

This is where the abstract engine meets the concrete business domain. It declares
the five business states (A-E) and the transitions between them, wiring each
transition to the real domain keywords. Tests then simply say:

    Ensure System State    DESKTOP_READY

...and the engine detects where the machine is and runs ONLY the missing steps.

WHY a Facade (design pattern, taught):
  * It gives tests ONE small, stable vocabulary ("ensure state X") instead of
    exposing the engine, the graph, and the domain libraries directly.
  * The messy wiring (which keyword, which cost, which detector) is hidden behind
    that simple surface, so the ~800 downstream tests are insulated from it.
  * Advantage: enormous reduction in coupling and duplication. Disadvantage: one
    more indirection to learn; mitigated by this documentation. Alternative: let
    each test import and drive the engine itself — rejected because it would leak
    orchestration details into hundreds of files.
"""

from __future__ import annotations

from robot.api import logger
from robot.api.deco import keyword, library

from core.context import Context
from core.state_machine import StateMachine
from core.state_model import StateDefinition, SystemState, Transition
from domain.BitLockerLibrary import BitLockerLibrary
from domain.DesktopStateLibrary import DesktopStateLibrary
from domain.MachineControlLibrary import MachineControlLibrary
from domain.SmartCardLibrary import SmartCardLibrary
from domain.WindowsLoginLibrary import WindowsLoginLibrary

# Relative transition costs. Named constants (not magic numbers) so the routing
# policy is readable and tunable in ONE place. Rebooting is modeled as far more
# expensive than any in-session step, so the planner avoids it when a cheaper
# route (e.g. signing out) exists.
_COST_POWER_CYCLE = 10.0   # power on / off: slow, disruptive
_COST_BITLOCKER = 3.0      # smart-card + PIN handshake
_COST_WINDOWS_LOGIN = 2.0  # typing credentials
_COST_SIGN_OUT = 2.0       # tearing a session down
_COST_DESKTOP_WAIT = 1.0   # waiting out the shell load


@library(scope="GLOBAL", auto_keywords=False)
class StateManager:
    """Facade exposing state-aware navigation keywords to Robot Framework."""

    def __init__(self) -> None:
        self._context = Context.instance()

        # The orchestrator OWNS its own domain-library instances (constructor-style
        # composition). They are cheap and all share the one backend via Context,
        # so driving a transition here and asserting a keyword in a test act on the
        # exact same machine.
        self._power = MachineControlLibrary()
        self._smart_card = SmartCardLibrary()
        self._bitlocker = BitLockerLibrary()
        self._windows = WindowsLoginLibrary()
        self._desktop = DesktopStateLibrary()

        # Build the engine and wire the concrete graph onto it.
        self._machine = StateMachine()
        self._register_states()
        self._register_transitions()

    # -- Public keywords ------------------------------------------------------

    @keyword("Initialize Framework")
    def initialize_framework(self) -> str:
        """Eagerly initialize the framework context and return the environment.

        Call this from the root suite's ``Suite Setup``. It is idempotent: because
        the environment is fixed via ``ROBOT_ENVIRONMENT`` before any import, this
        simply confirms (and logs) the already-active context rather than
        rebuilding it, so the wired backend is never swapped out mid-run.
        """
        context = Context.initialize()
        environment = context.configuration.environment
        logger.info(f"Framework initialized for environment '{environment}'.")
        return environment

    @keyword("Ensure System State")
    def ensure_system_state(self, target_state: str) -> list[str]:
        """Drive the machine to ``target_state``, running only missing transitions.

        This is THE keyword the reusable-precondition pattern is built on. It
        returns the list of transition names actually executed (empty if the
        machine was already in the target state), which the demonstration suites
        assert on to prove the "only the missing steps" behavior.

        ``target_state`` is a case-insensitive state name such as ``WINDOWS_LOGON``
        or ``DESKTOP_READY``.
        """
        target = SystemState.from_name(target_state)
        executed = self._machine.ensure_state(target, on_transition=self._log_transition)
        if executed:
            logger.info(
                f"Reached {target.name} via: " + ", ".join(step.name for step in executed)
            )
        else:
            logger.info(f"System already in {target.name}; no transitions were needed.")
        return [step.name for step in executed]

    @keyword("Get Current System State")
    def get_current_system_state(self) -> str:
        """Return the name of the state the machine is currently in."""
        return self._machine.detect_current_state().name

    @keyword("System State Should Be")
    def system_state_should_be(self, expected_state: str) -> None:
        """Fail unless the machine is currently in ``expected_state``."""
        expected = SystemState.from_name(expected_state)
        actual = self._machine.detect_current_state()
        if actual != expected:
            raise AssertionError(
                f"Expected system state {expected.name} but detected {actual.name}."
            )

    @keyword("List Known System States")
    def list_known_system_states(self) -> list[str]:
        """Return all modeled state names (handy for diagnostics and docs)."""
        return [state.name for state in self._machine.states]

    # -- Graph wiring (the single source of navigation truth) -----------------

    def _register_states(self) -> None:
        """Declare each business state and how to DETECT it from the backend.

        Detection priority is ascending: the most specific / most advanced screen
        is probed first so that, on real hardware, a fully loaded desktop is never
        misread as a weaker intermediate state.
        """
        backend = self._context.get_backend()
        self._machine.register_state(StateDefinition(
            SystemState.DESKTOP_READY, backend.is_desktop_ready, detection_priority=0,
        ))
        self._machine.register_state(StateDefinition(
            SystemState.USER_LOGGED_IN,
            # Logged in but the desktop has not finished loading yet.
            lambda: backend.is_user_logged_in() and not backend.is_desktop_ready(),
            detection_priority=1,
        ))
        self._machine.register_state(StateDefinition(
            SystemState.WINDOWS_LOGON, backend.is_windows_logon_visible, detection_priority=2,
        ))
        self._machine.register_state(StateDefinition(
            SystemState.BITLOCKER_PREBOOT,
            backend.is_bitlocker_preboot_visible, detection_priority=3,
        ))
        self._machine.register_state(StateDefinition(
            SystemState.POWERED_OFF,
            lambda: not backend.is_powered_on(), detection_priority=4,
        ))

    def _register_transitions(self) -> None:
        """Declare every legal edge of the graph exactly once.

        This method is the ONE place navigation lives. Add a screen to the login
        flow and you add a state + a transition here; nothing in the 800 tests
        changes. That is the whole payoff of the state-machine approach.
        """
        edges = [
            # Forward path: off -> pre-boot -> logon -> logged-in -> desktop.
            Transition(SystemState.POWERED_OFF, SystemState.BITLOCKER_PREBOOT,
                       self._power.power_on_machine,
                       name="Power On Machine", cost=_COST_POWER_CYCLE),
            Transition(SystemState.BITLOCKER_PREBOOT, SystemState.WINDOWS_LOGON,
                       self._authenticate_bitlocker,
                       name="Authenticate BitLocker With Smart Card", cost=_COST_BITLOCKER),
            Transition(SystemState.WINDOWS_LOGON, SystemState.USER_LOGGED_IN,
                       self._windows.log_in_to_windows,
                       name="Log In To Windows", cost=_COST_WINDOWS_LOGIN),
            Transition(SystemState.USER_LOGGED_IN, SystemState.DESKTOP_READY,
                       self._desktop.wait_until_desktop_is_ready,
                       name="Wait For Desktop", cost=_COST_DESKTOP_WAIT),

            # Backward edges — these make the graph a real graph, so the planner
            # has genuine choices and can prefer a cheap sign-out over a reboot.
            Transition(SystemState.DESKTOP_READY, SystemState.WINDOWS_LOGON,
                       self._windows.sign_out_of_windows,
                       name="Sign Out Of Windows", cost=_COST_SIGN_OUT),
            Transition(SystemState.USER_LOGGED_IN, SystemState.WINDOWS_LOGON,
                       self._windows.sign_out_of_windows,
                       name="Sign Out Of Windows", cost=_COST_SIGN_OUT),

            # Universal reset edges: power off is valid from any powered-on state.
            Transition(SystemState.BITLOCKER_PREBOOT, SystemState.POWERED_OFF,
                       self._power.power_off_machine,
                       name="Power Off Machine", cost=_COST_DESKTOP_WAIT),
            Transition(SystemState.WINDOWS_LOGON, SystemState.POWERED_OFF,
                       self._power.power_off_machine,
                       name="Power Off Machine", cost=_COST_DESKTOP_WAIT),
            Transition(SystemState.USER_LOGGED_IN, SystemState.POWERED_OFF,
                       self._power.power_off_machine,
                       name="Power Off Machine", cost=_COST_DESKTOP_WAIT),
            Transition(SystemState.DESKTOP_READY, SystemState.POWERED_OFF,
                       self._power.power_off_machine,
                       name="Power Off Machine", cost=_COST_DESKTOP_WAIT),
        ]
        for edge in edges:
            self._machine.register_transition(edge)

    # -- Composite transition actions -----------------------------------------

    def _authenticate_bitlocker(self) -> None:
        """Ensure the AUTHORIZED card is engaged, then unlock BitLocker with the PIN.

        This is the happy-path transition, so it must be hermetic: it guarantees
        the *configured, authorized* card is the one used, regardless of any card a
        previous test may have left in the reader. Any unexpected card is removed
        first, then the authorized card is inserted and the PIN submitted. Card
        insertion does not change the public state (we stay on the pre-boot screen),
        so it is a sub-step of this single transition rather than an edge of its own.
        Both the card id and PIN default to configuration.

        (On real hardware "insert" maps to engaging the authorized virtual/physical
        card; the point is that this transition owns, in ONE place, everything it
        takes to pass BitLocker — so hundreds of tests never worry about it.)
        """
        if self._smart_card.is_smart_card_present():
            self._smart_card.remove_smart_card()
        self._smart_card.insert_smart_card()
        self._bitlocker.unlock_bitlocker_with_smart_card()

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _log_transition(transition: Transition) -> None:
        """Callback used by the engine to narrate each executed transition."""
        logger.info(f"Transition: {transition.describe()}")
