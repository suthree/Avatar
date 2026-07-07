# FuXi Codex Dispatch SOP

## Trigger

在 FuXi runtime 中，Requirement Contract 已获用户确认，Avatar 准备把任务交给 `dev-workflowd`，或用户在飞书中询问 Codex 执行状态时触发。

## Core Rule

Avatar 不直接修改目标业务 repo，也不直接调度 Codex。固定 dispatcher 只能由 `dev-workflowd` 或经过授权的人工 operator 调用：

```bash
/usr/local/bin/fuxi-dispatch-codex --repo <owner/repo> --issue <number>
```

第一轮或新项目接入时，`dev-workflowd` 或人工 operator 先 dry run：

```bash
/usr/local/bin/fuxi-dispatch-codex --repo <owner/repo> --issue <number> --dry-run
```

## Preconditions

- Issue Contract 已被用户 `/approve`。
- Avatar 已读取 `fuxi_dev_workflowd_boundary_sop.md`。
- `dev-workflowd` API endpoint、allowlist method 和 request_id / audit log 机制已配置。
- 目标 repo、risk、lock_keys、delivery policy 和 source artifacts 已明确。
- 未触及未授权高风险区域。
- `dev-workflowd` 不可用时，Avatar 必须标记 `workflow controller unavailable` 或 `manual dispatch required`，不得自行补位。

## Allowed Avatar Actions

- 调用 `dev-workflowd` allowlist API：`enqueue_codex_run`、`get_issue_status`、`pause_issue`、`resume_issue`、`cancel_issue`、`request_ship`。
- 读取 `dev-workflowd` 返回的 Issue / PR / CI / blocker 摘要。
- 将 `needs_info`、`scope_change_required`、`high_risk_approval_required` 等 blocker 转成飞书问题。
- 向飞书汇报 Issue URL、PR URL、验证结果、未验证项和用户动作。
- 把稳定、已验证、可复用的失败处理经验沉淀到 Avatar memory。

## Forbidden Avatar Actions

- 在目标 repo 中使用 `file_write` / `file_patch` / 任意 shell 写业务文件。
- 在目标 repo 中执行 `git commit`、`git push`、`git merge`。
- 直接运行 `codex exec`。
- 直接运行 `/usr/local/bin/fuxi-dispatch-codex`。
- 绕过 dispatcher 自行创建 worktree。
- 修改 Codex prompt 以扩大 Agent Brief 范围。
- 直接创建、更新或删除 GitHub Issue / PR label 来推进状态机。
- 读取或输出 secret。

## Dispatch Flow

1. 重新确认 Requirement Contract 已 `/approve`，且 risk / lock_keys 已明确。
2. 调用 `dev-workflowd` API 提交或排队，不调用 dispatcher。
3. 轮询或订阅 `get_issue_status`，读取 controller 返回的状态摘要。
4. 如果状态为 `needs_info`，Avatar 一次只问用户一个具体问题。
5. 如果状态为 `scope_change_required` 或高风险未授权，回到 Issue Contract 确认。
6. 如果状态为 `ready_to_ship`，向飞书汇报 Issue URL、PR URL、验证结果、未验证项和 `/ship` / `/hold` 动作。
7. 任务结束后只沉淀可复用经验，不记录一次性 run dir、PID、完整日志或 secret。

## Stop Conditions

- `dev-workflowd` endpoint 未配置或不可达。
- API method 不在 allowlist。
- Issue 未确认或 Agent Brief 缺失。
- Agent Brief 与项目 `AGENTS.md` 冲突。
- Codex 返回 `NEEDS_INFO`、`SCOPE_CHANGE_REQUIRED`、`HIGH_RISK_APPROVAL_REQUIRED` 或 `VERIFY_FAILED`。
- Codex 连续失败达到 policy 限制。

## Output Shape

飞书或 Issue summary 至少包含：

```text
Issue: <url or unavailable>
Workflow: queued | running | needs-info | blocked | ready-to-ship | done | failed
PR: <url or reason>
Verification: <passed / failed / not-run>
Unverified: <items or none>
User action: <明确动作或“无需操作”>
```

## Memory Rule

只沉淀可复用 workflow handoff 经验，例如固定失败模式、缺失权限类别、worktree 冲突处理。不要记录一次性 run dir、PID、完整日志、secret 或未确认判断。
