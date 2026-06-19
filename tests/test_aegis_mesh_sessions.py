import unittest

from frontends.aegis_mesh_sessions import (
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_RUNNING,
    TASK_STOPPED,
    AegisMeshPeriodicReporter,
    AegisMeshSessionManager,
    build_feishu_session_id,
    plan_periodic_report_targets,
    render_dashboard_text,
    render_periodic_report_text,
)


class FakeAgent:
    def __init__(self):
        self.abort_calls = 0
        self.run_calls = 0

    def run(self):
        self.run_calls += 1

    def abort(self):
        self.abort_calls += 1


class AegisMeshSessionTests(unittest.TestCase):
    def test_build_feishu_session_id_distinguishes_group_and_private_routes(self):
        app_id = "cli_a/b"

        group_a = build_feishu_session_id(app_id, chat_id="oc_alpha", open_id="ou_user")
        group_b = build_feishu_session_id(app_id, chat_id="oc_beta", open_id="ou_user")
        private = build_feishu_session_id(app_id, chat_id=None, open_id="ou_user")

        self.assertNotEqual(group_a, group_b)
        self.assertNotEqual(group_a, private)
        self.assertIn("chat", group_a)
        self.assertIn("private", private)
        self.assertNotIn("/", group_a)

    def test_session_manager_reuses_same_session_and_isolates_distinct_agents(self):
        created = []

        def factory():
            agent = FakeAgent()
            created.append(agent)
            return agent

        manager = AegisMeshSessionManager(agent_factory=factory, start_agent=False)

        first = manager.get_or_create("session-a")
        again = manager.get_or_create("session-a")
        second = manager.get_or_create("session-b")

        self.assertIs(first, again)
        self.assertIsNot(first, second)
        self.assertIs(first.agent, created[0])
        self.assertIs(second.agent, created[1])
        self.assertIsNot(first.agent, second.agent)

    def test_same_session_allows_only_one_active_task(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)

        session, first_task = manager.begin_task("session-a", "task-1")
        same_session, second_task = manager.begin_task("session-a", "task-2")

        self.assertIs(session, same_session)
        self.assertIsNotNone(first_task)
        self.assertIsNone(second_task)
        self.assertIs(session.active_task, first_task)

    def test_different_sessions_can_both_be_active(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)

        session_a, task_a = manager.begin_task("session-a", "task-a")
        session_b, task_b = manager.begin_task("session-b", "task-b")

        self.assertIsNotNone(task_a)
        self.assertIsNotNone(task_b)
        self.assertIs(session_a.active_task, task_a)
        self.assertIs(session_b.active_task, task_b)

    def test_stop_task_is_scoped_to_one_session_agent(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)
        session_a, task_a = manager.begin_task("session-a", "task-a")
        session_b, task_b = manager.begin_task("session-b", "task-b")

        stopped = manager.stop_task("session-a")

        self.assertIs(stopped, True)
        self.assertIs(task_a.running, False)
        self.assertIs(task_b.running, True)
        self.assertEqual(session_a.agent.abort_calls, 1)
        self.assertEqual(session_b.agent.abort_calls, 0)

    def test_dashboard_counts_sessions_agents_and_task_states(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)
        manager.begin_task("session-running", "task-running", label="群 A")
        manager.begin_task("session-completed", "task-completed", label="群 B")
        manager.complete_task("session-completed", "task-completed", result_summary="已生成报告")
        manager.begin_task("session-failed", "task-failed", label="群 C")
        manager.fail_task("session-failed", "task-failed", error="模型调用失败")
        manager.begin_task("session-stopped", "task-stopped", label="群 D")
        manager.stop_task("session-stopped", reason="用户停止")

        snapshot = manager.dashboard_snapshot()

        self.assertEqual(snapshot["sessions_total"], 4)
        self.assertEqual(snapshot["agents_total"], 4)
        self.assertEqual(snapshot["tasks_running"], 1)
        self.assertEqual(snapshot["tasks_completed"], 1)
        self.assertEqual(snapshot["tasks_failed"], 1)
        self.assertEqual(snapshot["tasks_stopped"], 1)
        self.assertEqual(snapshot["notifications_pending"], 3)
        self.assertEqual(snapshot["sessions"]["session-running"]["active_task"]["status"], TASK_RUNNING)
        self.assertEqual(snapshot["sessions"]["session-completed"]["tasks"]["task-completed"]["status"], TASK_COMPLETED)
        self.assertEqual(snapshot["sessions"]["session-failed"]["tasks"]["task-failed"]["status"], TASK_FAILED)
        self.assertEqual(snapshot["sessions"]["session-stopped"]["tasks"]["task-stopped"]["status"], TASK_STOPPED)

    def test_notifications_are_bounded_and_consumable(self):
        manager = AegisMeshSessionManager(
            agent_factory=FakeAgent,
            start_agent=False,
            notification_limit=2,
        )

        for index in range(3):
            task_id = f"task-{index}"
            manager.begin_task(f"session-{index}", task_id)
            manager.complete_task(f"session-{index}", task_id, result_summary=f"result-{index}")

        self.assertEqual(manager.dashboard_snapshot()["notifications_pending"], 2)

        notifications = manager.consume_notifications()

        self.assertEqual([item["task_id"] for item in notifications], ["task-1", "task-2"])
        self.assertEqual(manager.dashboard_snapshot()["notifications_pending"], 0)
        self.assertEqual(manager.consume_notifications(), [])

    def test_task_events_are_bounded(self):
        manager = AegisMeshSessionManager(
            agent_factory=FakeAgent,
            start_agent=False,
            task_event_limit=2,
        )
        manager.begin_task("session-a", "task-a")

        for index in range(3):
            manager.record_task_event("session-a", "task-a", message=f"progress-{index}")

        events = manager.snapshot("session-a")["tasks"]["task-a"]["events"]

        self.assertEqual(len(events), 2)
        self.assertEqual([event["message"] for event in events], ["progress-1", "progress-2"])

    def test_completing_one_session_does_not_affect_another_running_task(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)
        session_a, task_a = manager.begin_task("session-a", "task-a")
        session_b, task_b = manager.begin_task("session-b", "task-b")

        completed = manager.complete_task("session-a", "task-a", result_summary="完成 A")

        self.assertIs(completed, True)
        self.assertEqual(task_a.status, TASK_COMPLETED)
        self.assertEqual(task_b.status, TASK_RUNNING)
        self.assertIsNone(session_a.active_task)
        self.assertIs(session_b.active_task, task_b)

    def test_dashboard_text_is_result_oriented_without_raw_turn_details(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)
        manager.begin_task("session-a", "task-a", label="群 A")
        manager.begin_task("session-b", "task-b", label="群 B")
        manager.fail_task("session-b", "task-b", error="工具失败")

        text = render_dashboard_text(manager.dashboard_snapshot())

        self.assertIn("Aegis Mesh 看板", text)
        self.assertIn("会话 2", text)
        self.assertIn("需关注", text)
        self.assertNotRegex(text.lower(), r"\bturn\b")

    def test_periodic_report_targets_use_task_route_metadata(self):
        now = [1000.0]
        manager = AegisMeshSessionManager(
            agent_factory=FakeAgent,
            start_agent=False,
            time_fn=lambda: now[0],
        )
        manager.begin_task(
            "session-running",
            "task-running",
            label="群 A",
            metadata={"receive_id": "oc_running", "receive_id_type": "chat_id"},
        )
        manager.begin_task("session-unknown", "task-unknown", label="群 B")
        now[0] = 1010.0
        manager.begin_task(
            "session-recent",
            "task-recent",
            label="用户 C",
            metadata={"receive_id": "ou_recent", "receive_id_type": "open_id"},
        )
        manager.complete_task("session-recent", "task-recent", result_summary="报告已生成")

        targets = plan_periodic_report_targets(manager.dashboard_snapshot(), since=1005.0)

        self.assertEqual(
            [(target.session_id, target.receive_id, target.receive_id_type) for target in targets],
            [
                ("session-running", "oc_running", "chat_id"),
                ("session-recent", "ou_recent", "open_id"),
            ],
        )

    def test_periodic_report_text_includes_progress_and_attention_without_turn_logs(self):
        manager = AegisMeshSessionManager(agent_factory=FakeAgent, start_agent=False)
        manager.begin_task(
            "session-running",
            "task-running",
            label="群 A",
            metadata={"receive_id": "oc_running", "receive_id_type": "chat_id"},
        )
        manager.record_task_event(
            "session-running",
            "task-running",
            message="turn 7 searched repo and found the failing test",
        )
        manager.begin_task(
            "session-failed",
            "task-failed",
            label="群 B",
            metadata={"receive_id": "oc_failed", "receive_id_type": "chat_id"},
        )
        manager.fail_task("session-failed", "task-failed", error="工具失败")

        text = render_periodic_report_text(manager.dashboard_snapshot())

        self.assertIn("Aegis Mesh 定时摘要", text)
        self.assertIn("运行中", text)
        self.assertIn("searched repo", text)
        self.assertIn("需关注", text)
        self.assertIn("工具失败", text)
        self.assertNotRegex(text.lower(), r"\bturn\b")

    def test_periodic_reporter_send_once_uses_fake_sender_without_sleeping(self):
        now = [2000.0]
        sent = []
        manager = AegisMeshSessionManager(
            agent_factory=FakeAgent,
            start_agent=False,
            time_fn=lambda: now[0],
        )
        manager.begin_task(
            "session-running",
            "task-running",
            label="群 A",
            metadata={"receive_id": "oc_running", "receive_id_type": "chat_id"},
        )
        manager.record_task_event("session-running", "task-running", message="正在整理结果")

        reporter = AegisMeshPeriodicReporter(
            manager,
            send_fn=lambda receive_id, content, receive_id_type="open_id": sent.append(
                (receive_id, receive_id_type, content)
            ),
            split_fn=lambda text, _limit: [text],
            interval_sec=1800,
            time_fn=lambda: now[0],
        )

        delivered = reporter.send_once()

        self.assertEqual(delivered, 1)
        self.assertEqual(sent[0][0], "oc_running")
        self.assertEqual(sent[0][1], "chat_id")
        self.assertIn("正在整理结果", sent[0][2])


if __name__ == "__main__":
    unittest.main()
