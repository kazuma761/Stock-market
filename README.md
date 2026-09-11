# MarketPipe

A Dockerized data pipeline that fetches daily stock market data from
[Alpha Vantage](https://www.alphavantage.co/), parses it, and stores it in PostgreSQL — orchestrated by Apache
Airflow and started with a single command.

---

## Quick start

You need **Docker** (with Compose v2). Nothing else — no local Python, no local Postgres.

```bash
git clone <this-repo> && cd MarketPipe

cp .env.example .env
# Open .env and paste your Alpha Vantage key into ALPHA_API_KEY.
# Claiming a free key takes ~20 seconds: https://www.alphavantage.co/support/#api-key

docker compose up
```

That is the only manual step. When the logs settle, open **http://localhost:8080** and log in with
`airflow` / `airflow` (change these in `.env` if you like).

The `stock_data_pipeline` DAG is enabled on startup. To see data immediately without waiting for the schedule,
press **▶ Trigger DAG**.

### Verify it worked

```bash
docker compose exec postgres psql -U marketpipe -d market_data \
  -c "SELECT symbol, name, price, volume, change_percent, date_collected FROM market_data.stocks ORDER BY symbol;"
```

```
 symbol |       name        | price  |  volume  | change_percent | date_collected
--------+-------------------+--------+----------+----------------+----------------
 AAPL   | Apple Inc         | 150.00 | 50000000 |     1.23450000 | 2026-09-10
 GOOG   | Alphabet Inc      | ...    | ...      |            ... | 2026-09-10
 MSFT   | Microsoft Corp    | ...    | ...      |            ... | 2026-09-10
```

Trigger the DAG a second time and re-run the query: the row count does not change. Writes are idempotent.

### Shutting down

```bash
docker compose down      # stop, keep data
docker compose down -v   # stop and delete data
```

> `database_setup/init.sql` runs **only when the database volume is first created**. If you change the schema,
> you must `docker compose down -v` for the change to take effect.

---

## Deliverables

| Deliverable | File |
| --- | --- |
| Docker Compose | [`docker-compose.yaml`](docker-compose.yaml) |
| Orchestrator logic (DAG) | [`dags/stock_data_dag.py`](dags/stock_data_dag.py) |
| Data fetching script | [`core/stock_fetcher.py`](core/stock_fetcher.py) |
| Instructions | this file |

Supporting files: [`core/storage.py`](core/storage.py) (database writes),
[`database_setup/init.sql`](database_setup/init.sql) (schema), [`config.json`](config.json) (symbols + schedule).

---

## How it works

```
                  ┌──────────────────── Airflow (scheduler + webserver) ────────────────────┐
                  │                                                                          │
   Alpha Vantage  │   ┌──────────────────┐         ┌───────────────────┐                    │
   ───────────────┼──▶│ fetch_stock_data │────────▶│ store_stock_data  │                    │
   GLOBAL_QUOTE   │   │  StockFetcher    │  XCom   │     Storage       │                    │
   OVERVIEW       │   └──────────────────┘         └─────────┬─────────┘                    │
                  │                                          │                               │
                  └──────────────────────────────────────────┼───────────────────────────────┘
                                                             ▼
                                              PostgreSQL  market_data.stocks
```

Two tasks rather than one, so the failure boundary is visible in the Airflow UI: an API problem and a database
problem light up different tasks.

**Schedule:** daily at 22:00 UTC (`config.json`), with `catchup=False`. Alpha Vantage's `GLOBAL_QUOTE` reports
daily-close figures, so a more frequent schedule would re-fetch identical values while consuming the free-tier
request budget.

### Adding a symbol

Edit `config.json` — no code change, no rebuild:

```json
{ "symbols": ["AAPL", "GOOG", "MSFT", "NVDA"], "schedule": "0 22 * * *" }
```

---

## Error handling

Alpha Vantage reports most failures **inside an HTTP 200 body** rather than through a status code, so
`raise_for_status()` alone is not enough — the response body is inspected before any field is read.

| Condition | How it is detected | What happens |
| --- | --- | --- |
| **Quota / rate limit spent** | `Information` or `Note` key in a 200 body | Logged, remaining symbols abandoned (the budget is account-wide, so further calls would only repeat the error), and **not retried** — retrying a quota error just burns quota |
| **Unknown or delisted symbol** | Empty `Global Quote`, or an `Error Message` key | Logged; **other symbols continue** |
| **API unreachable / HTTP error** | `requests.exceptions.RequestException` | Logged; other symbols continue; Airflow retries the task twice with a 5-minute delay |
| **Incomplete company data** | Missing `Name` or `MarketCapitalization` | Symbol skipped — both columns are `NOT NULL`, so a half-populated row never reaches the database |

**Partial failure is visible, not silent.** Symbols that succeeded are written and committed *first*, then the
task raises with the list of failures. You get the data that was collectable **and** a red task explaining
exactly what was missed — rather than a green task hiding a problem, or an all-or-nothing run where one delisted
ticker costs you everything.

### Request budget

Each symbol costs 2 requests (`GLOBAL_QUOTE` + `OVERVIEW`). At 3 symbols on a daily schedule that is **6
requests/day**, comfortably inside Alpha Vantage's free tier (~25/day at the time of writing) with headroom for
manual re-triggers.

> Confirm the current limit at [alphavantage.co/support](https://www.alphavantage.co/support/#support) — it has
> changed more than once. If you add symbols, keep `2 × symbols` inside your tier.

---

## Scalability & resilience

- **Config-driven symbols** — scale the workload by editing a JSON list, not by touching code.
- **Idempotent writes** — a `UNIQUE (symbol, date_collected)` constraint plus `INSERT … ON CONFLICT DO UPDATE`
  means re-runs and retries update in place. Safe to trigger repeatedly.
- **Isolated failures** — one bad symbol cannot fail the batch.
- **Task-level retries** — two retries with a 5-minute delay for transient network failure; quota errors are
  deliberately excluded.
- **`BIGINT` volume** — heavily traded tickers exceed `INT`'s ~2.1 billion ceiling.
- **`LocalExecutor`** — swapping to `CeleryExecutor` for parallel workers is a compose change, not a code change.

---

## Security

- All credentials come from environment variables; nothing is hardcoded.
- `.env` is git-ignored. Only `.env.example`, containing placeholders, is committed.
- A `detect-private-key` pre-commit hook guards against committing a key by accident.
- Postgres is reachable only inside the compose network (the published port is for local inspection).

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # Python 3.8-3.11; Airflow 2.9 does not support 3.12+
python -m unittest discover tests -v
black .
```

Tests are `unittest`, with all network and database calls mocked — the suite never touches the real API or a
live database. CI runs the same suite plus `black --check` on every push and pull request.

---

## Future work

Deliberately out of scope for this pipeline, and what would change first in production:

- `CeleryExecutor` or `KubernetesExecutor` for parallel workers
- A secrets manager instead of `.env`
- Alerting on DAG failure (Slack / PagerDuty via `on_failure_callback`)
- Intraday granularity and historical backfill
- A dead-letter table for symbols that fail repeatedly

---

## License

See [LICENSE.txt](LICENSE.txt).
