"""The application Context — a tiny dependency-injection root (composition root).

Every object the framework needs at runtime (the merged configuration and the
one shared :class:`SystemBackend`) is created and wired together HERE, in one
place. The rest of the codebase asks the context for collaborators instead of
constructing them itself. This is the "composition root" pattern.

WHY centralize construction?
  * One shared backend — the domain libraries, the detectors, and the state
    transitions must all talk to the *same* machine instance. A single context
    guarantees that; otherwise ``SmartCardLibrary`` and ``BitLockerLibrary`` might
    each hold a different simulated machine and the states would disagree.
  * One place to swap implementations — point the factory at a real backend and
    the entire suite retargets, no test edits.
  * Testability — unit tests call :meth:`reset` / :meth:`set_backend` to inject a
    fake, with no global state leaking between tests.

DESIGN TRADE-OFF (taught, not hidden):
  A process-wide singleton is a pragmatic choice for a Robot Framework library,
  because Robot itself instantiates libraries for us and there is no constructor
  we control to inject a context into. The downside of any singleton is hidden
  global state; we mitigate it with explicit :meth:`initialize`/:meth:`reset`
  entry points and by never mutating configuration after load. A "purer"
  alternative — constructor injection everywhere — is shown deeper in the stack
  (the ``StateMachine`` receives its collaborators as arguments). See
  docs/01_ARCHITECTURE.md -> "Dependency injection: service locator vs. ctor".
"""

from __future__ import annotations

import logging
import os

from backends.simulated_backend import SimulatedSystemBackend
from backends.system_backend import SystemBackend
from core.configuration import Configuration
from core.exceptions import ConfigurationError

_LOGGER = logging.getLogger(__name__)


class Context:
    """Process-wide holder of the configuration and the shared backend."""

    _instance: "Context | None" = None

    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration
        # The backend is built lazily on first use so that merely importing a
        # library (which Robot does eagerly) does not spin up a machine driver.
        self._backend: SystemBackend | None = None

    # -- Lifecycle ------------------------------------------------------------

    @classmethod
    def initialize(cls, environment: str | None = None) -> "Context":
        """Create (or re-create) the singleton for ``environment`` and return it.

        Called explicitly from the root suite's ``Suite Setup`` so the chosen
        environment is logged and deterministic. The environment name is resolved
        from the argument, else the ``ROBOT_ENVIRONMENT`` OS variable, else
        ``"default"``. Re-initializing with the SAME resolved environment is a
        cheap no-op that returns the existing instance — crucial so that an
        already-wired ``StateManager`` keeps pointing at the same live backend.
        Only a genuinely different environment rebuilds the context.
        """
        resolved = environment or os.environ.get("ROBOT_ENVIRONMENT") or "default"
        if cls._instance is not None and cls._instance._configuration.environment == resolved:
            return cls._instance

        configuration = Configuration.load(resolved)
        cls._instance = cls(configuration)
        # Publish the resolved environment so any lazily-created consumer agrees.
        os.environ["ROBOT_ENVIRONMENT"] = configuration.environment
        _LOGGER.info("Framework context initialized for environment '%s'.",
                     configuration.environment)
        return cls._instance

    @classmethod
    def instance(cls) -> "Context":
        """Return the singleton, lazily creating it with the default environment.

        Domain libraries use this when they need the backend but were not handed a
        context explicitly. The environment is taken from ``ROBOT_ENVIRONMENT`` (set
        by :meth:`initialize` or by the Robot variable file).
        """
        if cls._instance is None:
            cls._instance = cls.initialize()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Discard the singleton. Primarily for unit tests (clean slate)."""
        cls._instance = None

    # -- Accessors ------------------------------------------------------------

    @property
    def configuration(self) -> Configuration:
        return self._configuration

    def get_backend(self) -> SystemBackend:
        """Return the one shared backend, building it on first access."""
        if self._backend is None:
            self._backend = self._build_backend()
        return self._backend

    def set_backend(self, backend: SystemBackend) -> None:
        """Inject a backend explicitly (used by unit tests and real-HW wiring)."""
        self._backend = backend

    # -- Factory --------------------------------------------------------------

    def _build_backend(self) -> SystemBackend:
        """Instantiate the backend named by ``backend.type`` in configuration.

        This is the single switch point between simulation and real hardware. To
        add a real backend you implement :class:`SystemBackend` and extend the
        mapping below — nothing else in the framework changes.
        """
        backend_type = str(self._configuration.require("backend.type")).lower()
        _LOGGER.info("Building '%s' backend.", backend_type)

        if backend_type == "simulated":
            return SimulatedSystemBackend(
                valid_card_id=self._configuration.require("credentials.smart_card.card_id"),
                valid_pin=self._configuration.require("credentials.smart_card.pin"),
                valid_username=self._configuration.require("credentials.windows.username"),
                valid_password=self._configuration.require("credentials.windows.password"),
                action_delay_seconds=self._configuration.get(
                    "backend.simulated.action_delay_seconds", 0.0
                ),
                tpm_auto_unlock=self._configuration.get(
                    "backend.simulated.tpm_auto_unlock", False
                ),
            )

        # A real backend would be wired here, e.g.:
        #   if backend_type == "winappdriver":
        #       from backends.winappdriver_backend import WinAppDriverBackend
        #       return WinAppDriverBackend(self._configuration)
        raise ConfigurationError(
            f"Unsupported backend type '{backend_type}'. Supported: 'simulated'. "
            f"Add a new adapter under libraries/backends and register it in "
            f"Context._build_backend to support real hardware."
        )
