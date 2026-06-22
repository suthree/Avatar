# Design

## Chosen Structure

Use the DAYU governance pattern from prior memory, adapted to Avatar:

- `docs/` remains the stable documentation layer.
- `.trellis/spec/` becomes the concise agent-executable rule layer.
- `.trellis/tasks/` stores active and historical task records.
- `.trellis/workspace/`, `.trellis/.developer`, and `.trellis/.runtime` stay local-only.

## Why This Fits Avatar

Avatar already has `docs/GA_CODEX_LOOP.md`, which defines the controller/worker loop. The missing piece was a Trellis surface that agents can treat as current operating rules rather than prose-only docs.

Aegis Mesh already exists in code as:

- session/task lifecycle management
- Feishu route-aware session ids
- durable ledger mirroring
- board phases and safe artifact rendering
- health signals for verification

The Trellis spec captures those facts without changing code.

## Rejected Alternatives

- Putting active workflow rules only in `docs/`: this repeats the old problem of mixing stable docs and process state.
- Creating a large runtime framework: unnecessary for this docs/config task.
- Updating memory directly: this task records project rules in Trellis; memory writes require action-verified reusable facts and a separate deliberate change.
