# ST-02 · Delete the crypto ingestion path

**Phase:** phase-1-subtract
**Source:** PRD §8 (non-goals), architecture.md "Deleted outright"

## Description
The brief says "stock market data." Crypto ingestion is off-brief and carries a second API key (CoinMarketCap),
which directly works against the one-pasted-key cold start.

## Acceptance criteria
- [ ] `core/crypto_api_client.py` deleted
- [ ] Crypto tests deleted
- [ ] No remaining reference to crypto in `dags/`, `config`, `utils/`, or `README.md`
- [ ] `grep -ri crypto` over the tree returns nothing outside git history
- [ ] Remaining test suite still collects without import errors
