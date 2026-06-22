# Design

## Approach

Treat issue `#13` as a closeout task because the existing branch/develop state already contains the MVP implementation and prior independent verification evidence.

The only implementation adjustment is the `.worktree/` default ledger rule:

```text
/srv/projects/develop/Avatar/.worktree/<slug>
  -> /srv/projects/develop/Avatar/temp/state/aegis_mesh_ledger.sqlite3
```

This keeps the local Web GUI board shared across Avatar development worktrees. Explicit `AEGIS_MESH_LEDGER_PATH`, `AVATAR_STATE_DIR`, and `GA_WORKSPACE_ROOT` overrides continue to take precedence.

## Alternatives Rejected

- Per-worktree default ledger files: rejected because the board would fragment task visibility.
- Expanding `#13` with control-plane features: rejected because user accepted MVP closeout; those belong in future issues.
- Moving legacy parent-level worktrees: rejected as out of scope for this closeout.
