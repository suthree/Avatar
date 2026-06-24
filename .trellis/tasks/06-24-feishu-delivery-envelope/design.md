# Design

## Approach

Use standard-library, platform-neutral modules:

- `frontends/platform_budgets.py` for IM sanitation, digest building, and markdown segmentation.
- `frontends/outbox_store.py` for durable local outbox writing and retrieval.
- `frontends/message_delivery.py` for delivery-envelope construction and Feishu-facing digest rendering.

`frontends/fsapp.py` remains the integration layer. It will use markdown-aware segments for direct sends, persist oversized task-card details before displaying concise retrieval/index text, and always persist final full/raw output before marking a task done. Retrieval commands read local files only.

The default outbox root is `AVATAR_IM_OUTBOX_DIR` when set, otherwise `<project>/temp/feishu_outbox`, keeping development output local and outside Trellis.

## Alternatives Rejected

- Increasing Feishu message/card limits: rejected because platform limits still risk partial delivery.
- Keeping only raw text chunks in chat: rejected because long replies need standardized indexes and later retrieval.
- Adding service-backed storage: rejected because this task must be local/mocked and standard-library first.
