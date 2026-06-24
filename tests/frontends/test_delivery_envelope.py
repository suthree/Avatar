from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from frontends.message_delivery import build_delivery_envelope, render_feishu_digest
from frontends.outbox_store import read_chunk, read_full, read_manifest, write_outbox
from frontends.platform_budgets import build_digest, sanitize_for_im, segment_markdown


_MISSING = object()
_STUBBED_MODULES = (
    "frontends.fsapp",
    "frontends.chatapp_common",
    "agentmain",
    "continue_cmd",
    "btw_cmd",
    "review_cmd",
    "lark_oapi",
    "lark_oapi.api",
    "lark_oapi.api.im",
    "lark_oapi.api.im.v1",
)


class DeliveryEnvelopeTests(unittest.TestCase):
    def test_chinese_text_roundtrips_through_full_and_chunks(self):
        text = "这是完整回复。" * 2000
        self.assertGreater(len(text), 10000)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_outbox("task/chinese", text, base_dir=tmp, chunk_limit=3500)
            _manifest, full = read_full("task/chinese", base_dir=tmp)
            joined = "".join((Path(manifest["task_dir"]) / c["path"]).read_text(encoding="utf-8") for c in manifest["chunks"])

        self.assertEqual(full, text)
        self.assertEqual(joined, text)
        self.assertGreater(len(manifest["chunks"]), 1)

    def test_long_markdown_and_code_block_roundtrip(self):
        table = "| col | value |\n| --- | --- |\n" + "".join(f"| row {i} | value {i} |\n" for i in range(600))
        code = "```python\n" + "".join(f"print({i})\n" for i in range(2500)) + "```\n"
        text = "# Report\n\n" + table + "\n" + code
        self.assertGreater(len(text), 30000)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_outbox("task-markdown", text, base_dir=tmp, chunk_limit=3500)
            chunks = [(Path(manifest["task_dir"]) / c["path"]).read_text(encoding="utf-8") for c in manifest["chunks"]]

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 3500 for chunk in chunks))

    def test_code_fence_is_not_split_when_practical(self):
        text = "intro\n\n```python\nprint('hello')\nprint('world')\n```\n\noutro\n"
        chunks = segment_markdown(text, limit=45)

        self.assertEqual("".join(chunks), text)
        fenced_chunks = [chunk for chunk in chunks if "```python" in chunk]
        self.assertEqual(len(fenced_chunks), 1)
        self.assertIn("```\n", fenced_chunks[0])

    def test_manifest_records_sha_paths_chunks_artifacts_and_omissions(self):
        text = "answer body\n[FILE:/tmp/generated-report.md]\n"
        omitted = [{"section": "task_card_step", "chars": 123}]
        with tempfile.TemporaryDirectory() as tmp:
            manifest = write_outbox(
                "task-manifest",
                text,
                raw_text="<thinking>hidden</thinking>\n" + text,
                status="done",
                session={"id": "session-1"},
                metadata={"source": "test"},
                omitted_sections=omitted,
                base_dir=tmp,
            )
            manifest_path = Path(manifest["manifest_path"])
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(persisted["full"]["path"], "full.md")
        self.assertEqual(persisted["raw"]["path"], "raw_model_output.md")
        self.assertEqual(persisted["chunks"][0]["path"], "chunk_001.md")
        self.assertEqual(persisted["omitted_sections"], omitted)
        self.assertEqual(persisted["artifacts"][0]["path"], "/tmp/generated-report.md")

    def test_digest_budget_and_control_char_sanitation(self):
        dirty = "hello\x00\x08世界\r\nnext\u0085line"
        cleaned = sanitize_for_im(dirty)
        digest = build_digest("x" * 5000, budget=1200)

        self.assertEqual(cleaned, "hello世界\nnextline")
        self.assertLessEqual(len(digest), 1200)
        self.assertTrue(digest.endswith("]") or digest.endswith("…"))

    def test_render_feishu_digest_mentions_retrieval_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = build_delivery_envelope("task-render", "hello" * 1000, base_dir=tmp)
            rendered = render_feishu_digest(envelope)

        self.assertIn("Task: `task-render`", rendered)
        self.assertIn("/full task-render", rendered)
        self.assertIn("/chunk task-render 1", rendered)
        self.assertLess(rendered.find("Digest:"), rendered.find("Full:"))


