# Implementation Report — Slim Stock Pipeline

**Plan**: `.claude/plans/slim-stock-pipeline.md`
**Branch**: `assignment/slim-stock-pipeline`
**Status**: **PARTIAL** — all code complete; full suite (28/28) now passing including the DAG tests; two
environment-dependent validations still cannot run (Docker, live API)

## Summary

Reduced MarketPipe to the pipeline the brief asks for: one Alpha Vantage source, one stocks table, one DAG, one
Postgres, four compose services. Deleted the crypto path, Superset, the client factory, the FMP provider,
`pysertive`, and the broken `custom/` orphan. Added the three mechanisms the rubric probes and the repo lacked:
idempotent upserts, quota-exhaustion handling, and a visible partial-failure signal. Substantive Python went
from 892 to **380 lines**, inside the PRD's 300–450 guardrail.

## Tasks completed

| Task | Result |
| --- | --- |
| Delete off-brief modules | `core/crypto_api_client.py`, `core/base_api.py`, `core/data_processor.py`, `core/stock_api_client.py`, `custom/`, `docker/superset/`, `mdp_config.json`, 3 test files, 2 workflows (REMOVE) |
| Untrack secrets | `.gitignore` rule uncommented, `.env` untracked, `.env.example` (CREATE) |
| Slim config | `config.json` (CREATE), replaces `mdp_config.json` |
| Fix namespace leak | `utils/__init__.py`, `utils/market_data_processor_utils.py` (UPDATE) |
| Schema | `database_setup/init.sql` (UPDATE) — crypto table dropped, `volume`→`BIGINT`, unique constraint, `airflow` DB created |
| Upsert | `core/storage.py` (UPDATE) — `ON CONFLICT DO UPDATE`, table no longer caller-supplied |
| Fetcher | `core/stock_fetcher.py` (CREATE) — 4 error branches |
| DAG | `dags/stock_data_dag.py` (CREATE), `dags/market_data_dag.py` (REMOVE) |
| Compose | `docker-compose.yaml` (UPDATE) — 7 services → 4 |
| Version pins | `requirements.txt`, `docker/airflow/requirements.txt`, `docker/airflow/Dockerfile` (UPDATE) |
| Tests | `tests/test_stock_fetcher.py` (CREATE), `tests/test_storage.py`, `tests/test_dags.py` (UPDATE + rename) |
| CI | `.github/workflows/ci.yml` (CREATE), `.pre-commit-config.yaml` (UPDATE) |
| Docs | `README.md` (UPDATE), `assets/architecture.png` (REMOVE — depicted Superset/crypto) |

## Tests added

**28 tests total — all 28 executed and passing.** (An earlier pass reported 32 and could not run the DAG tests;
both are corrected here. The DAG tests now run against a Python 3.11 venv with Airflow 2.9.0 installed.)

`tests/test_stock_fetcher.py` — **12 tests, all passing**: happy path · two-requests-per-symbol · `Information`
quota key · `Note` quota key · loop stops after quota hit · symbols fetched before quota are kept · bad symbol
isolated · `Error Message` key · network error doesn't stop run · incomplete overview rejected · missing API key
· empty symbol list.

`tests/test_storage.py` — **8 tests, all passing**: env-var connection · connection failure · upsert SQL shape ·
repeat store still upserts · incomplete row skipped not fatal · high-volume BIGINT passthrough · empty input ·
rollback on DB error.

`tests/test_dags.py` — **8 tests, all passing**: DagBag import errors · DAG registered · task wiring · catchup and
static start_date · retries · raises on partial failure · stores before raising · silent on full success.

## Validation results

| Level | Result |
| --- | --- |
| L1 syntax & style | **PASS** — `black --check .` clean (10 files), `compileall` clean |
| L2 unit tests | **PASS** — 28/28, zero deprecation warnings (`python -m unittest discover tests`) |
| DagBag parse | **PASS** — no import errors, `stock_data_pipeline` registered, `fetch >> store` wired |
| L3 integration | **NOT RUN** — Docker daemon unavailable |
| L4 manual validation | **NOT RUN** — requires a running stack and a valid API key |
| L5 hygiene | **PASS** — `.env` untracked; zero off-brief references |

## Deviations from the plan

