# FuXi State Reporting SOP

Imported for Avatar on 2026-07-07 from the latest Hermes `fuxi-state-reporting` skill.

## Avatar integration note

Use this as Avatar's project-local FuXi skill when coordinating long-running Hermes/Codex/FuXi development tasks, recovering from context resets, deciding what to report to users, or closing workflow/documentation state. It complements, and does not replace:

- `memory/fuxi_dev_workflowd_boundary_sop.md` for Avatar/dev-workflowd authority boundaries;
- `memory/fuxi_codex_dispatch_sop.md` for Codex dispatch/status boundaries.

Keep the same safety rules as Avatar memory: do not store secrets, one-off run directories, full logs, PIDs, or unverified chat claims. Promote only stable workflow lessons.

---

# FuXi State & Reporting

## Purpose

Keep long-running project work recoverable without relying on chat context, while keeping user reports short and outcome-focused.

FuXi roles:
- User is upstream product owner.
- Hermes is user-facing coordinator and decision router.
- Codex/subagents are implementation workers.
- External artifacts are the durable source of truth: repo, branch/worktree, GitHub Issue/PR, docs/Trellis, CI, deployment logs, runtime status.

## Core rule

Do not expose routine implementation chatter to the user. Report only:
1. progress gates,
2. final delivery,
3. user-decision blockers,
4. material risk or acceptance-impacting changes.

## State model

For each active task, maintain or reconstruct this compact state:

```plain
当前任务：one-sentence outcome
阶段：需求确认 / 方案 / 实现 / 验证 / 发布 / 观察 / 完成
事实源：issue/pr/branch/worktree/docs/deploy target
已完成：only acceptance-level outcomes
证据：tests/CI/health check/user-visible artifact
未完成：remaining acceptance-level work
阻塞：only if user/Hermes decision needed
下一步：single next coordinator action
风险：only material risks
```

Prefer writing state into the task's durable artifact:
- GitHub Issue comment for issue-driven work.
- PR description/comment for PR-driven work.
- Project doc/Trellis when it is the project’s active planning artifact.
- Short session summary only when no project artifact exists yet.

## Project baseline hygiene audit

Use this when the user asks to “梳理干净” a project’s initial development environment, especially before new FuXi/Codex work:
1. Start read-only unless the user explicitly authorized cleanup. Locate/clone the repo, then inspect git status, remotes, default branch, open PRs, open issues, worktrees, and unmerged remote branches.
2. Confirm the project-specific trusted context chain before treating docs as facts: `AGENTS.md`/project guide, README, docs index, backend/frontend README, then only task-relevant plans. Mark historical plans/old workflow folders as background, not truth.
3. Check collaboration substrate explicitly: whether Trellis CLI exists, whether `.trellis/` exists in current branch and relevant remote branches, and whether issue-driven workflow docs already exist. Do not run `trellis init` on main as a “check”; it is an infrastructure-changing action and should be a scoped issue/branch/worktree task.
4. Inventory GitHub issues by dependency, blocker, and whether comments show completed work that was never merged/closed. Compare branch evidence (`main`, `develop`, feature branches) against issue comments; a completed comment on an unmerged branch is not current main truth.
5. Verify the current baseline with the project’s documented tests/builds after installing normal dependencies if needed. Report real outputs and note dependency/security audit warnings as follow-up risks, not automatic fixes.
6. Recommend a cleanup order that preserves traceability: create/confirm a cleanup issue, use a project-local `.worktree/`, reconcile unmerged branches/docs, then close/update stale issues with evidence. Avoid deleting history or initializing new workflow tools without explicit confirmation.

## Baseline / environment cleanup audit

When the user asks to “梳理干净”, “初始开发环境”, “确认文档/Trellis/Issue”, or otherwise wants a FuXi project reset before development, do an audit before implementation:
1. Local repo baseline: canonical repo path, current branch/upstream, dirty status, worktrees, local/remote branch residue, and whether the current checkout is on the intended base branch.
2. Project context artifacts: root agent entry, README/docs overview, engineering workflow docs, historical docs/archive markers, and any deprecated backlog entry (`todo.md`, old `docs/plans/`, etc.) that could pollute future context.
3. Trellis/FuXi state: `.trellis` install/config/spec/scripts, active task, active vs archived task list, task status drift against GitHub Issues/PRs, and Codex/agent hooks when relevant.
4. GitHub source of truth: open Issues, open PRs, stale pushed branches without PRs, recently closed canonical backlog items, CI/check availability, and issue comments that record blockers or handoffs.
5. Development environment readiness: language/tool versions, dependency directories, env-file presence, compose/services/ports, and minimal smoke tests from the correct working directory.
6. Report a concise cleanup queue: what is already clean, what is drifted, what is safe to clean automatically, and what requires user decision because it affects deploy/payment/RBAC/data/production or could discard work.

