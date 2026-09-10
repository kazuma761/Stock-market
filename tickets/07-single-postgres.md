# ST-07 · Collapse to one Postgres container serving both databases

**Phase:** phase-2-runtime · **Depends on:** ST-04
**Source:** PRD §8 (no separate Airflow metadata Postgres), architecture.md "Boundaries & contracts"

## Description
Compose currently runs `postgres-source` and `postgres-airflow`. One container holding two databases —
`airflow` for metadata, `market_data` for the pipeline — gives the same separation with half the runtime surface
and a faster cold start.

## Acceptance criteria
- [ ] A single `postgres` service in `docker-compose.yaml`
- [ ] Both `airflow` and `market_data` databases created on first boot
- [ ] Airflow's metadata connection string points at the `airflow` database
- [ ] Pipeline writes land in `market_data`
- [ ] A destroy-and-recreate (`docker compose down -v && docker compose up`) reaches a healthy stack unattended