1. **Phase 0 (the blocking spike) could not run.** The `ALPHA_API_KEY` in `.env` is a placeholder — Alpha Vantage
   rejects it. No fixtures were captured from live responses.
   **Mitigation, and a deliberate design change:** rather than betting on one guessed quota key, the fetcher
   treats **both** `Information` and `Note` as quota signals and `Error Message` as an API error. All documented
   variants are handled, so the branch is correct regardless of which one the spike would have found. Test
   fixtures were built from Alpha Vantage's published response shapes instead of captured payloads.
   *Real evidence gained anyway:* the rejected key returned **HTTP 200 with an `Error Message` key**, confirming
   the core premise that this API signals failures inside 200 bodies.

2. **Added a fourth error branch.** The plan specified three (quota, bad symbol, network). `Error Message` —
   which covers an invalid key, a bad endpoint, and some invalid symbols — was added after observing it live.

3. **`store_data()` dropped its `table` parameter.** The plan said hardcode the table; the parameter was removed
   entirely rather than left unused. This also removes an f-string interpolation of caller input into SQL.

4. **`name` column widened `VARCHAR(50)` → `VARCHAR(100)`.** Not in the plan. Alpha Vantage `OVERVIEW` returns
   full legal company names, which exceed 50 characters more often than the ticker set suggests, and the column
   is `NOT NULL`.

5. **CI split into two jobs** (`test`, `lint`) rather than one. Lint feedback doesn't wait on an Airflow install.

6. **`init.sql` now also creates the `airflow` database.** Implied by the one-Postgres decision but not stated as
   a task; without it the metadata connection has nowhere to land.

7. **`assets/architecture.png` deleted rather than redrawn.** The plan left this open. An ASCII data-flow diagram
   in the README replaces it — it cannot drift from the code the way a binary image silently did.

8. **Local validation ran in a scratch venv**, not the project environment. This machine runs Python 3.13, which
   Airflow 2.9 does not support.

## Second pass — defects found and fixed

A follow-up execution re-validated the tree and found four things the first pass left wrong:

1. **The container would have failed to parse the DAG.** `docker/airflow/Dockerfile` built
   `apache/airflow:2.9.0` against `constraints-3.8.txt` — that image tag ships **Python 3.8**, where the PEP 585
   builtin generics used in `core/stock_fetcher.py` and `core/storage.py` (`dict[str, str]`, `list[str]`,
   `tuple[...]` in signatures) raise `TypeError` at import time. Every test passed locally (3.13) and in CI
   (3.11) while the actual runtime was the one interpreter that breaks. **Fixed:** pinned
   `apache/airflow:2.9.0-python3.11` with matching `constraints-3.11.txt`, which also aligns the container with
   the CI interpreter. This was invisible to every validation in the plan, since Docker was unavailable.

2. **The `./logs` bind mount would have cost an undocumented manual step.** No `logs/` directory exists in the
   repo (it is gitignored), so Docker would create it root-owned while Airflow runs as UID 50000 — a
   `mkdir`/`chown` the README does not mention, breaking AC #10's "exactly one manual step". **Fixed:** replaced
   with a named `airflow-logs` volume.

3. **`schedule_interval` is deprecated** in Airflow 2.9 and emitted a `RemovedInAirflow3Warning` on every DAG
   parse. **Fixed:** switched to `schedule`.

4. **README claimed Python 3.8–3.11 support**, which the same PEP 585 generics make false. **Fixed:** 3.9–3.11.

## Issues encountered

- **No valid API key** — blocks Phase 0 and all live validation. *This is the main open risk.*
- **Docker daemon not running** — blocks image build, compose up, schema init, and the cold-start timing that is
  the PRD's stated RIGHT condition.
- **Python 3.13 is the default local interpreter** — Airflow 2.9 does not support it. Resolved by building a
  Python 3.11 venv from the project's own constraints file; the DAG tests now run locally rather than waiting
  for CI to exercise them for the first time.
- **`tests/dags_test.py` was never being discovered** — `unittest discover` only matches `test*.py`. Renamed to
  `tests/test_dags.py`; it is now collected.
- **Three conflicting Airflow versions** (`requirements.txt` 2.8.0, Dockerfile 2.9.0, CI 2.8.1) reconciled to
  2.9.0 with an official constraints file.

## Before submitting — required

1. Put a real key in `.env`, then run `docker compose up` and trigger the DAG. **This is also the first real
   test of the `-python3.11` image pin above** — the DAG parsing inside the container is the thing that was
   silently broken.
2. Confirm rows land, then trigger again and confirm the count is unchanged.
3. Confirm CI is green (this is where the 8 DAG tests first execute).
4. Verify the current free-tier limit still leaves 6 requests/day comfortable.
