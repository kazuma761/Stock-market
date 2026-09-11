# Code Review — slim stock pipeline

**Date:** 2026-09-11 · **Branch:** `publish` · **Baseline:** working tree vs `HEAD`

**Stats:**
- Files Modified: 11
- Files Added: 2 (+1 untracked dir `docs/planning/`)
- Files Deleted: 29 (planning docs relocated to `docs/planning/`)
- New lines: 1119
- Deleted lines: 1307

**Validation run during review:** 27/28 host tests pass (`test_dags.py` needs Airflow,
which is container-only); `black --check` clean; compose config valid; pipeline previously
proven end-to-end against the live API with idempotency confirmed.

---

## Findings

```
severity: high
file: core/stock_fetcher.py
line: 146
issue: `_optional` returns the literal string "None", which Postgres rejects and which aborts the entire batch
detail: Alpha Vantage's OVERVIEW endpoint returns `"MarketCapitalization": "None"` (the
  four-character string) for ETFs, indices and some ADRs, rather than omitting the key.
  `_optional` only filters falsy/whitespace values, so `"None"` is truthy and passes
  through. `market_cap` is `DECIMAL(20,2)`, and I verified against the live database that
  Postgres rejects it:
      INSERT ... VALUES ('TEST','Test Co','None',1,1.0,1.0);
      ERROR: invalid input syntax for type numeric: "None"
  That raises `psycopg2.Error`, which `Storage.store_data` catches at the batch level ->
  `self.conn.rollback()` -> re-raise. Every symbol in the run is lost, including the ones
  that fetched perfectly. One ETF in `config.json` destroys the whole day's collection.
  This directly defeats the stated "store the good, surface the bad" design.
suggestion: Treat the sentinel as absent in `_optional`:
      SENTINELS = {"none", "n/a", "-", "null"}
      value = quote.get(key)
      if not isinstance(value, str):
          return None
      value = value.strip()
      return value if value and value.lower() not in SENTINELS else None
  Note this is only reachable for OVERVIEW-sourced fields today, but applying it in
  `_optional` covers every optional field at once.
```

```
severity: high
file: core/storage.py
line: 119
issue: a single malformed value fails the whole batch; per-row isolation exists only in the pre-check
detail: `REQUIRED_FIELDS` screens for missing values before the INSERT, and that path
  correctly skips just the bad symbol. But any value that is present and *unparseable by
  Postgres* escapes that screen and surfaces as a `psycopg2.Error` from `cur.execute`,
  which is caught at batch scope and rolls back everything. The finding above is one
  instance; any malformed numeric string reaches the same place. The docstring promises
  "one incomplete symbol should not cost us the others", but the guarantee only holds for
  the failure mode the pre-check anticipates.
suggestion: Isolate each row with a SAVEPOINT so a bad row is skipped rather than fatal,
  while genuine connection/transaction failures still propagate:
      for symbol, fields in data.items():
          ...
          try:
              self.cur.execute("SAVEPOINT row")
              self.cur.execute(UPSERT_SQL, params)
              self.cur.execute("RELEASE SAVEPOINT row")
              written += 1
          except psycopg2.DataError as e:
              self.cur.execute("ROLLBACK TO SAVEPOINT row")
              self.logger.error(f"Skipping {symbol}: {e}")
  Keep the outer handler for `psycopg2.OperationalError` / `InterfaceError`, where aborting
  is the right call. This also makes the high finding above non-fatal even if a new
  sentinel value appears.
```

```
severity: medium
file: tests/test_stock_fetcher.py
line: (test_missing_market_cap_is_tolerated)
issue: the test's stated scenario is not the scenario it exercises
detail: The comment says "an ETF or index has no meaningful one", but the mock omits the
  `MarketCapitalization` key entirely. The real ETF case sends `"None"` as a string, which
  is the case that breaks (see the high finding). The test passes while the behaviour it
  claims to protect is broken — worse than no test, because it reads as coverage.
suggestion: Change the OVERVIEW mock to
  `{"Symbol": "SPY", "Name": "SPDR S&P 500", "MarketCapitalization": "None"}`
  and assert `result["SPY"]["market_cap"] is None`. Add a storage-level test that a row
  whose `market_cap` is rejected by the database does not discard its peers.
```

