from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from frontends.platform_budgets import DEFAULT_IM_SEGMENT_LIMIT, segment_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "manifest.json"
FULL_NAME = "full.md"
RAW_NAME = "raw_model_output.md"
SCHEMA = "avatar.im_outbox.v1"

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_SAFE_FILE_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_FILE_HINT_RE = re.compile(r"\[FILE:([^\]\n]+)\]")


def default_outbox_root() -> Path:
    env = os.environ.get("AVATAR_IM_OUTBOX_DIR")
    if env:
        return Path(env).expanduser()
    return PROJECT_ROOT / "temp" / "feishu_outbox"


def safe_outbox_id(task_id: object) -> str:
    raw = str(task_id or "task")
    safe = _SAFE_ID_RE.sub("_", raw).strip("._-") or "task"
    if safe != raw or len(safe) > 120:
        digest = _sha256_text(raw)[:12]
        safe = f"{safe[:80].strip('._-') or 'task'}_{digest}"
    return safe


def task_outbox_dir(task_id: object, base_dir: str | os.PathLike[str] | None = None) -> Path:
    root = Path(base_dir).expanduser() if base_dir is not None else default_outbox_root()
    return root / safe_outbox_id(task_id)


def write_outbox(
    task_id: object,
    full_text: object,
    *,
    raw_text: object | None = None,
    title: str | None = None,
    status: str | None = None,
    session: dict[str, Any] | str | None = None,
    metadata: dict[str, Any] | None = None,
    base_dir: str | os.PathLike[str] | None = None,
    chunk_limit: int = DEFAULT_IM_SEGMENT_LIMIT,
    omitted_sections: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any] | str] | None = None,
) -> dict[str, Any]:
    """Persist a complete IM delivery envelope and return its manifest."""
    task_id_text = str(task_id or "task")
    full = "" if full_text is None else str(full_text)
    raw = None if raw_text is None else str(raw_text)
    task_dir = task_outbox_dir(task_id_text, base_dir)
    task_dir.mkdir(parents=True, exist_ok=True)

    previous = _read_manifest_file(task_dir / MANIFEST_NAME)
    manifest = _base_manifest(
        task_id_text,
        task_dir,
        previous=previous,
        title=title,
        status=status,
        session=session,
        metadata=metadata,
    )

    _clean_old_chunks(task_dir)
    _write_text(task_dir / FULL_NAME, full)
    manifest["full"] = _file_entry(task_dir, FULL_NAME, full)
    manifest["sha256"] = manifest["full"]["sha256"]

    if raw is not None:
        _write_text(task_dir / RAW_NAME, raw)
        manifest["raw"] = _file_entry(task_dir, RAW_NAME, raw)
    else:
        manifest["raw"] = None

    chunks = []
    for idx, chunk in enumerate(segment_markdown(full, limit=chunk_limit), start=1):
        name = f"chunk_{idx:03d}.md"
        _write_text(task_dir / name, chunk)
        entry = _file_entry(task_dir, name, chunk)
        entry["index"] = idx
        chunks.append(entry)
    manifest["chunks"] = chunks

    existing_omitted = list(manifest.get("omitted_sections") or [])
    if omitted_sections:
        existing_omitted.extend(omitted_sections)
    manifest["omitted_sections"] = existing_omitted

    manifest["artifacts"] = _merge_artifacts(
        manifest.get("artifacts") or [],
        _extract_artifacts(full, source="full") + _extract_artifacts(raw or "", source="raw") + _coerce_artifacts(artifacts),
    )
    manifest["retrieval"] = _retrieval_commands(task_id_text)
    manifest["updated_at"] = _now_iso()
    _write_json(task_dir / MANIFEST_NAME, manifest)
    return manifest


