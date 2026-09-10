# ST-21 · Decide and fix CI workflows and pre-commit against the slimmed tree

**Phase:** phase-6-quality · **Depends on:** ST-20
**Source:** PRD §10 open question, architecture.md open questions

## Description
`run_tests.yml`, `run_black.yml` and the pre-commit config are good code-quality evidence — but only if they
pass against the slimmed tree. A red badge is worse than no badge.

## Acceptance criteria
- [ ] Decision made and recorded: keep or drop
- [ ] If kept: both workflows pass green on the branch
- [ ] If kept: pre-commit runs clean on a fresh `pre-commit run --all-files`
- [ ] If kept: workflows reference only paths that still exist
- [ ] If dropped: the files are deleted and any README badge removed
