# 06 · CI/CD, Parallelization & Diagnostics

> How this framework runs in automation — and the reasoning behind each choice.
> The guidance is split into what the repo **ships today** (a working GitHub
> Actions pipeline against the simulator) and what you **add for real hardware**.

---

## 1. Principles first

A test pipeline for a security-critical boot flow must be:

1. **Deterministic** — the same commit yields the same result. We get this for free
   because CI runs against the `SimulatedSystemBackend`, not a shared physical lab.
2. **Fast to fail** — unit tests (the engine) run first; they are milliseconds and
   catch planner/logic regressions before the slower Robot suites start.
3. **Diagnosable** — a red build must explain itself without a re-run: logs,
   `output.xml`, and a captured system snapshot per failure.
4. **Layered** — the same `make` targets developers use locally are what CI runs,
   so “works on my machine” and “works in CI” converge.

---

## 2. GitHub Actions (shipped)

The repository ships `.github/workflows/ci.yml`. Its shape and the *why*:

```text
on: [push, pull_request]          # run on every change and every PR
jobs:
  lint         → make install-dev && make lint        (fast static gate)
  unit         → make install    && make unit          (fast engine tests)
  robot        → make install     && make test-ci       (full Robot suite, ENV=ci)
```

Design decisions:

* **Separate `lint` / `unit` / `robot` jobs** rather than one script. *Why:* they
  run in parallel, fail independently, and the PR UI shows exactly *which* gate
  broke. *Disadvantage:* each job re-installs deps; we mitigate with pip caching
  (`actions/setup-python` `cache: pip`).
* **`ENV=ci`** selects `config/environments/ci.yaml` (zero artificial delays,
  CI-appropriate timeouts). *Why an env file and not inline flags:* the same
  mechanism developers use locally, one source of truth.
* **`--xunit xunit.xml`** (via `make test-ci`) emits JUnit-style XML so the GitHub
  UI and most dashboards render per-test results natively.
* **Always upload `results/`** (log.html, report.html, output.xml, diagnostics) as
  a build artifact — *even on success*, but especially on failure. *Why:* the first
  question on a red build is “what did the machine look like?”, and the answer is
  one artifact download away.
* **Secrets via repository/organization secrets**, injected as env vars and read by
  the `${env:NAME}` placeholders in config. *Why:* real PIN/password never live in
  the repo; the simulator uses fake values so most CI needs no secrets at all.

> Real-hardware runs would use a **self-hosted runner** physically attached to the
> encrypted laptop and card reader, selected with `runs-on: [self-hosted, bitlocker-lab]`
> and a `winappdriver` backend env. The *pipeline* barely changes — only the runner
> label and the environment file do. That is the ports-and-adapters payoff.

---

## 3. Azure DevOps (equivalent pipeline)

The same structure maps directly onto `azure-pipelines.yml`:

```yaml
trigger: [main]
pool: { vmImage: 'ubuntu-latest' }     # or a self-hosted pool for real hardware
steps:
  - task: UsePythonVersion@0
    inputs: { versionSpec: '3.12' }
  - script: make install-dev && make lint
    displayName: Lint
  - script: make unit
    displayName: Unit tests
  - script: make test-ci          # ENV=ci, emits xunit.xml
    displayName: Robot tests
    env: { ROBOT_ENVIRONMENT: ci }
  - task: PublishTestResults@2     # renders xUnit in the Tests tab
    condition: always()
    inputs: { testResultsFiles: 'results/xunit.xml', testResultsFormat: 'JUnit' }
  - task: PublishBuildArtifacts@1  # keep results/ (logs + diagnostics)
    condition: always()
    inputs: { pathToPublish: 'results', artifactName: 'robot-results' }
```

* **`condition: always()`** on the publish steps is the Azure equivalent of GitHub’s
  `if: always()` — *why:* you need results precisely when the test step failed.
* Using the **same `make` targets** keeps the two CI providers behaviorally
  identical; the YAML is just plumbing around the canonical commands.

---

## 4. Parallel execution (scaling to hundreds of suites)

Robot runs a single suite serially. For hundreds of suites, use **pabot**
(`robotframework-pabot`, in `requirements-dev.txt`):

```bash
pabot --processes 4 \
      --pythonpath libraries --pythonpath variables \
      --listener libraries/listeners/DiagnosticsListener.py \
      --outputdir results tests
```