Do not start feature implementation from a drifted checkout. If the main checkout is on a leftover feature/deploy branch, surface that as the first cleanup decision: preserve via PR, park it in a worktree, or return to the base branch.

## FuXi/Trellis baseline check

Before starting FuXi/Trellis project work in a repository, first verify the project is safe to use as context:
1. Check whether Trellis is installed and tracked (`.trellis/workflow.md`, `.trellis/fuxi-context.md`, `.agents/skills/`, `.codex/` when Codex is used). If missing, install/adopt Trellis before normal implementation work unless the user explicitly opts out.
2. Confirm current project documents are archived into the right layers: durable facts in `README.md` / `docs/`, task state in GitHub Issue / `.trellis/tasks/` / `plans/`, historical materials in archive or deleted from the active context path.
3. Search for stale historical docs or old server/deploy workflow claims that conflict with current facts (for example local Docker build vs GHCR/GitHub Actions, old secrets layout, Mastro vs FuXi/Trellis). Resolve these before using the repo as implementation context.
4. If a historical file is clearly useless, conflicting, or its audit value is already preserved by Git history / GitHub Issues / PRs, prefer deleting it outright instead of keeping it as “historical reference.” Archive only when the content is still useful for future decisions and can be placed outside default active context. Do not leave contradictory active documents that can steer agents down the wrong path.

## Context reset recovery

When a session resets or the user says “继续刚才任务”:
1. Do not guess from memory.
2. Reconstruct from external facts first:
   - repo git status, branch, worktree, recent commits;
   - GitHub Issue/PR comments and CI;
   - project docs/Trellis;
   - deployment/process/log/health state if relevant.
3. Use session_search only as secondary context for prior discussion.
4. Produce a compact state snapshot before continuing if the next action is non-trivial.

## Project environment cleanup / FuXi-Trellis adoption

When the user asks to “梳理干净” a project’s initial development environment, do not stop at inventory. Actively reconcile the repo with the current FuXi project baseline:

1. Inspect current branch/worktree, open Issues/PRs, docs indexes, Trellis presence, and deployment/runbook claims.
2. Treat the user’s correction about the current baseline as authoritative over stale repo docs. If docs say the opposite, update or archive them instead of repeating them.
3. If the project is supposed to use Trellis and `.trellis/` is absent, initialize/adopt Trellis in a project-local branch/worktree, track `.trellis/`, `.agents/skills/`, and relevant `.codex/` helpers, and add a project context manifest such as `.trellis/fuxi-context.md`.
4. Put project-local workflow facts in Trellis/AGENTS/docs entrypoints: `AGENTS.md` should point agents to `.trellis/workflow.md`, `.trellis/fuxi-context.md`, current docs, Issues/PRs, and task artifacts.
5. For deployment baseline disputes, verify against current cross-project convention and live artifacts before editing. In the WanXiang/JiuWei/BaiZe family, the corrected baseline is GitHub Actions + GHCR with runtime config under `/srv/secrets/apps/<Project>.<env>.env`; server local build is a fallback, not the default path.
6. After cleanup, run both workflow smoke checks (Trellis scripts/help/context) and project checks (deploy contract tests, compose rendering, Django checks, migration dry-run as applicable) before reporting.

## Proactive FuXi iteration control

When the user has delegated project momentum to Hermes under FuXi, Hermes should actively choose the next valuable slice instead of waiting for user confirmation on every low-risk step.

When the user confirms a broad architecture or stack direction, first run a low-risk architecture-direction slice before implementation: create a GitHub Issue, use a project-local `.worktree/`, write/update active architecture docs and Trellis/FuXi context, verify with existing tests plus `git diff --check`, PR/merge if safe, then clean the worktree. See `references/architecture-direction-slice.md` for the concrete pattern.

Default branch/environment convention:
- `main` maps to production and `develop` maps to alpha; both are protected branches and must not be deleted.
- Feature work normally starts from `develop`, uses a dedicated branch or project-local `.worktree/`, maps to one GitHub Issue, merges by PR, and closes the Issue only after the accepted slice is merged/verified.
- Merging into `main`, production deploy/data/secrets, or changing protected branch policy remains an explicit high-risk gate.

