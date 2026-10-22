# 02 · Naming Conventions

> Consistent names are the cheapest documentation you will ever write. On a repo
> that will grow to hundreds of suites and dozens of libraries, a predictable name
> lets any engineer *guess correctly* where something lives and what it does. This
> guide is the contract; every example below matches real files in this repo.

---

## 1. Guiding principles

1. **English only** — every file, folder, keyword, variable, comment, and doc.
2. **Reveal intent, not implementation** — `Ensure The Desktop Is Ready`, not
   `Click Login And Wait 30s`.
3. **One concept, one name** — pick *card* or *smart card* and never alternate.
4. **Name by layer** — the name should hint which layer owns it (see below).
5. **Searchability** — prefer unambiguous, greppable names over clever short ones.

---

## 2. Folders

| Folder               | Convention                        | Why                                          |
| -------------------- | --------------------------------- | -------------------------------------------- |
| `tests/`             | grouped by **feature/area**       | mirrors how humans reason about the product  |
| `resources/`         | grouped by **responsibility**     | `common` / `states` / `workflows` are roles  |
| `libraries/`         | grouped by **layer**              | `core` / `backends` / `domain` / … map to L0–L3 |
| `config/environments`| one file per environment          | environment == file is instantly findable    |
| `docs/`              | `NN_TOPIC.md`, zero-padded index  | numeric prefix gives a guaranteed read order |

Folder names are **lowercase, singular-where-natural** (`domain`, `backends`). We
use `snake_case` for multi-word folders if they ever appear.

---

## 3. Files

| Kind                   | Convention                  | Example                                   |
| ---------------------- | --------------------------- | ----------------------------------------- |
| Robot suite            | `snake_case.robot`          | `preboot_authentication.robot`            |
| Robot resource         | `snake_case.resource`       | `system_states.resource`                  |
| Robot init suite       | `__init__.robot`            | `tests/__init__.robot`                    |
| **Python library**     | **`PascalCase.py` + `Library` suffix** | `WindowsLoginLibrary.py`       |
| Python engine/support  | `snake_case.py`             | `state_machine.py`, `configuration.py`    |
| Python unit test       | `test_<unit>.py`            | `test_state_machine.py`                   |
| Config                 | `snake_case.yaml`           | `default.yaml`, `ci.yaml`                 |

> **Why two Python styles?** A class exposed to Robot as a *library* is named in
> `PascalCase` with a `Library` suffix so that, inside a `.robot` file, the import
> reads like a proper noun: `Library    WindowsLoginLibrary`. Internal engine
> modules are ordinary Python and follow PEP 8 `snake_case`. The suffix also makes
> “is this a Robot-facing library or an internal helper?” answerable at a glance.

---

## 4. Keywords (Robot)

* **Case:** `Title Case With Spaces` — e.g. `Ensure System State`.
* **Shape:** start with a **verb** for actions (`Insert Smart Card`,
  `Wait For Desktop`), or a BDD prefix for specifications.
* **BDD prefixes** for preconditions/assertions in resources:
  * `Given …` — establish a precondition (`Given The Desktop Is Ready`).
  * `When …` — perform the action under test.
  * `Then …` / `… Should Be …` — assert (`System State Should Be`).
* **Facades read as business language**, hiding mechanics:
  * ✅ `Given The Windows Logon Screen Is Visible`
  * ❌ `Boot And Wait For LogonUI.exe`

**Why BDD prefixes?** They make a test’s intent scannable and separate the three
phases (arrange/act/assert) without comments. A reader instantly knows
`Given The Desktop Is Ready` is setup, not the thing being verified.

---

## 5. Keywords (Python-exposed)

* Decorate explicitly: `@keyword("Insert Smart Card")` so the Robot name is
  **intentional**, not derived from a Python method name.
* Libraries use `@library(scope="GLOBAL", auto_keywords=False)` so **only**
  decorated methods become keywords — no accidental public helpers leaking into
  the keyword namespace.
* Python method names stay `snake_case` (`insert_smart_card`); the *keyword* name
  is the Title Case string in the decorator.

