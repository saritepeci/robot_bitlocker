# 01 · Architecture — the reasoning behind every decision

> Read this document as if a senior test architect were sitting next to you
> explaining *why* the framework looks the way it does. For every important
> decision you will find **Why it exists**, **Advantages**, **Disadvantages**, and
> **Alternatives considered**. Nothing here is “because that’s how we’ve always
> done it”.

---

## 1. The problem we are actually solving

We must test an application that only becomes reachable **after** a long, security
heavy boot sequence:

```
Power on ─▶ BitLocker pre-boot (smart card + PIN) ─▶ Windows logon ─▶ sign in ─▶ desktop ─▶ app
```

Roughly **800 test cases** need the machine to be “at a logged-in, ready desktop”
before they can begin. If each test re-implements that navigation, we get:

* 800 copies of the same fragile sequence,
* 800 places to edit when the logon screen changes,
* wildly inconsistent waits, hardcoded PINs, and copy-paste bugs.

The entire architecture exists to make that initialization **reusable, composable,
and defined exactly once**. The centrepiece is a **state machine** that can take
the system from *wherever it is* to *whatever a test needs*, running only the
missing steps.

---

## 2. Layered architecture

We separate the system into layers with a strict, **one-directional** dependency
rule: a layer may only know about the layers **below** it. Nothing ever points
upward, which keeps the graph acyclic and every layer independently testable.

```
┌─────────────────────────────────────────────────────────────┐
│ L5  Test suites (tests/**.robot)                             │  WHAT we verify
│       e.g. tests/application/post_login_smoke.robot          │
├─────────────────────────────────────────────────────────────┤
│ L4  Robot resource layers (resources/)                       │  HOW we phrase it
│       settings · common · states · workflows · preconditions │
├─────────────────────────────────────────────────────────────┤
│ L3  Orchestration (libraries/orchestration/StateManager.py)  │  WHERE to go
│       the Facade that wires the concrete state graph         │
├─────────────────────────────────────────────────────────────┤
│ L2  Domain libraries (libraries/domain/*.py)                 │  the VOCABULARY
│       SmartCard · BitLocker · WindowsLogin · Desktop · Power  │
├─────────────────────────────────────────────────────────────┤
│ L1  Engine (libraries/core/state_machine.py, state_model.py) │  the BRAIN
│       pure-Python graph + cost-aware path planning           │
├─────────────────────────────────────────────────────────────┤
│ L0  Infrastructure                                           │  the PLUMBING
│       core/configuration · core/context · core/exceptions    │
│       backends/* (the SUT adapters)                          │
└─────────────────────────────────────────────────────────────┘
```

**Dependency flow (who imports whom):**

```
tests ─▶ resources ─▶ orchestration.StateManager ─▶ domain.*Library ─▶ backends.SystemBackend (abstract)
                                   │                        │
                                   ├─▶ core.state_machine ──┘ (engine is pure; knows no domain)
                                   └─▶ core.context ─▶ core.configuration
                                                     └─▶ backends.SimulatedSystemBackend (concrete)
```

* **Why layered?** Each concern changes for different reasons and at a different
  pace. The logon *screen* changes often (L2). The *planning algorithm* almost
  never changes (L1). Keeping them apart means a UI tweak never risks the engine.
* **Advantages:** testable in isolation (the engine has 0 Robot/HW dependencies),
  replaceable parts (swap the backend, keep everything else), clear ownership.
* **Disadvantages:** more files and indirection than a single mega-`.robot`; a
  newcomer must learn the map (this document is the map).
* **Alternatives considered:** *(a)* one big resource file with everything —
  rejected, it is exactly the 800-copies problem; *(b)* a two-layer “tests +
  keywords” split — better, but still mixes navigation logic into keywords and
  cannot reuse the engine for other systems.

---

## 3. The reusable state model (the heart)

### 3.1 States map 1:1 onto the business states A–E

| Model state (`SystemState`) | Business state | Meaning                              |
| --------------------------- | -------------- | ------------------------------------ |
| `POWERED_OFF`               | **A**          | Machine powered off                  |
| `BITLOCKER_PREBOOT`         | **B**          | BitLocker pre-boot auth visible      |
| `WINDOWS_LOGON`             | **C**          | Windows logon screen visible         |
| `USER_LOGGED_IN`            | **D**          | Signed in, session initializing      |
| `DESKTOP_READY`             | **E**          | Desktop fully loaded & interactive   |

### 3.2 How “only the missing transitions run”

A test never says *how* to get somewhere; it declares *where* it needs to be:

```robot
Given The Desktop Is Ready      # = Ensure System State    DESKTOP_READY
```

`StateManager.ensure_system_state` then:

1. **Detects** the current state by asking the backend’s read-only probes
   (`core/state_machine.py::detect_current_state`).
2. **Plans** the cheapest route to the target with Dijkstra over the transition
   graph (`find_path`).
