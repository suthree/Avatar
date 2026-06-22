from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional


TASK_RUNNING = "running"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_STOPPED = "stopped"
TERMINAL_TASK_STATUSES = {TASK_COMPLETED, TASK_FAILED, TASK_STOPPED, "done"}

_WHITESPACE = re.compile(r"\s+")
_ARTIFACT_KEYS = {
    "project",
    "repo",
    "github_issue_url",
    "github_issue_number",
    "branch",
    "worktree",
    "codex_pid",
    "log_path",
    "answer_path",
    "handoff_path",
    "verification_artifact",
    "verification_artifacts",
    "verification_path",
    "avatar_verification_path",
}


def default_aegis_mesh_ledger_path() -> Path:
    """Return a local-safe default state path without touching the filesystem."""
    env_path = os.environ.get("AEGIS_MESH_LEDGER_PATH")
    if env_path:
        return Path(env_path).expanduser()

    env_state_dir = os.environ.get("AVATAR_STATE_DIR")
    if env_state_dir:
        state_path = Path(env_state_dir).expanduser()
        if state_path.suffix:
            return state_path
        return state_path / "aegis_mesh_ledger.sqlite3"

    workspace_root = os.environ.get("GA_WORKSPACE_ROOT")
    if workspace_root:
        return Path(workspace_root).expanduser() / "temp" / "state" / "aegis_mesh_ledger.sqlite3"

    project_root = Path(__file__).resolve().parents[1]
    if project_root.parent.name == ".worktree":
        return project_root.parent.parent / "temp" / "state" / "aegis_mesh_ledger.sqlite3"
    if project_root.parent.name == "Avatar_worktrees":
        avatar_root = project_root.parent.parent / "Avatar"
        if avatar_root.exists():
            return avatar_root / "temp" / "state" / "aegis_mesh_ledger.sqlite3"
    return project_root / "temp" / "state" / "aegis_mesh_ledger.sqlite3"


