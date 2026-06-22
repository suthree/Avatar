from __future__ import annotations

import argparse
import html
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

from frontends.aegis_mesh_ledger import AegisMeshLedger, default_aegis_mesh_ledger_path


BOARD_GROUPS = [
    ("intake", "Intake"),
    ("issue_ready", "Issue Ready"),
    ("codex_running", "Codex Running"),
    ("codex_done", "Codex Done"),
    ("avatar_verify", "Avatar Verify"),
    ("blocked/requires_user", "Blocked / User"),
    ("done/completed", "Done"),
    ("failed/stopped", "Failed / Stopped"),
]

SAFE_ARTIFACT_LABELS = [
    ("project", "Project"),
    ("repo", "Repo"),
    ("github_issue_url", "GitHub Issue"),
    ("github_issue_number", "Issue Number"),
    ("branch", "Branch"),
    ("worktree", "Worktree"),
    ("codex_pid", "Codex PID"),
    ("log_path", "Log Path"),
    ("answer_path", "Answer Path"),
    ("handoff_path", "Handoff Path"),
    ("verification_artifact", "Verification"),
    ("verification_artifacts", "Verification Artifacts"),
    ("verification_path", "Verification Path"),
    ("avatar_verification_path", "Avatar Verification"),
]

_GROUP_IDS = {group_id for group_id, _label in BOARD_GROUPS}
_CONFLICT_KEYS = {
    "repo_conflict",
    "worktree_conflict",
    "lock_conflict",
    "conflict_marker",
    "repo_lock_conflict",
    "worktree_lock_conflict",
}


def build_board_model(
    ledger_or_snapshot: Any,
    *,
    now: Optional[float] = None,
    stale_after_sec: float = 3600.0,
    verification_overdue_sec: float = 24 * 3600.0,
    process_exists_fn: Optional[Callable[[int], bool]] = None,
) -> Dict[str, Any]:
    snapshot = ledger_or_snapshot.snapshot() if hasattr(ledger_or_snapshot, "snapshot") else ledger_or_snapshot
    snapshot = snapshot or {}
    current_time = float(time.time() if now is None else now)
    process_exists = process_exists_fn or _process_exists
    sessions = []
    tasks = []
    groups = {group_id: [] for group_id, _label in BOARD_GROUPS}

    for session_id, session in (snapshot.get("sessions") or {}).items():
        task_values = list((session.get("tasks") or {}).values())
        sessions.append(
            {
                "session_id": session_id,
                "label": session.get("label"),
                "platform": session.get("platform"),
                "source": session.get("source"),
                "active_count": session.get("active_count", 0),
                "last_activity_at": session.get("last_activity_at") or session.get("updated_at"),
                "task_count": len(task_values),
            }
        )
        for raw_task in task_values:
            task = dict(raw_task)
            task["session_id"] = session_id
            task["session_label"] = session.get("label")
            task["platform"] = session.get("platform")
            task["display_artifacts"] = _display_artifacts(task)
            task["latest_note"] = _latest_note(task)
            task["health"] = _health_indicators(
                task,
                now=current_time,
                stale_after_sec=stale_after_sec,
                verification_overdue_sec=verification_overdue_sec,
                process_exists_fn=process_exists,
            )
            task["group"] = _task_group(task)
            task["anchor"] = _anchor_id(session_id, task.get("task_id"))
            groups.setdefault(task["group"], []).append(task)
            tasks.append(task)

    sessions.sort(key=lambda item: (item.get("last_activity_at") or 0, item["session_id"]), reverse=True)
    tasks.sort(key=lambda item: (item.get("updated_at") or 0, item["session_id"], item.get("task_id") or ""), reverse=True)
    for group_tasks in groups.values():
        group_tasks.sort(key=lambda item: (item.get("updated_at") or 0, item["session_id"], item.get("task_id") or ""), reverse=True)

    status_counts = dict(snapshot.get("tasks_by_status") or {})
    return {
        "generated_at": current_time,
        "ledger_path": snapshot.get("ledger_path"),
        "sessions_total": snapshot.get("sessions_total", len(sessions)),
        "tasks_total": snapshot.get("tasks_total", len(tasks)),
        "tasks_by_status": status_counts,
        "sessions": sessions,
        "tasks": tasks,
        "groups": groups,
        "group_order": BOARD_GROUPS,
        "health_total": sum(len(task["health"]) for task in tasks),
    }


