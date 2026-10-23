# robot_bitlocker — a state-driven Robot Framework reference architecture

An **educational, production-grade** Robot Framework framework for testing a
**BitLocker + Smart Card protected Windows PC**, built around one idea:

> A test declares the **system state it needs** (e.g. “a ready desktop”) and the
> framework automatically runs **only the missing steps** to get there — so
> hundreds of tests share the long login flow **without duplicating a single
> navigation step**.

This repo is also a **teaching artifact**: it runs green out-of-the-box against an
in-memory simulator (no hardware needed), and every important design decision is
explained in `docs/` with *why / advantages / disadvantages / alternatives*.

---

## The problem it solves

The system under test only becomes reachable after a long, security-critical boot:

```
Power on → BitLocker pre-boot (smart card + PIN) → Windows logon → sign in → desktop → app
```

About **800 test cases** need a logged-in desktop before they can start. If each
re-implements that sequence you get 800 fragile copies. The **state machine** at
the core of this framework makes that initialization reusable, composable, and
defined **exactly once**.

---

## Quick start

```bash
pip install -r requirements.txt     # Robot Framework + PyYAML (that's it)

make test                           # run the whole Robot suite (simulated SUT)
make unit                           # run the fast Python engine unit tests
```

Expected: **16 Robot tests** and **30 Python unit tests** pass. No BitLocker
laptop, card reader, or Windows box required. Full onboarding:
[`docs/04_GETTING_STARTED.md`](docs/04_GETTING_STARTED.md).

---

## What a test looks like (the payoff)

```robot
*** Settings ***
Resource      ../../resources/common/settings.resource
Test Setup    Given The Desktop Is Ready          # ← the entire login flow, one line

*** Test Cases ***
User Can Open The Application
    Open Application
    Application Should Be Visible
```

No power-on, no PIN, no logon steps. If the machine is already at the desktop,
the setup runs **zero** transitions — so putting this precondition on all 800
tests is essentially free. That one line replacing a whole login script, times
hundreds of tests, is the whole point.

---

## Architecture at a glance

Strictly downward dependencies — each layer only knows the layers below it:

```
tests/ (.robot)                  WHAT we verify
   └─ resources/                 HOW we phrase it (facades, preconditions)
        └─ orchestration/        WHERE to go  (StateManager facade)
             └─ domain/          VOCABULARY   (SmartCard, BitLocker, WindowsLogin, …)
                  └─ core/       BRAIN        (pure-Python cost-aware state machine)
                       └─ backends/  PLUMBING (SystemBackend port + Simulated adapter)
```

