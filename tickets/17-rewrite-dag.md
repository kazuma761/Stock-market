# ST-17 · Rewrite `dags/stock_data_dag.py` as a two-task chain

**Phase:** phase-5-orch · **Depends on:** ST-12, ST-11
**Source:** PRD §6 item 2, architecture.md "Recommended approach" (the orchestrator-logic deliverable)

## Description
The DAG stays a two-task chain, fetch → store, so the failure boundary is visible in the UI: a fetch problem and
a database problem light up different tasks. `start_date: datetime.now()` at parse time is an Airflow
antipattern — the start date drifts on every parse.

## Acceptance criteria
- [ ] `dags/stock_data_dag.py` defines exactly two tasks, `fetch` → `store`
- [ ] `start_date` is a fixed past date, not computed at parse time
- [ ] `catchup=False`
- [ ] Schedule is daily
- [ ] A manual trigger works immediately after `docker compose up`, with no backfill storm
- [ ] The DAG imports cleanly (`airflow dags list` shows no import errors)
