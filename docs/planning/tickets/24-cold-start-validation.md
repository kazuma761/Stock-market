# ST-24 · Cold-start validation run on a clean machine

**Phase:** phase-7-docs · **Depends on:** every preceding ticket
**Source:** PRD §4 (the RIGHT/WRONG condition), §7, architecture.md "Spike 2"

## Description
This is the hypothesis test, not a checklist item. Someone unfamiliar clones the repo onto a machine with
nothing but Docker and follows only the README.

**Decision rule:** any question asked, or any file edited that the README did not specify, means the hypothesis
failed — fix the README before submitting.

## Acceptance criteria
- [ ] Docker cache cleared, repo cloned fresh, README followed literally
- [ ] Time from `git clone` to rows visible in Postgres recorded, and under 15 minutes
- [ ] Exactly one manual step was required
- [ ] Zero failed tasks on the first triggered run
- [ ] Re-trigger produces zero duplicate rows (`count(*)` before/after)
- [ ] `git ls-files` shows no secrets
- [ ] Substantive Python (excluding tests) measured and inside ~300–450 lines
- [ ] Files needed to understand the flow counted, and ≤ 5
- [ ] Any friction found is fixed and the run repeated
