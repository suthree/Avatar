# Avatar Trellis Workflow

This file turns `docs/GA_CODEX_LOOP.md` into executable operating rules for agents.

## Sources of Truth

- Stable facts: `docs/`.
- Agent rules: `.trellis/spec/`.
- Work records: `.trellis/tasks/`.
- Verified reusable memory: `memory/`, governed by `memory/memory_management_sop.md`.
- Runtime state: `.trellis/workspace/`, `temp/`, `run/`, `logs/`, and local ledger files.

Do not duplicate long docs inside specs. Specs should link to stable docs and state the rule an agent must follow before editing.

## Aegis Mesh Loop

The Avatar self-evolving loop is:

```text
IM -> GA/avatar -> GitHub Issue -> Trellis Task -> Codex goal -> PR/branch -> CI/tests -> Avatar review -> Memory/Trellis update
```

Use Aegis Mesh phases consistently:

- `intake`: request captured, scope still being clarified.
- `issue_ready`: GitHub Issue or lightweight Trellis record exists.
- `codex_running`: Codex is executing the goal.
- `codex_done`: Codex has produced a handoff, answer, branch, or artifact.
- `avatar_verify`: Avatar is checking outcome, tests, diff scope, and risk boundaries.
- `blocked`: user input, repo lock, missing credential, or approval is required.
- `done`: acceptance criteria and verification evidence are recorded.

Blocked tasks must include `blocker` and `requires_user` when user action is needed.

## Task Rules

For non-trivial work, create or update `.trellis/tasks/<task-id>/` before making broad edits. A task directory should include:

- `task.json`: identity, status, risk, sources, and acceptance criteria.
- `prd.md`: user request, scope, non-goals, constraints, and acceptance criteria.
- `design.md`: chosen approach and alternatives rejected.
- `implement.md`: checklist and validation plan.
- `verification.md`: evidence after checks run, when useful.

Run:

```bash
python3 .trellis/scripts/task.py validate <task-id>
```

## Done Rules

A task is done only when:

- The original request or accepted revised scope is satisfied.
- Tests or checks are recorded, or the skip reason is explicit.
- Changed files are within scope.
- Secrets and local runtime state are not tracked.
- Follow-up gaps are captured in the task, issue, or memory only when they are reusable and verified.
