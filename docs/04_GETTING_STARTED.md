# 04 · Getting Started

> A hands-on onboarding guide. By the end you will have the whole framework
> running green on your machine against the built-in simulator — no BitLocker
> laptop, smart-card reader, or Windows box required.

---

## 1. Prerequisites

| Tool            | Version      | Why                                            |
| --------------- | ------------ | ---------------------------------------------- |
| Python          | 3.10+        | the engine uses modern typing features         |
| pip             | recent       | dependency installation                        |
| GNU Make        | optional     | the canonical task runner (`make help`)        |
| Git             | any          | version control                                |

> **Windows users:** everything works without `make` — each target is just a
> plain command line you can copy from the `Makefile`. To get `make`, install it
> via `choco install make` or use WSL.

---

## 2. Install

```bash
# 1) (Recommended) create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2) Install the runtime dependencies (Robot Framework + PyYAML)
pip install -r requirements.txt
#    …or, to also get linting/formatting/parallel tools used by CI:
pip install -r requirements-dev.txt
```

With `make`:

```bash
make install        # runtime deps
make install-dev    # runtime + dev/CI deps
```

---

## 3. Run everything (the 30-second happy path)

```bash
make test           # run the whole Robot suite against the 'default' environment
make unit           # run the fast Python unit tests for the engine
```

You should see **16 Robot tests** and **30 Python unit tests** pass. That is the
entire framework exercising itself end-to-end against the simulated backend.

Prefer raw commands? This is exactly what `make test` runs:

```bash
robot \
  --pythonpath libraries \
  --pythonpath variables \
  --listener libraries/listeners/DiagnosticsListener.py \
  --outputdir results \
  tests
```

* `--pythonpath libraries variables` lets Robot import the custom libraries and
  the dynamic variable file (we run **in place**, we do not `pip install` the repo
  — see `pyproject.toml` for why).
* `--listener …DiagnosticsListener.py` wires in automatic failure diagnostics.
* `--outputdir results` keeps all generated reports in one (git-ignored) place.

---

## 4. Selecting an environment

The framework reads **all** environment-specific values (timeouts, credentials,
backend type) from `config/environments/*.yaml`, chosen by the `ROBOT_ENVIRONMENT`
OS variable. `default.yaml` is the base; the selected file is deep-merged on top.

```bash
make test ENV=ci         # uses config/environments/ci.yaml
make test ENV=local      # uses config/environments/local.yaml
ENV defaults to 'default'
```

Raw equivalent (the Makefile just exports the variable for you):

```bash
ROBOT_ENVIRONMENT=ci robot --pythonpath libraries --pythonpath variables \
  --listener libraries/listeners/DiagnosticsListener.py --outputdir results tests
```

* **Why an OS variable and not a `--variable` CLI flag?** The variable file and the
  Python `Context` must agree on the environment *before* Robot parses CLI
  variables. Reading one OS variable avoids that chicken-and-egg problem and means
  the same selection mechanism works for Robot, the unit tests, and any script.
* **Where do real secrets come from?** Never from the YAML (those are fake,
  simulation-only). Any value may be written as `${env:NAME}` and is resolved from
  the real OS environment at load time — which is how a CI secret store injects a
  real PIN/password without it ever touching the repo. See
  `docs/01_ARCHITECTURE.md` §6.

---

## 5. Running a subset (tags)

As the suite grows to hundreds of tests you will rarely run them all locally:

```bash
make smoke                                   # only the fast smoke tests
robot --include smoke --pythonpath libraries --pythonpath variables tests
robot --include state:desktop_ready ... tests    # only tests that need State E
robot --exclude slow ... tests                   # skip the slow ones
```

Tag conventions (`type:`, `state:`, `layer:`, …) are documented in
`docs/02_NAMING_CONVENTIONS.md` §8.

---

## 6. Reading the results

After any run, open the standard Robot reports (in `results/` by default):

| File                        | What it is                                         |
| --------------------------- | -------------------------------------------------- |
| `results/report.html`       | high-level pass/fail dashboard                     |
| `results/log.html`          | step-by-step execution log (start here on failure) |
| `results/output.xml`        | machine-readable results (CI, history, rebot)      |
| `results/diagnostics/`      | failure snapshots written by the listener          |

When a test fails, the `DiagnosticsListener` captures a snapshot of the simulated
system state into `results/diagnostics/` so you can see *what state the machine was
in* at the moment of failure — the first thing you want to know. On a real backend
this is where screenshots would land (see `docs/06_CICD.md`).

---

## 7. Linting & formatting

```bash
make lint           # robocop check .   — static analysis (enforced in CI)
make format         # robocop format .  — apply the autoformatter
```

* `make lint` is the quality gate CI runs; the repo is kept lint-clean.
* `make format` is an optional convenience that applies Robocop's canonical
  formatting. (This teaching repo favors some hand-crafted visual grouping, so CI
  does **not** fail on formatting — only on lint.)

> Robocop 6+ is a single tool: `robocop check` lints and `robocop format` formats.
> It replaced the older `robocop` + `robotidy` pair.

---

## 8. First change — a 2-minute exercise

Prove the architecture to yourself:

1. Open `tests/application/post_login_smoke.robot`.
2. Copy a test case and change its name.
3. Note its setup is a single line — `Test Setup    Given A Freshly Logged In Desktop Session`
   — with no login steps (that precondition resolves to State E with a clean
   session; see `resources/workflows/preconditions.resource`).
4. Run `make test`. Your new test reaches a logged-in desktop with **zero**
   duplicated navigation, because the state engine supplied the missing
   transitions for you.

That one line replacing a whole login script — multiplied by hundreds of tests —
is the entire point of the framework. Continue with `docs/05_WRITING_AND_EXTENDING_TESTS.md`
to add states, backends, and real suites.

---

## 9. Troubleshooting

| Symptom                                             | Likely cause / fix                                             |
| --------------------------------------------------- | -------------------------------------------------------------- |
| `ModuleNotFoundError` for a library/variable file   | you ran `robot` without `--pythonpath libraries --pythonpath variables` (use `make`) |
| `ConfigurationError: Unsupported backend type 'winappdriver'` | the selected env requests a real backend not shipped here; use `ENV=ci`/`default` (all shipped envs are `simulated`) or add the adapter (see §Backends in `docs/01_ARCHITECTURE.md`) |
| Secrets look empty in logs                          | intentional — PIN/password are never exported as variables     |
| `make: command not found` (Windows)                 | run the raw `robot`/`python` commands from the `Makefile`      |
