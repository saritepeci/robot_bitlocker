"""Framework-specific exception hierarchy.

WHY a dedicated hierarchy instead of raising bare ``RuntimeError`` everywhere?

  * Precision — callers (and your future self) can ``except`` exactly the failure
    they know how to handle, instead of catching everything.
  * Readable logs — the class name alone tells you *which layer* failed
    (configuration vs. state navigation vs. the SUT).
  * A single, documented contract — every error the framework raises on purpose
    derives from ``FrameworkError``, so it is trivial to distinguish an expected,
    well-described failure from an unexpected bug.

DESIGN NOTE (teaching): we deliberately keep this hierarchy *shallow*. Deep
exception trees look impressive but are rarely useful; most code only ever needs
to branch on the three or four categories below.
"""

from __future__ import annotations


class FrameworkError(Exception):
    """Base class for every error intentionally raised by this framework.

    Catch this when you want to treat *any* framework-originated failure
    uniformly (e.g. in a listener) while still letting genuine, unexpected
    Python bugs (``KeyError``, ``AttributeError`` ...) propagate untouched.
    """


class ConfigurationError(FrameworkError):
    """Raised when configuration is missing, malformed, or inconsistent.

    Examples: an unknown environment name, a YAML syntax error, or a required
    ``${env:...}`` override that was never provided.
    """


class BackendError(FrameworkError):
    """Raised when the System-Under-Test adapter cannot honor a request.

    Example: asking the simulator to unlock BitLocker while the machine is still
    powered off. Real backends map driver/automation failures onto this type so
    the upper layers never need to know which concrete driver is in use.
    """


class StateError(FrameworkError):
    """Base class for problems in the state-model layer."""


class UnknownStateError(StateError):
    """Raised when the system is in a state the model does not recognize.

    This usually means a detector is missing or the SUT reached an unexpected
    screen — a strong signal that the model needs a new state or transition.
    """


class UnreachableStateError(StateError):
    """Raised when no sequence of transitions leads to the requested state.

    This is a *modeling* error surfaced early and loudly: it means the state
    graph has no path from the current state to the target, so the engine
    refuses to guess rather than silently doing nothing.
    """


class StateTransitionError(StateError):
    """Raised when a transition runs but the system does not end up as expected.

    Example: we executed "submit Windows credentials" but the logon screen is
    still visible. Failing here (instead of blindly continuing) is what makes the
    reusable preconditions trustworthy for hundreds of downstream tests.
    """