def write_artifact(
    task_id: object,
    name: str,
    content: object,
    *,
    kind: str = "artifact",
    title: str | None = None,
    status: str | None = None,
    session: dict[str, Any] | str | None = None,
    metadata: dict[str, Any] | None = None,
    omitted_section: dict[str, Any] | None = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Persist an outbox artifact without requiring final full text yet."""
    task_id_text = str(task_id or "task")
    task_dir = task_outbox_dir(task_id_text, base_dir)
    artifact_dir = task_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = task_dir / MANIFEST_NAME
    previous = _read_manifest_file(manifest_path)
    manifest = _base_manifest(
        task_id_text,
        task_dir,
        previous=previous,
        title=title,
        status=status,
        session=session,
        metadata=metadata,
    )

    artifact_index = _next_artifact_index(manifest)
    safe_name = _safe_filename(name)
    filename = f"{artifact_index:03d}_{safe_name}.md"
    path = artifact_dir / filename
    while path.exists():
        artifact_index += 1
        filename = f"{artifact_index:03d}_{safe_name}.md"
        path = artifact_dir / filename

    text = "" if content is None else str(content)
    _write_text(path, text)
    rel_path = _rel(path, task_dir)
    entry = {
        "index": artifact_index,
        "kind": kind,
        "name": name,
        "path": rel_path,
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "sha256": _sha256_text(text),
    }
    manifest.setdefault("artifacts", []).append(entry)
    manifest["artifacts"] = _merge_artifacts(manifest["artifacts"], [])

    if omitted_section is not None:
        omitted = dict(omitted_section)
        omitted.setdefault("kind", kind)
        omitted["artifact_index"] = artifact_index
        omitted["artifact_path"] = rel_path
        omitted["chars"] = len(text)
        omitted["sha256"] = entry["sha256"]
        manifest.setdefault("omitted_sections", []).append(omitted)

    manifest["retrieval"] = _retrieval_commands(task_id_text)
    manifest["updated_at"] = _now_iso()
    _write_json(manifest_path, manifest)
    return {"manifest": manifest, "artifact": entry, "task_dir": str(task_dir)}


def read_manifest(task_id: object, *, base_dir: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = task_outbox_dir(task_id, base_dir) / MANIFEST_NAME
    manifest = _read_manifest_file(path)
    if not manifest:
        raise FileNotFoundError(f"outbox manifest not found for task {task_id}")
    return manifest


def read_full(task_id: object, *, base_dir: str | os.PathLike[str] | None = None) -> tuple[dict[str, Any], str]:
    manifest = read_manifest(task_id, base_dir=base_dir)
    full = manifest.get("full") or {}
    path = _entry_path(manifest, full.get("path") or FULL_NAME)
    return manifest, path.read_text(encoding="utf-8")


def read_chunk(
    task_id: object,
    index: int,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if index < 1:
        raise IndexError("chunk index must be >= 1")
    manifest = read_manifest(task_id, base_dir=base_dir)
    chunks = manifest.get("chunks") or []
    try:
        entry = chunks[index - 1]
    except IndexError as exc:
        raise IndexError(f"chunk {index} not found for task {task_id}") from exc
    path = _entry_path(manifest, entry["path"])
    return manifest, path.read_text(encoding="utf-8"), entry


def read_artifact(
    task_id: object,
    index: int,
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    if index < 1:
        raise IndexError("artifact index must be >= 1")
    manifest = read_manifest(task_id, base_dir=base_dir)
    for entry in manifest.get("artifacts") or []:
        if entry.get("index") == index and entry.get("path"):
            path = _entry_path(manifest, entry["path"])
            return manifest, path.read_text(encoding="utf-8"), entry
    raise IndexError(f"artifact {index} not found for task {task_id}")


def _base_manifest(
    task_id: str,
    task_dir: Path,
    *,
    previous: dict[str, Any] | None = None,
    title: str | None = None,
    status: str | None = None,
    session: dict[str, Any] | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous = previous or {}
    now = _now_iso()
    manifest = {
        "schema": SCHEMA,
        "task_id": task_id,
        "outbox_id": safe_outbox_id(task_id),
        "base_dir": str(task_dir.parent),
        "task_dir": str(task_dir),
        "manifest_path": str(task_dir / MANIFEST_NAME),
        "created_at": previous.get("created_at") or now,
        "updated_at": now,
        "title": title if title is not None else previous.get("title", ""),
        "status": status if status is not None else previous.get("status", ""),
        "session": _session_value(session if session is not None else previous.get("session")),
        "metadata": _merged_dict(previous.get("metadata"), metadata),
        "sha256": previous.get("sha256", ""),
        "full": previous.get("full"),
        "raw": previous.get("raw"),
        "chunks": previous.get("chunks") or [],
        "artifacts": previous.get("artifacts") or [],
        "omitted_sections": previous.get("omitted_sections") or [],
        "retrieval": previous.get("retrieval") or _retrieval_commands(task_id),
    }
    return manifest


def _session_value(session: dict[str, Any] | str | None) -> dict[str, Any] | str:
    if session is None:
        return {}
    if isinstance(session, dict):
        return dict(session)
    return str(session)


def _merged_dict(previous: Any, update: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(previous) if isinstance(previous, dict) else {}
    if update:
        result.update(update)
    return result


def _clean_old_chunks(task_dir: Path) -> None:
    for path in task_dir.glob("chunk_*.md"):
        if path.is_file():
            path.unlink()


def _file_entry(task_dir: Path, rel_name: str, text: str) -> dict[str, Any]:
    return {
        "path": rel_name,
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "sha256": _sha256_text(text),
    }


def _entry_path(manifest: dict[str, Any], rel_path: str) -> Path:
    task_dir = Path(manifest["task_dir"])
    path = (task_dir / rel_path).resolve()
    task_root = task_dir.resolve()
    if task_root != path and task_root not in path.parents:
        raise ValueError(f"manifest path escapes outbox: {rel_path}")
    return path


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_manifest_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"invalid outbox manifest: {path}")
    return data


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_filename(name: str) -> str:
    stem = Path(name or "artifact").name
    if stem.endswith(".md"):
        stem = stem[:-3]
    safe = _SAFE_FILE_RE.sub("_", stem).strip("._-") or "artifact"
    return safe[:80]


def _extract_artifacts(text: str, *, source: str) -> list[dict[str, Any]]:
    artifacts = []
    for raw_path in _FILE_HINT_RE.findall(text or ""):
        value = raw_path.strip()
        if not value:
            continue
        artifacts.append({
            "kind": "generated_file",
            "source": source,
            "name": Path(value).name or value,
            "path": value,
        })
    return artifacts


def _coerce_artifacts(artifacts: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    result = []
    for item in artifacts or []:
        if isinstance(item, dict):
            result.append(dict(item))
        else:
            value = str(item)
            result.append({"kind": "artifact", "name": Path(value).name or value, "path": value})
    return result


def _merge_artifacts(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(item) for item in existing if isinstance(item, dict)]
    seen = {(_artifact_key(item)) for item in result}
    next_index = _next_artifact_index({"artifacts": result})
    for item in incoming:
        entry = dict(item)
        key = _artifact_key(entry)
        if key in seen:
            continue
        entry.setdefault("index", next_index)
        next_index = max(next_index, int(entry.get("index") or next_index)) + 1
        result.append(entry)
        seen.add(key)
    return result


def _artifact_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("kind", "")), str(item.get("path", "")), str(item.get("name", "")))


def _next_artifact_index(manifest: dict[str, Any]) -> int:
    indexes = []
    for item in manifest.get("artifacts") or []:
        try:
            indexes.append(int(item.get("index")))
        except (TypeError, ValueError):
            continue
    return (max(indexes) + 1) if indexes else 1


def _retrieval_commands(task_id: str) -> dict[str, str]:
    return {
        "full": f"/full {task_id}",
        "chunk": f"/chunk {task_id} <n>",
        "artifacts": f"/artifacts {task_id}",
        "more": "/more",
    }
