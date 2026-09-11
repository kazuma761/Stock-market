# ST-06 · Untrack `.env`, ship `.env.example`, restore the gitignore rule

**Phase:** phase-1-subtract
**Source:** PRD §2 (dead weight), §7 (secrets metric), architecture.md "Boundaries & contracts"

## Description
`.env` is tracked because its `.gitignore` rule is commented out. Values are placeholders so nothing has leaked,
but the brief has an explicit security requirement and this contradicts it visibly.

## Acceptance criteria
- [ ] `.gitignore` rule for `.env` uncommented
- [ ] `git rm --cached .env` applied; `git ls-files` no longer lists it
- [ ] `.env.example` committed with every required variable present and no real values
- [ ] `.env.example` documents `ALPHA_API_KEY` plus the DB credentials, and nothing else
- [ ] README's setup step points at copying `.env.example` → `.env`
- [ ] History-scrub question (PRD §10) resolved either way and the decision noted in the PR
