# Implementation

## Checklist

- [x] Read `grill-me` skill instructions.
- [x] Search Codex memory for Trellis governance precedent.
- [x] Inspect Avatar Aegis Mesh code, docs, tests, and setup files.
- [x] Add Avatar Trellis config and workflow.
- [x] Add Avatar Trellis specs for development environment, Aegis Mesh, Codex goals, and memory promotion.
- [x] Add root and docs entrypoints.
- [x] Add Trellis task validator.
- [x] Run Trellis validation.
- [x] Run formatting/diff checks.

## Validation Plan

```bash
python3 .trellis/scripts/task.py validate 06-22-avatar-trellis-dev-environment
git diff --check
uv run python -m unittest discover -s tests -v
```

Runtime tests are optional for this docs/config-only task, but useful because the new specs cite the current Aegis Mesh and LLM environment contracts.
