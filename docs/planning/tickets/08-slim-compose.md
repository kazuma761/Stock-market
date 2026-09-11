# ST-08 · Slim the compose topology to four services

**Phase:** phase-2-runtime · **Depends on:** ST-07
**Source:** PRD §6 item 1 (one command), architecture.md "Other calls — compose topology"

## Description
Target topology: `postgres`, `airflow-init`, `airflow-webserver`, `airflow-scheduler`. The triggerer goes —
nothing uses deferrable operators — and so does the `airflow-cli` profile.

## Acceptance criteria
- [ ] Exactly those four services defined; triggerer and CLI profile removed
- [ ] `docker compose up` is the only command needed to reach a running Airflow UI
- [ ] The target table exists on first boot without a manual step
- [ ] Health checks/`depends_on` ordering means no service crash-loops on a cold start
- [ ] Zero failed tasks on the first triggered run (PRD §7 metric)
