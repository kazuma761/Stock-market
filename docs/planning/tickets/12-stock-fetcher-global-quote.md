# ST-12 · Create `core/stock_fetcher.py` with `GLOBAL_QUOTE` fetch and parse

**Phase:** phase-4-fetch · **Depends on:** ST-01, ST-03
**Source:** PRD §6 item 3, architecture.md "Recommended approach" (the fetching-script deliverable)

## Description
The brief names "a fetching script" as a deliverable. This is that file — one module, self-locating from the
repo root, using `requests` against Alpha Vantage over a configurable symbol list.

## Acceptance criteria
- [ ] `core/stock_fetcher.py` exists and is the only module making HTTP calls
- [ ] `GLOBAL_QUOTE` is called per symbol from the configured list
- [ ] `price`, `volume`, `change_percent` parsed into a typed structure, not raw dicts passed onward
- [ ] The API key is read from the environment, never a literal or a file default
- [ ] Parsing is a pure function testable without network access
- [ ] A test covers a known-good payload end-to-end through the parser
