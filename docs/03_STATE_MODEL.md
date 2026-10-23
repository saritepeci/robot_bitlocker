# 03 · The State Model — a deep dive

> This is the single most important idea in the repository. If you understand this
> document, you understand *why* ~800 test cases can share one initialization flow
> without a single line of duplicated navigation.

---

## 1. States as a graph, not a script

A naïve framework writes the login flow as a linear script and calls it from every
test. The moment a test needs to start somewhere else (already logged in, or at
the logon screen), the script breaks down and people start copy-pasting variants.

We instead model the system as a **directed, weighted graph**:

* **Nodes = states** the system can be *in* (a condition you can observe).
* **Edges = transitions** — an action that moves the system from one state to
  another, with a **cost** reflecting how disruptive/slow it is.

```
                 Power On Machine (10)          Authenticate BitLocker (3)
   ┌───────────┐ ───────────────────▶ ┌─────────────────┐ ──────────────────▶ ┌───────────────┐
   │ POWERED_  │                      │ BITLOCKER_      │                     │ WINDOWS_      │
   │   OFF (A) │ ◀─── Power Off (1) ──│   PREBOOT (B)   │ ◀─── Power Off (1) ─│   LOGON (C)   │
   └───────────┘                      └─────────────────┘                     └───────┬───────┘
        ▲  ▲                                                                           │
        │  │                                                             Log In To     │  ▲
        │  │                                                             Windows (2)   ▼  │ Sign Out (2)
        │  │                                                                   ┌───────────────┐
        │  └────────────────────── Power Off (1) ───────────────────────────── │ USER_LOGGED_  │
        │                                                                      │   IN (D)      │
        │                                                                      └───────┬───────┘
        │                                                            Wait For Desktop (1) │ ▲
        │                                                                                 ▼ │ Sign Out (2)
        │                                                                         ┌───────────────┐
        └─────────────────────────── Power Off (1) ───────────────────────────── │ DESKTOP_      │
                                                                                  │   READY (E)   │
                                                                                  └───────────────┘
```

Numbers in parentheses are the transition **costs** (`StateManager._COST_*`):

| Transition                           | Cost | Rationale                              |
| ------------------------------------ | ---- | -------------------------------------- |
| `Power On Machine`                   | 10   | slowest, most disruptive              |
| `Authenticate BitLocker With Smart Card` | 3 | card + PIN handshake                  |
| `Log In To Windows`                  | 2    | typing credentials, profile load      |
| `Sign Out Of Windows`                | 2    | tearing a session down                 |
| `Wait For Desktop`                   | 1    | just waiting out the shell             |
| `Power Off Machine`                  | 1    | fast/cheap *as an edge* (see §6)       |

> These costs are **policy**, not physics. They encode “prefer a sign-out over a
> reboot”. Change the numbers and you change the planner’s preferences without
> touching any algorithm or test.

---

## 2. The public contract: `Ensure System State`

Everything a test needs is one keyword (surfaced through friendly `Given …`
facades):

```robot
${executed}=    Ensure System State    ${STATE_DESKTOP_READY}
```

It returns the **list of transitions actually executed**, which is what lets the
smoke suite *prove* the “only missing steps run” behavior. Internally
(`core/state_machine.py::ensure_state`) it does three things:

1. **Detect** the current state.
2. **Plan** the cheapest path current → target.
3. **Execute** each transition, **re-detecting** after every hop to verify the
   action actually achieved the state it claimed (fail fast otherwise).

---

## 3. Step 1 — detection (how the framework knows “where am I?”)

Each state registers a **detector**: a read-only predicate built from the
backend’s `is_*` queries (`StateManager._register_states`). Detectors are tried in
**priority order**, most-specific first:

| Priority | State             | Detector (read-only)                     |
| -------- | ----------------- | ---------------------------------------- |
| 0        | `DESKTOP_READY`   | `backend.is_desktop_ready`               |
| 1        | `USER_LOGGED_IN`  | `backend.is_user_logged_in`              |
| 2        | `WINDOWS_LOGON`   | `backend.is_windows_logon_visible`       |
| 3        | `BITLOCKER_PREBOOT` | `backend.is_bitlocker_preboot_visible` |
| 4        | `POWERED_OFF`     | `not backend.is_powered_on`              |

* **Why priority order?** Some conditions are supersets (a ready desktop is also
  “powered on”). Checking the most specific state first prevents a coarse detector
  from matching too early. The desktop must be tested before “powered on”.
