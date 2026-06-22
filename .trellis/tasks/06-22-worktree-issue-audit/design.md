# Design

## Approach

Use local Git and GitHub CLI as primary evidence:

- `git worktree list --porcelain` for registered worktrees.
- Parent-directory listing for historical `*_worktree` directories.
- `gh issue view` for issues `#1` through `#12`.

## Close-Readiness Criteria

Recommend closing an issue only when the issue is already closed, clearly superseded, already implemented with evidence, or no longer actionable. Keep open when implementation or verification evidence is missing.

## Worktree Convention

The project-local default is:

```text
.worktree/<branch-or-task-name>
```

Historical parent-level `*_worktree` directories should be treated as legacy unless deliberately retained.
