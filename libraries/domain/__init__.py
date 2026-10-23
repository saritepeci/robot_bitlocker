"""Domain libraries — the *vocabulary* of the System-Under-Test.

Each module here is a thin, single-responsibility Robot Framework library that
exposes business keywords for one slice of the authentication domain:

    SmartCardLibrary.py       Physical smart card (insert / remove / presence).
    BitLockerLibrary.py       BitLocker pre-boot unlock.
    WindowsLoginLibrary.py    Windows logon screen interaction.
    DesktopStateLibrary.py    Post-login desktop readiness & applications.
    MachineControlLibrary.py  Machine power control (on / off).

These libraries contain NO navigation logic ("how do I get from power-off to the
desktop?"). That orchestration lives in the state machine. Keeping the two apart
is the Separation of Concerns that lets ~800 tests reuse the same building blocks
(see docs/01_ARCHITECTURE.md -> "Why split domain libraries from the engine").
"""
