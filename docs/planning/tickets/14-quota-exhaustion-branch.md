# ST-14 · Detect quota exhaustion as a distinct, non-retried condition

**Phase:** phase-4-fetch · **Depends on:** ST-01, ST-12
**Source:** PRD §6 item 4 & §9, architecture.md "Other calls"

## Description
Alpha Vantage signals quota exhaustion *inside a 200 response*, so status codes cannot detect it. Current code
would `KeyError` on `response["Global Quote"]`. This is one of the three concrete branches the error-handling
criterion is scored on — and it must not be retried, since retrying a quota error just burns quota.

## Acceptance criteria
- [ ] Quota exhaustion is detected from the response body shape confirmed in ST-01
- [ ] It raises/returns a condition distinguishable from "bad symbol" and "network error"
- [ ] The task log names the condition in plain language, not a stack trace
- [ ] Airflow does **not** retry this condition (see ST-18)
- [ ] A test drives the real captured exhausted payload through the code path
