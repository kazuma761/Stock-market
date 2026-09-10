# ST-10 · Rewrite `init.sql`: drop `cryptos`, add the unique constraint

**Phase:** phase-3-data · **Depends on:** ST-02 · **Blocks:** ST-11
**Source:** PRD §6 item 5, architecture.md "Data model — idempotency"

## Description
`init.sql` has no unique constraint today, so re-runs duplicate rows. This is new work, not a cut: the PRD's
"0 duplicate rows" metric currently has no mechanism behind it.

## Acceptance criteria
- [ ] `market_data.stocks` keeps its shape: `symbol · name · market_cap · volume · price · change_percent · date_collected`
- [ ] A unique constraint on `(symbol, date_collected)` is present
- [ ] The `cryptos` table is gone
- [ ] `volume` width decision made (PRD/arch open question: `INT` caps at ~2.1B) — widened or explicitly noted as a known limit
- [ ] Schema applies cleanly on a fresh volume
