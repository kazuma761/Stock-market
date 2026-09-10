# ST-15 · Handle unknown symbol and unreachable API as separate branches

**Phase:** phase-4-fetch · **Depends on:** ST-12
**Source:** PRD §6 item 4 & §7 (≥3 handled failure modes with a test)

## Description
Together with ST-14 these are the three failure modes the PRD commits to. Each must produce a clear log line
and a sensible task outcome rather than a stack trace.

## Acceptance criteria
- [ ] A symbol Alpha Vantage does not know is handled without an exception escaping
- [ ] A connection error / timeout is handled distinctly and is eligible for retry
- [ ] Both log the offending symbol by name
- [ ] Neither aborts the remaining symbols in the run
- [ ] A test covers each branch, using a stubbed transport rather than the live API
