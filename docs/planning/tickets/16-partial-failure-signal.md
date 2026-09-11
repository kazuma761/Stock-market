# ST-16 · Partial-failure posture: store the good, surface the bad

**Phase:** phase-4-fetch · **Depends on:** ST-14, ST-15
**Source:** architecture.md "Failure posture" + "Missing pieces" #4 (no equivalent exists today)

## Description
Failures are swallowed today. The target posture is neither silent data loss nor all-or-nothing brittleness: a
failing symbol doesn't block its peers, successful symbols are written, and the run ends visibly non-green when
any symbol failed.

**Open question to resolve here:** how "succeeded with omissions" surfaces in the Airflow UI. Prefer a mechanism
that reads clearly without a custom operator.

## Acceptance criteria
- [ ] Successful symbols are persisted even when a peer symbol fails
- [ ] The run ends in a visibly non-green state when any symbol failed
- [ ] The chosen surfacing mechanism is documented in one line in the DAG or README
- [ ] A test covers a mixed run: some symbols succeed, at least one fails
- [ ] A fully-successful run is unambiguously green