Default decision policy:
- If a slice is low-risk, scoped to repo/docs/tests, and verifiable locally, proceed: create/update the issue, open a project-local `.worktree/` from the intended base branch (`develop` by default for feature/alpha work), dispatch Codex/subagents if useful, verify independently, PR/merge when green, clean the worktree, and record evidence.
- If an external dependency is unavailable (alpha runtime, DNS, upstream data service, webhook secret, browser/UAT target), do not stall the whole project. Record that issue as environment-blocked with evidence, then switch to the next independent slice that advances the product.
- Keep high-risk gates explicit: production deploy/data, secrets, payment/order/resource delivery, RBAC/admin/security boundary, irreversible changes, database migrations/backfills/deletes, and real notification sends still require user confirmation or a clearly authorized prior policy.
- Prefer closing loops over leaving artifacts open: if a hygiene/docs/code slice is verified and within the auto-merge boundary, merge and clean it before reporting.

When Codex returns questions, Hermes should answer from repo docs/code/issues/memory whenever possible. Only forward to the user when the answer is genuinely a product/security/data/permission/deployment decision or materially uncertain.

## Coding and reporting compression overlay

Apply these defaults during FuXi work unless the user asks for normal mode or fuller detail:

- Coding/implementation choices follow `public:ponytail` principles: understand the real flow first, then choose the smallest working change; reuse existing code, stdlib, native platform features, and installed dependencies before adding abstractions or new packages.
- Avoid speculative scaffolding. Prefer deletion, reuse, one shared root-cause fix, and one minimal runnable check for non-trivial logic.
- User-facing reports follow `public:caveman` principles: preserve Simplified Chinese, remove filler/tool narration/raw logs, keep only gates, blockers, final delivery, and material risks.
- Pairing rule: `ponytail` governs what to build; `caveman` governs how to report it.
- Use `public:headroom` only for context/tool-output compression scenarios; it is not a substitute for concise summaries. If Headroom compressed markers appear, retrieve originals instead of guessing.
- Do not compress away safety: security, RBAC/admin, payment/order/resource delivery, secrets, production/data, migrations, irreversible actions, and ambiguous multi-step instructions still require explicit clear wording and user decisions when needed.

## Codex/subagent message triage

When Codex or a subagent reports back, classify it:

- `silent_update`: routine progress, logs, implementation detail, minor test output. Record internally/artifact if useful; do not notify user.
- `progress_gate`: a major phase completed or acceptance criterion verified. Send a short progress note.
- `blocked_question`: requires product/security/data/deployment decision. Ask the user with clear options and a recommendation.
- `risk_alert`: material risk, failed verification after alternatives, destructive/irreversible action, production/security/payment/data concern. Notify user.
- `final_delivery`: requirement completed and verified. Send final result with evidence and any user action needed.

## User-facing report formats

### Progress gate

```plain
进度：<阶段完成>
结果：<用户可理解的完成情况>
下一步：<我会继续做什么>
```

### Blocker

```plain
需要你决定：<问题>
推荐：<选项/做法>
影响：<不决定会卡住什么，或不同选项的影响>
```

### Final delivery

```plain
已完成：<最终交付>
验证：<关键证据，测试/CI/健康检查/可访问地址>
还需你做：<如无则写“无”>
```

## Reporting constraints

- Do not include branch names, issue numbers, commits, deploy logs, or detailed file lists unless the user asks or they are needed as evidence.
- Do not forward raw Codex logs to the user.
- Do not report every implementation step.
- If the user asks for detail, provide expandable detail after the concise summary.
- If production, secrets, RBAC/admin, payments/orders/resource delivery, irreversible operations, database migrations, or insufficient verification are involved, stop and ask before proceeding.

## Baseline cleanup execution after audit

When the user agrees to “把前置工作准备好 / 梳理干净后再汇报”, treat that as authorization to complete the low-risk baseline-cleanup loop rather than stopping at a plan:
1. Create or reuse a GitHub Issue as the durable coordination artifact with scope, acceptance criteria, and risk boundaries.
2. Create a project-local `.worktree/` branch from the intended base; add `.worktree/` to git ignore if needed so the main checkout stays clean.
3. Apply only baseline hygiene changes in this task: trusted-context docs, archive markers, Trellis/FuXi auxiliary files, stale local backlog relocation, issue/branch queue notes. Keep large feature implementation, deploy semantics, CI/CD, secrets, migrations, production, and real push-channel sends out of this cleanup PR unless separately authorized.
4. Initialize Trellis only inside the scoped branch/worktree, record the command and generated-file boundary, and state that Trellis assists FuXi/GitHub Issue state rather than replacing the issue source of truth.
5. Run the documented backend/frontend/Trellis validation and record real outputs. Dependency audit warnings are follow-up risks; do not run broad breaking fixes without a dedicated issue.
6. Commit, push, open PR, and if the change is low-risk documentation/workflow hygiene with green local verification and no protected boundary touched, merge it autonomously when the user has asked for the environment to be prepared. Then fast-forward main, delete/clean the branch and project-local worktree, update/close the cleanup issue with evidence, and only then report.
7. Final report should be concise: what baseline is now clean, verification evidence, remaining open issue queue, and user decisions still needed.

