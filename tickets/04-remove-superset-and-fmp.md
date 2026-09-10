# ST-04 · Remove Superset assets and the FMP provider path

**Phase:** phase-1-subtract
**Source:** PRD §8, architecture.md "What's actually there today"

## Description
`docker/superset/*` is dead files — no compose service references it — so this is a plain delete, not compose
surgery. Financial Modeling Prep is the second market-data provider and the second API key; the design commits
to one source, one key.

## Acceptance criteria
- [ ] `docker/superset/` deleted
- [ ] The FMP code path removed from the stock client
- [ ] `FMP_API_KEY` (or equivalent) removed from `.env.example`, compose, and README
- [ ] Exactly one external host remains in the codebase: `alphavantage.co`
- [ ] `docker compose config` still parses
