# PRD

## User Request

继续挖 GitHub issue `#13`，使用 `grill-me` 确认需求。用户确认后，将 `#13` 收敛为 MVP 收尾：不扩大 scope，只补齐 `.worktree/` 约定、重新验证、记录证据，并关闭 issue。

## Scope

- Verify `suthree/Avatar#13` current state and existing MVP implementation.
- Preserve GitHub Issues as fact source and Trellis as local work record.
- Ensure local development worktrees default to `<repo>/.worktree/<task-or-branch-slug>`.
- Ensure Aegis Mesh ledger defaults are compatible with `.worktree/` based development.
- Re-run focused tests, full tests, Python compile checks, Trellis validation, diff check, and local Web GUI smoke.
- Post evidence back to `suthree/Avatar#13` and close it.

## Non-Goals

- Do not add destructive Web GUI controls such as stop, retry, resume, merge, or deploy.
- Do not add public network exposure, authentication, scheduler, watchdog, or GitHub write-back automation.
- Do not move legacy parent-level worktrees during this task.
- Do not commit local runtime state, logs, secrets, or generated GUI smoke output.

## Acceptance Criteria

- `#13` remains scoped to the accepted MVP.
- `.worktree/<slug>` runs share the main Avatar `temp/state/aegis_mesh_ledger.sqlite3` by default, while environment overrides still work.
- Tests and examples no longer use parent-level `Avatar_worktrees` for issue `#13`.
- Verification evidence is recorded in `verification.md` and GitHub issue `#13`.
- Issue `#13` is closed after evidence is posted.
