# Aegis Mesh Workflow

Aegis Mesh is Avatar's task-control surface. It connects IM sessions, task lifecycle, ledger persistence, board visibility, Codex artifacts, and Avatar verification.

## Session and Task Rules

- A Feishu session id must distinguish group routes from private routes.
- One session may have only one active task.
- Different sessions may run independently.
- `/stop` must affect only the target session.
- Progress events should be concise result notes, not raw turn logs.

## Ledger Rules

The ledger mirrors sessions, tasks, events, and safe artifacts. Safe artifact keys include:

- `project`
- `repo`
- `github_issue_url`
- `github_issue_number`
- `branch`
- `worktree`
- `codex_pid`
- `log_path`
- `answer_path`
- `handoff_path`
- `verification_artifact`
- `verification_artifacts`
- `verification_path`
- `avatar_verification_path`

Do not render or commit secret metadata, raw log previews, credentials, tokens, or local config values.

## Board Phases

Use these phase names for task metadata and board grouping:

- `intake`
- `issue_ready`
- `codex_running`
- `codex_done`
- `avatar_verify`
- `blocked`
- `done`
- `failed`
- `stopped`

The board also groups blocked tasks as `blocked/requires_user`, completed tasks as `done/completed`, and terminal failures as `failed/stopped`.

## Health Signals

Avatar must investigate before marking a task done when the board indicates:

- stale running task
- process not found
- missing handoff
- overdue verification
- requires user
- repo or worktree conflict

Health signals are not final conclusions; they are prompts for verification.

## Review Gate

Before Avatar closes a task:

1. Compare output against the original request and Trellis task.
2. Check branch/worktree, handoff, answer path, and verification artifact when present.
3. Confirm tests or skipped-check reasons.
4. Confirm no secrets or raw logs are exposed.
5. Write only durable, verified learning to memory or specs.