**Why `auto_keywords=False`?** It makes the public keyword surface an explicit,
reviewable decision. Helper methods can be plain Python without being exposed,
keeping each library’s Robot API small and deliberate.

---

## 6. Variables

| Scope / kind                 | Convention                 | Example                         |
| ---------------------------- | -------------------------- | ------------------------------- |
| Robot global (from var file) | `${UPPER_SNAKE_CASE}`      | `${STATE_DESKTOP_READY}`        |
| Robot local (in a keyword)   | `${lower_snake_case}`      | `${current_state}`              |
| Robot list/dict              | `@{...}` / `&{...}`        | `@{executed_transitions}`       |
| Python constant              | `UPPER_SNAKE_CASE`         | `DEFAULT_ENVIRONMENT`           |
| Python attribute/local       | `snake_case`               | `self._backend`, `target_state` |
| “Private” Python             | leading underscore         | `_build_backend`, `_SimState`   |

**Why distinguish global vs. local in Robot?** `${UPPER}` signals “this comes from
configuration / is shared and stable”; `${lower}` signals “temporary, lives inside
this keyword”. The casing alone tells a reader the variable’s lifetime and blast
radius.

**Secrets never become variables.** PIN/password are intentionally *not* exported
as `${...}` (see `variables/environment.py`) to keep them out of logs.

---

## 7. States & transitions

* **States** are an `enum` in `core/state_model.py`, `UPPER_SNAKE_CASE`, named for
  the **condition**, not the action: `WINDOWS_LOGON` (a place), not `DO_LOGIN`.
* **Transitions** are named for the **action** that performs them, in Title Case,
  because they surface in logs and in the “executed transitions” list a test can
  assert on: `Authenticate BitLocker`, `Sign Out`, `Wait For Desktop`.

**Why split the noun/verb like this?** A state answers “where am I?” and a
transition answers “what did we do?”. Keeping states as nouns and transitions as
verbs makes the planner’s output read like a sentence:
`POWERED_OFF → [Power On, Authenticate BitLocker] → WINDOWS_LOGON`.

---

## 8. Tags

Tags are how we slice hundreds of suites for CI, so they follow a **`key:value`**
convention plus a few bare flags:

| Tag pattern        | Meaning                              | Example                |
| ------------------ | ------------------------------------ | ---------------------- |
| `layer:<name>`     | which layer the suite exercises      | `layer:bitlocker`      |
| `state:<A-E>`      | the starting/target state involved   | `state:desktop_ready`  |
| `type:<kind>`      | test category                        | `type:smoke`           |
| `priority:<n>`     | execution priority                   | `priority:1`           |
| bare flags         | special handling                     | `negative`, `slow`     |

**Why `key:value` tags?** They let CI build precise selections
(`--include type:smoke AND state:desktop_ready`) as the suite count explodes,
without renaming files. A flat tag soup becomes unusable at hundreds of tests.

---

## 9. A quick “good vs. bad” gallery

| ❌ Avoid                               | ✅ Prefer                                   | Reason                         |
| ------------------------------------- | ------------------------------------------ | ------------------------------ |
| `test1.robot`                         | `preboot_authentication.robot`             | names describe content         |
| `utils.py`                            | `state_machine.py` / `SmartCardLibrary.py` | one clear responsibility       |
| `${x}` / `${tmp}`                     | `${current_state}`                         | intent-revealing               |
| `Do Login Stuff`                      | `Log In To Windows`                        | verb-first, specific           |
| `Given Login` (ambiguous)             | `Given The User Is Logged In`              | reads as a precondition        |
| hardcoded `30` sprinkled in keywords  | `${LOGON_TIMEOUT}` from config             | no magic numbers               |
| `pin = "123456"` in a test            | `config/environments/*.yaml` + `${env:}`   | no secrets/values in tests     |

---

## 10. Enforcement

These conventions are backed by tooling so they do not rot:

* **Robocop** / **Robotidy** (configured in `pyproject.toml`, run via
  `make lint` / `make format`) enforce Robot style and naming.
* **Code review** owns the semantic rules a linter can’t see (does the name reveal
  intent? is it on the right layer?).

A convention that isn’t checked is a convention that will drift — so prefer adding
a lint rule over adding a paragraph here.
