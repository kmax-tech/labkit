"""The chat path must send `num_predict` — else generation runs free.

Why this file exists: until 2026-08-19 `llm.complete` set the token budget
ONLY in the `raw=True` branch at `/api/generate`. The chat branch that every
experiment takes sent nothing but `temperature` and silently dropped
`max_tokens`. Consequence: `gpt-oss` generated 3520 tokens at a nominal
2048 and was not done (server log, ~19 t/s), the request ran into the
timeout, and the symptom — timeouts, aborted runs — looked like an
overloaded cluster. Half a session went to the wrong hypothesis.

The bug was invisible because `max_tokens` has a default: every call looked
correct while the effect was missing. Against exactly that, this test
checks the *payload sent*, not the signature.
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


class TestChatPathSendsTokenBudget(unittest.TestCase):
    def setUp(self):
        from labkit import llm
        self.llm = llm
        self.sent = {}
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: {"backend": "ollama", "model": "gpt-oss:latest",
                                     "endpoint": "http://example.invalid:11490"}

        def fake_urlopen(req, timeout=None):
            self.sent["url"] = req.full_url
            self.sent["payload"] = json.loads(req.data.decode("utf-8"))
            self.sent["timeout"] = timeout
            return _FakeResponse({"message": {"content": "a situation"}})

        llm.urllib.request.urlopen = fake_urlopen

    def tearDown(self):
        self.llm.resolve = self._resolve
        self.llm.urllib.request.urlopen = self._urlopen

    def test_num_predict_is_sent(self):
        self.llm.complete("gpt-oss", "prompt", max_tokens=2048, temperature=0.0)
        self.assertIn("/api/chat", self.sent["url"])
        options = self.sent["payload"].get("options", {})
        self.assertEqual(options.get("num_predict"), 2048,
                         "the chat path must send the token budget — without "
                         "it the model generates until the context is full")
        self.assertEqual(options.get("temperature"), 0.0)

    def test_default_budget_is_sent_too(self):
        """Even without an explicit max_tokens the cap must not be missing."""
        self.llm.complete("gpt-oss", "prompt")
        self.assertIsNotNone(
            self.sent["payload"].get("options", {}).get("num_predict"))

    def test_timeout_reaches_the_transport(self):
        """The wait window is the knob that does NOT touch the measurement."""
        self.llm.complete("gpt-oss", "prompt", timeout=900)
        self.assertEqual(self.sent["timeout"], 900)


class TestEmptyContentIsReported(unittest.TestCase):
    """If the model thinks and says nothing, it must not look like an answer."""

    def setUp(self):
        import io
        from labkit import llm
        self.llm, self.io = llm, io
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: {"backend": "ollama", "model": "gpt-oss:latest",
                                     "endpoint": "http://example.invalid:11490"}
        llm.urllib.request.urlopen = lambda req, timeout=None: _FakeResponse(
            {"message": {"content": "", "thinking": "The user says: ..."},
             "done_reason": "length", "eval_count": 2048})

    def tearDown(self):
        self.llm.resolve = self._resolve
        self.llm.urllib.request.urlopen = self._urlopen

    def test_empty_content_returns_empty_and_warns(self):
        err = self.io.StringIO()
        stderr, sys.stderr = sys.stderr, err
        try:
            out = self.llm.complete("gpt-oss", "prompt")
        finally:
            sys.stderr = stderr
        self.assertEqual(out, "", "empty content stays empty — the caller "
                                  "counts it as unreadable")
        self.assertIn("EMPTY content", err.getvalue())
        self.assertIn("thinking", err.getvalue())


if __name__ == "__main__":
    unittest.main()
