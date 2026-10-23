# 05 · Writing & Extending Tests

> A practical cookbook. Four recipes, ordered from the thing you will do daily
> (write an application test) to the thing you do rarely (add a real hardware
> backend). Each recipe says **which layer to touch** and, crucially, **which
> layers you must NOT touch** — staying inside the lines is what keeps the
> framework maintainable at hundreds of tests.

---

## Recipe 1 — Write a new application test (the 90% case)

**Goal:** verify something that requires a logged-in, ready desktop.

**Touch only:** a suite file under `tests/`.

```robot
*** Settings ***
Documentation       Verifies the corporate VPN client auto-connects after login.
Resource            ../../resources/common/settings.resource
Test Setup          Given The Desktop Is Ready          # ← the whole login flow, 1 line
Force Tags          layer:application    type:smoke

*** Test Cases ***
VPN Client Connects Automatically After Login
    [Documentation]    After reaching the desktop the VPN must be connected.
    VPN Status Should Be    connected
```

**Why this is all you write:**

* `Test Setup    Given The Desktop Is Ready` asks the **state engine** to reach
  State E. If the machine is already there (because a previous test left it there),
  **zero** transitions run — the precondition is effectively free.
* You never write power-on, card-insert, PIN, or logon steps. They live **once** in
  `StateManager` + `resources/`, and the engine supplies only the missing ones.

**Do NOT:**

* ❌ put navigation (`Power On Machine`, `Log In To Windows`) in the test — that is
  the 800-copies anti-pattern the framework exists to kill.
* ❌ hardcode a timeout or credential — pull it from config via an existing keyword.

**Choosing a starting state.** Use the facade that matches what your test needs
(each maps 1:1 to States A–E):

| Need the machine at…                | Use this `[Setup]`                                   |
| ----------------------------------- | ---------------------------------------------------- |
| powered off (State A)               | `Given The Machine Is Powered Off`                   |
| BitLocker pre-boot (State B)        | `Given The BitLocker Preboot Screen Is Visible`      |
| Windows logon (State C)             | `Given The Windows Logon Screen Is Visible`          |
| logged in, session starting (D)     | `Given The User Is Logged In`                         |
| desktop ready (State E)             | `Given The Desktop Is Ready`                          |

---

## Recipe 2 — Add a reusable precondition (a “state + context”)

Sometimes a suite needs *more* than a bare state — e.g. “a freshly logged-in
desktop with no leftover session”. That is a **composable precondition**: a state
facade plus a little extra setup.

**Touch only:** `resources/workflows/preconditions.resource`.

The repo already ships examples you can copy:

* `Given A Clean BitLocker Preboot Prompt` — State B **with** any leftover card
  removed (a deterministic negative-test starting point).
* `Given A Freshly Logged In Desktop Session` — State E reached via an explicit
  fresh sign-in (used by `tests/application/post_login_smoke.robot`).
* `Given The User Has Just Signed In` — State D, guaranteeing the session is new.

```robot
Given A Kiosk Desktop With The Browser Open
    [Documentation]    State E, plus the kiosk browser launched and focused.
    Given The Desktop Is Ready          # reuse the engine — do not re-implement login
    Launch Application    kiosk-browser
    Application Should Be Visible
```

**Why put it here and not in the test?** Because the *next* 30 kiosk tests will
want the same starting point. A named precondition is written once and reused,
exactly like the state facades — just at a higher level of context.

**Why build on `Given The Desktop Is Ready` rather than calling the engine
directly?** So there is still **one** definition of “how to reach the desktop”.
Your precondition adds context on top; it never duplicates navigation.

---

## Recipe 3 — Add a new state or transition (extend the model)

**When:** the login flow gains a screen (e.g. a BIOS menu, an MFA prompt, a
“press Ctrl-Alt-Del” gate).

**Touch only:** `libraries/core/state_model.py` (the enum) and
`libraries/orchestration/StateManager.py` (one detector + the edges).

**Steps:**

