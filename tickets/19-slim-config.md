# ST-19 · Slim `config.json` to symbol list plus schedule

**Phase:** phase-5-orch · **Depends on:** ST-03, ST-01
**Source:** PRD §3 (scalability argument), architecture.md "Other calls — config stays a JSON file"

## Description
This file *is* the scalability evidence: adding a ticker must be a one-line edit with no code change. That claim
is only credible if the config contains nothing else.

## Acceptance criteria
- [ ] Config contains only the symbol list and the schedule
- [ ] The client registry and all crypto/FMP keys are gone
- [ ] Adding a symbol requires no code change — demonstrated by adding one and running
- [ ] The shipped symbol count is justified against the ST-01 quota finding, in a comment or the README
- [ ] Both the fetcher and the DAG read the schedule/symbols from this one file