3. **Executes** only that route, **verifying** the state after every hop.

If the machine is already at the target, the plan is empty and **nothing runs** —
which is what makes putting a precondition on all 800 tests essentially free.

> Worked example (verified by `tests/smoke/state_transitions.robot`):
> * From `POWERED_OFF`, request `WINDOWS_LOGON` ⇒
>   `[Power On Machine, Authenticate BitLocker With Smart Card]` (2 steps).
> * Then request `DESKTOP_READY` ⇒ `[Log In To Windows, Wait For Desktop]`
>   (only the 2 remaining steps).
> * Request `DESKTOP_READY` again ⇒ `[]` (already there).
> * From `DESKTOP_READY`, request `WINDOWS_LOGON` ⇒ `[Sign Out Of Windows]` — the
>   planner picks the cheap sign-out instead of a full power-cycle.

### 3.3 Why a graph + Dijkstra (not an `if/elif` ladder)?

* **Why:** states form a graph with cycles (you can sign out *or* reboot to leave
  the desktop). A shortest-/cheapest-path search expresses “get me there for the
  least disruption” declaratively; an `if/elif` ladder would hardcode every
  from→to pair (O(n²) brittle branches).
* **Advantages:** add a state/edge in **one** place and every route that could use
  it is reconsidered automatically; costs let us say “a reboot is 10× a click”.
* **Disadvantages:** a graph search is “cleverer” than a ladder, so it needs the
  unit tests and docs that accompany it here.
* **Alternatives considered:** *(a)* hardcoded per-pair setup keywords — does not
  scale; *(b)* a 3rd-party state-machine library (e.g. `transitions`) — fine, but
  a ~120-line, dependency-free engine we fully control is more educational and
  avoids coupling the teaching material to an external API.

See **`docs/03_STATE_MODEL.md`** for a deeper, diagram-driven treatment.

---

## 4. What stays in Robot vs. what moves to Python

This is one of the most common questions on real projects, so we are explicit.

| Put it in **Python** (a library) when…                | Put it in **Robot** (a resource) when…                 |
| ----------------------------------------------------- | ------------------------------------------------------ |
| it talks to the SUT (UI driver, power, smart card)    | it *composes* existing keywords into a readable flow   |
| it needs real logic: loops, graph search, retries     | it is a business-level precondition or assertion       |
| it needs structured error handling / typed exceptions | it is test data or a data-driven table                 |
| it benefits from fast, pure unit tests                | it is the human-facing “specification” of a test       |

**Why this split?** Robot Framework is superb at *readable orchestration* and
*reporting*, and poor at *algorithms*. Python is the reverse. We play to both
strengths: the **engine** and **SUT interaction** live in Python
(`libraries/`); the **vocabulary and composition** live in Robot (`resources/`,
`tests/`). Concretely:

* Navigation planning → **Python** (`core/state_machine.py`), because it is an
  algorithm that must be unit-tested.
* “Insert the card, then unlock” → **Robot** facade
  (`resources/workflows/authentication.resource`) *and* a Python transition —
  both call the same domain keywords, so there is no duplicated logic, only two
  intention-revealing entry points.
* “What counts as a valid PIN” → **neither**: it is **configuration**
  (`config/environments/*.yaml`), never hardcoded in code or tests.

---

## 5. Backends & the Dependency Inversion Principle

The framework talks to the machine through exactly one abstraction,
`backends/system_backend.py::SystemBackend`. High-level code depends on this
**port**, never on a concrete driver.

```
domain.*Library ─▶ SystemBackend (abstract)  ◀─ SimulatedSystemBackend   (shipped: demo + CI)
                                              ◀─ WinAppDriverBackend      (you add: real HW)
```

* **Why:** the System-Under-Test is the least stable, least available dependency
  (real encrypted laptops with card readers are scarce in CI). Inverting the
  dependency lets the *entire* framework run against an in-memory simulator today
  and a real machine tomorrow, with **zero** changes above L0.
* **Advantages:** the repo is a runnable teaching artifact; negative paths (wrong
  PIN, rogue card) are trivial to simulate; parallel CI needs no hardware.
* **Disadvantages:** the simulator is a *model*, not reality — it can drift from a
  real machine. We mitigate by treating `SystemBackend` as the single contract
  both must honor, and by keeping the simulator honest (it rejects illegal
  commands exactly as hardware would).
* **Alternatives considered:** *(a)* mock the UI driver inside each test —
  rejected, it leaks SUT details everywhere; *(b)* record/replay — powerful but
  heavy and opaque for a learning project.

**Command–Query Separation** is enforced on the port: `is_*` methods are
read-only *queries* (used to build detectors) and the rest are *commands* with
side effects (used to build transitions). Detecting a state can therefore never
accidentally change it.

---

## 6. Centralized configuration & secrets

