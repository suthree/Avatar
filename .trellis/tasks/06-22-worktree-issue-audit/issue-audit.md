# Issue and Worktree Audit

## Worktree Findings

- `git worktree list` for Avatar reports only the main checkout: `/srv/projects/develop/Avatar` on `develop`.
- No Avatar `.worktree/` directory exists yet.
- Parent-level `/srv/projects/develop/Avatar_worktrees/jiuwei-issue42-avatar-codex` exists, but it is a `suthree/JiuWei` worktree registered under `/srv/projects/develop/JiuWei/.git/worktrees/jiuwei-issue42-avatar-codex`, not an Avatar worktree.
- Parent-level `*_worktrees` directories are legacy layout. New Avatar development worktrees should use `.worktree/<task-or-branch-slug>` inside the Avatar repo.

## Issue Close-Readiness

Issues `#1` through `#12` were all open on `suthree/Avatar` before this audit. After user approval, they were closed as superseded/not-planned with a triage comment.

Current repo evidence:

- `harness/` does not exist.
- `tests/harness/` does not exist.
- `docs/workflows/` does not exist.
- `docs/superpowers/` no longer exists.
- The source branch referenced by the issues, `origin/codex/genericagent-personal-agent-os-plan`, is not present on the remote.
- The plan was migrated into `.trellis/tasks/05-22-personal-agent-harness/`; that task explicitly says the harness package has not been implemented.

Recommendation used:

- Do not close `#1` through `#12` as completed.
- Close them together as superseded/migrated to Trellis because the project no longer wants those GitHub issues as active implementation tickets.
- If implementation tracking should remain in GitHub, keep them open or replace them with a smaller refreshed issue set derived from `.trellis/tasks/05-22-personal-agent-harness/`.

## Per-Issue Recommendation

| Issue | Title | Recommendation |
| --- | --- | --- |
| `#1` | Personal Agent Harness: add contract dataclasses | Close only as superseded by Trellis; not implemented. |
| `#2` | Personal Agent Harness: add file-backed store | Close only as superseded by Trellis; not implemented. |
| `#3` | Personal Agent Harness: persist desktop session manifests | Close only as superseded by Trellis; not implemented. |
| `#4` | Personal Agent Harness: add run ledger for prompt execution | Close only as superseded by Trellis; not implemented. |
| `#5` | Personal Agent Harness: add process runtime adapters | Close only as superseded by Trellis; not implemented. |
| `#6` | Personal Agent Harness: add worktree lease manager | Close only as superseded by Trellis; not implemented. Future worktree root should be `.worktree/`, not parent-level `*_worktrees`. |
| `#7` | Personal Agent Harness: add capability manifest reader | Close only as superseded by Trellis; not implemented. |
| `#8` | Personal Agent Harness: add memory promotion queue | Close only as superseded by Trellis; not implemented. |
| `#9` | Personal Agent Harness: integrate development session worktree allocation | Close only as superseded by Trellis; not implemented. The issue body's `temp/worktrees` default is stale relative to the new `.worktree/` rule. |
| `#10` | Personal Agent Harness: add lightweight workflow templates | Close only as superseded by Trellis; not implemented as `docs/workflows/`. |
| `#11` | Personal Agent Harness: integrate conductor run ledgers | Close only as superseded by Trellis; not implemented. |
| `#12` | Personal Agent Harness: end-to-end smoke verification | Close only as superseded by Trellis; final implementation milestone has not run because implementation issues are not complete. |

## Suggested Closure Comment

```text
Closing as superseded by the Avatar Trellis migration, not as completed implementation.

The historical Personal Agent Harness plan and checklist now live at:
`.trellis/tasks/05-22-personal-agent-harness/`

Current repo state does not contain the planned `harness/` package or `tests/harness/`. Future harness work should start from the Trellis task or a refreshed issue set. New Avatar local development worktrees should default to `.worktree/<task-or-branch-slug>` under the repo root.
```
