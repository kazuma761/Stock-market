# System Review — Slim Stock Pipeline

**Plan:** `.claude/plans/slim-stock-pipeline.md`
**Execution report:** `.claude/reports/slim-stock-pipeline-report.md`
**Date:** 2026-09-11
**Scope:** process, not code. Bugs in *how the work was planned and executed*.

---

## Overall Alignment Score: 7/10

Every divergence was justified and documented — none were shortcuts or pattern violations. The score
is held down not by bad divergence but by a **planning failure that let four container-only defects
reach a "COMPLETE" claim**, and by a **verification method that produced three false readings in a row**.

---

## Divergence Analysis

```yaml
- divergence: Phase 0 spike never ran
  planned: "Blocking. Capture 4 live payloads before writing parsers."
  actual: Parsers written against documented shapes; fixtures hand-built
  reason: ALPHA_API_KEY in .env was a placeholder
  classification: good ✅ (mitigation), bad ❌ (plan design)
  justified: partly
  root_cause: missing validation — the plan marked a task "blocking" but gave
              the executor no instruction for what to do when it is blocked

- divergence: Fourth error branch (Error Message) added
  planned: three branches (quota, bad symbol, network)
  actual: four
  reason: observed live when the placeholder key was rejected
  classification: good ✅
  root_cause: plan relied on a spike that could not run

- divergence: store_data() lost its `table` parameter
  planned: "hardcode the table"
  actual: parameter removed entirely
  reason: also removes f-string interpolation of caller input into SQL
  classification: good ✅

- divergence: name column VARCHAR(50) -> VARCHAR(100)
  planned: preserve the column set
  actual: widened
  reason: OVERVIEW returns full legal names
  classification: good ✅ — later confirmed ("Microsoft Corporation", "Alphabet Inc Class C")
  root_cause: plan said "preserve schema" without checking the new source's field widths

- divergence: init.sql also creates the `airflow` database
  planned: not stated
  actual: added
  reason: one-Postgres decision implied it; metadata conn had nowhere to land
  classification: good ✅
  root_cause: architecture decision not decomposed into its implied tasks

- divergence: architecture.png deleted, not redrawn
  planned: left open
  actual: deleted, ASCII diagram in README
  reason: a binary image drifts silently
  classification: good ✅

- divergence: schema restructured AFTER "COMPLETE" (trading_day key, 5 new columns)
  planned: preserve existing schema
  actual: rebuilt around (symbol, trading_day)
  reason: date_collected labelled rows by run date, not session — rows were
          already off by one day, and weekend runs would duplicate
  classification: good ✅ — a real correctness defect
  root_cause: **plan never questioned the inherited unique key.** The architecture
              doc decided "upsert keyed on (symbol, date)" without asking whether
              that date described the data or the pipeline.
```

---

## Root Cause Themes

### Theme 1 — "Blocking" tasks with no blocked-path instruction
Phase 0 was marked blocking. It could not run. The executor improvised well (handling every documented
variant rather than guessing one), but nothing in the plan *required* that response. A less careful pass
would have guessed one key and shipped a latent bug.

### Theme 2 — Local-environment validation masquerading as real validation
The first pass reported "all tests pass" from a Python 3.13 venv. Four defects survived that were only
observable in the container:
- PEP 585 generics vs the Python 3.8 base image (DAG would not parse at all)
- `./logs` bind mount creating a root-owned dir against UID 50000
- `schedule_interval` deprecation
- README claiming 3.8 support the code contradicted

**Every one of these is a "passes locally, fails in the deployment target" defect.** The plan's
VALIDATE commands were written as bare shell, implicitly host-run. None required container execution.

### Theme 3 — Verification by unreliable probe, repeated three times
Quota state was checked with a single-symbol API request. Alpha Vantage serves cached responses for
recently-requested symbols, so the probe reported "available" while the quota was spent — **three
separate times**, each producing a wrong statement to the user. It was only resolved by a 2x2 matrix
(two symbols x host/container). A one-sample probe was treated as proof of a rate-limited system's state.

### Theme 4 — Moves made with `mv` instead of `git mv`
Planning docs were "moved out of the way", but git still tracked them at the old paths. A fresh clone
would still have delivered 25 ticket files to the repo root — the exact problem the move was meant to
solve. The working tree looked right; the artifact a stranger receives did not.

