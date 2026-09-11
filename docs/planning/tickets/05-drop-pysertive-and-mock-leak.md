# ST-05 · Drop pysertive and stop test helpers leaking into the production namespace

**Phase:** phase-1-subtract
**Source:** PRD §8, architecture.md "What's actually there today"

## Description
`pysertive` wraps a one-line null check in a third-party decorator. Separately, `utils/__init__.py` does
`import *` from a module that imports `MagicMock`, so `mock_imports` test helpers land in the production
namespace — a code-quality reviewer notices both.

## Acceptance criteria
- [ ] The `pysertive` decorator removed from all call sites; the invariant expressed as plain Python where still needed
- [ ] `pysertive` removed from `requirements.txt`
- [ ] `utils/__init__.py` no longer star-imports test helpers
- [ ] No `MagicMock` import is reachable from production code
- [ ] Test suite still passes
