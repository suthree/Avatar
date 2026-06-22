# Avatar Agent Guide

Avatar is the personal controller. Codex is the coding worker.

Before changing project behavior:

1. Read `docs/GA_CODEX_LOOP.md`.
2. Read `.trellis/workflow.md` and the relevant `.trellis/spec/*.md`.
3. For non-trivial work, create or update a `.trellis/tasks/<task-id>/` record before edits.

Boundaries:

- `docs/` holds stable user and developer documentation.
- `.trellis/spec/` holds executable rules for agents.
- `.trellis/tasks/` holds active or historical work records.
- `.trellis/workspace/`, `.trellis/.developer`, and `.trellis/.runtime` are local-only.
- `memory/` holds verified reusable SOPs; follow `memory/memory_management_sop.md` before memory changes.

Development:

- Prefer Python 3.11 or 3.12. The package allows `>=3.10,<3.14`; do not use Python 3.14.
- Keep dependencies tiered. Install extras only when the touched frontend needs them.
- Run targeted `unittest` discovery for the touched area, or full `uv run python -m unittest discover -s tests -v` before handoff when feasible.
- Do not put secrets, raw logs, generated files, or local runtime state into Trellis.
