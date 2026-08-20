# Avatar fork maintenance

## Purpose

Avatar is a maintained downstream fork of [GenericAgent](https://github.com/lsdefine/GenericAgent). It keeps only deliberate, verified local extensions while periodically integrating upstream improvements.

This document governs source synchronization. It does **not** authorize a runtime deployment or an IM integration.

## Remote roles

- `origin`: Avatar's repository.
- `upstream`: `lsdefine/GenericAgent`.
- `main`: the reviewed Avatar baseline.
- A feature or synchronization task uses an Issue-linked branch in `.worktree/`.

## Synchronization procedure

1. Inspect the current checkout, branches, worktrees, open Issues/PRs, and remote divergence.
2. Fetch the upstream remote without changing `main`.
3. Create an Issue and a project-local worktree from Avatar `main`.
4. Merge `upstream/main` with `--no-commit` so every conflict can be reviewed.
5. Apply these resolution defaults:
   - Current upstream wins for core execution, LLM client behavior, generic frontends, packaging, templates, and upstream documentation.
   - Preserve a downstream addition only when its purpose is still clear, it remains API-compatible, and it has a verification path.
   - Remove unreferenced historical artifacts rather than leaving them in the active tree; Git history remains the audit record.
6. Run source-only verification:

   ```bash
   git diff --check
   python -m compileall -q .
   git diff --name-only --diff-filter=U
   ```

7. Commit the synchronization merge, push the branch, and open a PR. Large historical synchronizations are not merged into `main` automatically.

## Runtime boundary

Source synchronization must not reuse another GA instance's credentials, persistent workspace, HTTP port, or IM bot. Before any future Avatar runtime is started, create a separate runtime plan covering:

- isolated `mykey.py` / credential source;
- isolated workspace and logs;
- a distinct local port and reverse-proxy decision;
- a distinct test IM application or a controlled cutover plan;
- model, configuration, and inbound/outbound IM smoke checks.

## Follow-up work

Product or frontend features—including the Feishu delivery-envelope work—remain separate Issue slices after the fork baseline is synchronized. They should not be folded into an upstream merge merely because related historical code exists.
