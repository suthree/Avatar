# PRD

## User Request

The user asked Avatar to use its own memory, understand the existing Aegis Mesh workflow, and update itself by adding basic development environment and Trellis files.

## Goal

Initialize an Avatar-native Trellis structure that makes the Aegis Mesh workflow, development environment, Codex dispatch contract, and memory promotion rules discoverable to future agents.

## Scope

- Add `.trellis/config.yaml`.
- Add `.trellis/workflow.md`.
- Add `.trellis/spec/` guidance for development environment, Aegis Mesh, Codex goals, and memory promotion.
- Add a small Trellis task validator.
- Record this work under `.trellis/tasks/06-22-avatar-trellis-dev-environment/`.
- Add lightweight repo/doc entrypoints if missing.

## Non-Goals

- No runtime code changes.
- No Feishu, Aegis Mesh, or ledger schema changes.
- No dependency installation.
- No memory file mutation beyond documentation references.

## Acceptance Criteria

- Trellis files exist in the Avatar repo root.
- Development setup commands reflect current `pyproject.toml`, README, scripts, and tests.
- Aegis Mesh phases and safe artifact boundaries reflect current code and tests.
- The task validates with `.trellis/scripts/task.py`.
- `git diff --check` passes.
