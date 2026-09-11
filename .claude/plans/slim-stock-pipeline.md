# Feature: Slim MarketPipe to a Single-Source Dockerized Stock Pipeline

The following plan should be complete, but it's important that you validate documentation and codebase patterns
and task sanity before you start implementing.

Pay special attention to naming of existing utils, types and models. Import from the right files.

## Feature Description

Reduce the existing MarketPipe repository to exactly the pipeline the assignment brief asks for: one Alpha
Vantage source, one stocks table, one DAG, one Postgres, running from a single `docker compose up` plus one
pasted API key. Most of this work is **deletion**. The genuinely new code is an idempotent upsert path,
quota-exhaustion handling, and a partial-failure signal.

## User Story

As an **evaluator assessing a data-engineering submission**
I want to **clone the repo, run one command, and see stock rows land in Postgres**
So that **I can judge the pipeline's error handling and design rather than fighting its setup**.

## Problem Statement

The pipeline works but cannot be run by a stranger: it needs three API keys, carries a crypto path, a Superset
directory, a client factory, a broken orphan module and a second Postgres, and it duplicates rows on every
re-run. An evaluator with ~15 minutes reads past all of it or gives up.

## Solution Statement

Flatten to the brief's own nouns — a fetching script, a storage module, a DAG, a compose file, a README — cut
everything else from the tree, and add the three mechanisms the rubric actually probes: idempotent writes,
recognised quota exhaustion, and visible partial failure.

## Out of Scope / Non-Goals

- **Not included:** crypto ingestion, Superset, the FMP provider, the `ApiClientFactory` / `BaseApiClient`
  seam, `pysertive` — all deleted, not deferred.
- **Not included:** historical backfill (`catchup=False`), CeleryExecutor, alerting, secrets managers.
- **Not included:** rewriting `.env` out of git history — untracked going forward only.
- **Not changing:** the `market_data.stocks` column set (beyond `volume` → `BIGINT` and the new unique
  constraint), the `market_data` schema name, or Airflow as the orchestrator.
- **Not migrating** the test framework to pytest — this repo uses `unittest`.

## Feature Metadata

**Feature Type**: Refactor (subtractive) + targeted New Capability
**Estimated Complexity**: Medium — low per-change difficulty, high change count
**Primary Systems Affected**: `dags/`, `core/`, `database_setup/`, `docker/`, `docker-compose.yaml`, `tests/`, CI
**Dependencies**: Alpha Vantage API (single external service), Airflow 2.9, Postgres 15, `requests`, `psycopg2-binary`

## Related Work

**Implements**: `dockerized-stock-pipeline.prd.md` (intent) · **Architecture**: `architecture.md` (the how)

**Back-references:**
- `architecture.md` — Why: all cross-cutting calls (stack, data model, boundaries, failure posture) are decided
  there and inherited here. Do not reopen them.
- `dockerized-stock-pipeline.prd.md` — Why: the success metrics below trace to its metrics table.

**Forward-references:** (none yet)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `core/stock_api_client.py` (lines 45-95) — Why: the fetch loop, the per-symbol try/except shape, and the
  `Global Quote` field keys (`"05. price"`, `"06. volume"`, `"10. change percent"`) to preserve. **The FMP
  block at lines 66-80 is what gets replaced by an Alpha Vantage `OVERVIEW` call.**
- `core/storage.py` (lines 28-45) — Why: `_connect`/`_close` env-var pattern to keep verbatim.
- `core/storage.py` (lines 60-90) — Why: the `INSERT` to convert to an upsert, and the required-field check.
- `dags/market_data_dag.py` — Why: the two-task `fetch >> store` wiring to preserve. **Anti-patterns to fix:
  `start_date: datetime.now()` (line 18) and the trailing comma at line 53 that wraps the operator in a tuple.**
- `tests/test_stock_api_client.py` (lines 20-40) — Why: the exact mocking pattern to mirror —
  `@patch("<module>.requests.get")` with `MagicMock` responses.
- `tests/test_storage.py` (lines 16-30) — Why: `@patch.dict(os.environ, ...)` + `@patch("core.storage.psycopg2.connect")`.
- `database_setup/init.sql` — Why: current DDL; the `cryptos` table goes, `volume` widens, a constraint is added.
- `docker-compose.yaml` — Why: service topology to reduce from 7 services to 4.
- `.gitignore` (line 17) — Why: the `#.env` rule is commented out; this is why `.env` is tracked.

