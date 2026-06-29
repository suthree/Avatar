# PRD

## User Request

用户希望用 Avatar 测试一套 Hermes/Avatar 作为 user-facing coordinator、Codex 作为 coding worker 的 skill 使用和澄清问题路由流程。重点问题：类似 `grill-me` 的需求澄清 skill 是 Hermes/Avatar 用，还是 Codex 用；Codex 如果遇到问题，是直接问用户，还是先问 Hermes/Avatar。

## Scope

- Documentation/policy-only workflow test in Avatar.
- Define a lightweight clarification-routing protocol for Hermes/Avatar ↔ Codex.
- Preserve the existing model: Avatar is personal controller, Codex is coding worker.
- Make the policy explicit in docs/specs so future Codex goals can follow it.
- Verify by inspection and docs checks only.

## Non-Goals

- No runtime behavior changes.
- No production deployment.
- No GitHub Actions or Feishu API changes.
- No secret, token, cookie, local runtime ledger, or generated log inspection.
- No merge to develop/main during this test unless separately approved.

## Acceptance Criteria

- `docs/GA_CODEX_LOOP.md` states that Hermes/Avatar owns user-facing clarification and final routing decisions.
- `.trellis/spec/codex-goal-contract.md` includes a structured `BLOCKED_QUESTION` format for Codex.
- A spec or workflow doc distinguishes three outcomes: Hermes/Avatar answers directly, Codex proceeds autonomously for low-risk implementation choices, or Hermes/Avatar forwards the question to the user.
- Codex is instructed not to directly ask the user.
- Verification evidence is written to this task directory.
