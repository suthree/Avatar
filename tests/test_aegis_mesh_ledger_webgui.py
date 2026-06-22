import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from frontends import aegis_mesh_ledger
from frontends.aegis_mesh_ledger import AegisMeshLedger
from frontends.aegis_mesh_sessions import (
    TASK_COMPLETED,
    TASK_RUNNING,
    AegisMeshSessionManager,
)
from frontends.aegis_mesh_webgui import build_board_model, render_dashboard_html


class FakeAgent:
    def __init__(self):
        self.abort_calls = 0

    def abort(self):
        self.abort_calls += 1


class AegisMeshLedgerTests(unittest.TestCase):
    def make_ledger(self, tmpdir, now=1000.0):
        path = Path(tmpdir) / "state" / "aegis_mesh.sqlite3"
        return AegisMeshLedger(path, time_fn=lambda: now)

    def test_default_ledger_path_uses_main_repo_state_from_project_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            avatar_root = Path(tmp) / "Avatar"
            worktree_root = avatar_root / ".worktree" / "issue-13-aegis-mesh-webgui"
            frontend_dir = worktree_root / "frontends"
            frontend_dir.mkdir(parents=True)

            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(
                    aegis_mesh_ledger,
                    "__file__",
                    str(frontend_dir / "aegis_mesh_ledger.py"),
                ),
            ):
                path = aegis_mesh_ledger.default_aegis_mesh_ledger_path()

            self.assertEqual(path, avatar_root / "temp" / "state" / "aegis_mesh_ledger.sqlite3")

    def test_ledger_persists_sessions_tasks_events_and_artifacts_after_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp, now=1000.0)
            ledger.upsert_session(
                "session-a",
                label="Feishu group A",
                platform="feishu",
                source="chat",
                metadata={"chat_id": "oc_a"},
            )
            ledger.upsert_task(
                "session-a",
                "task-13",
                label="Issue 13 MVP",
                status=TASK_RUNNING,
                phase="codex_running",
                metadata={"github_issue_number": 13},
                artifacts={
                    "github_issue_url": "https://github.com/suthree/Avatar/issues/13",
                    "branch": "issue/13-aegis-mesh-webgui",
                    "worktree": "/srv/projects/develop/Avatar/.worktree/issue13-aegis-mesh-webgui",
                    "codex_pid": "99999999",
                    "log_path": "/tmp/codex.log",
                },
            )
            ledger.record_event(
                "session-a",
                "task-13",
                event_type="progress",
                message="Codex is implementing durable state",
                metadata={"phase": "codex_running"},
            )
            first_snapshot = ledger.snapshot()
            ledger.close()

            reloaded = AegisMeshLedger(Path(tmp) / "state" / "aegis_mesh.sqlite3", time_fn=lambda: 1000.0)
            reloaded_snapshot = reloaded.snapshot()

            self.assertEqual(reloaded_snapshot["sessions"], first_snapshot["sessions"])
            task = reloaded_snapshot["sessions"]["session-a"]["tasks"]["task-13"]
            self.assertEqual(task["phase"], "codex_running")
            self.assertEqual(
                task["artifacts"]["worktree"],
                "/srv/projects/develop/Avatar/.worktree/issue13-aegis-mesh-webgui",
            )
            self.assertEqual(task["events"][0]["message"], "Codex is implementing durable state")
            reloaded.close()

    def test_session_manager_mirrors_lifecycle_to_ledger_without_cross_session_bleed(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [2000.0]
            ledger = AegisMeshLedger(Path(tmp) / "aegis_mesh.sqlite3", time_fn=lambda: now[0])
            manager = AegisMeshSessionManager(
                agent_factory=FakeAgent,
                start_agent=False,
                time_fn=lambda: now[0],
                ledger=ledger,
                platform="feishu",
            )

            session_a, task_a = manager.begin_task(
                "session-a",
                "task-a",
                label="Chat A",
                metadata={
                    "phase": "codex_running",
                    "github_issue_url": "https://github.com/suthree/Avatar/issues/13",
                    "worktree": "/tmp/worktree-a",
                    "codex_pid": 99999999,
                },
            )
            session_b, task_b = manager.begin_task(
                "session-b",
                "task-b",
                label="Chat B",
                metadata={"phase": "codex_running", "worktree": "/tmp/worktree-b"},
            )
            now[0] = 2010.0
            manager.record_task_event(
                "session-a",
                "task-a",
                event_type="handoff",
                message="handoff written",
                metadata={"phase": "avatar_verify", "handoff_path": "/tmp/task-a-handoff.md"},
            )
            manager.complete_task(
                "session-a",
                "task-a",
                result_summary="Avatar verified task A",
                metadata={"phase": "done", "answer_path": "/tmp/task-a-answer.md"},
            )

            self.assertEqual(task_a.status, TASK_COMPLETED)
            self.assertEqual(task_b.status, TASK_RUNNING)
            self.assertIsNone(session_a.active_task)
            self.assertIs(session_b.active_task, task_b)

            snapshot = ledger.snapshot()
            persisted_a = snapshot["sessions"]["session-a"]["tasks"]["task-a"]
            persisted_b = snapshot["sessions"]["session-b"]["tasks"]["task-b"]
            self.assertEqual(persisted_a["status"], TASK_COMPLETED)
            self.assertEqual(persisted_a["phase"], "done")
            self.assertEqual(persisted_a["artifacts"]["handoff_path"], "/tmp/task-a-handoff.md")
            self.assertEqual(persisted_b["status"], TASK_RUNNING)
            self.assertEqual(persisted_b["phase"], "codex_running")
            self.assertEqual(persisted_b["artifacts"]["worktree"], "/tmp/worktree-b")
            ledger.close()


class AegisMeshWebGuiTests(unittest.TestCase):
    def test_webgui_script_entrypoint_is_runnable_directly(self):
        script = Path(__file__).resolve().parents[1] / "frontends" / "aegis_mesh_webgui.py"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Serve or render the local Aegis Mesh task board", result.stdout)

    def test_dashboard_renders_grouped_board_and_task_detail_without_log_or_secret_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = AegisMeshLedger(Path(tmp) / "aegis_mesh.sqlite3", time_fn=lambda: 3000.0)
            ledger.upsert_session("session-a", label="Feishu A", platform="feishu")
            ledger.upsert_task(
                "session-a",
                "task-running",
                label="Issue 13 running",
                status=TASK_RUNNING,
                phase="codex_running",
                metadata={"secret_token": "DO_NOT_RENDER"},
                artifacts={
                    "github_issue_url": "https://github.com/suthree/Avatar/issues/13",
                    "project": "Avatar",
                    "repo": "suthree/Avatar",
                    "branch": "issue/13-aegis-mesh-webgui",
                    "worktree": "/srv/projects/develop/Avatar/.worktree/issue13-aegis-mesh-webgui",
                    "codex_pid": "99999999",
                    "log_path": "/tmp/codex.log",
                    "answer_path": "/tmp/answer.md",
                    "handoff_path": "/tmp/handoff.md",
                    "log_preview": "secret log text DO_NOT_RENDER",
                },
            )
            ledger.upsert_task(
                "session-a",
                "task-verify",
                label="Avatar verification",
                status=TASK_RUNNING,
                phase="avatar_verify",
                artifacts={"verification_artifact": "/tmp/avatar_verification.md"},
            )
            ledger.upsert_task(
                "session-a",
                "task-blocked",
                label="Needs user",
                status=TASK_RUNNING,
                phase="blocked",
                blocker="Need GitHub issue scope",
                requires_user=True,
            )
            ledger.upsert_task(
                "session-a",
                "task-done",
                label="Done task",
                status=TASK_COMPLETED,
                phase="done",
            )

            model = build_board_model(ledger.snapshot(), now=3000.0, process_exists_fn=lambda pid: True)
            html = render_dashboard_html(model)

            self.assertIn("Aegis Mesh Board", html)
            self.assertIn("data-board-group=\"codex_running\"", html)
            self.assertIn("data-board-group=\"avatar_verify\"", html)
            self.assertIn("data-board-group=\"blocked/requires_user\"", html)
            self.assertIn("data-board-group=\"done/completed\"", html)
            self.assertIn('href="https://github.com/suthree/Avatar/issues/13"', html)
            self.assertIn("/srv/projects/develop/Avatar/.worktree/issue13-aegis-mesh-webgui", html)
            self.assertIn("/tmp/codex.log", html)
            self.assertIn("/tmp/answer.md", html)
            self.assertIn("/tmp/handoff.md", html)
            self.assertNotIn("secret log text", html)
            self.assertNotIn("DO_NOT_RENDER", html)
            ledger.close()

    def test_health_indicators_are_visible_in_model_and_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = 10000.0
            ledger = AegisMeshLedger(Path(tmp) / "aegis_mesh.sqlite3", time_fn=lambda: now)
            ledger.upsert_session("session-health", label="Health session", platform="feishu")
            ledger.upsert_task(
                "session-health",
                "task-stale",
                label="Stale Codex",
                status=TASK_RUNNING,
                phase="codex_running",
                artifacts={"codex_pid": "99999999", "log_path": "/tmp/stale.log"},
                timestamp=now - 7200,
            )
            ledger.upsert_task(
                "session-health",
                "task-missing-handoff",
                label="Needs handoff",
                status=TASK_RUNNING,
                phase="codex_done",
                timestamp=now - 100,
            )
            ledger.upsert_task(
                "session-health",
                "task-overdue-verify",
                label="Overdue verification",
                status=TASK_RUNNING,
                phase="avatar_verify",
                timestamp=now - 90000,
            )
            ledger.upsert_task(
                "session-health",
                "task-user",
                label="Waiting for user",
                status=TASK_RUNNING,
                phase="blocked",
                blocker="Need user confirmation",
                requires_user=True,
            )
            ledger.upsert_task(
                "session-health",
                "task-conflict",
                label="Repo conflict",
                status=TASK_RUNNING,
                phase="issue_ready",
                metadata={"repo_conflict": "worktree already locked"},
            )

            model = build_board_model(ledger.snapshot(), now=now, process_exists_fn=lambda pid: False)
            health_codes = {
                indicator["code"]
                for task in model["tasks"]
                for indicator in task["health"]
            }
            html = render_dashboard_html(model)

            self.assertTrue(
                {
                    "stale_running_task",
                    "process_not_found",
                    "missing_handoff",
                    "overdue_verification",
                    "requires_user",
                    "repo_worktree_conflict",
                }.issubset(health_codes)
            )
            self.assertIn("stale-running-task", html)
            self.assertIn("process-not-found", html)
            self.assertIn("missing-handoff", html)
            self.assertIn("overdue-verification", html)
            self.assertIn("requires-user", html)
            self.assertIn("repo-worktree-conflict", html)
            ledger.close()


if __name__ == "__main__":
    unittest.main()
