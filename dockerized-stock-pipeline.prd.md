# PRD — Dockerized Stock Market Data Pipeline

**Status:** Draft (rev 2) · **Date:** 2026-09-10 · **Branch:** `assignment/slim-stock-pipeline`
**Derived from:** the "Dockerized Data Pipeline with Airflow/Dagster" assignment brief, applied to the existing
MarketPipe codebase.

> **Framing note.** This is an assignment deliverable, not a market-facing product. The "user" is the evaluator
> reading and running the repo; the "evidence" is the published brief and rubric rather than user research. The
> PRD's job here is to fix *what must be true for this to score well* and *what we are deliberately not
> building*. The engineering decisions belong to the spec (`plan-architecture`).

---

## 1. Problem Statement

**Who:** An evaluator who will clone this repository onto a machine they have never used it on, read the brief,
and decide within roughly fifteen minutes whether the submission demonstrates competence across five criteria —
correctness, error handling, scalability, code quality, dockerization.

**The problem today:** MarketPipe already solves the *technical* problem — it fetches market data on a schedule
and lands it in Postgres. As it stands it fails the *evaluation* problem in three concrete ways:

- **It cannot be run by a stranger.** It requires three separate API keys (Alpha Vantage, Financial Modeling
  Prep, CoinMarketCap) before a single task succeeds. An evaluator who cannot get it running scores correctness
  and dockerization from source-reading alone — the worst case for us.
- **Its surface area exceeds its brief.** Superset, a crypto ingestion path, a second Postgres instance, a
  dynamic class-loading factory, and a `pysertive` invariant decorator are all present. Each one is something
  the evaluator must read *past* to find the four things the brief actually asks for.
- **It carries visible dead weight.** `custom/api_client.py` imports `core.base_api_client`, a module that does
  not exist. `.env` is git-tracked because its `.gitignore` rule is commented out. Both are exactly the sort of
  detail a code-quality reviewer notices, and the second one contradicts the brief's security requirement.

**Cost of not solving it:** the work is already done and would be marked down for presentation, not substance.

## 2. Evidence

| Claim | Basis |
| --- | --- |
| Five weighted criteria: correctness, error handling, scalability, code quality, dockerization | Brief, "Evaluation Criteria" — **direct** |
| Four required deliverables: `docker-compose.yml`, orchestrator logic, fetching script, `README.md` | Brief, "Deliverables" — **direct** |
| Single-command build-and-run is explicitly required | Brief: "seamless building and deployment of the entire pipeline with a single command" — **direct** |
| Either hourly *or* daily scheduling satisfies the brief | Brief: "on a scheduled basis (hourly or daily)" — **direct** |
| Secrets must come from environment variables | Brief, "Security" — **direct** |
| Repo currently needs 3 API keys and cannot run cold | `core/stock_api_client.py`, `core/crypto_api_client.py`, `.env` — **observed** |
| `custom/api_client.py` is broken | Imports `core.base_api_client`; only `core/base_api.py` exists — **observed** |
| `.env` is tracked in git | `git ls-files` returns `.env`; the `.gitignore` line is commented out. Values are placeholders, so nothing has leaked — **observed** |
| Compose runs two Postgres instances plus a Superset stack | `docker-compose.yaml`: `postgres-source`, `postgres-airflow`, `docker/superset/*` — **observed** |
| ~892 lines of Python today, roughly half of it off-brief | `wc -l` across `core/`, `custom/`, `utils/`, `dags/`, `tests/` — **observed** |
| Alpha Vantage free tier is ~25 requests/day | Vendor's published free-tier limit — **needs confirmation at build time**; this limit has changed more than once |
| Quota exhaustion returns HTTP 200 with an `Information` key, not an error status | Vendor behaviour — **needs confirmation at build time**; if true, naive `response["Global Quote"]` access raises `KeyError` |
| An evaluator spends ~15 minutes | **Assumption** — validate by having someone unfamiliar clone and run it cold |

## 3. Thesis (why build it)

The substance already exists. What is missing is that the repository does not currently *argue its own case* to
someone encountering it cold.

