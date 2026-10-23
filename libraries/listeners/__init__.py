"""Robot Framework listeners — cross-cutting execution concerns.

Listeners observe the test execution lifecycle without the tests knowing about
them. We use the Listener API v3 to centralize failure diagnostics (screenshots,
system-state snapshots, structured logs) so that NO test case has to remember to
capture evidence on failure. See docs/06_CICD.md -> "Failure diagnostics".
"""