def render_dashboard_html(model: Dict[str, Any]) -> str:
    model = model or {}
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Aegis Mesh Board</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        '<header class="topbar">',
        "<div>",
        "<h1>Aegis Mesh Board</h1>",
        "</div>",
        '<a class="refresh" href="/">Refresh</a>',
        "</header>",
        '<main class="shell">',
        _render_summary(model),
        _render_sessions(model.get("sessions") or []),
        _render_board(model),
        _render_task_details(model.get("tasks") or []),
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


def serve(
    *,
    ledger_path: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    path = ledger_path or str(default_aegis_mesh_ledger_path())

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self._send_json({"ok": True, "ledger_path": path})
                return
            if parsed.path not in {"/", "/task"}:
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            with AegisMeshLedger(path) as ledger:
                model = build_board_model(ledger.snapshot())
            if parsed.path == "/task":
                model = _filter_task_model(model, query.get("session_id", [None])[0], query.get("task_id", [None])[0])
            self._send_html(render_dashboard_html(model))

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: Dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"Aegis Mesh Web GUI serving http://{host}:{int(port)} with ledger {path}")
    server.serve_forever()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Serve or render the local Aegis Mesh task board.")
    parser.add_argument("--ledger", default=str(default_aegis_mesh_ledger_path()), help="SQLite ledger path")
    parser.add_argument("--host", default="127.0.0.1", help="Local bind host")
    parser.add_argument("--port", type=int, default=8765, help="Local bind port")
    parser.add_argument("--render-once", action="store_true", help="Render dashboard HTML to stdout and exit")
    args = parser.parse_args(argv)

    if args.render_once:
        with AegisMeshLedger(args.ledger) as ledger:
            print(render_dashboard_html(build_board_model(ledger.snapshot())))
        return 0
    serve(ledger_path=args.ledger, host=args.host, port=args.port)
    return 0


def _render_summary(model: Dict[str, Any]) -> str:
    rows = [
        ("Sessions", model.get("sessions_total", 0)),
        ("Tasks", model.get("tasks_total", 0)),
        ("Health", model.get("health_total", 0)),
    ]
    counts = model.get("tasks_by_status") or {}
    for key in ("running", "completed", "failed", "stopped"):
        if key in counts:
            rows.append((key.title(), counts[key]))
    if model.get("ledger_path"):
        rows.append(("Ledger", model.get("ledger_path")))
    items = []
    for label, value in rows:
        items.append(
            '<div class="metric">'
            f'<span class="metric-label">{_e(label)}</span>'
            f'<strong>{_e(value)}</strong>'
            "</div>"
        )
    return '<section class="metrics" aria-label="Summary">' + "".join(items) + "</section>"