The bet is that a **smaller, colder-startable repo scores higher than a larger, more capable one**, because
every rubric line is judged against what the evaluator can actually see and run. Scalability in particular is
scored on whether the design *reads* as extensible — not on how many asset classes ship. A single clean
ingestion path with a config-driven symbol list and safe retries makes that argument better than two paid-API
clients behind a dynamic import factory, because the evaluator can verify the first claim in a minute and must
take the second on faith.

**Why now:** the pipeline is feature-complete. The remaining work is subtraction, and subtraction is cheap and
low-risk in a way that adding a third asset class is not.

**Why it beats the current cope:** the cope is "submit MarketPipe as-is and explain the extra parts in the
README." That relies on the evaluator reading an explanation *before* forming an impression, which inverts how
code review actually happens.

## 4. Hypothesis

> **We believe** that cutting the pipeline to a single stocks path, deleting every component the brief does not
> ask for, and making a cold clone work end-to-end from one command
> **will cause** an evaluator unfamiliar with the project
> **to** successfully run the pipeline and locate all four deliverables without assistance,
> **resulting in** the submission being judged on its error handling and design rather than on setup friction.

**We'll know we're RIGHT if:** someone who has never seen the repo goes from `git clone` to rows visible in
Postgres using only the README, in under 15 minutes, on a machine with nothing but Docker installed — their only
manual step being to paste in one API key.

**We'll know we're WRONG if:** that person has to ask a question, edit a file the README did not tell them to
edit, or hits a failed task on first run. **Also wrong if** the slimmed repo drops below roughly 300 lines of
substantive Python — at which point "readable" has become "trivial," and the scalability and error-handling
criteria have nothing left to point at.

## 5. Target User & JTBD

**Primary user:** the assignment evaluator. Reads first, runs second, has limited patience, and is scoring
against a fixed rubric rather than forming an open-ended opinion.

**JTBD:** *When I'm handed a data-engineering submission to assess, I want to get it running and read its core
logic quickly, so I can judge whether this person builds production-shaped systems rather than demos.*

**Secondary user:** you, presenting it live or in a walkthrough — the repo needs a narrative you can talk
through, with a visible failure-handling story.

**Explicit non-users:** anyone operating this as a real production market-data system; anyone wanting crypto,
multi-exchange, or intraday tick data; anyone needing a BI or visualisation layer.

## 6. MVP — the thinnest line that proves the hypothesis

A cold clone reaches rows in Postgres via a single command plus one pasted API key:

1. **One command** brings up Postgres and Airflow together, with the target table present on first boot.
2. **One DAG**, scheduled **daily**, with catchup disabled and a manual trigger that works immediately.
3. **Fetch → parse → store** over a configurable symbol list, using `requests` against Alpha Vantage.
4. **Failure paths that are visible, not theoretical** — a symbol that doesn't exist, a quota-exhausted
   response, and an unreachable API each produce a clear log line and a sensible task outcome rather than a
   stack trace.
5. **Re-running the same day** leaves the row count unchanged.
6. **A README** that assumes zero prior knowledge of the project.
7. **A small test suite** covering parsing and the missing-data branches.

**Door check:** every item is a **two-way door** — reversible, since `main` retains the full MarketPipe and this
work happens on a branch. Build directly; no spike needed.

## 7. Success Metrics

| Metric | Target | How measured |
| --- | --- | --- |
| Cold-start time to first row in Postgres | < 15 min, incl. image build | Someone unfamiliar times themselves on a clean machine |
| Manual steps beyond the single command | Exactly 1 (paste API key into `.env`) | Count steps in the README |
| First-run task failures | 0 | Airflow UI after initial trigger |
| API calls consumed in a full day of scheduled operation | Within the free-tier daily limit, with headroom for manual re-triggers | Count endpoints × symbols × runs per day |
| Re-running the same day's data | 0 duplicate rows | `SELECT count(*)` before/after a re-trigger |
| Handled failure modes with an explicit branch and a test | ≥ 3 (bad symbol · quota exhausted · network error) | Test suite |
| Deliverables locatable from repo root | 4 of 4 | Inspection against the brief |
| Files an evaluator must read to understand the flow | ≤ 5 | Inspection |
| Substantive Python remaining | ~300–450 lines | `wc -l`, excluding tests |
| Secrets in version control | 0 | `git ls-files`; `.env.example` present and `.env` ignored |

