# Implementation Checklist

- [x] Inspect existing Feishu send, task-card, and command handling.
- [x] Add platform-neutral budget, outbox, and delivery modules.
- [x] Integrate markdown segmentation into `send_text`.
- [x] Persist oversized task-card step details without silent truncation.
- [x] Persist final full/raw task output and render concise digest in cards.
- [x] Add local retrieval command handlers.
- [x] Add focused tests under `tests/frontends/`.
- [x] Run targeted tests and compile checks.
- [x] Write handoff under `temp/plan_feishu_delivery_envelope/codex/issue14_handoff.md`.
