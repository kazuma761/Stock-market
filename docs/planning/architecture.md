# Architecture — Dockerized Stock Market Data Pipeline

**Status:** Decided · **Date:** 2026-09-10 · **Branch:** `assignment/slim-stock-pipeline`
**Intent:** [`dockerized-stock-pipeline.prd.md`](./dockerized-stock-pipeline.prd.md) — read that for *what* and
*why*. This doc is *how*. Mode: **brownfield** — the pipeline exists; the work is mostly subtraction.

---

## Problem & goals

An evaluator clones this repo cold and has ~15 minutes to judge it against five criteria. The PRD's bet is that
a smaller, colder-startable repo scores higher than a larger, more capable one. Every decision below is judged
against one question: **does this make the pipeline easier to run and easier to read, without leaving the
error-handling and scalability criteria with nothing to point at?**

## What's actually there today

Read before deciding, because it changes the effort estimate in both directions:

| Finding | Consequence |
| --- | --- |
| `docker/superset/*` is **dead files** — no compose service references it | Deleting Superset is `rm -rf`, not compose surgery. Cheaper than the PRD assumed. |
| `custom/api_client.py` imports `core.base_api_client`, which doesn't exist | Genuinely broken, but an orphan — nothing imports it. Deletes cleanly. |
| `core/base_api.py`'s `ApiClientFactory` **is** complete (`load_clients` + `get_client` both defined) | The factory works; we remove it for being indirection over one asset type, not for being broken. |
| `init.sql` has **no unique constraint**; `storage.py` does a bare `INSERT` | Re-runs duplicate rows today. The PRD's "0 duplicates" metric has no mechanism yet — this is new work, not a cut. |
| `start_date: datetime.now()` at DAG-parse time | Airflow antipattern — start date drifts every parse. Fix. |
| `requirements.txt` pins `apache-airflow==2.8.0`; Dockerfile builds `apache/airflow:2.9.0` | Version mismatch. `requests==2.26.0` (2021) will also fight Airflow 2.9's constraints. |
| `utils/__init__.py` does `import *` from a module importing `MagicMock` | Test helpers (`mock_imports`) leak into the production namespace. |
| `mdp_config.json` schedule is already `29 22 * * *` | Already daily — the PRD's schedule decision costs nothing to implement. |

## Approaches considered

**A. Slim in place — keep the layering, delete the branches.** Strip crypto and the factory, keep
`DataProcessor` → client → `Storage`. Lowest diff, preserves existing tests. But `DataProcessor` becomes a
pass-through over a single client, and the evaluator still traverses four objects to follow one code path.

**B. Flatten to the brief's own nouns. ← recommended**
Restructure into exactly the artifacts the brief names: a fetching script, a storage module, a DAG. Bigger diff,
rewrites the tests — but the deliverables become self-locating, which is precisely the PRD's hypothesis.

**C. Greenfield rewrite in a clean tree.** Cleanest possible result, but throws away working error-handling and
tested parsing logic, and re-earns bugs already fixed. The PRD's thesis is that the substance is fine; only the
presentation fails. Rewriting contradicts that.

## Recommended approach

**B — flatten to the brief's nouns.** One ingestion path, stocks only, structured so each of the four
deliverables is a file the evaluator can point at:

```
docker-compose.yaml        → the single-command deliverable
dags/stock_data_dag.py     → the orchestrator-logic deliverable
core/stock_fetcher.py      → the data-fetching-script deliverable
core/storage.py            → upsert into Postgres (kept, adapted)
config.json                → symbol list + schedule
README.md                  → the instructions deliverable
```

The DAG stays a two-task chain (fetch → store) so the failure boundary is visible in the Airflow UI: a fetch
problem and a database problem light up different tasks.

**Deleted outright:** `core/crypto_api_client.py`, `core/base_api.py`, `core/data_processor.py`,
`custom/`, `docker/superset/`, the FMP path inside the stock client, `pysertive`, and the `mock_imports`
helpers. `main` retains the full MarketPipe.

## Key decisions

### Stack & libraries
Unchanged where it already works — **Airflow 2.9 + LocalExecutor, `requests`, `psycopg2-binary`, Postgres 15**.
The brief names `requests` explicitly; Airflow is already wired. **Version pins get reconciled** (drop the 2.8.0
pin, move `requests` to a current release) — the mismatch is exactly what a code-quality reviewer catches.
*Dropped:* `pysertive` (a one-line null check behind a third-party decorator), and the FMP client.
*Considered and rejected:* Dagster — the brief allows it, but Airflow is already working here and familiarity
beats novelty on a timed deliverable. `SQLAlchemy` — an ORM over one table is more surface, not less.

### Data model
One table, `market_data.stocks`, shape preserved: `symbol · name · market_cap · volume · price ·
change_percent · date_collected`. The `cryptos` table is dropped from `init.sql`.

**`name` and `market_cap` come from a second Alpha Vantage call.** They're `NOT NULL` and FMP supplied them;
`GLOBAL_QUOTE` has neither. So each symbol costs **`GLOBAL_QUOTE` + `OVERVIEW` = 2 calls**, or 6/day at three
symbols against a ~25/day limit — comfortable headroom, and it keeps "extract all relevant data points" honest.

