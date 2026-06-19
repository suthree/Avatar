import hashlib
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
_MULTI_UNDERSCORES = re.compile(r"_+")
_RAW_TURN_TEXT = re.compile(r"\bturn\s*(?:[#:]?\s*\d+)?\b[:：,.\-\s]*", re.IGNORECASE)

TASK_RUNNING = "running"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_STOPPED = "stopped"
DEFAULT_AEGIS_REPORT_INTERVAL_SEC = 1800
TERMINAL_TASK_STATUSES = {TASK_COMPLETED, TASK_FAILED, TASK_STOPPED}
_STATUS_LABELS = {
    TASK_RUNNING: "运行中",
    TASK_COMPLETED: "已完成",
    TASK_FAILED: "失败",
    TASK_STOPPED: "已停止",
}


def _safe_id_part(value: str, fallback: str, max_len: int = 64) -> str:
    raw = str(value or "").strip()
    cleaned = _UNSAFE_ID_CHARS.sub("_", raw)
    cleaned = _MULTI_UNDERSCORES.sub("_", cleaned).strip("._-")
    if not cleaned:
        cleaned = fallback
    if len(cleaned) <= max_len:
        return cleaned
    digest = hashlib.blake2s(raw.encode("utf-8"), digest_size=4).hexdigest()
    prefix_len = max_len - len(digest) - 1
    return f"{cleaned[:prefix_len].rstrip('._-')}-{digest}"


def build_feishu_session_id(
    app_id: Optional[str],
    chat_id: Optional[str],
    open_id: Optional[str],
) -> str:
    """Build a stable, filesystem-safe Feishu session id from routing identity."""
    if chat_id:
        route_kind = "chat"
        route_id = chat_id
    elif open_id:
        route_kind = "private"
        route_id = open_id
    else:
        raise ValueError("chat_id or open_id is required to build a Feishu session id")

    app_part = _safe_id_part(app_id or "default", "default")
    route_part = _safe_id_part(route_id, route_kind)
    digest_source = f"{app_id or ''}\0{route_kind}\0{route_id}"
    digest = hashlib.blake2s(digest_source.encode("utf-8"), digest_size=5).hexdigest()
    return f"feishu_{app_part}_{route_kind}_{route_part}_{digest}"


@dataclass
class AegisMeshActiveTask:
    task_id: str
    started_at: float
    updated_at: float
    status: str = TASK_RUNNING
    label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[float] = None
    result_summary: Optional[str] = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.status == TASK_RUNNING

    @running.setter
    def running(self, value: bool) -> None:
        if value:
            self.status = TASK_RUNNING
        elif self.status == TASK_RUNNING:
            self.status = TASK_STOPPED


@dataclass
class AegisMeshSessionState:
    session_id: str
    agent: Any
    agent_thread: Optional[threading.Thread]
    created_at: float
    updated_at: float
    label: Optional[str] = None
    active_task: Optional[AegisMeshActiveTask] = None
    tasks: Dict[str, AegisMeshActiveTask] = field(default_factory=dict)


@dataclass(frozen=True)
class AegisMeshReportTarget:
    session_id: str
    receive_id: str
    receive_id_type: str
    session_label: Optional[str] = None


