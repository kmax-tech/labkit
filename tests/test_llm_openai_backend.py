"""The 'openai' backend must send the right payload to the right route.

Same spirit as test_llm_chat_options.py: test what is SENT, not the
signature. vLLM/sglang serve OpenAI-compatible /v1/chat/completions; the
backend exists so experiments can point an alias at a vLLM server without
touching any experiment code.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Base(unittest.TestCase):
    SPEC = {"backend": "openai", "model": "openai/gpt-oss-20b",
            "endpoint": "http://vllm.invalid:8000"}

    def setUp(self):
        from labkit import llm
        self.llm = llm
        self.sent = {}
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: dict(self.SPEC)

        def fake_urlopen(req, timeout=None):
            self.sent["url"] = req.full_url
            self.sent["headers"] = dict(req.header_items())
            self.sent["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(
                {"choices": [{"message": {"content": "OK"},
                              "finish_reason": "stop"}]})

        llm.urllib.request.urlopen = fake_urlopen

    def tearDown(self):
        self.llm.resolve = self._resolve
        self.llm.urllib.request.urlopen = self._urlopen


class TestReasoningGuard(_Base):
    """`reasoning = true` aliases must receive the trace as its own field.

    Without a server-side --reasoning-parser the trace lands inside content,
    where letter/label readouts silently read the DELIBERATION instead of the
    answer (measured in thesis-nandan: 6.6% one-directional label shift).
    Content without a trace field is that misconfiguration's signature."""

    SPEC = {**_Base.SPEC, "reasoning": True}

    def _respond_with(self, message: dict):
        self.calls = 0

        def fake_urlopen(req, timeout=None):
            self.calls += 1
            return _FakeResponse(
                {"choices": [{"message": message, "finish_reason": "stop"}]})
        self.llm.urllib.request.urlopen = fake_urlopen

    def test_separated_trace_passes(self):
        self._respond_with({"content": "A", "reasoning_content": "hmm, B? no."})
        self.assertEqual(self.llm.complete("x", "p"), "A")

    def test_newer_vllm_reasoning_key_passes(self):
        self._respond_with({"content": "A", "reasoning": "hmm, B? no."})
        self.assertEqual(self.llm.complete("x", "p"), "A")

    def test_content_without_trace_fails_loud_and_without_retry(self):
        self._respond_with({"content": "thinking... B. So: A"})
        with self.assertRaises(ValueError):
            self.llm.complete("x", "p")
        self.assertEqual(self.calls, 1)   # a server config is not retryable

    def test_thought_but_said_nothing_is_empty_not_guard_error(self):
        self._respond_with({"content": "", "reasoning_content": "endless..."})
        self.assertEqual(self.llm.complete("x", "p", attempts=1), "")

    def test_non_reasoning_alias_is_untouched(self):
        self.llm.resolve = lambda alias: dict(_Base.SPEC)   # reasoning absent
        self._respond_with({"content": "plain answer"})
        self.assertEqual(self.llm.complete("x", "p"), "plain answer")


class TestOpenAIBackend(_Base):
    def test_route_payload_and_budget(self):
        out = self.llm.complete("x", "prompt", max_tokens=2048, temperature=0.0)
        self.assertEqual(out, "OK")
        self.assertTrue(self.sent["url"].endswith("/v1/chat/completions"))
        p = self.sent["payload"]
        self.assertEqual(p["max_tokens"], 2048)
        self.assertEqual(p["temperature"], 0.0)
        self.assertEqual(p["model"], "openai/gpt-oss-20b")
        self.assertEqual(p["messages"][-1]["content"], "prompt")
        self.assertNotIn("Authorization", self.sent["headers"])

    def test_stop_and_system_are_sent(self):
        self.llm.complete("x", "p", system="be brief", stop=["\n\n"])
        p = self.sent["payload"]
        self.assertEqual(p["stop"], ["\n\n"])
        self.assertEqual(p["messages"][0], {"role": "system", "content": "be brief"})

    def test_api_key_becomes_bearer_header(self):
        self.SPEC = {**self.SPEC, "api_key": "sk-test"}
        self.llm.resolve = lambda alias: dict(self.SPEC)
        self.llm.complete("x", "p")
        self.assertEqual(self.sent["headers"].get("Authorization"), "Bearer sk-test")

    def test_raw_mode_refuses(self):
        with self.assertRaises(ValueError):
            self.llm.complete("x", "p", raw=True, attempts=1)

    def test_empty_content_returns_empty_not_crash(self):
        def empty_urlopen(req, timeout=None):
            return _FakeResponse({"choices": [{"message": {"content": ""},
                                               "finish_reason": "length"}]})
        self.llm.urllib.request.urlopen = empty_urlopen
        self.assertEqual(self.llm.complete("x", "p", attempts=1), "")

    def test_controls_temperature_is_true_for_openai(self):
        import tempfile
        llm = self.llm
        llm.resolve = self._resolve          # real resolve for this one
        saved_find, saved_frozen = llm._find_models_toml, dict(llm._FROZEN)
        try:
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / "models.toml"
                p.write_text('[models.v]\nbackend = "openai"\n'
                             'model = "m"\nendpoint = "http://x.invalid:1"\n',
                             encoding="utf-8")
                llm._find_models_toml = lambda: p
                llm._FROZEN.clear()
                self.assertTrue(llm.resolve("v")["controls_temperature"])
        finally:
            llm._find_models_toml = saved_find
            llm._FROZEN.clear(); llm._FROZEN.update(saved_frozen)


if __name__ == "__main__":
    unittest.main()