All environment-specific values live in `config/environments/*.yaml` and are read
by `core/configuration.py`. A `default.yaml` base is **deep-merged** with an
environment override (`ci.yaml`, `local.yaml`), selected by the
`ROBOT_ENVIRONMENT` OS variable.

* **Why:** “no hardcoded values” is a hard requirement. One source of truth for
  timeouts/credentials/paths means a test can never invent a magic number, and an
  environment move is a one-line override, not a find-and-replace.
* **Secrets:** committed credentials are **fake, simulation-only**. Any value may
  be replaced at load time with `${env:NAME}`, resolved from the real OS
  environment (injected by the CI secret store). We additionally **do not export**
  the PIN/password as Robot variables (see `variables/environment.py`) so they
  cannot leak into `log.html`.
* **Advantages:** safe by default, trivial to retarget, diff-friendly YAML.
* **Disadvantages:** YAML has sharp edges and no built-in schema; we mitigate with
  typed `get`/`require` accessors and fail-fast errors.
* **Alternatives considered:** `.env` files (too flat for nested config), Python
  config modules (invite logic creep), a config service (overkill here).

---

## 7. Dependency injection: service locator vs. constructor injection

The framework deliberately shows **both** styles so you can see the trade-off.

* **Composition root** — `core/context.py::Context` builds the configuration and
  the one shared backend in a single place. Domain libraries fetch the backend
  from it (`Context.instance()`), a **service-locator**. *Why here?* Robot
  Framework instantiates libraries for us; we don’t control their constructors, so
  a locator is the pragmatic fit. *Downside (taught, not hidden):* it is global
  state; we contain it with explicit `initialize`/`reset` and immutable config.
* **Constructor injection** — the pure `StateMachine` receives its collaborators
  (states, transitions, detectors) as arguments; it reaches for **nothing**
  global. *Why here?* it is the part we unit-test most, and ctor injection makes
  that trivial (pass fakes). This is the “purer” style, used where we fully
  control construction.

**Takeaway:** choose the DI style that matches who controls construction. Prefer
constructor injection; fall back to a well-contained locator at framework
boundaries you don’t own (like Robot library instantiation).

---

## 8. Facade keywords

`StateManager` (Python) and the `resources/` layers are **Facades**: they offer a
tiny, stable surface (`Ensure System State`, `Given The Desktop Is Ready`) that
hides the engine, the graph wiring, and the domain libraries.

* **Why:** 800 tests must not depend on *how* navigation works, only on *what*
  they need. A facade is the seam that lets the internals change freely.
* **Advantages:** massive reduction in coupling; the business language
  (`Given The Desktop Is Ready`) reads like a specification and is refactor-safe.
* **Disadvantages:** one more indirection to learn (mitigated by these docs).
* **Alternatives considered:** let each test import and drive the engine — rejected
  because it re-couples hundreds of files to engine internals.

---

## 9. Cross-cutting concerns: the listener

Failure diagnostics are a **cross-cutting concern** — every test needs them, no
test should implement them. `libraries/listeners/DiagnosticsListener.py` (Listener
API v3) captures a system snapshot on every failure, automatically.

* **Why a listener and not a teardown keyword?** a listener cannot be forgotten,
  stays out of the test body, and can observe lifecycle events keywords can’t.
* **Disadvantages:** it runs “invisibly”; we keep it tiny and guard it so a
  diagnostic error can never fail a passing test.

---

## 10. Test isolation on a shared, stateful SUT (an honest hazard)

Because the machine is a single, stateful thing shared across tests, state
**leaks** between tests by nature (a card left inserted, a session left open).
Our answer is a principle, not a hack:

> **Every reusable precondition fully determines the state it promises.**

So the forward “Authenticate BitLocker” transition is *hermetic* — it guarantees
the authorized card is the one used, regardless of leftovers — and each suite
declares its starting state via a `[Setup]`. This makes tests order-independent
**and** fast (shared progress is reused, not rebuilt). The trade-off (shared
mutable state vs. a pristine machine per test) and how parallel workers get their
own simulator instance are covered in **`docs/06_CICD.md`**.

---

## 11. Where to make common changes (cheat-sheet)

| You want to…                                   | Touch only…                                                        |
| ---------------------------------------------- | ------------------------------------------------------------------ |
| Add a new screen/state to the login flow       | `core/state_model.py` (enum) + `StateManager` (one state + edge)   |
| Change how BitLocker is unlocked               | `domain/BitLockerLibrary.py` (and the backend)                     |
| Target a real machine instead of the simulator | add a `SystemBackend` adapter + register it in `Context`           |
| Change a timeout / credential / path           | `config/environments/*.yaml`                                       |
| Add a reusable precondition                     | `resources/workflows/preconditions.resource`                       |
| Add application tests                           | a new suite under `tests/`, using `Given The Desktop Is Ready`     |

If a change forces you to edit more than one of these columns at once, that is a
smell worth pausing on — the layers may be leaking into each other.