Pitfall: Do not leave the user with an open PR/worktree when they asked for preparation to be completed, unless a high-risk boundary or failed verification blocks autonomous merge.

## Project baseline cleanup / restart pass

Use this when the user asks to “梳理干净” a project, align it with FuXi/Trellis, or prepare a clean development baseline before new work.

Sequence:
1. Reconstruct external facts first: local repo branch/status/worktrees/remotes, project docs/AGENTS/README, Trellis tasks/specs/workspace, GitHub open issues/PRs, and runtime/dev environment status if relevant.
2. Separate findings into: safe auto-fix, high-risk/user-decision, and backlog/follow-up. Do not ask for confirmation for clearly safe docs/task/branch hygiene if the user has authorized autonomous cleanup.
3. Close or PR-merge outstanding low-risk hygiene branches before feature work. Keep each branch/PR single-purpose; never continue ordinary development from a leftover deploy/docs branch.
4. Fix Trellis/context pollution early: fill or remove placeholder specs, archive completed bootstrap/workflow tasks, and make `task.py list` show no stale active tasks unless a task is truly current.
5. Re-verify PR claims yourself before merging. For worktrees, copy/recreate local dependency environments only as a convenience; report the real commands that ran and avoid treating missing deps as a product failure.
6. After squash merges, sync `develop`, prune worktrees, delete local branches whose work is merged, and explicitly check whether same-repo remote branches were actually deleted; clean them if the merge command left them behind.
7. If a stale feature branch is fully subsumed by a broader cleanup branch, compare it with the cleanup branch first (`git log --left-right --cherry-pick old...new` or equivalent), then delete only the redundant local branch and leave the remote branch/PR decision explicit.
8. Deployment-baseline restoration is not ordinary docs hygiene. When cleanup reintroduces or changes GitHub Actions, GHCR, deploy scripts, secret layout, SSH deploy secrets, or runtime env authority, open a Draft PR with verification evidence and a clear merge gate instead of autonomously merging, even if local tests pass.
9. Before leaving the repo, move the canonical checkout back to the intended base branch (`develop`/`main`) so future agents do not start from a leftover feature/deploy branch; keep only the project-local worktree that corresponds to the open PR.
10. Leave high-risk issues open with precise next slices instead of over-closing: payment provider integration, callback endpoint behavior, admin/RBAC boundaries, migrations with runtime effect, production deploy/data, iOS signing, deployment baseline changes, and secrets need separate authorization or external inputs.

User-facing reporting for this cleanup class should still be gate/final only: summarize what was cleaned, what was verified, current clean baseline, and which open issues remain blocked by high-risk decisions.

See `references/project-baseline-cleanup.md` for a condensed runbook and command patterns from the JiuWei cleanup pass.

See `references/protected-branch-sync-drift.md` for the pattern where `main` and `develop`/alpha have drifted so far that a normal protected-branch sync becomes a large replacement-style diff. In that case, stop the actual sync, reset the worktree to a clean base, open a Draft docs-only strategy PR with measured drift and recommendations, and require explicit authorization before any protected-branch reset or large replacement merge.

See `references/active-context-document-cleanup.md` for the narrower pattern where Trellis/FuXi exists but old plans, superpowers docs, demo folders, or stale deployment runbooks must be deleted from active context so future agents are not polluted.

For a final active-context cleanup pass after an initial cleanup PR, also check for second-order residue: root `AGENTS.md` containing only a generated Trellis block and no project facts/safety gates; product docs linking to plans that were deleted in the cleanup; templates that still allow local issue IDs; agent templates with placeholder markdown links; legacy secret paths hidden in mobile/runbook docs; and stale statements about phantom files such as `.codex/AGENTS.md`. After merging, rerun the stale-reference grep and markdown-link check from the canonical base checkout, close the cleanup issue with evidence, and verify the cleanup branch/worktree/remote branch is gone.

Pitfall: `gh pr merge` invoked from a PR worktree may successfully merge on GitHub and then fail locally when a chained script tries to checkout the base branch already used by the canonical worktree. Treat this as a local cleanup failure, not necessarily a merge failure: inspect `gh pr view`, then sync and clean from the canonical checkout.

See `references/jiuwei-trellis-active-context-cleanup.md` for the stronger JiuWei lesson: before choosing any further issue/branch iteration, first verify Trellis task state and active docs; when the user says historical docs are polluting context, delete stale/superseded files from the default read path rather than merely marking them historical.