### New Files to Create

- `core/stock_fetcher.py` — the brief's "data fetching script" deliverable
- `config.json` — slimmed symbol list + schedule (replaces `mdp_config.json`)
- `.env.example` — template with placeholder values
- `tests/test_stock_fetcher.py` — unit tests for fetch/parse/error branches
- `.github/workflows/ci.yml` — one lean workflow (replaces both existing ones)

### Files to DELETE

`core/crypto_api_client.py` · `core/base_api.py` · `core/data_processor.py` · `core/stock_api_client.py`
(superseded by `stock_fetcher.py`) · `custom/` · `docker/superset/` · `mdp_config.json` ·
`tests/test_crypto_api_client.py` · `tests/test_base_api_client.py` · `tests/test_data_processor.py` ·
`.github/workflows/run_tests.yml` · `.github/workflows/run_black.yml`

### Relevant Documentation — READ BEFORE IMPLEMENTING

- [Alpha Vantage GLOBAL_QUOTE](https://www.alphavantage.co/documentation/#latestprice) — response shape; note
  keys are numbered strings like `"05. price"`.
- [Alpha Vantage OVERVIEW](https://www.alphavantage.co/documentation/#company-overview) — supplies `Name` and
  `MarketCapitalization`. **Verify field names against a live response (Spike 1) before coding the parser.**
- [Alpha Vantage support / rate limits](https://www.alphavantage.co/support/#support) — confirm the current
  free-tier daily limit.
- [Postgres INSERT … ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT) —
  the upsert; requires a unique constraint on the conflict target.
- [Airflow DAG scheduling](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#running-dags) —
  why `start_date` must be static, not `datetime.now()`.
- [Airflow exceptions](https://airflow.apache.org/docs/apache-airflow/stable/_api/airflow/exceptions/index.html) —
  `AirflowException` for the partial-failure signal.

### Patterns to Follow

**Naming:** `snake_case` modules and functions, `PascalCase` classes. Modules live in `core/`, DAGs in `dags/`,
tests in `tests/` named `test_<module>.py`.

**Logging:** a `logging.Logger` is passed into constructors, never module-global. Mirror `core/storage.py:22`:
```python
def __init__(self, logger: logging.Logger):
    self.logger = logger
```

**Error handling:** catch the narrow exception, log with the symbol named, then decide. Mirror
`core/stock_api_client.py:88`:
```python
except requests.exceptions.RequestException as req_error:
    self.logger.error(f"Error during API request for {symbol}: {req_error}")
```

**DB access:** always `_connect()` → work → `_close()` in a `finally`, with `conn.rollback()` on error.
Mirror `core/storage.py:60-95`.

**Tests:** `unittest.TestCase`, `setUp` builds a `MagicMock(spec=logging.Logger)`, network and DB are patched at
the module path (`@patch("core.stock_fetcher.requests.get")`). **Never** hit the real API in a test.

---

## IMPLEMENTATION PLAN

### Phase 0: Verify vendor assumptions
**Blocking.** Two load-bearing assumptions are unverified. Capture real payloads before writing parsers.

### Phase 1: Subtraction
**Independent of:** Phase 0 — deletion doesn't depend on API behaviour. Can run in parallel.
Delete the off-brief tree and the secrets-in-git problem.

### Phase 2: Data layer
**Depends on:** Phase 1. Schema + upsert — the core new mechanism.

### Phase 3: Fetch layer
**Depends on:** Phase 0 (needs confirmed response shapes) and Phase 1.

### Phase 4: Orchestration & compose
**Depends on:** Phases 2 and 3.

### Phase 5: Tests, CI, docs
**Depends on:** Phases 2-4.

### Phase 6: Cold-start validation
**Depends on:** everything. This is the PRD's RIGHT condition.

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom.

### VERIFY Alpha Vantage behaviour (Phase 0)
- **IMPLEMENT**: Register a free key. Capture verbatim JSON for: (a) `GLOBAL_QUOTE` for AAPL, (b) `OVERVIEW` for
  AAPL, (c) `GLOBAL_QUOTE` for a nonsense symbol e.g. `ZZZZNOPE`, (d) a quota-exhausted response. Save all four
  under `tests/fixtures/` — they become the test doubles.
- **GOTCHA**: Quota exhaustion is believed to return **HTTP 200 with an `Information` key**, so
  `raise_for_status()` will NOT catch it. Confirm the exact key — it has also appeared as `Note` historically.
  If the daily limit is under 6 calls, STOP and revisit the symbol count with the user.
- **VALIDATE**: `ls tests/fixtures/*.json | wc -l` returns 4
- **SATISFIES**: AC #8

### REMOVE off-brief modules and directories (Phase 1)
- **IMPLEMENT**: `git rm -r` the full delete list under "Files to DELETE".
- **GOTCHA**: `core/stock_api_client.py` is deleted but its parsing logic is the source material for
  `core/stock_fetcher.py` — **read it before deleting**, or delete it last.
- **VALIDATE**: `grep -rn "crypto\|superset\|pysertive\|ApiClientFactory\|BaseApiClient\|DataProcessor" --include="*.py" --include="*.yaml" --include="*.txt" . ; test $? -eq 1`
- **SATISFIES**: AC #1

### UPDATE `.gitignore` and untrack `.env` (Phase 1)
- **IMPLEMENT**: Uncomment the `.env` rule (line 17), `git rm --cached .env`, create `.env.example` with
  `ALPHA_API_KEY=`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`,
  `AIRFLOW_UID`.
- **GOTCHA**: Do NOT rewrite git history — decided against; values are placeholders. `--cached` only.
- **VALIDATE**: `git ls-files | grep -x ".env"; test $? -eq 1 && test -f .env.example`
- **SATISFIES**: AC #7

### CREATE `config.json`, REMOVE `mdp_config.json` (Phase 1)
- **IMPLEMENT**: `{"symbols": ["AAPL","GOOG","MSFT"], "schedule": "0 22 * * *"}`. Drop the `clients` registry,
  `account_id`, and the crypto block.
- **PATTERN**: read via `utils.read_json` — `utils/market_data_processor_utils.py:5`
- **VALIDATE**: `python -c "import json;c=json.load(open('config.json'));assert c['symbols'] and c['schedule']"`
- **SATISFIES**: AC #6

### UPDATE `utils/market_data_processor_utils.py` (Phase 1)
- **IMPLEMENT**: Keep `read_json`. REMOVE `validate_symbols` (pysertive is gone), `mock_imports`,
  `destroy_mock_imports`, and the `MagicMock`/`sys` imports.
- **GOTCHA**: `utils/__init__.py` does `from .market_data_processor_utils import *`, which is why `MagicMock`
  currently leaks into the production namespace. Replace the star-import with `from .market_data_processor_utils import read_json`.
- **VALIDATE**: `python -c "import utils; assert not hasattr(utils,'MagicMock') and not hasattr(utils,'mock_imports')"`
- **SATISFIES**: AC #9

### UPDATE `database_setup/init.sql` (Phase 2)
- **IMPLEMENT**: Drop the `cryptos` table. On `stocks`: `volume` → `BIGINT`, add
  `CONSTRAINT stocks_symbol_date_key UNIQUE (symbol, date_collected)`. Keep schema name `market_data`.
- **GOTCHA**: `init.sql` runs **only on first volume creation**. Any re-test needs `docker compose down -v`, and
  the README must say so.
- **VALIDATE**: `grep -c "cryptos" database_setup/init.sql` returns 0; `grep -q "UNIQUE (symbol, date_collected)" database_setup/init.sql`
- **SATISFIES**: AC #3

### UPDATE `core/storage.py` — upsert (Phase 2)
- **IMPLEMENT**: Convert the `INSERT` to `INSERT ... ON CONFLICT (symbol, date_collected) DO UPDATE SET
  name=EXCLUDED.name, market_cap=EXCLUDED.market_cap, volume=EXCLUDED.volume, price=EXCLUDED.price,
  change_percent=EXCLUDED.change_percent`. Hardcode the table as `market_data.stocks`; drop the `table` param.
- **PATTERN**: mirror the existing `_connect`/`try`/`rollback`/`finally _close` structure at `core/storage.py:60-95`.
- **GOTCHA**: the current f-string builds the table name into SQL. With the parameter gone, use a module
  constant — never interpolate caller input into SQL.
- **VALIDATE**: `python -m unittest tests.test_storage -v`
- **SATISFIES**: AC #3, AC #4

### CREATE `core/stock_fetcher.py` (Phase 3)
- **IMPLEMENT**: `StockFetcher(logger)` with `fetch()` returning `(data: dict, failures: list[str])`. Per symbol:
  call `GLOBAL_QUOTE` then `OVERVIEW`; parse `price`, `volume`, `change_percent` (strip `%`), `Name`,
  `MarketCapitalization`. Three distinct error branches:
  1. **Quota exhausted** — the `Information`/`Note` key is present → log, record failure, **stop iterating**
     (further calls are futile) and do NOT retry.
  2. **Unknown symbol** — `Global Quote` present but empty → log, record failure, continue to next symbol.
  3. **Network/HTTP error** — `requests.exceptions.RequestException` → log, record failure, continue.
- **PATTERN**: mirror the loop and logging shape of `core/stock_api_client.py:45-95`.
- **IMPORTS**: `os`, `requests`, `logging`, `from dotenv import load_dotenv`, `from utils import read_json`
- **GOTCHA**: `raise_for_status()` will not fire on a quota error — **check the body for the `Information` key
  BEFORE indexing `Global Quote`**, or you get the exact `KeyError` this refactor exists to fix.
- **VALIDATE**: `python -m unittest tests.test_stock_fetcher -v`
- **SATISFIES**: AC #2, AC #5

### UPDATE `dags/market_data_dag.py` → `dags/stock_data_dag.py` (Phase 4)
- **IMPLEMENT**: One DAG `stock_data_pipeline`, two `PythonOperator`s (`fetch_stock_data` >> `store_stock_data`),
  schedule from `config.json`, `catchup=False`. The store task writes successes first, commits, then raises
  `AirflowException` naming the failed symbols if `failures` is non-empty.
- **GOTCHA (three of them)**: (1) `start_date` MUST be a fixed past `datetime(2024,1,1)`, not `datetime.now()`.
  (2) The current `store_data_task = (PythonOperator(...),)` has a trailing comma making it a **tuple** — drop
  it. (3) Raise only **after** the commit, or the partial data is lost — that inverts the chosen posture.
- **VALIDATE**: `python -c "from airflow.models import DagBag; d=DagBag('dags'); assert not d.import_errors, d.import_errors; assert 'stock_data_pipeline' in d.dags"`
- **SATISFIES**: AC #2, AC #5

### UPDATE `docker-compose.yaml` (Phase 4)
- **IMPLEMENT**: Reduce to 4 services: `postgres`, `airflow-init`, `airflow-webserver`, `airflow-scheduler`.
  Remove `postgres-airflow`, `airflow-triggerer`, `airflow-cli` and the second volume. One Postgres hosts both
  the `airflow` metadata DB and `market_data`. Mount `database_setup/init.sql` into
  `/docker-entrypoint-initdb.d/`. Keep `env_file: .env` and the healthcheck/`depends_on` conditions.
- **GOTCHA**: Airflow's metadata DB and the market data DB now share an instance — the init script must create
  both, and `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` must point at the right one.
- **VALIDATE**: `docker compose config --quiet && docker compose config --services | wc -l` returns 4
- **SATISFIES**: AC #1, AC #10

### UPDATE `requirements.txt` and `docker/airflow/Dockerfile` (Phase 4)
- **IMPLEMENT**: Reconcile to a single Airflow version (2.9.0, matching the base image). Drop `pysertive`.
  Move `requests` off the 2021-era `2.26.0` pin. Remove `pre-commit` from runtime requirements.
- **GOTCHA**: **Three files currently disagree** — `requirements.txt` (2.8.0), Dockerfile (2.9.0), CI (2.8.1).
  All three must land on one version. Install with Airflow's constraints file to avoid dependency conflicts.
- **VALIDATE**: `docker compose build --quiet`
- **SATISFIES**: AC #9

### CREATE `tests/test_stock_fetcher.py` + UPDATE `tests/test_storage.py` (Phase 5)
- **IMPLEMENT**: Using the Phase 0 fixtures — happy path; unknown symbol; quota exhausted; network error;
  partial success (one of two symbols fails → good data returned AND failure recorded). Storage: upsert SQL
  contains `ON CONFLICT`; re-store of the same key doesn't add a row.
- **PATTERN**: mirror `tests/test_stock_api_client.py:20-40` exactly — `@patch("core.stock_fetcher.requests.get")`.
- **GOTCHA**: rename `tests/dags_test.py` → `tests/test_dags.py`; `unittest discover` only matches `test*.py`,
  so it is currently **not being discovered** and CI runs it via a separate explicit line.
- **VALIDATE**: `python -m unittest discover tests -v`
- **SATISFIES**: AC #5, AC #11

### CREATE `.github/workflows/ci.yml`, REMOVE the old two (Phase 5)
- **IMPLEMENT**: One workflow: checkout → Python 3.10 → `pip install -r requirements.txt` →
  `python -m unittest discover tests` → `black --check .`. Drop every PR-label `curl` step.
- **GOTCHA**: those curl steps POST to the issues API using `github.event.number`, which is **undefined on a
  branch push** — they fail outside a PR context. That's why they go.
- **VALIDATE**: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- **SATISFIES**: AC #9

### UPDATE `README.md` (Phase 5)
- **IMPLEMENT**: Assume zero prior knowledge. Prerequisites (Docker only) → `cp .env.example .env` → paste key →
  `docker compose up` → open Airflow → trigger DAG → verify with a `SELECT`. Name the four deliverables and
  where they live. Document the three handled failure modes, the daily quota math (2 calls × 3 symbols = 6/day),
  the `docker compose down -v` note for re-initialising the schema, and future work.
- **GOTCHA**: `assets/architecture.png` depicts Superset and crypto — redraw or remove it. A stale diagram
  contradicting the tree is worse than no diagram.
- **VALIDATE**: `grep -q "docker compose up" README.md && grep -q ".env.example" README.md`
- **SATISFIES**: AC #6, AC #10

### VALIDATE cold start end-to-end (Phase 6)
- **IMPLEMENT**: `docker compose down -v`, clone fresh to a temp dir, follow ONLY the README, time it. Trigger
  the DAG, confirm rows. Trigger a second time, confirm the row count is unchanged.
- **VALIDATE**: `docker compose exec postgres psql -U $POSTGRES_USER -d market_data -c "SELECT count(*), max(date_collected) FROM market_data.stocks;"`
- **SATISFIES**: AC #4, AC #10, AC #12

---

## TESTING STRATEGY

### Unit Tests
`unittest`, mirroring existing structure. All network and DB calls patched at the module path. Fixtures are the
**real captured payloads** from Phase 0, not hand-written approximations — this is the whole point of the spike.

### Integration Tests
The compose stack itself: DAG parses without import errors (`DagBag`), the schema initialises, and a triggered
run writes rows. Verified manually in Phase 6, not automated — automating a live-API integration test would
consume quota on every CI run.

### Edge Cases (each needs a test)
1. Quota exhausted mid-run — 200 + `Information`, no `KeyError`, loop stops.
2. Unknown symbol — empty `Global Quote`, other symbols still processed.
3. Network unreachable — `RequestException` caught, run continues.
4. Partial success — good rows stored AND the task ends non-green.
5. Re-run same day — row count unchanged (upsert).
6. `OVERVIEW` succeeds but `GLOBAL_QUOTE` fails (and the reverse) — no half-populated row violating `NOT NULL`.
7. High-volume symbol — value exceeding INT range persists (regression guard for the BIGINT widening).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```bash
black --check .
python -m compileall -q core dags utils tests
```

### Level 2: Unit Tests
```bash
python -m unittest discover tests -v
```

### Level 3: Integration
```bash
docker compose config --quiet
docker compose build
docker compose up -d
python -c "from airflow.models import DagBag; d=DagBag('dags'); assert not d.import_errors, d.import_errors"
```

### Level 4: Manual Validation
```bash
# trigger, then verify
docker compose exec postgres psql -U "$POSTGRES_USER" -d market_data \
  -c "SELECT symbol, name, price, volume, date_collected FROM market_data.stocks ORDER BY symbol;"
# idempotency: re-trigger, count must not change
```

### Level 5: Hygiene
```bash
git ls-files | grep -x ".env" && echo "FAIL: .env tracked" || echo "OK"
grep -rn "crypto\|superset\|pysertive\|PREP_API_KEY" --include="*.py" --include="*.yaml" . || echo "OK: clean"
```

---

## ACCEPTANCE CRITERIA

- [ ] **AC #1** — Off-brief code is gone: no crypto, Superset, factory, `custom/`, or `pysertive` in the tree
- [ ] **AC #2** — One DAG, two tasks, daily schedule, `catchup=False`, manual trigger works immediately
- [ ] **AC #3** — Unique constraint on `(symbol, date_collected)`; writes go through `ON CONFLICT DO UPDATE`
- [ ] **AC #4** — Re-triggering the same day leaves the row count unchanged
- [ ] **AC #5** — Three failure modes each have an explicit branch and a passing test
- [ ] **AC #6** — All four brief deliverables exist and are locatable from the repo root
- [ ] **AC #7** — `.env` untracked, `.gitignore` rule active, `.env.example` present, zero secrets in git
- [ ] **AC #8** — Daily quota math documented and within the verified free-tier limit
- [ ] **AC #9** — One Airflow version across all files; `black --check` and CI pass
- [ ] **AC #10** — Cold clone → rows in Postgres in under 15 min, one manual step (paste key)
- [ ] **AC #11** — `unittest discover` finds and passes every test, including the renamed DAG test
- [ ] **AC #12** — First run produces zero task failures
- [ ] Substantive Python lands in the ~300-450 line band (PRD guardrail against over-cutting)

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation passed immediately
- [ ] All five validation levels executed
- [ ] Full test suite passes
- [ ] No lint errors
- [ ] Cold-start manual test confirms the PRD's RIGHT condition
- [ ] All acceptance criteria met

---

## OPEN QUESTIONS / ASSUMPTIONS

**Resolved before planning** (do not reopen): daily schedule · delete-don't-document · one pasted key · AV
`OVERVIEW` for name/market_cap · two-module code shape · 4-service compose · store-then-raise on partial failure
· slim JSON config · BIGINT + untrack `.env` without history rewrite · keep AAPL/GOOG/MSFT · lean single CI
workflow · stay on `unittest`.

**Still assumed — confirm in Phase 0:**
- **Assumed** — Alpha Vantage free tier is ~25 requests/day. If materially lower, the symbol count is the lever.
  *Blocks the quota math in AC #8.*
- **Assumed** — quota exhaustion returns HTTP 200 with an `Information` key. Historically it has also used
  `Note`. *If wrong, the detection branch in `stock_fetcher.py` changes.*
- **Assumed** — `OVERVIEW` counts against the same daily budget as `GLOBAL_QUOTE`.
- **Assumed** — `OVERVIEW` returns non-empty `Name` and `MarketCapitalization` for all three symbols. Both are
  `NOT NULL`; a blank would fail the insert.

## NOTES (open canvas)

**Why deletion is riskier than it sounds.** The instinct is that removing code can't break anything. But
`utils/__init__.py`'s star-import and the factory's *dynamic* `import_module` mean imports resolve at runtime,
not statically — a missed reference surfaces as a DagBag import error inside a container rather than at edit
time. That's why nearly every task carries a grep-based validation and why the DagBag check runs early.

**The ordering trap.** `core/stock_api_client.py` is on the delete list, but it's also the reference for the
parsing logic being rewritten. Read it (or write `stock_fetcher.py`) before deleting. Phases 0 and 1 are
otherwise independent and can run in parallel.

**On stopping the loop when quota is exhausted.** Alternative considered: keep iterating and let each remaining
symbol fail individually. Rejected — it produces N identical error log lines and burns nothing useful, since the
quota is account-wide. Breaking early makes the log readable, which matters when the log *is* the evidence an
evaluator reads.

**On raising after commit.** The inverse (raise, then let the store task be retried) was considered and
rejected: Airflow would retry the whole store task, and without the commit the good data would be lost on a
transient failure. Commit-then-raise keeps the data and still turns the task red.

**Line-count guardrail.** The PRD says below ~300 lines of substantive Python the submission reads as trivial.
Rough post-cut estimate: `stock_fetcher.py` ~120, `storage.py` ~90, `stock_data_dag.py` ~60, `utils` ~10 → ~280,
plus tests. That is *just under* the band. If it lands lower, the fix is richer error handling and docstrings,
not padding.

## AMENDMENTS

<!-- newest at the bottom -->