```
severity: medium
file: core/stock_fetcher.py
line: 122
issue: README states quota errors are never retried; the code retries four times over 65 seconds
detail: `BACKOFF_SCHEDULE_SECONDS = (5, 15, 45)` plus the final attempt means up to four
  calls and ~65s of sleeping per endpoint before `QuotaExhausted` is raised. The README's
  error-handling table still says quota is "**not retried** — retrying a quota error just
  burns quota", and the Scalability section repeats that quota errors are "deliberately
  excluded" from retries. The new behaviour is defensible (it is the only way to separate
  a transient throttle from a spent daily budget), but it burns 4 calls of a ~25/day budget
  to discover exhaustion, and the documentation now contradicts the implementation. Error
  handling is a scored criterion and the README is the entry point, so the contradiction
  costs more than either behaviour alone.
suggestion: Update the README table to describe the escalating-backoff probe and why it
  exists. Separately, consider whether 3 retries is the right trade against the request
  budget — (5, 20) would halve the cost and still distinguish a burst limit.
```

```
severity: low
file: core/stock_fetcher.py
line: 124
issue: dead variable
detail: `last: Exception | None = None` is assigned in the loop (`last = e`) and never
  read; the final `except RateLimited as final` supplies the exception that is actually
  chained. Harmless, but it reads as if the retry loop's last error were being preserved
  for something.
suggestion: Delete the `last` binding and the assignment.
```

```
severity: low
file: dags/stock_data_dag.py
line: 56
issue: retrying `store_stock_data` after a fetch failure re-runs an operation that cannot succeed
detail: When `failures` is non-empty, the task raises `AirflowException` and Airflow retries
  it twice at 5-minute intervals. The retry re-reads the same XCom payload, re-writes the
  same rows (harmless — the upsert is idempotent), and raises the identical error. The
  outcome is fixed from the first attempt; the retries only add 10 minutes before the task
  goes red. No quota is consumed (the fetch task already succeeded), so this is cosmetic
  rather than costly.
suggestion: Raise `AirflowFailException` instead — it skips remaining retries and fails the
  task immediately, which also reads more honestly in the UI.
```

```
severity: low
file: docker-compose.yml
line: 22
issue: the test suite is bind-mounted into the Airflow runtime
detail: `- ./tests:/opt/airflow/tests` puts test code on the container's `PYTHONPATH` root.
  It is convenient for running the suite in-container and harmless here, but it ships test
  fixtures into what is nominally the production image's working tree.
suggestion: Keep it if in-container testing is intended (worth a one-line comment saying
  so, as the neighbouring mounts all have one); otherwise drop the mount and run tests via
  `docker compose run --rm --volume ./tests:/opt/airflow/tests`.
```

---

## Checked and clean

- **SQL injection** — `UPSERT_SQL` interpolates only module-level constants (`QUALIFIED_TABLE`,
  `COLUMNS`); all values are passed as bound parameters. No user-controlled string reaches SQL.
- **Secrets** — no hardcoded credentials. `.env` is untracked, matched by `.gitignore:15`, and
  absent from the `publish` tree; `.env.example` holds placeholders only. Verified the live key
  cannot be committed.
- **Column/parameter drift** — deriving `COLUMNS`, `_PLACEHOLDERS` and `_UPDATES` from one tuple
  removes the classic INSERT-ordering bug. Good call.
- **`trading_day` as the conflict target** — keying on the session the data describes rather than
  the run date is correct, and prevents a weekend run from inventing a duplicate session.
- **`_throttle`** — initial `_last_request_at = 0.0` yields a large elapsed value, so the first
  call is not delayed. Correct.
- **Connection lifecycle** — `_close()` in `finally` covers the raising paths; no leak found.
- **`BIGINT` volume, `DECIMAL(12,4)` prices** — appropriate widths; the INT overflow ceiling is gone.

## Operational note (not a code defect)

`init.sql` runs only on first volume creation, so the schema rewrite (`date_collected` ->
`trading_day`, new price columns) does not reach an existing volume. I confirmed mid-review that
the then-running database still had the old columns, against which the new `ON CONFLICT
(symbol, trading_day)` would fail. `docker compose down -v` is required, and the README already
documents this. Worth re-running the end-to-end check on a fresh volume before submitting.
