# ST-11 · Convert `storage.py` to an idempotent upsert

**Phase:** phase-3-data · **Depends on:** ST-10
**Source:** PRD §6 item 5 & §7 (0 duplicate rows), architecture.md "Data model"

## Description
`storage.py` currently does a bare `INSERT`. Re-triggering the DAG is the first thing an evaluator does, so
re-running the same day must update in place rather than duplicate.

## Acceptance criteria
- [ ] Writes use `INSERT … ON CONFLICT (symbol, date_collected) DO UPDATE`
- [ ] `SELECT count(*)` is unchanged after re-triggering the same day's run
- [ ] Changed values (e.g. a later price) are reflected after the re-run
- [ ] Connection/cursor lifecycle is handled so a failure can't leak a connection
- [ ] A test covers the write-then-rewrite path
