"""Orchestration layer — composes the engine and the domain libraries.

This package sits ABOVE the domain libraries and the pure engine, and BELOW the
Robot resource files. Its single member, ``StateManager``, is the Facade that:

  * instantiates the domain-agnostic ``StateMachine`` engine, and
  * wires the concrete BitLocker/Windows states and transitions onto it using the
    domain libraries' keywords.

Dependency direction (strictly downward):

    resources (.robot)
        -> orchestration.StateManager        (this package)
            -> domain.*Library               (business keywords)
            -> core.state_machine            (planning engine)
                -> core.state_model          (value objects)
            -> core.context                  (shared backend + config)

Nothing below ever imports upward, which is what keeps the architecture acyclic
and each layer independently testable (see docs/01_ARCHITECTURE.md).
"""