## JiuWei alpha / packaging authorization boundary

For JiuWei FuXi delivery, the current standing authorization is:
- Low-risk PR merge and alpha deployment may be handled autonomously by Hermes after independent verification, with evidence recorded to the Issue/PR.
- Production deployment, production data changes, and production secrets still require explicit user confirmation.
- Android and iOS packaging currently use cloud packaging; Hermes must not trigger cloud packaging without user confirmation, and should not default to local/server mobile packaging or leave local packaging dependencies/artifacts behind.
- If a change touches payment provider runtime behavior, callback endpoint side effects, order/payment/balance/fulfillment core logic, admin/RBAC/security boundaries, migrations with runtime impact, secrets, or insufficiently verified changes, stop and route a blocker even if alpha deploy is otherwise authorized.
- When the user explicitly skips a high-risk/externally gated lane (for example mobile cloud packaging), remove that lane from the active selection and re-triage the remaining issues from GitHub/source artifacts. Prefer the smallest independently useful slice that advances the blocker chain without crossing a new gate: docs/tests, pure helpers, validation utilities, or plan-state updates before endpoints, provider wiring, event writes, migrations, secrets, deploys, or production data. Record the skipped lane and the chosen boundary in the issue/PR so future agents do not restart the skipped work by accident.

## Alpha deploy verification after autonomous merge

When the user has authorized autonomous alpha PR merge/deploy, do not equate a successful deploy command or container `healthy` status with final delivery. After merging to the alpha integration branch:

1. Sync the canonical checkout to `origin/develop` (or the project alpha branch).
2. Run the documented alpha deploy command.
3. Run independent smoke checks for backend health, frontend root, API schema, and at least one real app endpoint such as product list. App endpoints can expose missing runtime dependencies that health checks do not.
4. If a smoke check fails, treat it as part of the same delivery loop when the fix is low-risk (for example a missing runtime dependency), create a narrow PR, verify, merge, redeploy alpha, and rerun smoke.
5. If CI/GitHub Actions build succeeds but deploy fails on external automation boundaries (SSH reachability, GHCR package visibility/token read, DNS/firewall), retry once if transient, then record a dedicated deploy-automation issue with non-secret evidence. Do not let the failed automation obscure whether a server-local alpha fallback deploy/smoke can safely advance the feature.
6. When running deploy config/render commands, assume Docker Compose and env renderers may print secrets. Prefer non-secret key probes or explicit redaction before any user-visible output; never paste full env/config output into chat or issue comments.
7. Do not trigger Android/iOS cloud packaging during alpha deploy unless the user separately confirms the packaging run.

See `references/fuxi-alpha-deploy-verification.md` for command patterns and the Redis cache dependency pitfall.
See `references/baomei-ghcr-alpha-deploy.md` for WanXiang/JiuWei/BaiZe on-Baomei GHCR alpha deploy details, including BaiZe `Baize.alpha.env` casing, Actions SSH secret drift, and local Baomei fallback deploy verification.

See `references/baize-branch-baseline-cleanup.md` for the BaiZe-specific cleanup pattern: choose `main` as content baseline when it contains current product capabilities, rebuild `develop` as `main + Baomei alpha deploy`, sync both branches to an empty tree diff, close old non-WanXiang-blocked issues, and remove worktrees/temp dependency dirs.

For WanXiang-specific alpha GO-readiness after FuXi/Trellis/GHCR baseline cleanup, see `references/wanxiang-alpha-go-readiness.md`: Hermes is authorized to autonomously iterate/merge/deploy alpha when low-risk and verified, while keeping production/secrets/Admin/security/data-migration boundaries explicit; it also captures the pattern of separating app readiness from Actions SSH/GHCR transport failures.

For choosing one branch as the new base when `main`/`develop` drift and then closing only truly satisfied old UAT issues, see `references/branch-normalization-and-uat-closure.md`: pick the product/content branch as base, back up the superseded branch, re-apply only intended deploy deltas, use `git merge -s ours` when a replacement PR needs ancestry, redeploy alpha, and distinguish formal `wanxiang_api ready` evidence from preview-only degraded data before closing issues.from `develop`, make GHCR pull the default server path with `/srv/secrets/apps/<Project>.<env>.env`, run deploy-contract/backend/frontend/compose/workflow YAML checks, and keep Actions/GHCR/SSH/secrets as an explicit merge gate.