def _render_sessions(sessions: Iterable[Dict[str, Any]]) -> str:
    rows = []
    for session in sessions:
        rows.append(
            "<tr>"
            f"<td><code>{_e(session.get('session_id'))}</code></td>"
            f"<td>{_e(session.get('label') or '')}</td>"
            f"<td>{_e(session.get('platform') or '')}</td>"
            f"<td>{_e(session.get('active_count'))}</td>"
            f"<td>{_format_ts(session.get('last_activity_at'))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5" class="empty">No sessions recorded</td></tr>')
    return (
        '<section class="section">'
        "<h2>Sessions</h2>"
        '<div class="table-wrap">'
        "<table>"
        "<thead><tr><th>Session</th><th>Label</th><th>Platform</th><th>Active</th><th>Last Activity</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
        "</section>"
    )


def _render_board(model: Dict[str, Any]) -> str:
    columns = []
    groups = model.get("groups") or {}
    for group_id, label in model.get("group_order") or BOARD_GROUPS:
        tasks = groups.get(group_id) or []
        cards = "".join(_render_task_card(task) for task in tasks)
        if not cards:
            cards = '<div class="empty">No tasks</div>'
        columns.append(
            f'<section class="column" data-board-group="{_e(group_id)}">'
            f"<h2>{_e(label)} <span>{len(tasks)}</span></h2>"
            f"{cards}"
            "</section>"
        )
    return '<section class="board" aria-label="Task board">' + "".join(columns) + "</section>"


def _render_task_card(task: Dict[str, Any]) -> str:
    health = "".join(_render_health(indicator) for indicator in task.get("health") or [])
    artifacts = _render_artifact_list(task.get("display_artifacts") or [], compact=True)
    note = task.get("latest_note")
    note_html = f'<p class="note">{_e(note)}</p>' if note else ""
    return (
        f'<article class="task" id="{_e(task.get("anchor"))}">'
        f'<div class="task-head"><strong>{_e(task.get("label") or task.get("task_id"))}</strong>'
        f'<span>{_e(task.get("status") or "")}</span></div>'
        f'<div class="meta"><code>{_e(task.get("session_id"))}</code> · <code>{_e(task.get("task_id"))}</code></div>'
        f'<div class="phase">{_e(task.get("phase") or task.get("group"))}</div>'
        f'<div class="health-row">{health}</div>'
        f"{note_html}"
        f"{artifacts}"
        "</article>"
    )


def _render_task_details(tasks: Iterable[Dict[str, Any]]) -> str:
    blocks = []
    for task in tasks:
        events = task.get("events") or []
        event_rows = []
        for event in events[-5:]:
            event_rows.append(
                "<li>"
                f"<span>{_format_ts(event.get('timestamp'))}</span>"
                f"<strong>{_e(event.get('event_type'))}</strong>"
                f"<em>{_e(event.get('message') or event.get('result_summary') or event.get('error') or '')}</em>"
                "</li>"
            )
        if not event_rows:
            event_rows.append('<li class="empty">No events recorded</li>')
        blocks.append(
            '<section class="detail">'
            f"<h3>{_e(task.get('label') or task.get('task_id'))}</h3>"
            '<div class="detail-grid">'
            f"<div><span>Session</span><code>{_e(task.get('session_id'))}</code></div>"
            f"<div><span>Task</span><code>{_e(task.get('task_id'))}</code></div>"
            f"<div><span>Status</span><code>{_e(task.get('status'))}</code></div>"
            f"<div><span>Phase</span><code>{_e(task.get('phase'))}</code></div>"
            f"<div><span>Updated</span><code>{_format_ts(task.get('updated_at'))}</code></div>"
            "</div>"
            f"{_render_artifact_list(task.get('display_artifacts') or [], compact=False)}"
            f"<ul class=\"events\">{''.join(event_rows)}</ul>"
            "</section>"
        )
    if not blocks:
        blocks.append('<div class="empty">No task details recorded</div>')
    return '<section class="section"><h2>Task Detail</h2>' + "".join(blocks) + "</section>"


def _render_artifact_list(artifacts: Iterable[Dict[str, str]], *, compact: bool) -> str:
    items = []
    for artifact in artifacts:
        key = artifact["key"]
        value = artifact["value"]
        label = artifact["label"]
        if key == "github_issue_url":
            rendered_value = f'<a href="{_e(value)}" rel="noreferrer">{_e(value)}</a>'
        else:
            rendered_value = f"<code>{_e(value)}</code>"
        items.append(f"<li><span>{_e(label)}</span>{rendered_value}</li>")
    if not items:
        return "" if compact else '<ul class="artifacts empty"><li>No artifacts recorded</li></ul>'
    klass = "artifacts compact" if compact else "artifacts"
    return f'<ul class="{klass}">' + "".join(items) + "</ul>"


def _render_health(indicator: Dict[str, str]) -> str:
    code = str(indicator.get("code") or "unknown")
    css_code = code.replace("_", "-")
    label = indicator.get("label") or css_code
    return (
        f'<span class="health health--{_e(css_code)}" '
        f'data-health-code="{_e(code)}" title="{_e(indicator.get("detail") or "")}">'
        f"{_e(label)}"
        "</span>"
    )


def _filter_task_model(model: Dict[str, Any], session_id: Optional[str], task_id: Optional[str]) -> Dict[str, Any]:
    if not session_id or not task_id:
        return model
    tasks = [
        task
        for task in model.get("tasks") or []
        if task.get("session_id") == session_id and task.get("task_id") == task_id
    ]
    filtered = dict(model)
    filtered["tasks"] = tasks
    filtered["groups"] = {group_id: [] for group_id, _label in BOARD_GROUPS}
    for task in tasks:
        filtered["groups"].setdefault(task["group"], []).append(task)
    filtered["tasks_total"] = len(tasks)
    filtered["health_total"] = sum(len(task.get("health") or []) for task in tasks)
    return filtered


def _task_group(task: Dict[str, Any]) -> str:
    status = str(task.get("status") or "").lower()
    phase = str(task.get("phase") or "").lower()
    if task.get("requires_user") or task.get("blocker") or status == "blocked" or phase in {"blocked", "requires_user"}:
        return "blocked/requires_user"
    if status in {"failed", "stopped"} or phase in {"failed", "stopped"}:
        return "failed/stopped"
    if status in {"completed", "done"} or phase in {"completed", "done"}:
        return "done/completed"
    if phase in _GROUP_IDS:
        return phase
    if status == "running":
        return "codex_running"
    return "intake"


def _health_indicators(
    task: Dict[str, Any],
    *,
    now: float,
    stale_after_sec: float,
    verification_overdue_sec: float,
    process_exists_fn: Callable[[int], bool],
) -> List[Dict[str, str]]:
    indicators = []
    status = str(task.get("status") or "").lower()
    phase = str(task.get("phase") or "").lower()
    updated_at = _float_or_zero(task.get("updated_at"))
    age = max(0.0, now - updated_at) if updated_at else 0.0
    artifacts = task.get("artifacts") or {}
    metadata = task.get("metadata") or {}

    if status == "running" and age > stale_after_sec:
        indicators.append(
            {
                "code": "stale_running_task",
                "label": "stale-running-task",
                "detail": f"No activity for {int(age)} seconds",
            }
        )

    pid = _int_or_none(artifacts.get("codex_pid") or metadata.get("codex_pid"))
    if pid is not None and (status == "running" or phase == "codex_running") and not process_exists_fn(pid):
        indicators.append(
            {
                "code": "process_not_found",
                "label": "process-not-found",
                "detail": f"PID {pid} is not running",
            }
        )

    if phase in {"codex_done", "avatar_verify"} and not artifacts.get("handoff_path"):
        indicators.append(
            {
                "code": "missing_handoff",
                "label": "missing-handoff",
                "detail": "Codex handoff path is absent",
            }
        )

    if phase == "avatar_verify" and age > verification_overdue_sec:
        indicators.append(
            {
                "code": "overdue_verification",
                "label": "overdue-verification",
                "detail": f"Verification has waited {int(age)} seconds",
            }
        )

    if task.get("requires_user") or task.get("blocker") or phase in {"blocked", "requires_user"}:
        indicators.append(
            {
                "code": "requires_user",
                "label": "requires-user",
                "detail": str(task.get("blocker") or "Task requires user input"),
            }
        )

    conflict = _first_conflict_marker(metadata, artifacts)
    if conflict:
        indicators.append(
            {
                "code": "repo_worktree_conflict",
                "label": "repo-worktree-conflict",
                "detail": conflict,
            }
        )
    return indicators


def _display_artifacts(task: Dict[str, Any]) -> List[Dict[str, str]]:
    artifacts = task.get("artifacts") or {}
    display = []
    for key, label in SAFE_ARTIFACT_LABELS:
        if key not in artifacts or artifacts[key] in (None, ""):
            continue
        display.append({"key": key, "label": label, "value": str(artifacts[key])})
    return display


def _latest_note(task: Dict[str, Any]) -> str:
    for event in reversed(task.get("events") or []):
        for key in ("result_summary", "error", "message"):
            if event.get(key):
                return str(event[key])
    for key in ("result_summary", "error", "blocker"):
        if task.get(key):
            return str(task[key])
    return ""


def _first_conflict_marker(metadata: Dict[str, Any], artifacts: Dict[str, Any]) -> str:
    for source in (metadata or {}, artifacts or {}):
        for key in _CONFLICT_KEYS:
            value = source.get(key)
            if value:
                return str(value)
    return ""


def _process_exists(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return False
    return True


def _anchor_id(session_id: Any, task_id: Any) -> str:
    raw = f"{session_id or 'session'}-{task_id or 'task'}"
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw)


def _format_ts(value: Any) -> str:
    ts = _float_or_zero(value)
    if not ts:
        return ""
    return html.escape(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)))


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(value: Any) -> Optional[int]:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


