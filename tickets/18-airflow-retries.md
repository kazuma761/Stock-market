# ST-18 · Task-level retries with exponential backoff, excluding quota errors

**Phase:** phase-5-orch · **Depends on:** ST-17, ST-14
**Source:** architecture.md "Other calls — retries belong to Airflow, not hand-rolled loops"

## Description
Transient network failure should retry; quota exhaustion should not, because retrying it just burns the
remaining quota. Retries live in Airflow task config, not in hand-rolled loops inside the fetcher.

## Acceptance criteria
- [ ] `retries` and `retry_delay` with exponential backoff set on the fetch task
- [ ] No hand-rolled retry loop remains in `stock_fetcher.py`
- [ ] A quota-exhausted run does not consume retry attempts
- [ ] Retry behaviour is stated in one line in the README's error-handling section
