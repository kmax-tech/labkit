"""`last_thinking()` hands out the reasoning trace the answer alone hides.

Why: uniagent kept only the classifier's answers, so a false framework `yes`
on a BNC cable set could not be explained afterwards (2026-10-07). The
trace was in the server's reply all along and labkit dropped it.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestLastThinking(unittest.TestCase):
    def setUp(self):
        from labkit import llm

        self.llm = llm
        self.reply = {}
        self._resolve, self._urlopen = llm.resolve, llm.urllib.request.urlopen
        llm.resolve = lambda alias: {
            "backend": "ollama",
            "model": "gpt-oss:latest",
            "endpoint": "http://example.invalid:11490",
        }
        llm.urllib.request.urlopen = lambda req, timeout=None: _FakeResponse(self.reply)

    def tearDown(self):
        setattr(self.llm, "resolve", self._resolve)
        self.llm.urllib.request.urlopen = self._urlopen

    def test_the_trace_of_the_last_call_is_kept(self):
        self.reply = {
            "message": {"content": "yes", "thinking": "Cables are accessories."}
        }
        self.assertEqual(self.llm.complete("gpt-oss", "p"), "yes")
        self.assertEqual(self.llm.last_thinking(), "Cables are accessories.")

    def test_a_call_without_a_trace_does_not_inherit_the_previous_one(self):
        self.reply = {"message": {"content": "yes", "thinking": "first"}}
        self.llm.complete("gpt-oss", "p")
        self.reply = {"message": {"content": "no"}}
        self.llm.complete("gpt-oss", "p")
        self.assertEqual(self.llm.last_thinking(), "")


if __name__ == "__main__":
    unittest.main()
