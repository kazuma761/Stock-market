# ST-13 · Add the `OVERVIEW` call and parser for `name` and `market_cap`

**Phase:** phase-4-fetch · **Depends on:** ST-01, ST-12
**Source:** architecture.md "Data model" — a response shape nothing currently reads

## Description
`name` and `market_cap` are `NOT NULL` and were supplied by FMP, which is being removed. `GLOBAL_QUOTE` has
neither, so each symbol costs `GLOBAL_QUOTE` + `OVERVIEW` = 2 calls (6/day at three symbols).

## Acceptance criteria
- [ ] `OVERVIEW` is called per symbol and its payload parsed for `Name` and `MarketCapitalization`
- [ ] Parsed values merge with the `GLOBAL_QUOTE` result into one record per symbol
- [ ] `market_cap` is coerced to the column's numeric type, with a non-numeric value handled rather than raised
- [ ] Per-run call count is asserted or documented against the limit confirmed in ST-01
- [ ] A test covers a known-good `OVERVIEW` payload and one with a missing field
