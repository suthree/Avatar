# FuXi Requirement Runtime SOP

## Trigger

用户通过飞书提出开发、修复、调研、自动化或 FuXi / Avatar / Codex runtime 相关需求时触发。

## Core Rule

不要把原始飞书需求直接交给 Codex。Avatar 必须先通过多轮澄清，把模糊需求压缩成可执行、可验证、可审计的 Issue Contract 草案；用户确认后，只能把草案提交给 `dev-workflowd` 窄 API。GitHub Issue、Agent Brief、worktree、Codex run、PR / CI 状态机都由 `dev-workflowd` 负责。

## Tool Boundaries

| 组件 | 职责 | 不负责 |
| --- | --- | --- |
| Feishu | 人机入口、澄清、确认、通知 | 事实源、长期合同 |
| Avatar | coordinator、memory、requirement grilling、Issue Contract draft、用户确认、调用 `dev-workflowd` 窄 API、delivery summary、SOP 沉淀 | GitHub Issue / Agent Brief materialization、worktree、Codex 调度、PR / CI 状态机、业务代码修改、commit、push、merge、deploy |
| dev-workflowd | GitHub Issue / Agent Brief materialization、queue、lock、worktree、Codex runner、PR / CI watcher、fix loop、delivery summary | 飞书自然语言对话、长期记忆、业务代码实现 |
| GitHub Issue | 需求合同、状态、审计 | 未确认聊天碎片 |
| Agent Brief | Codex 执行合同 | 长期项目知识 |
| Codex | worktree coding、验证、PR、fix loop | 需求澄清、飞书对话、权限决策 |
| GitHub PR / Actions | diff、CI、review、交付事实 | 需求讨论 |
| Avatar Memory / SOP | 稳定流程经验、已验证边界 | secret、未确认事实、易变状态 |
| FuXi | 跨项目模板、policy、checklist | 单个 Avatar 实例的运行记忆 |
| grill-me | 一问一答需求拷问方法 | 调度、编码 |
| grill-with-docs | 结合项目文档、术语和决策校准需求 | 替代 Issue |
| Trellis | 后期复杂任务 PRD / design / task graph | V0 主链、Codex 调度 |
| MCP / Gateway | 工具连接和权限收敛 | workflow owner |
| ACE / Augment | 本地代码语义证据 | 产品需求决策 |
| smart-search-cli | 外部当前资料证据 | 本地代码验证 |

## Flow

1. 判断是否是开发 / runtime 需求；不是则普通对话。
2. 进入 requirement grilling，一次只问一个关键问题。
3. 能通过目标 repo `AGENTS.md`、`docs/*`、Issue / PR 或代码回答的问题，先查证据再问用户。
4. 澄清 Goal / Context / Scope / Non-goals / Acceptance / Verification / Risk / Delivery。
5. 生成 Requirement Contract 并要求用户确认。
6. 用户 `/approve` 后，调用 `dev-workflowd` 窄 API 提交 Issue Contract；Avatar 不直接调用裸 `gh`，不直接创建 GitHub Issue。
7. 由 `dev-workflowd` 创建或更新 GitHub Issue，并生成 Agent Brief，作为 Codex 权威执行合同。
8. 读取 `fuxi_dev_workflowd_boundary_sop.md` 和 `fuxi_codex_dispatch_sop.md`，确认 Avatar 只查询/转述 workflow 状态，不直接调度 Codex。
9. 通过 `dev-workflowd` 返回的 PR / CI / blocker 状态，向飞书汇报 Issue URL、PR URL、验证结果、未验证项和用户动作。
10. 任务完成后，只将稳定、已确认、已验证、跨任务可复用的经验写入 Avatar memory。

## Requirement Contract Shape

```markdown
## Goal

## Context

## Scope

## Non-goals

## Acceptance Criteria

## Verification Requirements

## Risk Boundaries

## Delivery Requirements
```

## Stop Conditions

- Goal 不清楚。
- Acceptance Criteria 不可验证。
- Verification Requirements 缺失。
- Risk Boundaries 未确认。
- 触及 auth、payment、database、CI/CD、deployment、secret、data deletion 等高风险区域但未授权。
- Agent Brief 与目标项目 `AGENTS.md` 或安全规则冲突。
- `dev-workflowd` API 不可用、未配置或返回未授权。
- Codex 需要改变 scope。
- Codex 连续失败或无法运行关键验证。

## Memory Rule

可以写入长期 memory：

- 已确认的跨项目运行时 SOP。
- 已验证的失败经验。
- 可复用的需求澄清问题树。
- 稳定的工具边界和风险门禁。

不得写入长期 memory：

- secret、token、登录态。
- 未确认的飞书聊天片段。
- 未验证的项目事实。
- 当前 PID、临时 session id、一次性 run log 等易变状态。
- 模型猜测。

## V0 Constraint

第一版只跑单线程闭环：

```text
Feishu
→ Avatar requirement grilling
→ approved Requirement Contract
→ dev-workflowd API handoff
→ GitHub Issue / Agent Brief
→ Codex worktree / PR
→ Avatar delivery summary
→ Avatar memory update
```

Trellis、scheduler、多 Codex worker、MCP Gateway 和自动 ship 都是后续迭代，不进入 V0 主链。