**Idempotency:** a unique constraint on `(symbol, date_collected)`, written via `INSERT … ON CONFLICT … DO
UPDATE`. Re-triggering the same day updates in place rather than duplicating — and re-triggering is the first
thing an evaluator does.

### Boundaries & contracts
- **Secrets:** one variable, `ALPHA_API_KEY`, plus DB credentials — all env-injected. **`.env` gets untracked
  and its `.gitignore` rule uncommented; `.env.example` ships in its place.** Cold start = paste one key.
- **External surface:** exactly one — `alphavantage.co` over HTTPS. Down from three vendors.
- **Datastore:** a single Postgres container holding two databases — `airflow` (metadata) and `market_data`.
  Separation without a second container.
- **Failure posture:** **store the good, surface the bad.** A failing symbol doesn't block its peers; successful
  symbols are written, failures are logged with the symbol named, and the task ends in a visibly non-green
  state when any symbol failed. Neither silent data loss nor all-or-nothing brittleness.

### Other calls
- **Quota exhaustion is a first-class condition.** Alpha Vantage signals it *inside a 200 response* (an
  `Information` key), so status codes can't detect it. Current code would `KeyError`. Handling it distinctly
  from "bad symbol" and "network down" gives the error-handling criterion three concrete, testable branches.
- **Retries belong to Airflow, not to hand-rolled loops** — task-level `retries` with exponential backoff for
  transient network failure. A quota error is *not* retried; retrying a quota error just burns the quota.
- **Config stays a JSON file**, slimmed to symbols + schedule. Adding a ticker is a one-line edit with no code
  change — the concrete evidence for "scalability."
- **Compose topology:** `postgres`, `airflow-init`, `airflow-webserver`, `airflow-scheduler`. The triggerer goes
  (nothing uses deferrable operators), the `airflow-cli` profile goes, the second Postgres goes.
- **`start_date` becomes a fixed past date** with `catchup=False`.

## Missing pieces

Things that don't exist yet and that this approach depends on:

1. **The unique constraint and upsert path** — the largest piece of genuinely *new* code.
2. **An `OVERVIEW` parser** — a response shape nothing currently reads.
3. **Quota-exhaustion detection** — a branch that has no equivalent today.
4. **A partial-failure signal** — some mechanism for "succeeded with omissions"; today failures are swallowed.
5. **`.env.example`** — doesn't exist; `.env` is tracked instead.
6. **A rewritten test suite** — the current tests cover modules being deleted.
7. **A redrawn or removed architecture diagram** — `assets/architecture.png` shows Superset and crypto.

## Spikes & experiments

**Spike 1 — Confirm the Alpha Vantage free tier (blocking, do first).**
- *Question:* Is the daily limit still ~25? Does quota exhaustion really return 200 + `Information`? Does
  `OVERVIEW` count against the same budget?
- *Spike:* Register a key, call `GLOBAL_QUOTE` and `OVERVIEW` for one symbol, capture both payloads verbatim,
  then deliberately exhaust the quota and capture that response. **Timebox: 30 minutes.**
- *Decision rule:* limit ≥ 25/day and `OVERVIEW` affordable → proceed as specced. If the budget is tighter than
  6 calls/day → cut to one symbol or revisit dropping `name`/`market_cap`. If exhaustion presents differently
  than assumed → the detection strategy changes, and it's better to learn that from a real payload than a test
  double.

**Spike 2 — Cold-start timing on a clean machine.**
- *Question:* Does `docker compose up` actually reach rows in under 15 minutes from nothing?
- *Spike:* Clean Docker cache, clone, follow only the README, time it. **Timebox: one run.**
- *Decision rule:* This *is* the PRD's RIGHT condition. Any question asked or any file edited that the README
  didn't specify = the hypothesis failed; fix the README before submitting.

Everything else is a **two-way door** — reversible on a branch with `main` intact. Build directly.

## Open questions

- [ ] **Which symbols ship?** AAPL/GOOG/MSFT = 6 calls/day. The count is the lever if Spike 1 finds a lower limit.
- [ ] **Is an `OVERVIEW` call every day wasteful?** Company name and market cap barely move. Caching was
      rejected as extra machinery, but if quota turns out tight it's the first thing to reconsider.
- [ ] **How does "succeeded with omissions" surface in Airflow?** Several mechanisms exist; pick during
      implementation and prefer the one that reads clearly in the UI without custom operators.
- [ ] **Scrub `.env` from git history, or just untrack it going forward?** Values are placeholders — tidiness,
      not a security incident.
- [ ] **Keep the GitHub Actions workflows and pre-commit config?** Good code-quality evidence, but only if they
      pass against the slimmed tree.
- [ ] **`volume INT` caps at ~2.1B.** Fine for these three tickers; would break on a high-volume penny stock.
      Widen now, or note it as a known limit?

---

*Next: `piv-slice-epic` to break this into tickets, or `piv-plan-implementation` to plan it in one pass — the
scope is small enough that one pass is defensible. Spike 1 should run before either.*
