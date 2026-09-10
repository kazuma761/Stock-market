# ST-03 · Delete the dynamic client-loading factory layer

**Phase:** phase-1-subtract
**Source:** PRD §8, architecture.md "Recommended approach — B, flatten to the brief's nouns"

## Description
`ApiClientFactory` works, but it is indirection over a single asset type. Scalability is argued instead through
a config-driven symbol list (ST-19). Removing the layer means the evaluator traverses one code path, not four
objects. `custom/api_client.py` is additionally broken — it imports `core.base_api_client`, which does not exist.

## Acceptance criteria
- [ ] `custom/` deleted in full
- [ ] `core/base_api.py` deleted
- [ ] `core/data_processor.py` deleted
- [ ] The client registry removed from `mdp_config.json`
- [ ] Nothing in the tree imports any deleted module (`grep -r "base_api\|data_processor\|custom\."` is clean)