For choosing one branch as the new base when `main`/`develop` drift and then closing only truly satisfied old UAT issues, see `references/branch-normalization-and-uat-closure.md`: pick the product/content branch as base, back up the superseded branch, re-apply only intended deploy deltas, use `git merge -s ours` when a replacement PR needs ancestry, redeploy alpha, and distinguish formal `wanxiang_api ready` evidence from preview-only degraded data before closing issues.

## Partial upstream data / preview mode

When an upstream service has partial usable data but does not satisfy its readiness contract, do not weaken the normal production/provider path. Keep the formal path fail-closed, and add a separate preview/review path only if it is explicitly marked as non-final and cannot trigger real sends, buys/sells, production deploys, or formal ready UAT. Use the preview path to advance UI layout, strategy-review candidates, evidence/counter-evidence, invalidators, and review-ledger work while the upstream remains partial.

For UI slices, surface the safety boundary before ordinary output: add a Decision Gate (`OPEN` / `DEGRADED` / `CLOSED` / `UNKNOWN`), promote evidence/counter-evidence/invalidators/trace/strategy version, collapse login/sync/raw indicator tools into Debug/Admin, and ensure non-OPEN refreshes do not imply real push/send. See `references/partial-upstream-data-review-workbench.md`.

See `references/partial-upstream-data-preview.md` for the condensed provider/backend pattern and BaiZe/WanXiang example.

For BaiZe-style strategy review UI slices, see `references/strategy-review-workbench-slice.md`: keep Decision Gate and data contract state first, treat `wanxiang_preview_only` as preview-only, demote admin/sync/indicator tools, and verify with frontend build plus stale-copy/garbled-label grep before autonomous merge.

For WanXiang Phase 1 UAT/check command slices, see `references/wanxiang-phase1-decision-check.md`: add a stable JSON management command that keeps formal `wanxiang_api` fail-closed, reports unavailable reasons, and allows `wanxiang_preview` only as `ready=false` degraded preview output.

For exposing that check to a BaiZe-style strategy workbench, see `references/wanxiang-phase1-check-api-ui.md`: wrap the existing check in an authenticated read-only endpoint, load `wanxiang_preview` status in the frontend, feed it into Decision Gate only as fallback observability, and keep `wanxiang_api` fail-closed.

For minimal Review Ledger slices, see `references/minimal-review-ledger-api.md`: use existing `DecisionRunRecord.outcome_payload` for run-level ledger MVP, expose `record_id` on latest decisions, keep `brief_payload` immutable, and defer new models/migrations until proven needed. For the next candidate-level UI step, see `references/candidate-review-ledger-selection.md`: keep a blank whole-brief option, reuse `brief.top_candidates`, submit `stock_code` through the existing ledger API, and verify persistence/list response without adding schema.

## Verification before final delivery

Before final delivery, check:
- acceptance criteria or user-stated requirement is satisfied;
- tests/CI/health checks or equivalent verification ran;
- alpha deploy smoke includes real app endpoints when alpha was deployed;
- smoke checks use the deployed runtime's actual port/domain/env from the deploy command or env file, not a guessed port from another project/session;
- no known blocker remains;
- state artifact is updated enough for reset recovery;
- project issue/status docs reflect the real open/closed queue when those docs exist;
- Trellis/project-local task lists do not still show completed slices as active; archive completed Trellis tasks in a low-risk hygiene PR if they would otherwise pollute future context;
- project worktree/branch cleanup rules are followed when applicable.

---

## Reference: Branch normalization and UAT issue closure pattern

# Branch normalization and UAT issue closure pattern

Use when `main` and `develop` drift and the user wants one branch chosen as the base while old UAT issues are closed where possible.

## Choose a base deliberately

When `develop` originally came from `main` but later drifted, do not treat the fix as a normal merge if it would replace large parts of the tree. Reconstruct facts first:

```bash
git diff --shortstat origin/develop..origin/main
git diff --name-status origin/develop..origin/main
git rev-list --count origin/develop..origin/main
git rev-list --count origin/main..origin/develop
git log --oneline origin/develop..origin/main
git log --oneline origin/main..origin/develop
```

If one branch clearly contains the product/content truth and the other mostly contains deploy/history drift, choose the product/content branch as the base. For BaiZe, `main` held the strategy workbench / Review Ledger / WanXiang Phase 1 UI features, while old `develop` mainly held alpha deploy and old drift; the safe target was `develop = main + alpha deploy`.

## Safe execution sequence

1. Create a GitHub issue for the normalization and record the chosen base and discard boundary.
2. Create a read-only backup of the branch being superseded, for example:

```bash
git push origin origin/develop:refs/heads/archive/develop-before-main-baseline-YYYYMMDD
```