**The non-obvious hazard — and how the architecture already solves it:** parallel
workers must **not** share one machine’s state. Here each pabot process gets its
**own** `SimulatedSystemBackend` instance (the `Context` singleton is per-process),
so workers are fully isolated by construction. On **real** hardware you cannot share
one laptop across workers — you would shard by **runner** (one physical machine per
worker) and let pabot parallelize across runners, not within one.

Guidance:

* **Parallelize at the suite level** (`--testlevelsplit` only if suites are huge).
  *Why:* suite setup (reaching a state) is the expensive part; splitting mid-suite
  re-pays that cost.
* **Right-size `--processes`** to the simulator (CPU-bound) or to the number of
  physical machines (hardware-bound) — not blindly to core count.
* **Merge results** automatically: pabot produces a combined `output.xml`; use
  `rebot` to re-merge or build historical trends.

---

## 5. Reporting

* **Native Robot reports** — `report.html` (dashboard) and `log.html` (step log)
  are the primary human artifacts; always published.
* **`output.xml`** is the source of truth — feed it to `rebot` for merged/historical
  reports, or to dashboards (Allure via `allure-robotframework`, ReportPortal, etc.)
  if you need cross-run trends at scale.
* **JUnit/xUnit XML** (`--xunit`) for the CI provider’s built-in test tab.
* **Tag-based slicing** (`type:`, `state:`, `layer:` — see
  `docs/02_NAMING_CONVENTIONS.md`) lets dashboards and CI stages group hundreds of
  tests meaningfully (e.g. a “smoke” gate on every PR, the full matrix nightly).

---

## 6. Logging

* **Robot’s own log** captures every keyword call/argument/return — usually enough
  to diagnose a failure step-by-step. Keep keywords small so the log reads well.
* **Python `logging`** inside libraries (the engine and `Context` already use it)
  surfaces in the Robot log and in CI stdout. *Why both:* library-level logs explain
  *decisions* (“Building 'simulated' backend”, “planned path: …”) that keyword logs
  don’t show.
* **Never log secrets.** The PIN/password are deliberately **not** exported as Robot
  variables and are never logged by the domain keywords (see `docs/01_ARCHITECTURE.md`
  §6). Treat this as a hard rule when adding real integrations — scrub tokens.
* **Log level:** run CI at the default `INFO`; drop to `--loglevel DEBUG:INFO` when
  chasing a flaky failure to get trace-level detail without changing code.

---

## 7. Screenshot & snapshot strategy

On a GUI SUT, a picture at the moment of failure is the fastest diagnosis. The
framework centralizes this as a **cross-cutting concern** in
`libraries/listeners/DiagnosticsListener.py` (Listener API v3) so **no test** has to
remember to do it:

* **When:** the listener fires on **every** failed keyword/test automatically — it
  cannot be forgotten and stays out of the test body.
* **What it captures today:** a snapshot of the simulated system state (current
  state + card/session details) written under `results/diagnostics/`. This is the
  simulator’s analogue of a screenshot.
* **What to capture on real hardware:** swap the snapshot for a real screen grab
  (e.g. the WinAppDriver/pywinauto screenshot API) and, where relevant, the Windows
  event log or a BitLocker status dump. The listener is the **one** place to add
  this — every suite inherits it instantly.
* **Why a listener, not a teardown keyword:** a teardown can be omitted or overridden
  per suite; a listener is global, observes lifecycle events keywords can’t, and is
  guarded so a diagnostics error never turns a green test red.

**Screenshot policy recommendation:** capture **on failure only** by default
(storage + speed), with an opt-in “screenshot every step” mode for hard flaky cases.
Name artifacts by `suite · test · timestamp` so they’re trivially correlated with
`log.html`.

---

## 8. Failure diagnostics — the triage order

When CI goes red, this is the fastest path to root cause (and what the pipeline is
built to support):

1. **CI test tab (xUnit)** → *which* test failed.
2. **`report.html`** → failure summary and tags (is it one area or systemic?).
3. **`log.html`** → the exact keyword and arguments that failed.
4. **`results/diagnostics/`** → *what state the machine was in* at that moment — the
   question that usually cracks a boot-flow failure.
5. **Library logs / Python stacktrace** (`robotframework-stacktrace` is pulled in by
   pabot) → the underlying exception if a backend command threw.

Because every one of these is produced automatically and published as an artifact,
a red build is almost always diagnosable **without a re-run** — which is the single
biggest time saver in a CI system for a slow, stateful SUT.
