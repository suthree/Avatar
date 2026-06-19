import os
import tempfile
import unittest
from unittest.mock import patch

import llmcore


_ENV_KEYS = [
    "MYKEY_JSON",
    "APIKEY",
    "APIBASE",
    "MODEL",
    "NAME",
    "API_MODE",
    "REASONING_EFFORT",
    "MAX_RETRIES",
    "CONNECT_TIMEOUT",
    "TIMEOUT",
    "READ_TIMEOUT",
    "CONTEXT_WIN",
    "MAX_TOKENS",
    "TEMPERATURE",
    "PROXY",
    "SERVICE_TIER",
    "THINKING_TYPE",
    "THINKING_BUDGET_TOKENS",
    "STREAM",
    "VERIFY",
    "USER_AGENT",
    "CONFIG_TOML",
    "ENABLE_MIXIN",
    "MIXIN_MAX_RETRIES",
    "MIXIN_BASE_DELAY",
]


def _clean_env(extra):
    env = {}
    for key in _ENV_KEYS:
        env.pop(key, None)
        env.pop(f"JARVIS_{key}", None)
    env.update(extra)
    return env


class LLMCoreEnvTests(unittest.TestCase):
    def test_generic_env_builds_native_oai_config(self):
        with patch.dict(
            os.environ,
            _clean_env(
                {
                    "APIKEY": "sk-generic",
                    "APIBASE": "https://example.test/v1",
                    "MODEL": "gpt-5.5",
                    "NAME": "generic",
                    "API_MODE": "responses",
                    "REASONING_EFFORT": "xhigh",
                    "MAX_RETRIES": "7",
                    "STREAM": "false",
                }
            ),
            clear=True,
        ):
            data = llmcore._load_mykeys_from_env()

        cfg = data["native_oai_config"]
        self.assertEqual(cfg["apikey"], "sk-generic")
        self.assertEqual(cfg["apibase"], "https://example.test/v1")
        self.assertEqual(cfg["model"], "gpt-5.5")
        self.assertEqual(cfg["name"], "generic")
        self.assertEqual(cfg["api_mode"], "responses")
        self.assertEqual(cfg["reasoning_effort"], "xhigh")
        self.assertEqual(cfg["max_retries"], 7)
        self.assertIs(cfg["stream"], False)
        self.assertEqual(data["mixin_config"]["llm_nos"], ["generic"])

    def test_generic_env_takes_precedence_over_legacy_jarvis_env(self):
        with patch.dict(
            os.environ,
            _clean_env(
                {
                    "APIKEY": "sk-generic",
                    "MODEL": "gpt-5.5",
                    "REASONING_EFFORT": "xhigh",
                    "JARVIS_APIKEY": "sk-legacy",
                    "JARVIS_MODEL": "legacy-model",
                    "JARVIS_REASONING_EFFORT": "low",
                }
            ),
            clear=True,
        ):
            cfg = llmcore._load_mykeys_from_env()["native_oai_config"]

        self.assertEqual(cfg["apikey"], "sk-generic")
        self.assertEqual(cfg["model"], "gpt-5.5")
        self.assertEqual(cfg["reasoning_effort"], "xhigh")

    def test_legacy_jarvis_env_remains_fallback(self):
        with patch.dict(
            os.environ,
            _clean_env(
                {
                    "JARVIS_APIKEY": "sk-legacy",
                    "JARVIS_MODEL": "legacy-model",
                    "JARVIS_REASONING_EFFORT": "medium",
                }
            ),
            clear=True,
        ):
            cfg = llmcore._load_mykeys_from_env()["native_oai_config"]

        self.assertEqual(cfg["apikey"], "sk-legacy")
        self.assertEqual(cfg["model"], "legacy-model")
        self.assertEqual(cfg["reasoning_effort"], "medium")

    def test_generic_mykey_json_takes_precedence_over_legacy_json(self):
        with patch.dict(
            os.environ,
            _clean_env(
                {
                    "MYKEY_JSON": '{"native_oai_config": {"apikey": "sk-generic", "apibase": "https://generic.test/v1", "model": "gpt-5.5"}}',
                    "JARVIS_MYKEY_JSON": '{"native_oai_config": {"apikey": "sk-legacy", "apibase": "https://legacy.test/v1", "model": "legacy-model"}}',
                }
            ),
            clear=True,
        ):
            data = llmcore._load_mykeys_from_env()

        self.assertEqual(data["native_oai_config"]["apikey"], "sk-generic")
        self.assertEqual(data["native_oai_config"]["model"], "gpt-5.5")

    def test_generic_config_toml_is_used_before_legacy_config_toml(self):
        old_path = llmcore._mykey_path
        try:
            with tempfile.TemporaryDirectory() as td:
                generic_path = os.path.join(td, "generic.toml")
                legacy_path = os.path.join(td, "legacy.toml")
                with open(generic_path, "w", encoding="utf-8") as f:
                    f.write(
                        '[native_oai_config]\n'
                        'apikey = "sk-generic"\n'
                        'apibase = "https://generic.test/v1"\n'
                        'model = "gpt-5.5"\n'
                    )
                with open(legacy_path, "w", encoding="utf-8") as f:
                    f.write(
                        '[native_oai_config]\n'
                        'apikey = "sk-legacy"\n'
                        'apibase = "https://legacy.test/v1"\n'
                        'model = "legacy-model"\n'
                    )

                with patch.dict(
                    os.environ,
                    _clean_env(
                        {
                            "CONFIG_TOML": generic_path,
                            "JARVIS_CONFIG_TOML": legacy_path,
                        }
                    ),
                    clear=True,
                ):
                    data = llmcore._load_mykeys()
        finally:
            llmcore._mykey_path = old_path

        self.assertEqual(data["native_oai_config"]["apikey"], "sk-generic")
        self.assertEqual(data["native_oai_config"]["model"], "gpt-5.5")


class DummySession:
    def __init__(self, *, api_mode):
        self.api_key = "sk-test"
        self.api_base = "https://example.test/v1"
        self.api_mode = api_mode
        self.model = "gpt-5.5"
        self.stream = False
        self.system = ""
        self.reasoning_effort = "xhigh"
        self.max_tokens = None
        self.temperature = 1
        self.tools = None
        self.service_tier = None
        self.user_agent = "test-agent"


class OpenAIReasoningPayloadTests(unittest.TestCase):
    def _capture_payload(self, api_mode):
        captured = {}

        def fake_stream_with_retry(sess, url, headers, payload, parse_fn):
            captured["url"] = url
            captured["payload"] = payload
            if False:
                yield None
            return [{"type": "text", "text": "ok"}]

        with patch.object(llmcore, "_stream_with_retry", fake_stream_with_retry):
            list(llmcore._openai_stream(DummySession(api_mode=api_mode), [{"role": "user", "content": "hi"}]))
        return captured

    def test_responses_payload_keeps_model_and_reasoning_effort_separate(self):
        captured = self._capture_payload("responses")
        payload = captured["payload"]

        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["reasoning"], {"effort": "xhigh"})
        self.assertNotIn("reasoning_effort", payload)

    def test_chat_payload_keeps_model_and_reasoning_effort_separate(self):
        captured = self._capture_payload("chat_completions")
        payload = captured["payload"]

        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["reasoning_effort"], "xhigh")
        self.assertNotIn("reasoning", payload)


if __name__ == "__main__":
    unittest.main()