3. Create a project-local worktree from the chosen base (`origin/main` in the BaiZe case).
4. Re-apply only the intended kept delta from the other branch (for example alpha deploy files and runtime docs), not the whole historical branch.
5. Verify from the new tree: deploy-contract tests, focused backend tests, Django check, frontend build, compose config render, and `git diff --check`.
6. Open a PR to `develop` explaining that this is a baseline replacement/normalization, not a normal feature merge.
7. If GitHub cannot merge because the PR branch does not share the current base cleanly, merge the old branch with `-s ours` on the PR branch after verifying the tree is correct. This records that the old branch history is intentionally superseded while preserving the chosen-base tree:

```bash
git merge -s ours --no-edit origin/develop
```

8. Merge the PR, sync canonical `develop`, remove project-local worktrees, and delete the temporary PR branches. Keep the archive branch until the user explicitly wants archive pruning.
9. Close obsolete strategy PRs after the actual normalization lands.

Pitfall: `gh pr merge` from a PR worktree may merge on GitHub and then fail locally with “branch is already used by worktree”. Treat this as local cleanup only: inspect PR state, sync from the canonical checkout, then remove the worktree and local branch.

## Re-verify runtime after normalization

When normalizing from `main`, do not assume deploy runtime helpers from `develop` survived intact. Re-check:

- backend settings still parse `DATABASE_URL`; otherwise containers may fall back to `127.0.0.1:5432`;
- deploy script frontend build args match the actual Dockerfile stages; do not pass `--target runtime` unless the frontend Dockerfile defines that stage;
- runtime env casing and app-specific Redis variables still match the live `/srv/secrets/apps/<Project>.<env>.env` file.

If deploy fails after normalization, fix these as a narrow follow-up PR, merge, then redeploy alpha.

## Closing old UAT issues

Close only issues whose acceptance criteria are actually satisfied by live evidence.

For WanXiang/BaiZe-style data dependencies:

- `wanxiang_api` ready path is the formal closure criterion for true end-to-end UAT.
- `wanxiang_preview` with candidates is useful evidence that partial data exists, but if it is `preview_only`, `degraded`, or `ready=false`, do not close issues that require formal ready data.
- Record preview evidence and leave the issue open with the upstream blocker (`dataset status=failed`, missing test webhook, missing real-send authorization, etc.).

Example evidence split:

```plain
wanxiang_api: status=unavailable, ready=false, error="dataset status=failed" → do not close formal UAT.
wanxiang_preview: status=degraded, candidate_count=10, trace=<id>, wanxiang_preview_only → record progress, keep gate closed/degraded.
```

For notification issues, do not close real Feishu/Telegram delivery tasks unless test webhook/token/chat_id and explicit real-send authorization exist. Missing-config/no-push checks are not a substitute for a real authorized test send.

---

## Reference: BaiZe branch baseline cleanup and issue closure pattern

# BaiZe branch baseline cleanup and issue closure pattern

Use when BaiZe `main` and `develop` drift and the user wants one branch chosen as the durable base, the other aligned/retired, and old issues closed where only WanXiang data remains blocked.

## Durable lesson

BaiZe alpha runs on the current Baomei server, not Tencent Cloud. For WanXiang/JiuWei/BaiZe family work, verify Baomei local runtime first before trying remote SSH aliases.

## Branch decision pattern

1. Inventory `origin/main`, `origin/develop`, open PRs, open issues, worktrees, remote residue, and Baomei alpha runtime.
2. Compare tree and ancestry separately:
   - `git diff --shortstat origin/main..origin/develop`
   - `git diff --name-status origin/main..origin/develop`
   - `git rev-list --count origin/develop..origin/main`
   - `git rev-list --count origin/main..origin/develop`
3. If `main` contains the current product capabilities and `develop` contains only deploy/alpha or old drift, choose `main` as the content baseline.
4. Rebuild `develop` as the clean tree: `main + Baomei alpha deploy/runtime baseline`; do not let an old `develop` merge reintroduce stale Trellis/docs/demo/context files.
5. If preserving ancestry is needed, create a branch from `origin/main`, apply the intended deploy/runtime files, then use `git merge -s ours origin/develop` only when the resulting tree is still the intended clean tree. Verify with `git diff origin/main..HEAD` before PR/merge.
6. If a later merge accidentally brings old develop drift back, align `develop` to `main` again with a main-based branch and an `ours` merge of old develop, then verify the final tree diff is empty.

## PR/merge mechanics pitfall