## 8. Non-goals

Everything below is **deleted from the working tree**, not merely undocumented. `main` retains the full
MarketPipe, so nothing is lost.

- **Crypto ingestion** (`core/crypto_api_client.py` and its tests) — out of scope for a brief that says "stock
  market data," and it carries a second API key.
- **Superset / any BI or visualisation layer** (`docker/superset/*` and its compose service) — not a deliverable.
- **The dynamic client-loading factory** (`custom/api_client.py`, `core/base_api.py`, the `mdp_config.json`
  client registry) and the `pysertive` invariant decorator. Scalability is argued instead through a
  config-driven symbol list, non-duplicating writes, and safe retries — claims an evaluator can verify by
  reading one file.
- **A separate Postgres instance for Airflow metadata** — one Postgres serves both.
- **The second market-data provider** (Financial Modeling Prep) — one source, one key.
- **Historical backfill** — `catchup=False`; the pipeline captures data going forward.
- **Production concerns** — no CeleryExecutor, no multi-worker scaling, no alerting integration, no secrets
  manager. Named as future work in the README, not built.
- **Intraday / tick granularity** — one row per symbol per interval.

## 9. Constraints the spec inherits (not decisions this PRD makes)

Recorded so `plan-architecture` starts from them rather than re-deriving them:

- **Orchestrator: Airflow**, slimmed from the existing setup — not Dagster.
- **Source: Alpha Vantage** via the `requests` library, as the brief specifies.
- **Schedule: daily**, with a manual trigger available. This is the resolution of the free-tier quota problem:
  daily × a small symbol list stays inside the published limit with headroom, where hourly did not. It is also
  the honest cadence for daily-close data, which does not change between overnight runs.
- **Scope: stocks only**, flattened — no client-factory hierarchy.
- **Cold start: one pasted API key.** Committing a working key would satisfy "single command" at the direct
  expense of the brief's security requirement, so it is ruled out.
- **Repeat runs must not duplicate rows** — the write semantics that achieve this are the spec's call.
- **Quota exhaustion is a recognised condition, not a crash** — the vendor signals it inside a 200 response, so
  it cannot be detected from status code alone. How it is detected and what the task does next is the spec's
  call.
- **Location:** branch `assignment/slim-stock-pipeline`, off `main`. Tests are kept, rewritten small.

## 10. Open Questions

- [ ] **Confirm Alpha Vantage's current free-tier daily limit** at build time, and confirm the daily schedule
      plus the shipped symbol count sits inside it with headroom. (Owner: spec stage.)
- [ ] **Confirm the quota-exhausted response shape.** If it is not a 200 with an `Information` key, the
      detection strategy changes. (Owner: spec stage.)
- [ ] **Which symbols ship as the default?** Currently AAPL, GOOG, MSFT. The count directly drives quota
      consumption and is the lever if the limit turns out lower than expected.
- [ ] **Does `.env` need scrubbing from git history**, or is removing it going forward sufficient? Values are
      placeholders, so this is a tidiness question, not a security incident.
- [ ] **Keep or drop the GitHub Actions workflows** (`run_tests.yml`, `run_black.yml`) and the pre-commit
      config? They are evidence of code-quality practice, but only if they pass against the slimmed tree.
- [ ] **Does the README keep the architecture diagram** (`assets/architecture.png`)? It currently depicts the
      full MarketPipe including Superset and crypto, so it is either redrawn or removed.
- [ ] **Is a live demo part of the submission?** If so the README needs screenshots and the DAG needs to produce
      a visible result fast.
- [ ] **How long is `main` kept intact?** Assumed indefinitely — the branch is the deliverable.

---

*Next: run `plan-architecture` to decide **how** — table DDL and write strategy, retry/backoff and quota
handling, module layout, compose topology, and test boundaries. This PRD deliberately leaves all of those open.*
