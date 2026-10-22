"""``DiagnosticsListener`` — centralized failure diagnostics via Listener API v3.

A *listener* observes the test-execution lifecycle without any test or keyword
importing it. We use it to solve a cross-cutting concern ONCE: "whenever a test
fails, capture evidence (a screenshot / system-state snapshot) and attach it to
the Robot log." Without a listener, every one of the ~800 tests would need its
own teardown to do this — a textbook DRY violation.

WHY the Listener API (vs. a shared teardown keyword)?
  * It is impossible to forget: it fires for every test automatically.
  * It is non-invasive: tests stay focused on behavior, not on evidence capture.
  * It can react to events (start/end suite, end test) that keywords cannot see.

Trade-off (taught): listeners run "magically" in the background, which can
surprise newcomers. We keep this one small and well-documented, and we guard
every hook so a diagnostic failure can never fail an otherwise-passing test.

Registered via the command line, e.g.:
    robot --listener libraries/listeners/DiagnosticsListener.py tests
"""

from __future__ import annotations

import os
from datetime import datetime

from robot.api import logger


class DiagnosticsListener:
    """Capture system diagnostics on test failure and log run metadata."""

    # Listener API version 3 passes rich ``result``/``data`` model objects to the
    # hooks (v2 passed plain dicts). v3 is the modern, recommended choice.
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self) -> None:
        # The listener is imported very early by Robot — BEFORE the suite runs and
        # before the context is initialized by Suite Setup. We therefore resolve
        # everything we need LAZILY, inside the hooks, never in __init__.
        self._failures = 0

    # -- Lifecycle hooks ------------------------------------------------------

    def start_suite(self, data, result) -> None:  # noqa: ARG002 - RF passes both
        """Log which environment the top-level suite is running against."""
        # Only announce once, for the root suite (no parent), to avoid noise.
        if not getattr(data, "parent", None):
            environment = os.environ.get("ROBOT_ENVIRONMENT", "default")
            logger.info(f"[Diagnostics] Executing against environment '{environment}'.")

    def end_test(self, data, result) -> None:  # noqa: ARG002 - RF passes both
        """On failure, capture a diagnostics artifact from the backend."""
        if result.status != "FAIL":
            return
        self._failures += 1
        self._capture_for(result)

    def close(self) -> None:
        """Report a short summary once the whole run is over."""
        if self._failures:
            logger.info(f"[Diagnostics] Captured artifacts for {self._failures} failed test(s).")

    # -- Internals ------------------------------------------------------------

    def _capture_for(self, result) -> None:
        """Best-effort capture; a diagnostics error must never mask the real one."""
        try:
            # Imported lazily so merely loading the listener never drags in the
            # whole framework (keeps `--listener` cheap and import-order-safe).
            from core.context import Context

            context = Context.instance()
            artifacts_dir = context.configuration.get(
                "diagnostics.artifacts_dir", "results/diagnostics"
            )
            if not context.configuration.get("diagnostics.capture_on_failure", True):
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_name = "".join(c if c.isalnum() else "_" for c in result.name)[:80]
            destination = os.path.join(artifacts_dir, f"{safe_name}_{timestamp}.txt")

            saved_path = context.get_backend().capture_diagnostics(destination)
            # Surfacing the path in the log makes CI artifacts one click away.
            logger.info(f"[Diagnostics] Saved failure evidence to: {saved_path}")
        except Exception as exc:  # noqa: BLE001 - diagnostics must be non-fatal
            logger.warn(f"[Diagnostics] Could not capture diagnostics: {exc!r}")