`gh pr merge` from a linked worktree may merge on GitHub and then fail locally because `develop` is already checked out in the canonical worktree. Treat this as a local checkout failure, not a failed merge:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,url
git -C /srv/projects/develop/BaiZe fetch --prune origin
git -C /srv/projects/develop/BaiZe checkout develop
git -C /srv/projects/develop/BaiZe reset --hard origin/develop
```

Then clean the project-local worktree and branch from the canonical checkout.

## Main/develop finalization

After `develop` is clean and verified, sync `main` too:

1. If `develop -> main` PR has conflicts, create a branch from `origin/main` and apply the intended `develop` tree changes manually (deployment/runtime files only if product code is already on main).
2. Open/merge a PR to `main`.
3. Re-align `develop` to `main` so `git diff origin/main..origin/develop` is empty.
4. Delete obsolete open strategy PRs, temporary branches, archive branches, and project-local worktrees.
5. Remove local transient directories created during verification: `.worktree`, `backend/.venv`, `frontend/node_modules`, `frontend/dist`.

## Issue closure policy from this cleanup

Close old issues whose remaining uncertainty is entirely covered by the WanXiang formal-data blocker:

- Close frontend/UI-state issues if current code and Baomei alpha verify loading/error/empty/degraded/closed behavior and only formal `ready` data is missing.
- Close notification-boundary issues if payload construction and no-push/missing-config behavior are tested; real sends require a later task with test webhook/token/chat_id and explicit authorization.
- Keep open issues whose acceptance explicitly requires formal `wanxiang_api` ready refresh while WanXiang dataset status is `failed`.

Record the reason on each issue before closing or leaving it open.

## Verification checklist

- `origin/main` and `origin/develop` tree diff is empty when the user wants both branches aligned.
- `gh pr list --state open` is empty unless a deliberate PR remains.
- Only legitimate blockers remain open (for BaiZe: #5/#9 style WanXiang formal data readiness).
- Baomei alpha smoke passes:
  - `GET /api/health/` 200
  - `GET /api/schema/` 200
  - frontend `/` 200
  - `baize-alpha-backend-1` healthy and `baize-alpha-frontend-1` running
- Temporary worktrees and dependency/build directories are removed.

---

## Reference: FuXi Codex Tool SOP Layer

# FuXi Codex Tool SOP Layer

Use when evolving a FuXi-managed project so Hermes/GA becomes the expert driver for Codex rather than forwarding raw prompts.

## Pattern

Create a project-local Tool SOP layer under the existing project context system, typically:

```text
.trellis/tool-sop/
  README.md
  task-classifier.md
  codex-capabilities.md
  codex-profiles.md
  subagent-policy.md
  verification-policy.md
  review-gates.md
  blocked-question-policy.md
  learning-log.md
  failure-patterns.md
```

This layer sits below FuXi coordination and above Codex execution:

```text
User/Feishu -> Hermes/GA -> read project context -> classify task/risk -> choose Codex capability/profile/subagents/gates -> dispatch Codex -> Hermes verifies -> write evidence/lessons -> concise report
```

## Source-of-truth boundary

- Trellis remains owner of workflow phase, task, spec, context, and task artifact definitions.
- GitHub Issues/PRs remain durable collaboration/audit records.
- Codex remains the primary coding execution core unless the project explicitly adopts another executor.
- Hermes/GA owns task classification, Codex profile selection, subagent/gate decisions, blocked-question routing, independent verification, and user-facing reporting.
- CodeStable or similar review systems should not be introduced as another task/spec authority. If considered, make them external gates that consume Trellis/GitHub context and produce findings only.

## Recommended implementation steps

1. Inspect project entrypoints (`AGENTS.md`, `.trellis/fuxi-context.md`, `.trellis/workflow.md`, docs index) and current branch/worktree state.
2. Create an Issue and a project-local `.worktree/` branch for the workflow-docs slice when the repo uses issue-driven FuXi.
3. Add `.trellis/tool-sop/` files with concise rules, not a monolithic workflow document.
4. Link the SOP from `AGENTS.md`, `.trellis/fuxi-context.md`, `.trellis/workflow.md`, and the docs index.
5. Avoid recording transient open/closed issue state as long-lived docs; point readers to live GitHub for real-time status.
6. Validate with `git diff --check`, Trellis task validation/context commands, and the project’s existing lightweight tests if available.
7. Merge low-risk docs/workflow SOP changes autonomously only after verification, then clean the project-local worktree and branch.

## Pitfalls

- Do not duplicate the whole common FuXi workflow inside project docs; project docs should point to the tool SOP and keep project facts separate.
- Do not let Tool SOP files redefine Trellis task/spec semantics.
- Do not add OpenCode or other adapters prematurely when Codex is still the only active coding core.
- Do not store raw task logs as reusable rules. Promote only stable tool-use lessons into `learning-log.md` / `failure-patterns.md`.