class AegisMeshLedger:
    """Durable local mirror of Aegis Mesh sessions, tasks, events, and artifacts."""

    def __init__(
        self,
        path: Optional[os.PathLike[str] | str] = None,
        *,
        time_fn: Callable[[], float] = time.time,
    ):
        self.path = Path(path).expanduser() if path is not None else default_aegis_mesh_ledger_path()
        self.time_fn = time_fn
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "AegisMeshLedger":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def upsert_session(
        self,
        session_id: str,
        *,
        label: Optional[str] = None,
        platform: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        now = self._timestamp(timestamp)
        incoming_metadata = _coerce_dict(metadata)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, label, platform, source, metadata_json,
                        created_at, updated_at, last_activity_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        label,
                        platform,
                        source,
                        _json_dumps(incoming_metadata),
                        now,
                        now,
                        now,
                    ),
                )
            else:
                merged_metadata = _merge_json(row["metadata_json"], incoming_metadata)
                self._conn.execute(
                    """
                    UPDATE sessions
                    SET label = ?, platform = ?, source = ?, metadata_json = ?,
                        updated_at = ?, last_activity_at = ?
                    WHERE session_id = ?
                    """,
                    (
                        label if label is not None else row["label"],
                        platform if platform is not None else row["platform"],
                        source if source is not None else row["source"],
                        _json_dumps(merged_metadata),
                        now,
                        now,
                        session_id,
                    ),
                )
            self._conn.commit()

    def upsert_task(
        self,
        session_id: str,
        task_id: str,
        *,
        label: Optional[str] = None,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        blocker: Optional[str] = None,
        requires_user: Optional[bool] = None,
        started_at: Optional[float] = None,
        completed_at: Optional[float] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        if not task_id:
            raise ValueError("task_id is required")
        now = self._timestamp(timestamp)
        incoming_metadata = _coerce_dict(metadata)
        extracted_artifacts = _extract_artifacts(incoming_metadata)
        if artifacts:
            extracted_artifacts.update(_coerce_dict(artifacts))
        incoming_phase = phase or _string_or_none(incoming_metadata.get("phase"))
        incoming_blocker = blocker or _string_or_none(incoming_metadata.get("blocker"))
        incoming_requires_user = requires_user
        if incoming_requires_user is None and "requires_user" in incoming_metadata:
            incoming_requires_user = bool(incoming_metadata.get("requires_user"))

        with self._lock:
            self.upsert_session(session_id, timestamp=now)
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE session_id = ? AND task_id = ?",
                (session_id, task_id),
            ).fetchone()
            if row is None:
                effective_status = status or TASK_RUNNING
                effective_completed_at = completed_at
                if effective_completed_at is None and effective_status in TERMINAL_TASK_STATUSES:
                    effective_completed_at = now
                self._conn.execute(
                    """
                    INSERT INTO tasks (
                        session_id, task_id, label, status, phase, metadata_json,
                        result_summary, error, blocker, requires_user,
                        created_at, started_at, updated_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        task_id,
                        label,
                        effective_status,
                        incoming_phase,
                        _json_dumps(incoming_metadata),
                        _compact_text(result_summary) if result_summary is not None else None,
                        _compact_text(error) if error is not None else None,
                        _compact_text(incoming_blocker) if incoming_blocker is not None else None,
                        1 if incoming_requires_user else 0,
                        now,
                        started_at if started_at is not None else now,
                        now,
                        effective_completed_at,
                    ),
                )
            else:
                merged_metadata = _merge_json(row["metadata_json"], incoming_metadata)
                effective_status = status if status is not None else row["status"]
                effective_completed_at = completed_at if completed_at is not None else row["completed_at"]
                if effective_completed_at is None and effective_status in TERMINAL_TASK_STATUSES:
                    effective_completed_at = now
                effective_requires_user = (
                    int(bool(incoming_requires_user))
                    if incoming_requires_user is not None
                    else int(row["requires_user"] or 0)
                )
                self._conn.execute(
                    """
                    UPDATE tasks
                    SET label = ?, status = ?, phase = ?, metadata_json = ?,
                        result_summary = ?, error = ?, blocker = ?, requires_user = ?,
                        started_at = ?, updated_at = ?, completed_at = ?
                    WHERE session_id = ? AND task_id = ?
                    """,
                    (
                        label if label is not None else row["label"],
                        effective_status,
                        incoming_phase if incoming_phase is not None else row["phase"],
                        _json_dumps(merged_metadata),
                        (
                            _compact_text(result_summary)
                            if result_summary is not None
                            else row["result_summary"]
                        ),
                        _compact_text(error) if error is not None else row["error"],
                        (
                            _compact_text(incoming_blocker)
                            if incoming_blocker is not None
                            else row["blocker"]
                        ),
                        effective_requires_user,
                        started_at if started_at is not None else row["started_at"],
                        now,
                        effective_completed_at,
                        session_id,
                        task_id,
                    ),
                )
            if extracted_artifacts:
                self._record_artifacts_locked(session_id, task_id, extracted_artifacts, now=now)
            self._touch_session_locked(session_id, now)
            self._conn.commit()

    def record_event(
        self,
        session_id: str,
        task_id: str,
        *,
        event_type: str,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        message: Optional[str] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        if not event_type:
            raise ValueError("event_type is required")
        now = self._timestamp(timestamp)
        incoming_metadata = _coerce_dict(metadata)
        event_phase = phase or _string_or_none(incoming_metadata.get("phase"))
        with self._lock:
            self.upsert_task(
                session_id,
                task_id,
                status=status,
                phase=event_phase,
                metadata=incoming_metadata,
                result_summary=result_summary,
                error=error,
                timestamp=now,
            )
            self._conn.execute(
                """
                INSERT INTO task_events (
                    session_id, task_id, timestamp, event_type, status, phase,
                    message, result_summary, error, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    now,
                    event_type,
                    status,
                    event_phase,
                    _compact_text(message) if message is not None else None,
                    _compact_text(result_summary) if result_summary is not None else None,
                    _compact_text(error) if error is not None else None,
                    _json_dumps(incoming_metadata),
                ),
            )
            self._touch_session_locked(session_id, now)
            self._conn.commit()

    def record_artifacts(
        self,
        session_id: str,
        task_id: str,
        artifacts: Dict[str, Any],
        *,
        timestamp: Optional[float] = None,
    ) -> None:
        now = self._timestamp(timestamp)
        with self._lock:
            self.upsert_task(session_id, task_id, timestamp=now)
            self._record_artifacts_locked(session_id, task_id, _coerce_dict(artifacts), now=now)
            self._touch_session_locked(session_id, now)
            self._conn.commit()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            sessions = {}
            session_rows = self._conn.execute(
                """
                SELECT * FROM sessions
                ORDER BY last_activity_at DESC, session_id ASC
                """
            ).fetchall()
            for row in session_rows:
                sessions[row["session_id"]] = {
                    "session_id": row["session_id"],
                    "label": row["label"],
                    "platform": row["platform"],
                    "source": row["source"],
                    "metadata": _json_loads(row["metadata_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "last_activity_at": row["last_activity_at"],
                    "active_count": 0,
                    "tasks": {},
                }

            task_rows = self._conn.execute(
                """
                SELECT * FROM tasks
                ORDER BY updated_at DESC, session_id ASC, task_id ASC
                """
            ).fetchall()
            counts = {}
            for row in task_rows:
                session = sessions.setdefault(
                    row["session_id"],
                    {
                        "session_id": row["session_id"],
                        "label": None,
                        "platform": None,
                        "source": None,
                        "metadata": {},
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "last_activity_at": row["updated_at"],
                        "active_count": 0,
                        "tasks": {},
                    },
                )
                artifacts = self._task_artifacts(row["session_id"], row["task_id"])
                events = self._task_events(row["session_id"], row["task_id"])
                task = {
                    "session_id": row["session_id"],
                    "task_id": row["task_id"],
                    "label": row["label"],
                    "status": row["status"],
                    "phase": row["phase"],
                    "metadata": _json_loads(row["metadata_json"]),
                    "artifacts": artifacts,
                    "result_summary": row["result_summary"],
                    "error": row["error"],
                    "blocker": row["blocker"],
                    "requires_user": bool(row["requires_user"]),
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "updated_at": row["updated_at"],
                    "completed_at": row["completed_at"],
                    "events": events,
                }
                if task["status"] == TASK_RUNNING:
                    session["active_count"] += 1
                counts[task["status"] or "unknown"] = counts.get(task["status"] or "unknown", 0) + 1
                session["tasks"][row["task_id"]] = task

            return {
                "ledger_path": str(self.path),
                "generated_at": self._timestamp(None),
                "sessions_total": len(sessions),
                "tasks_total": sum(counts.values()),
                "tasks_by_status": counts,
                "sessions": sessions,
            }

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    label TEXT,
                    platform TEXT,
                    source TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_activity_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    label TEXT,
                    status TEXT,
                    phase TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    result_summary TEXT,
                    error TEXT,
                    blocker TEXT,
                    requires_user INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    updated_at REAL NOT NULL,
                    completed_at REAL,
                    PRIMARY KEY (session_id, task_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT,
                    phase TEXT,
                    message TEXT,
                    result_summary TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (session_id, task_id) REFERENCES tasks(session_id, task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_task_events_task
                    ON task_events(session_id, task_id, timestamp, id);

                CREATE TABLE IF NOT EXISTS task_artifacts (
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    artifact_key TEXT NOT NULL,
                    artifact_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (session_id, task_id, artifact_key),
                    FOREIGN KEY (session_id, task_id) REFERENCES tasks(session_id, task_id)
                );
                """
            )
            self._conn.commit()

    def _record_artifacts_locked(self, session_id: str, task_id: str, artifacts: Dict[str, Any], *, now: float) -> None:
        for key, value in artifacts.items():
            clean_key = str(key or "").strip()
            if not clean_key or value is None:
                continue
            self._conn.execute(
                """
                INSERT INTO task_artifacts (
                    session_id, task_id, artifact_key, artifact_value, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, task_id, artifact_key)
                DO UPDATE SET artifact_value = excluded.artifact_value,
                              updated_at = excluded.updated_at
                """,
                (session_id, task_id, clean_key, _artifact_value(value), now),
            )

    def _task_artifacts(self, session_id: str, task_id: str) -> Dict[str, str]:
        rows = self._conn.execute(
            """
            SELECT artifact_key, artifact_value
            FROM task_artifacts
            WHERE session_id = ? AND task_id = ?
            ORDER BY artifact_key ASC
            """,
            (session_id, task_id),
        ).fetchall()
        return {row["artifact_key"]: row["artifact_value"] for row in rows}

    def _task_events(self, session_id: str, task_id: str) -> list[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT timestamp, event_type, status, phase, message,
                   result_summary, error, metadata_json
            FROM task_events
            WHERE session_id = ? AND task_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (session_id, task_id),
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "status": row["status"],
                "phase": row["phase"],
                "message": row["message"],
                "result_summary": row["result_summary"],
                "error": row["error"],
                "metadata": _json_loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def _touch_session_locked(self, session_id: str, now: float) -> None:
        self._conn.execute(
            """
            UPDATE sessions
            SET updated_at = ?, last_activity_at = ?
            WHERE session_id = ?
            """,
            (now, now, session_id),
        )

    def _timestamp(self, timestamp: Optional[float]) -> float:
        return float(self.time_fn() if timestamp is None else timestamp)


def _json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _json_loads(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _merge_json(existing_json: Optional[str], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = _json_loads(existing_json)
    merged.update(incoming or {})
    return merged


def _compact_text(value: Any, max_len: int = 1000) -> str:
    text = _WHITESPACE.sub(" ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_artifacts(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {key: metadata[key] for key in _ARTIFACT_KEYS if key in metadata and metadata[key] is not None}


def _artifact_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _coerce_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
