# ST-23 · Redraw or remove the architecture diagram

**Phase:** phase-7-docs · **Depends on:** ST-08
**Source:** PRD §10 open question, architecture.md "Missing pieces" #7

## Description
`assets/architecture.png` depicts the full MarketPipe including Superset and crypto. Left as-is it actively
contradicts the slimmed repo in the most visible place in the README.

## Acceptance criteria
- [ ] Decision made and recorded: redraw or remove
- [ ] If redrawn: shows only `postgres · airflow · alphavantage` and the fetch → store chain
- [ ] If removed: the README reference is removed too, no broken image
- [ ] No stale image files left in `assets/`