class AegisMeshSessionManager:
    def __init__(
        self,
        agent_factory: Callable[[], Any],
        *,
        start_agent: bool = True,
        time_fn: Callable[[], float] = time.time,
        notification_limit: int = 100,
        task_event_limit: int = 50,
    ):
        self._agent_factory = agent_factory
        self._start_agent = start_agent
        self._time_fn = time_fn
        self._lock = threading.RLock()
        self._sessions: Dict[str, AegisMeshSessionState] = {}
        self._notifications: Deque[Dict[str, Any]] = deque(maxlen=max(0, int(notification_limit)))
        self._task_event_limit = max(0, int(task_event_limit))

    def get_or_create(self, session_id: str, *, label: Optional[str] = None) -> AegisMeshSessionState:
        if not session_id:
            raise ValueError("session_id is required")
        with self._lock:
            state = self._sessions.get(session_id)
            now = self._time_fn()
            if state is not None:
                if label and state.label != label:
                    state.label = label
                state.updated_at = now
                return state

            agent = self._agent_factory()
            thread = self._start_agent_thread(session_id, agent) if self._start_agent else None
            state = AegisMeshSessionState(
                session_id=session_id,
                agent=agent,
                agent_thread=thread,
                created_at=now,
                updated_at=now,
                label=label,
            )
            self._sessions[session_id] = state
            return state

    def begin_task(
        self,
        session_id: str,
        task_id: str,
        *,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[AegisMeshSessionState, Optional[AegisMeshActiveTask]]:
        with self._lock:
            state = self.get_or_create(session_id, label=label)
            if state.active_task and state.active_task.running:
                return state, None
            now = self._time_fn()
            task = AegisMeshActiveTask(
                task_id=task_id,
                started_at=now,
                updated_at=now,
                status=TASK_RUNNING,
                label=label,
                metadata=dict(metadata or {}),
            )
            state.active_task = task
            state.tasks[task_id] = task
            state.updated_at = now
            self._record_task_event_locked(
                state,
                task,
                event_type="started",
                message="任务已开始",
                notify=False,
                timestamp=now,
            )
            return state, task

    def finish_task(self, session_id: str, task_id: Optional[str] = None) -> bool:
        return self.complete_task(session_id, task_id)

    def record_task_event(
        self,
        session_id: str,
        task_id: str,
        *,
        event_type: str = "progress",
        status: Optional[str] = None,
        message: Optional[str] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        notify: bool = False,
    ) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return False
            task = state.tasks.get(task_id)
            if task is None:
                return False
            self._record_task_event_locked(
                state,
                task,
                event_type=event_type,
                status=status,
                message=message,
                result_summary=result_summary,
                error=error,
                metadata=metadata,
                notify=notify,
            )
            return True

    def complete_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
        *,
        result_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._set_terminal_task(
            session_id,
            task_id,
            TASK_COMPLETED,
            event_type="completed",
            message="任务已完成",
            result_summary=result_summary,
            metadata=metadata,
            notify=True,
        )

    def fail_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
        *,
        error: Optional[str] = None,
        result_summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._set_terminal_task(
            session_id,
            task_id,
            TASK_FAILED,
            event_type="failed",
            message="任务失败",
            result_summary=result_summary,
            error=error,
            metadata=metadata,
            notify=True,
        )

    def stop_task(self, session_id: str, task_id: Optional[str] = None, *, reason: Optional[str] = None) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return False
            task = self._find_task_locked(state, task_id)
            had_active_task = task is not None and task.running and state.active_task is task
            if task is not None:
                self._record_task_event_locked(
                    state,
                    task,
                    event_type="stopped",
                    status=TASK_STOPPED,
                    message=reason or "任务已停止",
                    error=reason,
                    notify=True,
                )
            agent = state.agent

        abort = getattr(agent, "abort", None) if had_active_task else None
        if callable(abort):
            abort()
        return had_active_task

    def notify_task_result(
        self,
        session_id: str,
        task_id: str,
        status: str,
        *,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
    ) -> bool:
        """In-process hook for future Codex watchers to publish task results."""
        with self._lock:
            state = self.get_or_create(session_id, label=label)
            if task_id not in state.tasks:
                now = self._time_fn()
                state.tasks[task_id] = AegisMeshActiveTask(
                    task_id=task_id,
                    started_at=now,
                    updated_at=now,
                    status=TASK_RUNNING,
                    label=label,
                    metadata=dict(metadata or {}),
                )
            if status == TASK_COMPLETED:
                return self.complete_task(session_id, task_id, result_summary=result_summary, metadata=metadata)
            if status == TASK_FAILED:
                return self.fail_task(session_id, task_id, error=error, result_summary=result_summary, metadata=metadata)
            if status == TASK_STOPPED:
                return self.stop_task(session_id, task_id, reason=error or result_summary)
            if status == TASK_RUNNING:
                return self.record_task_event(
                    session_id,
                    task_id,
                    status=TASK_RUNNING,
                    message=result_summary,
                    metadata=metadata,
                )
            raise ValueError(f"unsupported task status: {status}")

    def is_busy(self, session_id: str) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            return bool(state and state.active_task and state.active_task.running)

    def snapshot(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if session_id is not None:
                state = self._sessions.get(session_id)
                return self._snapshot_state(state) if state else {}
            return {sid: self._snapshot_state(state) for sid, state in self._sessions.items()}

    def dashboard_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            sessions = {sid: self._snapshot_state(state) for sid, state in self._sessions.items()}
            counts = {
                TASK_RUNNING: 0,
                TASK_COMPLETED: 0,
                TASK_FAILED: 0,
                TASK_STOPPED: 0,
            }
            attention = []
            for state in self._sessions.values():
                for task in state.tasks.values():
                    if task.status in counts:
                        counts[task.status] += 1
                    if task.status in {TASK_FAILED, TASK_STOPPED}:
                        attention.append(
                            {
                                "session_id": state.session_id,
                                "session_label": state.label,
                                "task_id": task.task_id,
                                "task_label": task.label,
                                "status": task.status,
                                "updated_at": task.updated_at,
                                "result_summary": task.result_summary,
                                "error": task.error,
                            }
                        )
            attention.sort(key=lambda item: item["updated_at"], reverse=True)
            return {
                "sessions_total": len(self._sessions),
                "agents_total": sum(1 for state in self._sessions.values() if state.agent is not None),
                "tasks_running": counts[TASK_RUNNING],
                "tasks_completed": counts[TASK_COMPLETED],
                "tasks_failed": counts[TASK_FAILED],
                "tasks_stopped": counts[TASK_STOPPED],
                "notifications_pending": len(self._notifications),
                "attention_required": attention,
                "sessions": sessions,
            }

    def consume_notifications(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if limit is None or limit < 0 or limit >= len(self._notifications):
                notifications = list(self._notifications)
                self._notifications.clear()
                return notifications
            notifications = []
            for _ in range(limit):
                if not self._notifications:
                    break
                notifications.append(self._notifications.popleft())
            return notifications

    def _start_agent_thread(self, session_id: str, agent: Any) -> Optional[threading.Thread]:
        run = getattr(agent, "run", None)
        if not callable(run):
            return None
        thread = threading.Thread(
            target=run,
            daemon=True,
            name=f"aegis-mesh-agent-{session_id[:48]}",
        )
        thread.start()
        return thread

    def _set_terminal_task(
        self,
        session_id: str,
        task_id: Optional[str],
        status: str,
        *,
        event_type: str,
        message: str,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        notify: bool,
    ) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return False
            task = self._find_task_locked(state, task_id)
            if task is None:
                return False
            if task.status in TERMINAL_TASK_STATUSES:
                return task.status == status
            self._record_task_event_locked(
                state,
                task,
                event_type=event_type,
                status=status,
                message=message,
                result_summary=result_summary,
                error=error,
                metadata=metadata,
                notify=notify,
            )
            return True

    @staticmethod
    def _find_task_locked(
        state: AegisMeshSessionState,
        task_id: Optional[str],
    ) -> Optional[AegisMeshActiveTask]:
        if task_id is None:
            return state.active_task
        return state.tasks.get(task_id)

    def _record_task_event_locked(
        self,
        state: AegisMeshSessionState,
        task: AegisMeshActiveTask,
        *,
        event_type: str,
        status: Optional[str] = None,
        message: Optional[str] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        notify: bool,
        timestamp: Optional[float] = None,
    ) -> None:
        now = self._time_fn() if timestamp is None else timestamp
        if status is not None:
            task.status = status
        if result_summary is not None:
            task.result_summary = _compact_text(result_summary)
        if error is not None:
            task.error = _compact_text(error)
        if metadata:
            task.metadata.update(metadata)
        task.updated_at = now
        if task.status in TERMINAL_TASK_STATUSES:
            task.completed_at = now
            if state.active_task is task:
                state.active_task = None
        state.updated_at = now
        event = {
            "timestamp": now,
            "event_type": event_type,
            "status": task.status,
            "message": _compact_text(message) if message else None,
            "result_summary": task.result_summary,
            "error": task.error,
            "metadata": dict(metadata or {}),
        }
        task.events.append(event)
        if self._task_event_limit == 0:
            task.events.clear()
        elif len(task.events) > self._task_event_limit:
            del task.events[:-self._task_event_limit]
        if notify:
            self._notifications.append(
                {
                    "timestamp": now,
                    "event_type": event_type,
                    "session_id": state.session_id,
                    "session_label": state.label,
                    "task_id": task.task_id,
                    "task_label": task.label,
                    "status": task.status,
                    "message": event["message"],
                    "result_summary": task.result_summary,
                    "error": task.error,
                    "metadata": dict(task.metadata),
                }
            )

    @staticmethod
    def _snapshot_state(state: Optional[AegisMeshSessionState]) -> Dict[str, Any]:
        if state is None:
            return {}
        active = None
        if state.active_task is not None:
            active = AegisMeshSessionManager._snapshot_task(state.active_task)
        return {
            "session_id": state.session_id,
            "label": state.label,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "active_task": active,
            "tasks": {
                task_id: AegisMeshSessionManager._snapshot_task(task)
                for task_id, task in state.tasks.items()
            },
            "agent_running": bool(getattr(state.agent, "is_running", False)),
        }

    @staticmethod
    def _snapshot_task(task: AegisMeshActiveTask) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "running": task.running,
            "status": task.status,
            "started_at": task.started_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
            "label": task.label,
            "metadata": dict(task.metadata),
            "result_summary": task.result_summary,
            "error": task.error,
            "events": [dict(event) for event in task.events],
        }


def _compact_text(value: Any, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _status_label(status: Optional[str]) -> str:
    return _STATUS_LABELS.get(status or "", status or "未知")


def _scrub_report_text(value: Any, max_len: int = 240) -> str:
    text = _compact_text(value, max_len=max_len)
    text = _RAW_TURN_TEXT.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _latest_task_note(task: Dict[str, Any]) -> str:
    for event in reversed(task.get("events") or []):
        for key in ("result_summary", "error", "message"):
            if event.get(key):
                note = _scrub_report_text(event.get(key))
                if note:
                    return note
    for key in ("result_summary", "error"):
        if task.get(key):
            note = _scrub_report_text(task.get(key))
            if note:
                return note
    return ""


def _report_task_label(task: Dict[str, Any]) -> str:
    return task.get("label") or task.get("task_id") or "任务"


def _report_session_label(session: Dict[str, Any], session_id: str) -> str:
    return session.get("label") or session_id or "会话"


def _task_updated_at(task: Dict[str, Any]) -> float:
    try:
        return float(task.get("updated_at") or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_recent_task(task: Dict[str, Any], since: Optional[float]) -> bool:
    return since is not None and _task_updated_at(task) >= since


def _report_route(task: Dict[str, Any]) -> Tuple[str, str]:
    metadata = task.get("metadata") or {}
    receive_id = str(metadata.get("receive_id") or "").strip()
    receive_id_type = str(metadata.get("receive_id_type") or "open_id").strip() or "open_id"
    return receive_id, receive_id_type


def _eligible_route_task(session: Dict[str, Any], since: Optional[float]) -> Optional[Dict[str, Any]]:
    tasks = list((session.get("tasks") or {}).values())
    eligible = [
        task
        for task in tasks
        if task.get("status") == TASK_RUNNING or _is_recent_task(task, since)
    ]
    eligible.sort(
        key=lambda task: (
            1 if task.get("status") == TASK_RUNNING else 0,
            _task_updated_at(task),
        ),
        reverse=True,
    )
    for task in eligible:
        receive_id, _ = _report_route(task)
        if receive_id:
            return task
    return None


def plan_periodic_report_targets(
    snapshot: Dict[str, Any],
    *,
    since: Optional[float] = None,
) -> List[AegisMeshReportTarget]:
    candidates = []
    sessions = snapshot.get("sessions") or {}
    for session_id, session in sessions.items():
        task = _eligible_route_task(session, since)
        if not task:
            continue
        receive_id, receive_id_type = _report_route(task)
        candidates.append(
            (
                0 if task.get("status") == TASK_RUNNING else 1,
                -_task_updated_at(task),
                session_id,
                AegisMeshReportTarget(
                    session_id=session_id,
                    receive_id=receive_id,
                    receive_id_type=receive_id_type,
                    session_label=session.get("label"),
                ),
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    seen = set()
    targets = []
    for _, _, _, target in candidates:
        key = (target.receive_id_type, target.receive_id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def _iter_report_sessions(
    snapshot: Dict[str, Any],
    target_session_id: Optional[str],
) -> List[Tuple[str, Dict[str, Any]]]:
    sessions = snapshot.get("sessions") or {}
    if target_session_id is not None:
        session = sessions.get(target_session_id)
        return [(target_session_id, session)] if session else []
    return list(sessions.items())


def _format_report_task_line(session_id: str, session: Dict[str, Any], task: Dict[str, Any]) -> str:
    session_label = _report_session_label(session, session_id)
    task_label = _report_task_label(task)
    status = _status_label(task.get("status"))
    note = _latest_task_note(task)
    suffix = f" · {note}" if note else ""
    return f"- {session_label} · {task_label} · {status}{suffix}"


def _report_running_tasks(
    sessions: List[Tuple[str, Dict[str, Any]]],
    limit: int,
) -> List[str]:
    running = []
    for session_id, session in sessions:
        for task in (session.get("tasks") or {}).values():
            if task.get("status") == TASK_RUNNING:
                running.append((session_id, session, task))
    running.sort(key=lambda item: _task_updated_at(item[2]), reverse=True)
    return [_format_report_task_line(*item) for item in running[:limit]]


def _report_recent_tasks(
    sessions: List[Tuple[str, Dict[str, Any]]],
    *,
    since: Optional[float],
    target_session_id: Optional[str],
    limit: int,
) -> List[str]:
    recent = []
    for session_id, session in sessions:
        tasks = list((session.get("tasks") or {}).values())
        for task in tasks:
            if task.get("status") == TASK_RUNNING:
                continue
            if since is not None and not _is_recent_task(task, since):
                continue
            recent.append((session_id, session, task))
    recent.sort(key=lambda item: _task_updated_at(item[2]), reverse=True)
    if since is None and target_session_id is not None:
        recent = recent[:1]
    elif since is None:
        recent = []
    return [_format_report_task_line(*item) for item in recent[:limit]]


def _report_attention_lines(
    snapshot: Dict[str, Any],
    *,
    target_session_id: Optional[str],
    limit: int,
) -> List[str]:
    attention = []
    for item in snapshot.get("attention_required") or []:
        if target_session_id is not None and item.get("session_id") != target_session_id:
            continue
        session = item.get("session_label") or item.get("session_id") or "未知会话"
        task = item.get("task_label") or item.get("task_id") or "未知任务"
        reason = _scrub_report_text(item.get("error") or item.get("result_summary") or "")
        suffix = f" · {reason}" if reason else ""
        attention.append(f"- {session} · {task} · {_status_label(item.get('status'))}{suffix}")
        if len(attention) >= limit:
            break
    return attention


def render_periodic_report_text(
    snapshot: Dict[str, Any],
    *,
    target_session_id: Optional[str] = None,
    recent_since: Optional[float] = None,
    running_limit: int = 8,
    activity_limit: int = 6,
    attention_limit: int = 5,
) -> str:
    sessions = _iter_report_sessions(snapshot, target_session_id)
    lines = [
        "Aegis Mesh 定时摘要",
        f"会话 {snapshot.get('sessions_total', 0)} · Agent {snapshot.get('agents_total', 0)}",
        (
            "任务 "
            f"运行中 {snapshot.get('tasks_running', 0)} / "
            f"已完成 {snapshot.get('tasks_completed', 0)} / "
            f"失败 {snapshot.get('tasks_failed', 0)} / "
            f"已停止 {snapshot.get('tasks_stopped', 0)}"
        ),
        f"待通知 {snapshot.get('notifications_pending', 0)}",
    ]
    if target_session_id is not None:
        target_label = sessions[0][1].get("label") if sessions else target_session_id
        lines.append(f"范围: {target_label or target_session_id}")

    running_lines = _report_running_tasks(sessions, running_limit)
    lines.append("运行中:")
    lines.extend(running_lines or ["- 暂无"])

    recent_lines = _report_recent_tasks(
        sessions,
        since=recent_since,
        target_session_id=target_session_id,
        limit=activity_limit,
    )
    if recent_lines:
        lines.append("最近活动:")
        lines.extend(recent_lines)

    attention_lines = _report_attention_lines(
        snapshot,
        target_session_id=target_session_id,
        limit=attention_limit,
    )
    lines.append("需关注:")
    lines.extend(attention_lines or ["- 暂无"])
    return "\n".join(lines)


class AegisMeshPeriodicReporter:
    def __init__(
        self,
        session_manager: AegisMeshSessionManager,
        *,
        send_fn: Callable[..., Any],
        split_fn: Callable[[str, int], List[str]],
        interval_sec: int = DEFAULT_AEGIS_REPORT_INTERVAL_SEC,
        split_limit: int = 4000,
        time_fn: Callable[[], float] = time.time,
        on_error: Optional[Callable[[BaseException], None]] = None,
    ):
        self.session_manager = session_manager
        self.send_fn = send_fn
        self.split_fn = split_fn
        self.interval_sec = max(0, int(interval_sec))
        self.split_limit = split_limit
        self.time_fn = time_fn
        self.on_error = on_error
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_report_at: Optional[float] = self.time_fn()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> bool:
        if self.interval_sec <= 0:
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="aegis-mesh-periodic-reporter",
            )
            self._thread.start()
            return True

    def stop(self, timeout: Optional[float] = None) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout)

    def send_once(self) -> int:
        now = self.time_fn()
        since = self._last_report_at
        snapshot = self.session_manager.dashboard_snapshot()
        targets = plan_periodic_report_targets(snapshot, since=since)
        delivered = 0
        for target in targets:
            text = render_periodic_report_text(
                snapshot,
                target_session_id=target.session_id,
                recent_since=since,
            )
            for part in self.split_fn(text, self.split_limit):
                self.send_fn(target.receive_id, part, receive_id_type=target.receive_id_type)
            delivered += 1
        self._last_report_at = now
        return delivered

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.interval_sec):
            try:
                self.send_once()
            except Exception as exc:
                if self.on_error:
                    self.on_error(exc)


def render_dashboard_text(snapshot: Dict[str, Any], *, attention_limit: int = 5) -> str:
    lines = [
        "Aegis Mesh 看板",
        f"会话 {snapshot.get('sessions_total', 0)} · Agent {snapshot.get('agents_total', 0)}",
        (
            "任务 "
            f"运行中 {snapshot.get('tasks_running', 0)} / "
            f"已完成 {snapshot.get('tasks_completed', 0)} / "
            f"失败 {snapshot.get('tasks_failed', 0)} / "
            f"已停止 {snapshot.get('tasks_stopped', 0)}"
        ),
        f"待通知 {snapshot.get('notifications_pending', 0)}",
    ]
    attention = list(snapshot.get("attention_required") or [])
    if attention:
        lines.append("需关注:")
        for item in attention[:attention_limit]:
            session = item.get("session_label") or item.get("session_id") or "未知会话"
            task = item.get("task_label") or item.get("task_id") or "未知任务"
            reason = item.get("error") or item.get("result_summary") or ""
            suffix = f" · {reason}" if reason else ""
            lines.append(f"- {session} · {task} · {_status_label(item.get('status'))}{suffix}")
    else:
        lines.append("需关注: 暂无")
    return "\n".join(lines)


def render_session_status_text(
    session_snapshot: Dict[str, Any],
    *,
    dashboard: Optional[Dict[str, Any]] = None,
) -> str:
    if not session_snapshot:
        return "当前会话未初始化。"
    label = session_snapshot.get("label") or session_snapshot.get("session_id") or "当前会话"
    tasks = list((session_snapshot.get("tasks") or {}).values())
    latest_task = session_snapshot.get("active_task")
    if latest_task is None and tasks:
        latest_task = max(tasks, key=lambda item: item.get("updated_at") or 0)
    lines = [f"会话: {label}"]
    if latest_task:
        task_label = latest_task.get("label") or latest_task.get("task_id") or "任务"
        lines.append(f"任务: {_status_label(latest_task.get('status'))} · {task_label}")
        if latest_task.get("result_summary"):
            lines.append(f"结果: {latest_task['result_summary']}")
        if latest_task.get("error"):
            lines.append(f"原因: {latest_task['error']}")
    else:
        lines.append("任务: 空闲")
    if dashboard:
        lines.append(
            "全局: "
            f"会话 {dashboard.get('sessions_total', 0)} · "
            f"Agent {dashboard.get('agents_total', 0)} · "
            f"运行中 {dashboard.get('tasks_running', 0)} · "
            f"待通知 {dashboard.get('notifications_pending', 0)}"
        )
    return "\n".join(lines)