1. **Add the state** to the `SystemState` enum in `core/state_model.py`.
2. **Register a detector** in `StateManager._register_states` — a *read-only*
   backend query that answers “is the system in this state right now?”. Give it a
   detection priority (most specific states are checked first). It must not have
   side effects (Command–Query Separation).
3. **Register the transitions** in `StateManager._register_transitions` — the
   edge(s) in and out, each with an action and a `cost` (see the `_COST_*`
   constants). Cost encodes preference: cheap clicks beat expensive reboots.
4. Run `make unit` and `make test`. **No test changes are needed** — the planner
   automatically routes through the new state wherever it is on the cheapest path.

**Why is this the whole change?** Navigation lives in exactly one place. That “one
place to change the login flow” property is the entire return on the state-machine
design; if adding a screen forced edits across suites, the model would have failed.

**Trade-off to remember:** every state needs a *reliable* detector. A flaky
detector makes the planner misjudge “where am I?”. Invest in detection accuracy —
it is the foundation the whole engine stands on. See `docs/03_STATE_MODEL.md` §3.

---

## Recipe 4 — Target real hardware (add a backend adapter)

The whole framework talks to the machine through one abstraction,
`backends/system_backend.py::SystemBackend` (a **port**). The shipped
`SimulatedSystemBackend` is one **adapter**; a real Windows target is another.

**Touch only:** a new file under `libraries/backends/`, plus one line in
`libraries/core/context.py`.

**Steps:**

1. **Create** `libraries/backends/winappdriver_backend.py` with a class that
   subclasses `SystemBackend` and implements every abstract method — the `is_*`
   **queries** (read-only) and the **commands** (power, insert card, unlock, log
   in, sign out). This is where the real pywinauto / WinAppDriver / smart-card
   middleware calls go.
2. **Register** it in `Context._build_backend` by adding a branch for the new
   `backend.type` value (the method already shows the exact pattern in a comment).
3. **Point an environment at it:** set `backend.type: winappdriver` in a new
   `config/environments/<env>.yaml`, and supply real secrets via `${env:NAME}`.
4. Run the **same** suites with `ENV=<env>`. Nothing above L0 changes — the
   domain libraries, engine, resources, and all tests are reused verbatim.

**Why ports & adapters (Dependency Inversion)?** The SUT is the least stable, least
available dependency. Inverting it lets the entire repo run green in CI today
against the simulator and against a real laptop tomorrow, with no rewrite. The
`SystemBackend` contract is the single thing both adapters must honor — keep the
simulator honest and it stays a faithful executable spec of that contract.

---

## Recipe 5 — Data-driven tests (many inputs, one behavior)

When the *same* behavior must be checked across many inputs (valid/invalid PINs,
locked/expired accounts), use Robot’s `Test Template` instead of copy-pasting
tests. See `tests/authentication/windows_login.robot` for the shipped example.

```robot
*** Settings ***
Test Template       Verify Windows Login Outcome

*** Test Cases ***        USERNAME          PASSWORD          EXPECTED
Valid Credentials         USE_CONFIGURED    USE_CONFIGURED    SUCCESS
Empty Password            test.user         ${EMPTY}          FAILURE
Wrong Password            test.user         wrong-password    FAILURE
```

**Why templates?** One behavior, defined once; each row is a named test. Adding a
case is a one-line edit, and the report shows each row as its own pass/fail.

**Why the `USE_CONFIGURED` sentinel?** The happy-path row must sign in without the
real password appearing in the test data or the log. The template keyword
translates `USE_CONFIGURED` to `${None}`, so the domain keyword falls back to the
configured secret internally. Never paste real secrets into a data table.

---

## The golden rule

> **If a change makes you edit more than one layer’s column in the “what to touch”
> tables above, stop.** The layers are probably leaking into each other, and the
> right fix is usually to move logic down (into a library) or behind a facade —
> not to spread it across files. See the cheat-sheet in `docs/01_ARCHITECTURE.md`.