* **Why read-only detectors?** Detection must never change the thing it observes
  (**Command–Query Separation**). If detecting `WINDOWS_LOGON` accidentally
  dismissed it, planning would be built on lies. The backend port enforces this by
  splitting `is_*` queries from mutating commands.
* **Unknown is a first-class answer.** If no detector matches, the state is
  `UNKNOWN`; the engine then refuses to guess and raises a typed error rather than
  blundering forward.

---

## 4. Step 2 — planning (Dijkstra, and why)

`find_path` runs **Dijkstra’s shortest-path** over the cost graph.

* **Why Dijkstra and not BFS?** BFS minimizes the *number* of hops; we want to
  minimize *total disruption*. With weights, “one expensive reboot” should lose to
  “two cheap clicks”. Dijkstra respects the costs; BFS would ignore them.
* **Why not A\*?** A\* needs a good heuristic and shines on huge graphs. Ours has a
  handful of nodes; the heuristic would be more code to get wrong for no measurable
  gain. Dijkstra is the right-sized tool.
* **Determinism:** the priority queue breaks ties with a monotonic counter
  (`(cost, counter, state)`), so equal-cost plans are stable run-to-run — important
  for tests that assert on the exact plan. (It also sidesteps comparing enum
  members, which aren’t ordered.)
* **No path?** If the target is unreachable from the current state, the engine
  raises `StateTransitionError` instead of looping forever.

---

## 5. Step 3 — execution with verification

For each planned edge the engine calls the transition’s action, then **re-detects**
and asserts the system is now in the expected state. If not, it raises immediately
with context (from/to/actual). This turns a silent “the click didn’t register”
into a precise, early failure — the opposite of a flaky test that limps on and
dies three keywords later.

---

## 6. Design choices, with trade-offs

### 6.1 Why model “Power Off” from *every* powered-on state?
It guarantees the graph is strongly connected enough that **any** target is
reachable from **any** state — the engine can always “reset and rebuild” as a last
resort. The edge cost is kept low *as a graph weight* so it stays available, but
the planner still prefers forward/sign-out edges when they reach the goal without a
reboot. *Alternative:* model only a single off→on path — simpler, but then
recovering from a weird state is impossible without manual steps.

### 6.2 Why re-detect after every transition instead of trusting the action?
Hardware/UI lie. A click can be swallowed; a boot can hang. Verifying each hop
localizes failures to the exact transition that broke. *Disadvantage:* extra
detection calls per hop. *Why it’s worth it:* on a 4-step login, knowing *which*
step failed is the difference between a 1-minute and a 1-hour diagnosis.

### 6.3 Why return the executed-transitions list?
It makes the behavior **observable and testable**. The smoke suite asserts exact
plans (e.g. desktop→logon yields `[Sign Out Of Windows]`, length 1), so a
regression in the planner fails loudly. *Alternative:* return nothing — simpler API
but the “only missing steps” guarantee becomes untestable folklore.

### 6.4 Hermetic transitions (the subtle one)
The forward `Authenticate BitLocker With Smart Card` transition first removes any
card a previous test left inserted, then inserts the *configured authorized* card,
then unlocks. **Why:** on a shared, stateful SUT a prior negative test might leave a
rogue card in the reader; a non-hermetic transition would then “succeed” for the
wrong reason or fail spuriously. A transition must **fully determine** the state it
promises. *Disadvantage:* a transition does a little more than its name suggests;
we document it at the call site so it isn’t surprising.

---

## 7. How a test uses all of this (and why it stays trivial)

```robot
*** Settings ***
Resource    ../../resources/common/settings.resource
Test Setup  Given The Desktop Is Ready          # ← the ONLY precondition line

*** Test Cases ***
User Can Open The Application
    Open Application
    Application Should Be Visible
```

* The test says **what state it needs**, never **how** to reach it.
* If a previous test already left the machine at the desktop, `Test Setup` runs
  **zero** transitions — the precondition is effectively free.
* Multiply by 800: the initialization flow is written **once**
  (`StateManager` + `resources/`), and every test reuses it with one readable line.

---

## 8. Extending the model (the 5-minute change)

To add, say, a **“BIOS menu”** state between power-on and BitLocker:

1. Add `BIOS_MENU` to the `SystemState` enum (`core/state_model.py`).
2. In `StateManager`, register its detector and the two edges
   (`POWERED_OFF → BIOS_MENU → BITLOCKER_PREBOOT`) with costs.
3. Done — the planner automatically routes through it where appropriate, and **no
   test changes**.

That “one place to change navigation” property is the entire return on the
architecture’s complexity. If adding a screen forced edits across many tests, the
model would have failed at its one job.
