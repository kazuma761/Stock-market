# Backlog — Dockerized Stock Market Data Pipeline

Generated from [`../dockerized-stock-pipeline.prd.md`](../dockerized-stock-pipeline.prd.md) (intent) and
[`../architecture.md`](../architecture.md) (how). 24 tickets across 8 phases.

The PRD is product-level by design and has no literal "Implementation Phases" section — the phase grouping
below is derived from the architecture doc's decisions, each of which traces back to a PRD section.

## Phase 0 — De-risk (do first, blocking)
| # | Ticket |
|---|---|
| ST-01 | [Spike: confirm Alpha Vantage free-tier limits and response shapes](01-spike-alpha-vantage-limits.md) |

## Phase 1 — Subtraction
| # | Ticket |
|---|---|
| ST-02 | [Delete the crypto ingestion path](02-delete-crypto-path.md) |
| ST-03 | [Delete the dynamic client-loading factory layer](03-delete-client-factory.md) |
| ST-04 | [Remove Superset assets and the FMP provider path](04-remove-superset-and-fmp.md) |
| ST-05 | [Drop pysertive and the test-helper namespace leak](05-drop-pysertive-and-mock-leak.md) |
| ST-06 | [Untrack `.env`, ship `.env.example`](06-untrack-env.md) |

## Phase 2 — Runtime & single-command cold start
| # | Ticket |
|---|---|
| ST-07 | [Collapse to one Postgres container](07-single-postgres.md) |
| ST-08 | [Slim the compose topology to four services](08-slim-compose.md) |
| ST-09 | [Reconcile dependency pins with the built image](09-reconcile-pins.md) |

## Phase 3 — Data model & idempotency
| # | Ticket |
|---|---|
| ST-10 | [Rewrite `init.sql`: drop `cryptos`, add unique constraint](10-init-sql-unique-constraint.md) |
| ST-11 | [Convert `storage.py` to an idempotent upsert](11-storage-upsert.md) |

## Phase 4 — Fetching & error handling
| # | Ticket |
|---|---|
| ST-12 | [Create `core/stock_fetcher.py` (`GLOBAL_QUOTE`)](12-stock-fetcher-global-quote.md) |
| ST-13 | [Add the `OVERVIEW` call and parser](13-overview-parser.md) |
| ST-14 | [Detect quota exhaustion as a distinct, non-retried condition](14-quota-exhaustion-branch.md) |
| ST-15 | [Handle unknown symbol and unreachable API separately](15-bad-symbol-and-network-branches.md) |
| ST-16 | [Partial-failure posture: store the good, surface the bad](16-partial-failure-signal.md) |

## Phase 5 — Orchestration
| # | Ticket |
|---|---|
| ST-17 | [Rewrite the DAG as a two-task chain](17-rewrite-dag.md) |
| ST-18 | [Task-level retries excluding quota errors](18-airflow-retries.md) |
| ST-19 | [Slim `config.json` to symbols + schedule](19-slim-config.md) |

## Phase 6 — Tests & quality gates
| # | Ticket |
|---|---|
| ST-20 | [Rewrite the test suite](20-rewrite-tests.md) |
| ST-21 | [Decide and fix CI workflows + pre-commit](21-ci-and-precommit.md) |

## Phase 7 — Documentation & validation
| # | Ticket |
|---|---|
| ST-22 | [Rewrite `README.md` for a cold start](22-rewrite-readme.md) |
| ST-23 | [Redraw or remove the architecture diagram](23-architecture-diagram.md) |
| ST-24 | [Cold-start validation run on a clean machine](24-cold-start-validation.md) |

## Dependency notes
- **ST-01 gates ST-13, ST-14 and ST-19** — the quota finding decides the symbol count and the detection strategy.
- **ST-10 gates ST-11** — the constraint must exist before the upsert can target it.
- **ST-24 is the hypothesis test**, not a formality. Failing it means fixing the README and re-running.
- Phases 1–3 are independent of each other and can run in parallel worktrees; phase 4 depends on 1 and 3.

## PRD open questions still unresolved
Each is assigned to a ticket rather than left floating:
- Alpha Vantage limit + quota response shape → **ST-01**
- Which symbols ship → **ST-19**
- `.env` history scrub → **ST-06**
- Keep the CI workflows → **ST-21**
- Architecture diagram → **ST-23**
- "Succeeded with omissions" surfacing → **ST-16**
- `volume INT` width → **ST-10**

*Next: each phase is now runnable as a PIV loop — `piv-plan-implementation` on a ticket, then `piv-implement`.*
