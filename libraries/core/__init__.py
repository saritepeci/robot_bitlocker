"""Core framework engine (domain-agnostic).

This package contains the reusable machinery that knows *nothing* about
BitLocker, smart cards, or Windows:

    configuration.py   Layered, environment-aware configuration loader.
    context.py         Service container / dependency-injection root.
    exceptions.py      Framework-specific exception hierarchy.
    state_model.py     Value objects describing states and transitions.
    state_machine.py   Pure-Python state graph + shortest-path engine.

The Robot-facing orchestration facade that wires the BitLocker/Windows graph onto
this engine lives one layer up, in ``libraries/orchestration/StateManager.py``.

Keeping this layer free of domain knowledge is what lets the very same engine be
reused for a completely different System-Under-Test later (see
docs/01_ARCHITECTURE.md -> "Layered architecture").
"""