def _install_lark_stub():
    lark = types.ModuleType("lark_oapi")
    lark.LogLevel = types.SimpleNamespace(INFO="INFO")
    lark.Client = types.SimpleNamespace(builder=lambda: types.SimpleNamespace(
        app_id=lambda _value: lark.Client.builder(),
        app_secret=lambda _value: lark.Client.builder(),
        log_level=lambda _value: lark.Client.builder(),
        build=lambda: object(),
    ))
    sys.modules["lark_oapi"] = lark
    sys.modules["lark_oapi.api"] = types.ModuleType("lark_oapi.api")
    sys.modules["lark_oapi.api.im"] = types.ModuleType("lark_oapi.api.im")
    sys.modules["lark_oapi.api.im.v1"] = types.ModuleType("lark_oapi.api.im.v1")


def _install_agentmain_stub():
    agentmain = types.ModuleType("agentmain")

    class GeneraticAgent:
        def _handle_slash_cmd(self, raw_query, display_queue):
            return raw_query

        pass

    agentmain.GeneraticAgent = GeneraticAgent
    sys.modules["agentmain"] = agentmain


def _install_chat_command_stubs():
    continue_cmd = types.ModuleType("continue_cmd")
    continue_cmd.install = lambda _cls: None
    continue_cmd.handle_frontend_command = lambda _agent, _cmd: "continue"
    continue_cmd.reset_conversation = lambda _agent: "new"
    sys.modules["continue_cmd"] = continue_cmd

    btw_cmd = types.ModuleType("btw_cmd")
    btw_cmd.install = lambda _cls: None
    btw_cmd.handle_frontend_command = lambda _agent, _cmd: "btw"
    sys.modules["btw_cmd"] = btw_cmd

    review_cmd = types.ModuleType("review_cmd")
    review_cmd.install = lambda _cls: None
    sys.modules["review_cmd"] = review_cmd


def _import_fsapp():
    os.environ["AVATAR_SKIP_CONFIG_LOAD"] = "1"
    _install_lark_stub()
    _install_agentmain_stub()
    _install_chat_command_stubs()
    sys.modules.pop("frontends.fsapp", None)
    return importlib.import_module("frontends.fsapp")


class FeishuDeliveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._module_snapshot = {name: sys.modules.get(name, _MISSING) for name in _STUBBED_MODULES}
        self._old_skip_config = os.environ.get("AVATAR_SKIP_CONFIG_LOAD", _MISSING)

    def tearDown(self):
        for name, module in self._module_snapshot.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        if self._old_skip_config is _MISSING:
            os.environ.pop("AVATAR_SKIP_CONFIG_LOAD", None)
        else:
            os.environ["AVATAR_SKIP_CONFIG_LOAD"] = self._old_skip_config

    def test_task_card_long_detail_is_saved_without_truncation_text(self):
        fsapp = _import_fsapp()
        cards = []
        fsapp._send_raw = lambda _rid, payload, _msg_type, _rtype: cards.append(payload) or "message-id"
        fsapp._patch_card = lambda _message_id, payload: cards.append(payload) or True

        detail = "步骤详情\n" * 2000
        with tempfile.TemporaryDirectory() as tmp:
            card = fsapp._TaskCard("rid", "open_id", task_id="task-card", outbox_dir=tmp)
            card.step("long detail", detail)
            manifest = read_manifest("task-card", base_dir=tmp)
            artifact = manifest["artifacts"][0]
            artifact_text = (Path(manifest["task_dir"]) / artifact["path"]).read_text(encoding="utf-8")

        self.assertTrue(cards)
        self.assertNotIn("已截断", cards[-1])
        self.assertIn("/artifacts task-card", cards[-1])
        self.assertIn("/full task-card", cards[-1])
        self.assertEqual(artifact_text, detail)
        self.assertEqual(manifest["omitted_sections"][0]["section"], "task_card_step")


    def test_task_card_keeps_recent_steps_under_card_budget(self):
        fsapp = _import_fsapp()
        cards = []
        fsapp._send_raw = lambda _rid, payload, _msg_type, _rtype: cards.append(payload) or "message-id"
        fsapp._patch_card = lambda _message_id, payload: cards.append(payload) or True

        with tempfile.TemporaryDirectory() as tmp:
            card = fsapp._TaskCard("rid", "open_id", task_id="task-many-steps", outbox_dir=tmp)
            for i in range(12):
                card.step(f"step-{i}", f"detail-{i}")

        self.assertTrue(cards)
        latest = cards[-1]
        self.assertIn("已折叠 4 个较早步骤", latest)
        self.assertNotIn("step-0", latest)
        self.assertNotIn("detail-0", latest)
        self.assertIn("step-11", latest)
        self.assertIn("detail-11", latest)
        self.assertIn("/full task-many-steps", latest)


    def test_feishu_post_payload_wraps_markdown_and_code_blocks(self):
        fsapp = _import_fsapp()
        payload = json.loads(fsapp._post("# 标题\n\n正文 before\n```python\nprint(1)\n```\n正文 after"))
        rows = payload["zh_cn"]["content"]

        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(all(row and row[0]["tag"] == "md" for row in rows))
        self.assertIn("# 标题", rows[0][0]["text"])
        self.assertIn("```python", rows[1][0]["text"])
        self.assertIn("正文 after", rows[-1][0]["text"])

    def test_feishu_send_text_uses_post_rich_text(self):
        fsapp = _import_fsapp()

        class DummySessionManager:
            pass

        calls = []

        def fake_send_message(receive_id, content, msg_type="text", use_card=False, receive_id_type="open_id"):
            calls.append({
                "receive_id": receive_id,
                "content": content,
                "msg_type": msg_type,
                "use_card": use_card,
                "receive_id_type": receive_id_type,
            })
            return "mid-rich"

        old = fsapp.send_message
        fsapp.send_message = fake_send_message
        try:
            app = fsapp.FeishuApp(DummySessionManager())
            asyncio.run(app.send_text("chat-1", "**bold**\n\n```python\nprint(1)\n```"))
        finally:
            fsapp.send_message = old

        self.assertTrue(calls)
        self.assertTrue(all(call["msg_type"] == "post" for call in calls))
        self.assertTrue(all(call["use_card"] is False for call in calls))
        self.assertIn("**bold**", calls[0]["content"])

    def test_retrieval_commands_are_listed_in_help(self):
        fsapp = _import_fsapp()
        self.assertIn("/full [task_id]", fsapp._FEISHU_HELP_TEXT)
        self.assertIn("/chunk [task_id] <n>", fsapp._FEISHU_HELP_TEXT)
        self.assertIn("/artifacts [task_id]", fsapp._FEISHU_HELP_TEXT)
        self.assertIn("/more", fsapp._FEISHU_HELP_TEXT)

    def test_chunk_command_reads_local_outbox(self):
        fsapp = _import_fsapp()

        class DummySessionManager:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            text = "alpha\n" * 1200
            manifest = write_outbox("task-retrieve", text, base_dir=tmp, chunk_limit=1000)
            _manifest, expected, _entry = read_chunk("task-retrieve", 2, base_dir=tmp)
            app = fsapp.FeishuApp(DummySessionManager(), outbox_dir=tmp)
            app._remember_task("session-1", "task-retrieve")
            sent = []

            async def fake_send_text(_chat_id, content, **_ctx):
                sent.append(content)

            app.send_text = fake_send_text
            asyncio.run(app.handle_command("chat-1", "/chunk 2", session_id="session-1"))

        self.assertEqual(len(sent), 1)
        self.assertIn(f"Chunk 2/{len(manifest['chunks'])}", sent[0])
        self.assertIn(expected, sent[0])


if __name__ == "__main__":
    unittest.main()