The engine (`core/`) is **pure Python** with no Robot or hardware dependencies, so
it is fully unit-tested. The real machine is reached through one abstraction
(`backends/SystemBackend`), so the whole framework runs against a simulator today
and real hardware tomorrow with no changes above the backend layer. Deep dive:
[`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md).

### The reusable state model (States A–E)

| State | Name                | Meaning                           |
| ----- | ------------------- | --------------------------------- |
| A     | `POWERED_OFF`       | machine off                       |
| B     | `BITLOCKER_PREBOOT` | pre-boot auth screen visible      |
| C     | `WINDOWS_LOGON`     | Windows logon screen visible      |
| D     | `USER_LOGGED_IN`    | signed in, session initializing   |
| E     | `DESKTOP_READY`     | desktop fully loaded, interactive |

`Ensure System State` detects where the machine is, plans the cheapest route with
Dijkstra over a cost-weighted graph, and executes only the missing transitions —
preferring a cheap sign-out over an expensive reboot. Full explanation:
[`docs/03_STATE_MODEL.md`](docs/03_STATE_MODEL.md).

---

## Repository structure

```
robot_bitlocker/
├─ config/                      # Centralized, layered configuration
│  ├─ environments/             #   default.yaml + ci.yaml / local.yaml overrides
│  └─ README.md
├─ docs/                        # Teaching-mode documentation (start here)
│  ├─ 01_ARCHITECTURE.md        #   layers, patterns, decisions (why/pros/cons/alts)
│  ├─ 02_NAMING_CONVENTIONS.md  #   the naming contract
│  ├─ 03_STATE_MODEL.md         #   the state machine, in depth
│  ├─ 04_GETTING_STARTED.md     #   install & run
│  ├─ 05_WRITING_AND_EXTENDING_TESTS.md   # cookbook: add tests/states/backends
│  └─ 06_CICD.md                #   CI/CD, parallelization, diagnostics
├─ libraries/                   # Custom Python libraries (grouped by layer)
│  ├─ core/                     #   engine: state_machine, state_model, config, context
│  ├─ backends/                 #   SystemBackend port + SimulatedSystemBackend
│  ├─ domain/                   #   SmartCard / BitLocker / WindowsLogin / Desktop / Power
│  ├─ orchestration/            #   StateManager (the Facade that wires the A–E graph)
│  └─ listeners/                #   DiagnosticsListener (automatic failure snapshots)
├─ resources/                   # Robot resource layers (grouped by responsibility)
│  ├─ common/                   #   settings import hub + generic keywords
│  ├─ states/                   #   state facades (Given The Desktop Is Ready, …)
│  └─ workflows/                #   authentication actions + composable preconditions
├─ tests/                       # Example suites (grouped by feature)
│  ├─ smoke/                    #   proves the state model (asserts exact plans)
│  ├─ bitlocker/                #   pre-boot authentication
│  ├─ authentication/           #   data-driven Windows login
│  └─ application/              #   post-login application smoke
├─ tests_python/               # Unit tests for the pure-Python engine
├─ variables/                   # Dynamic variable file (environment.py)
├─ .github/workflows/ci.yml     # GitHub Actions pipeline (lint · unit · robot)
├─ Makefile                     # Canonical commands (make help)
├─ pyproject.toml               # Project metadata + Robocop configuration
├─ requirements.txt             # Runtime deps (robotframework, PyYAML)
└─ requirements-dev.txt         # Dev/CI deps (robocop, pabot)
```

---

## Common commands

```bash
make help            # list every target
make test ENV=ci     # run the suite against a named environment (default|ci|local)
make smoke           # run only the fast smoke tests (by tag)
make unit            # run the Python engine unit tests
make lint            # robocop check . (static analysis; enforced in CI)
make format          # robocop format . (optional autoformatter)
```

Environment-specific values (timeouts, credentials, backend type) come from
`config/environments/*.yaml`, selected by the `ROBOT_ENVIRONMENT` variable. Real
secrets are injected via `${env:NAME}` placeholders — never committed.

---

## Where the requested deliverables live

| # | Deliverable                        | Location                                             |
| - | ---------------------------------- | ---------------------------------------------------- |
| 1 | Complete repository tree           | this README + [`docs/01`](docs/01_ARCHITECTURE.md)   |
| 2 | Example Robot files                | `tests/**/*.robot`                                   |
| 3 | Example Resource files             | `resources/**/*.resource`                            |
| 4 | Example Python libraries           | `libraries/domain/*.py`, `libraries/core/*.py`       |
| 5 | Example State Manager              | `libraries/orchestration/StateManager.py`, `core/state_machine.py` |
| 6 | Reusable precondition example      | `resources/workflows/preconditions.resource`, `resources/states/system_states.resource` |
| 7 | Configuration handling             | `config/`, `libraries/core/configuration.py`, `variables/environment.py` |
| 8 | Example test suite                 | `tests/smoke/state_transitions.robot` (+ the rest)   |
| 9 | Naming conventions guide           | [`docs/02_NAMING_CONVENTIONS.md`](docs/02_NAMING_CONVENTIONS.md) |
| 10| Architectural explanation document | [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) + `docs/03`, `docs/05`, `docs/06` |

---

## Status & tooling

* **Robot Framework 7.5**, **Python 3.10+**, **PyYAML** — a deliberately tiny
  runtime footprint (real integrations live behind the backend port).
* **Robocop 9.x** (unified lint + format) keeps the `.robot` files clean; the repo
  passes `make lint` with zero issues.
* **pabot** is used for parallel execution at scale (see `docs/06_CICD.md`).
* Tests are green: **16 Robot tests + 30 Python unit tests**.

> New here? Read [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md), then
> [`docs/03_STATE_MODEL.md`](docs/03_STATE_MODEL.md), then try the 2-minute
> exercise in [`docs/04_GETTING_STARTED.md`](docs/04_GETTING_STARTED.md).
