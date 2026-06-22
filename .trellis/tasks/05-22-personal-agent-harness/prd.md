# PRD

## Goal

Add a thin personal agent harness around GenericAgent so sessions, runs, worktrees, capabilities, and memory promotion are durable and isolated without changing the minimalist agent loop.

## Scope

- Session manifests.
- Run ledgers.
- File-backed harness store.
- Optional worktree leases for development sessions.
- Capability manifests and verification gates.
- Memory promotion queue.
- Later integrations with `frontends/desktop_bridge.py` and `frontends/conductor.py`.

## Non-Goals

- Do not turn GenericAgent into a large agent OS.
- Do not require GitHub Issues for every personal task.
- Do not install new dependencies by default.
- Do not change `agent_loop.py` in the first milestone.
- Do not write global memory automatically.

## Current State

This task is a migrated plan, not an active implementation. The repo currently has Aegis Mesh ledger/session code and tests, but the broader `harness/` package described in the plan has not been implemented.

## Acceptance Criteria

- The migrated design and implementation plan remain recoverable.
- Future implementation starts from this Trellis task or a new task that references it.
- Stable harness rules are available in `.trellis/spec/personal-agent-harness.md`.
