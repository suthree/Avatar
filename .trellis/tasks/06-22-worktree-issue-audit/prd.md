# PRD

## User Request

梳理当前项目中的本地 worktree 和远程 open issue，判断 1-12 号 issue 是否都可以关闭。用户同时明确本地开发 worktree 默认应放在项目下的 `.worktree/` 目录，而不是在父级目录使用 `XXX_worktree` 命名。

## Scope

- Inspect local `git worktree` state.
- Inspect local parent-directory worktree-like folders.
- Inspect GitHub issues `#1` through `#12`.
- Record the `.worktree/` convention in project rules.

## Non-Goals

- Do not close GitHub issues without explicit user approval.
- Do not move existing worktrees during this audit.
- Do not modify runtime code.

## Acceptance Criteria

- Worktree findings are available in the final handoff.
- Each issue from `#1` to `#12` has a close-readiness recommendation.
- Project guidance prefers `<repo>/.worktree/<name>` for local development worktrees.
- Trellis validation passes.