---

## Pattern Compliance

- [x] Followed codebase architecture (logger injection, `_connect`/`finally _close`, unittest+mock)
- [x] Used documented patterns — mirrored `file:line` references from the plan
- [x] Applied testing patterns correctly — `@patch("<module>.requests.get")`, never live calls
- [ ] **Met validation requirements** — validation ran in the wrong environment on the first pass
- [x] No new architecture invented; no shortcuts taken

---

## System Improvement Actions

### Update CLAUDE.md

```markdown
## Validation environment
Validate in the environment the code will RUN in, not the one it was authored in.
For containerised projects the authoritative command is:
    docker compose exec <service> python -m unittest discover tests
A green local suite is necessary, not sufficient. Base-image Python version,
filesystem ownership, and installed library versions all differ from the host.

## Verifying rate-limited external APIs
Never infer quota state from a single request — cached responses make one sample
meaningless. Vary BOTH the resource and the caller before concluding.

## Moving tracked files
Use `git mv`. A plain `mv` leaves the old path in the index, so the artifact a
clone receives differs from the working tree.

## Natural keys
When a row describes an external event, key it on the event's own identifier,
not on when the pipeline ran. `(symbol, trading_day)`, never `(symbol, date_collected)`.
```

### Update Plan skill (`piv-plan-implementation`)

- [ ] **Every task marked "blocking" must carry an `IF BLOCKED:` clause** stating what to do when its
      precondition is unavailable. Phase 0 had none, and only luck produced a good outcome.
- [ ] **VALIDATE commands must name their execution environment.** Add a required field:
      `VALIDATE (host)` or `VALIDATE (container)`. Bare commands default to host and hide target defects.
- [ ] **Add a plan section: "Inherited decisions to re-examine."** The `(symbol, date_collected)` key
      came from the architecture doc and was never questioned, because the plan's job was to implement
      the architecture, not audit it. One prompt — *does this key describe the data or the pipeline?* —
      would have caught it before any code was written.
- [ ] When a plan changes the **data source**, require a field-width/type check against the new
      source's real responses (the `VARCHAR(50)` near-miss).

### Update Execute skill (`piv-implement`)

- [ ] Before writing the report, run the suite **in the deployment target**, not just locally. Status
      may not be `COMPLETE` while the only green run is host-local.
- [ ] `git status` must be clean of unstaged renames before reporting. Add:
      `git status --short | grep -E "^ D|^\?\?"` → investigate before claiming done.

### Create new skill

- [ ] **`verify-deliverable-clone`** — materialise a repo from *tracked files only* into a temp dir,
      assert required files present / secrets absent / no stray directories, then `docker compose up`
      and health-check. This session did it ad hoc and it immediately found the `git mv` defect. It is
      the only check that sees what a stranger actually receives.

---

## Key Learnings

**What worked well**
- Documenting deviations in the report made this review possible — every divergence had a stated reason.
- Handling all documented API-error variants instead of guessing one turned a blocked spike into a
  *more* robust branch than the plan specified.
- The plan's `GOTCHA` fields caught real traps (the tuple-wrapping trailing comma, the `datetime.now()`
  start_date, the non-discovered `dags_test.py`).
- The PRD's line-count guardrail (~300–450) worked exactly as intended: the result landed at 380.

**What needs improvement**
- Validation ran in the wrong environment and produced a false COMPLETE.
- A blocking task had no blocked-path plan.
- An inherited architectural decision (the unique key) was implemented without being questioned, and
  was wrong.
- The same unreliable verification method was repeated three times after producing a wrong answer.

**For next implementation**
1. Run validation inside the container before writing any report.
2. Give every blocking task an `IF BLOCKED:` clause.
3. Add one planning prompt: "which inherited decisions should this ticket challenge?"
4. When a check gives a surprising result twice, change the method — do not repeat it.

---

## Note on environment integrity

Three state changes occurred that this session did not initiate: git commits plus a branch switch to
`publish`, a DAG run with `run_id: rerun-idempotency`, and a full `coldtest` docker stack holding ports
5433 and 8080. None caused damage — the `coldtest` stack incidentally proved a cold deployment works —
but process conclusions drawn from this environment should be held loosely, since it was not under
exclusive control.
