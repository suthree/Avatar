from __future__ import annotations

from typing import Any

from frontends.outbox_store import write_outbox
from frontends.platform_budgets import DEFAULT_DIGEST_BUDGET, build_digest, sanitize_for_im


def build_delivery_envelope(
    task_id: object,
    full_text: object,
    *,
    raw_text: object | None = None,
    title: str | None = None,
    status: str | None = None,
    session: dict[str, Any] | str | None = None,
    metadata: dict[str, Any] | None = None,
    base_dir: str | None = None,
    digest_budget: int = DEFAULT_DIGEST_BUDGET,
) -> dict[str, Any]:
    full = "" if full_text is None else str(full_text)
    manifest = write_outbox(
        task_id,
        full,
        raw_text=raw_text,
        title=title,
        status=status,
        session=session,
        metadata=metadata,
        base_dir=base_dir,
    )
    return {
        "task_id": manifest["task_id"],
        "digest": build_digest(full, budget=digest_budget),
        "manifest": manifest,
    }


def render_feishu_digest(envelope: dict[str, Any]) -> str:
    manifest = envelope.get("manifest", envelope)
    task_id = str(manifest.get("task_id") or envelope.get("task_id") or "")
    digest = envelope.get("digest") or ""
    full = manifest.get("full") or {}
    chunks = manifest.get("chunks") or []
    artifacts = manifest.get("artifacts") or []
    omitted = manifest.get("omitted_sections") or []

    if not digest and full:
        digest = f"Full content saved in {full.get('path', 'full.md')}."
    if not digest:
        digest = "Full content is not available yet."

    full_line = "Full: pending"
    if full:
        full_line = f"Full: `{full.get('path', 'full.md')}` ({full.get('chars', 0)} chars, sha256 {str(full.get('sha256', ''))[:12]})"

    lines = [
        f"Task: `{task_id}`",
        "",
        "Digest:",
        digest,
        "",
        full_line,
        f"Chunks: {len(chunks)} (`/chunk {task_id} 1`, `/more`)",
        f"Artifacts: {len(artifacts)} (`/artifacts {task_id}`)",
    ]
    if omitted:
        lines.append(f"Omitted card sections: {len(omitted)} saved in outbox artifacts")
    lines.extend([
        "",
        f"Retrieve full: `/full {task_id}`",
    ])
    return sanitize_for_im("\n".join(lines))


def render_artifact_index(manifest: dict[str, Any]) -> str:
    task_id = str(manifest.get("task_id") or "")
    artifacts = manifest.get("artifacts") or []
    if not artifacts:
        return f"Task `{task_id}` has no recorded artifacts."

    lines = [f"Artifacts for `{task_id}`:"]
    for item in artifacts:
        index = item.get("index", "?")
        kind = item.get("kind", "artifact")
        name = item.get("name") or item.get("path") or "artifact"
        path = item.get("path", "")
        chars = item.get("chars")
        suffix = f" ({chars} chars)" if chars is not None else ""
        lines.append(f"{index}. {kind}: `{name}`{suffix}")
        if path and path != name:
            lines.append(f"   path: `{path}`")
    lines.append(f"Use `/full {task_id}` for the final answer or `/chunk {task_id} <n>` for saved chunks.")
    return sanitize_for_im("\n".join(lines))
