# ST-01 · Spike: confirm Alpha Vantage free-tier limits and response shapes

**Phase:** phase-0-derisk · **Blocks:** ST-13, ST-14, ST-19 · **Timebox:** 30 min
**Source:** PRD §10 (open questions 1–2), architecture.md "Spike 1"

## Description
Two PRD assumptions are marked *needs confirmation at build time* and both change downstream design if wrong:
the free-tier daily request limit (~25/day assumed) and the shape of a quota-exhausted response (HTTP 200 with
an `Information` key assumed). Confirm both against the live API before writing fetch code.

## Acceptance criteria
- [ ] A real API key is registered and stored in local `.env` (not committed)
- [ ] Verbatim `GLOBAL_QUOTE` payload for one symbol captured to `docs/spikes/alpha-vantage.md`
- [ ] Verbatim `OVERVIEW` payload for the same symbol captured
- [ ] Quota deliberately exhausted; the exhausted response captured verbatim (status code + body)
- [ ] Confirmed whether `OVERVIEW` draws on the same budget as `GLOBAL_QUOTE`
- [ ] Decision recorded: proceed as specced, OR cut the symbol list, OR drop `name`/`market_cap`
- [ ] If exhaustion does not present as 200 + `Information`, ST-14's detection strategy is updated in writing
