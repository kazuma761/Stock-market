# ST-22 · Rewrite `README.md` for a zero-prior-knowledge cold start

**Phase:** phase-7-docs · **Depends on:** ST-08, ST-17
**Source:** PRD §6 item 6 & §7, brief deliverable #4

## Description
The README is one of the four named deliverables and is the only thing standing between the evaluator and a
running pipeline. It must assume no prior knowledge of MarketPipe.

## Acceptance criteria
- [ ] Exactly one manual step beyond the single command: paste the API key into `.env`
- [ ] The single command to bring the stack up is given verbatim and works as written
- [ ] All four brief deliverables are named with their file paths
- [ ] The error-handling story (three branches + retry posture) is stated explicitly
- [ ] The scalability story (config-driven symbols, upsert, retries) is stated explicitly
- [ ] Deliberate non-goals from PRD §8 are listed as future work
- [ ] No reference to Superset, crypto, FMP, or any deleted module survives