_CSS = """
:root {
  color-scheme: light;
  --bg: #f7f8f5;
  --panel: #ffffff;
  --ink: #202124;
  --muted: #626a73;
  --line: #d9ded7;
  --blue: #2766ad;
  --green: #257a4f;
  --amber: #9b6500;
  --red: #b3261e;
  --violet: #6f4aae;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 20px 24px 14px;
  border-bottom: 1px solid var(--line);
  background: #ffffff;
  position: sticky;
  top: 0;
  z-index: 2;
}
h1 { margin: 0; font-size: 24px; font-weight: 680; letter-spacing: 0; }
h2 { margin: 0 0 10px; font-size: 15px; letter-spacing: 0; }
h3 { margin: 0 0 10px; font-size: 14px; letter-spacing: 0; }
.subtle { margin: 3px 0 0; color: var(--muted); }
.refresh {
  color: #fff;
  background: var(--blue);
  border-radius: 6px;
  padding: 8px 12px;
  text-decoration: none;
  font-weight: 650;
}
.shell { padding: 18px 24px 28px; display: grid; gap: 18px; }
.metrics { display: flex; flex-wrap: wrap; gap: 10px; }
.metric {
  min-width: 130px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
}
.metric-label { display: block; color: var(--muted); font-size: 12px; }
.metric strong { overflow-wrap: anywhere; }
.section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 640px; }
th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: top; }
th { color: var(--muted); font-weight: 650; font-size: 12px; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #eef1ed;
  border-radius: 5px;
  padding: 2px 4px;
  overflow-wrap: anywhere;
}
.board {
  display: grid;
  grid-template-columns: repeat(4, minmax(240px, 1fr));
  gap: 12px;
  align-items: start;
}
.column {
  min-width: 0;
  background: #f1f4ef;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
}
.column h2 { display: flex; justify-content: space-between; gap: 8px; }
.column h2 span { color: var(--muted); }
.task {
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 4px solid var(--blue);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
}
.task-head { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.task-head strong { overflow-wrap: anywhere; }
.task-head span, .phase {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.meta, .note { color: var(--muted); margin: 6px 0; overflow-wrap: anywhere; }
.health-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 7px; }
.health {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  border-radius: 999px;
  padding: 2px 8px;
  border: 1px solid currentColor;
  font-size: 12px;
  font-weight: 650;
  color: var(--amber);
  background: #fff8e8;
}
.health--process-not-found, .health--missing-handoff, .health--repo-worktree-conflict {
  color: var(--red);
  background: #fff0ee;
}
.health--requires-user, .health--overdue-verification {
  color: var(--violet);
  background: #f6f0ff;
}
.artifacts {
  list-style: none;
  padding: 0;
  margin: 10px 0 0;
  display: grid;
  gap: 6px;
}
.artifacts.compact { font-size: 12px; }
.artifacts li {
  display: grid;
  grid-template-columns: minmax(86px, 140px) minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
}
.artifacts span, .detail-grid span { color: var(--muted); font-size: 12px; }
a { color: var(--blue); overflow-wrap: anywhere; }
.detail {
  border-top: 1px solid var(--line);
  padding-top: 12px;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 8px;
}
.detail-grid div { min-width: 0; }
.detail-grid span { display: block; }
.events {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: grid;
  gap: 5px;
}
.events li {
  display: grid;
  grid-template-columns: 150px 110px minmax(0, 1fr);
  gap: 8px;
  border-top: 1px solid #edf0ec;
  padding-top: 5px;
}
.events span { color: var(--muted); }
.events em { font-style: normal; overflow-wrap: anywhere; }
.empty { color: var(--muted); font-style: normal; }
@media (max-width: 1180px) {
  .board { grid-template-columns: repeat(2, minmax(220px, 1fr)); }
  .detail-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
}
@media (max-width: 720px) {
  .topbar { position: static; align-items: flex-start; }
  .shell { padding: 14px; }
  .board { grid-template-columns: minmax(0, 1fr); }
  .metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric { min-width: 0; }
  .events li { grid-template-columns: minmax(0, 1fr); }
}
"""


if __name__ == "__main__":
    raise SystemExit(main())
