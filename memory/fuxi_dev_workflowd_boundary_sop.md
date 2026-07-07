# FuXi dev-workflowd Boundary SOP

## Trigger

Avatar 需要把已确认的 FuXi 开发需求交给自动开发 workflow，或用户在飞书里查询 / 暂停 / 继续 / 取消 / ship 某个 Issue 时触发。

## Core Rule

Avatar sees workflow, but does not own workflow.

Avatar 只负责人机对话、长期记忆、Issue Contract 草拟、用户确认、状态摘要和 SOP 沉淀。`dev-workflowd` 是唯一 workflow controller，负责 GitHub Issue / Agent Brief、queue、lock、worktree、Codex runner、PR / CI / review、fix loop 和 delivery summary。

## Allowed API

Avatar 只能调用 `dev-workflowd` allowlist API：

```text
create_issue_contract(draft)
update_issue_contract(contract_id, patch)
create_github_issue(contract_id)
append_issue_comment(issue_id, body)
enqueue_codex_run(issue_id, repo, risk, lock_keys)
get_issue_status(issue_id)
pause_issue(issue_id)
resume_issue(issue_id)
cancel_issue(issue_id)
request_ship(issue_id)
record_memory(repo, kind, content, source_artifact)
lookup_memory(repo, query)
```

每次调用都必须有：

```yaml
request_id:
actor: avatar
repo:
issue_or_contract:
method:
reason:
source_artifacts:
```

## Forbidden

Avatar 不得：

- 直接写目标业务 repo。
- 直接运行裸 `gh` 推进 Issue / PR 状态。
- 直接创建 worktree。
- 直接运行 `codex exec`。
- 直接运行 `fuxi-dispatch-codex`。
- 直接 commit / push / merge。
- 直接 deploy / publish。
- 修改 Codex prompt 来扩大 Agent Brief 范围。
- 把飞书聊天记录当事实源。
- 把 secret、token、登录态或一次性运行状态写入 memory。

## Handoff Flow

1. 读取目标项目允许的 `AGENTS.md`、docs 和相关证据。
2. 通过 requirement grilling 形成 Issue Contract 草案。
3. 让用户确认 `/approve`、`/revise` 或 `/cancel`。
4. `/approve` 后调用 `dev-workflowd`，提交 contract、repo、risk、lock_keys、delivery policy 和 source artifacts。
5. 之后只通过 `get_issue_status` 或 controller 回调读取状态。
6. 如果 controller 返回 `needs_info`，Avatar 一次只问用户一个具体问题。
7. 如果 controller 返回 `scope_change_required`，回到 contract 修改和用户确认。
8. 如果 controller 返回 `high_risk_approval_required`，暂停并请求明确授权。
9. 如果 controller 返回 `ready_to_ship`，向飞书汇报 Issue、PR、验证、未验证项、风险和用户动作。

## Stop Conditions

- `dev-workflowd` endpoint 未配置或不可达。
- API method 不在 allowlist。
- 请求缺少 request_id、repo、issue_or_contract、reason 或 source_artifacts。
- Issue Contract 未经用户确认。
- risk / lock_keys 缺失或与目标项目 policy 冲突。
- 用户要求 Avatar 直接改代码、直接跑 Codex、直接 merge 或 deploy。
- controller 状态与 GitHub Issue / PR 事实冲突。

## Memory Rule

可以写入 Avatar memory：

- 已验证的 workflow 边界。
- 可复用的 requirement grilling 问题。
- 稳定的 controller 失败模式。
- 已确认的状态汇报格式。

不得写入 Avatar memory：

- secret、token、登录态。
- 未确认聊天片段。
- 一次性 run dir、PID、session id。
- Codex JSONL 全量日志。
- 模型猜测或未验证项目事实。
