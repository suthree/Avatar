# PRD

## User Request

Implement GitHub Issue `#14`: add a Feishu/IM delivery envelope so long agent replies are complete and standardized. Feishu should send a short digest in IM, persist full content in a local outbox, segment markdown-aware chunks, expose artifact indexes, support `/full` retrieval, and avoid losing content during long task staging.

## Scope

- Add platform-neutral delivery helpers under `frontends/`.
- Sanitize IM text and split markdown without unnecessary code-fence damage.
- Write full, raw, chunk, artifact, and manifest files to a configurable local outbox.
- Integrate the helpers into `frontends/fsapp.py` for normal sends, task-card step details, and final task completion.
- Add local retrieval commands: `/full`, `/chunk`, `/artifacts`, and `/more`.
- Add tests under `tests/frontends/` with mocked Feishu/Lark behavior only.
- Write the implementation handoff with exact verification evidence.

## Non-Goals

- Implementation and validation must not call real Feishu/Lark write APIs or external services; GitHub issue/PR lifecycle is handled only by the approved Avatar development workflow.
- Do not read secret files, token files, cookie files, password files, `.env`, or `/srv/secrets`.
- Do not redesign unrelated frontend behavior.
- Do not commit generated runtime outbox contents.

## Acceptance Criteria

- Long replies round-trip through `full.md` and chunks without content loss.
- Markdown segmentation preserves text order and keeps fenced code blocks intact when practical.
- Outbox manifests contain stable checksums, relative paths, chunk metadata, omitted sections, and artifact indexes.
- Feishu task-card panels no longer silently truncate detail text with `"已截断"`.
- Retrieval commands read local outbox content and send results through existing async send paths.
- Targeted local tests pass or skipped checks are explicitly recorded.
