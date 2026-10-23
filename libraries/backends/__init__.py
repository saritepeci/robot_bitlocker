"""Backends — adapters to the real (or simulated) System-Under-Test.

The framework talks to the machine ONLY through the ``SystemBackend`` interface
(system_backend.py). This is the Dependency Inversion Principle in action: the
high-level domain libraries depend on an abstraction, not on a concrete driver.

    system_backend.py      Abstract interface (the "port").
    simulated_backend.py   In-memory simulator used for the reference demo & CI.

To target a real machine you add a new adapter here (e.g. ``winappdriver_backend.py``)
that implements the same interface. Nothing in the tests, keywords, domain
libraries, or state model has to change — that is the entire point of the port.
See docs/01_ARCHITECTURE.md -> "Backends & Dependency Inversion".
"""
