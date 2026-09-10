# ST-20 · Rewrite the test suite around parsing and the failure branches

**Phase:** phase-6-quality · **Depends on:** ST-12 … ST-16
**Source:** PRD §6 item 7 & §7, architecture.md "Missing pieces" #6

## Description
Current tests cover modules being deleted. The replacement suite is small and points at exactly what the
error-handling criterion is scored on.

## Acceptance criteria
- [ ] `GLOBAL_QUOTE` and `OVERVIEW` parsing covered with real captured payloads
- [ ] One test per failure branch: bad symbol · quota exhausted · network error (≥3 total)
- [ ] The upsert/no-duplicate path covered
- [ ] The mixed partial-failure run covered
- [ ] No test requires a live API key or network access
- [ ] Whole suite runs in well under a minute
