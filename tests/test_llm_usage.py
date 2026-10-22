"""`last_usage()` hands out what a completion cost — the token counts every
backend reports and labkit dropped until 0.81.0.

Why: 30 Claude Code transcripts (labkit, uniagent, 2026-10-11) summed to
seven billion cache-read tokens, and no labkit line anywhere said what one
audit or one probe had cost. The counts were in every reply.
"""

import contextlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test
from llm_fixture import typed  # noqa: E402

from labkit.run import llm, llm_backends  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stack(patches) -> contextlib.ExitStack:
    """Several patches as one context manager."""
    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


def _http(backend: str, reply: dict):
    return (
        mock.patch.object(
            llm,
            "spec",
            typed(
                lambda alias: {
                    "backend": backend,
                    "model": "m",
                    "endpoint": "http://example.invalid:1",
                }
            ),
        ),
        mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
        mock.patch.object(
            llm.urllib.request,
            "urlopen",
            lambda req, timeout=None: _FakeResponse(reply),
        ),
    )


class Ollama(unittest.TestCase):
    def test_prompt_and_output_counts_come_from_the_chat_reply(self):
        reply = {
            "message": {"content": "yes"},
            "prompt_eval_count": 120,
            "eval_count": 7,
        }
        with _stack(_http("ollama", reply)):
            self.assertEqual(llm.complete("a", "p"), "yes")
        self.assertEqual(llm.last_usage(), llm_backends.Usage(120, 7, None, None))

    def test_a_reply_without_counts_reports_none_not_zero(self):
        with _stack(_http("ollama", {"message": {"content": "yes"}})):
            llm.complete("a", "p")
        self.assertEqual(llm.last_usage(), llm_backends.NO_USAGE)

    def test_the_raw_route_counts_too(self):
        reply = {"response": "B", "prompt_eval_count": 33, "eval_count": 1}
        with _stack(_http("ollama", reply)):
            self.assertEqual(llm.complete("a", "p", raw=True, stop=["\n"]), "B")
        self.assertEqual(llm.last_usage().prompt_tokens, 33)


class OpenAI(unittest.TestCase):
    def test_usage_with_cached_detail(self):
        reply = {
            "choices": [{"message": {"content": "yes"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 12,
                "prompt_tokens_details": {"cached_tokens": 400},
            },
        }
        with _stack(_http("openai", reply)):
            llm.complete("a", "p")
        self.assertEqual(llm.last_usage(), llm_backends.Usage(500, 12, 400, None))


CLI_REPLY = {
    "type": "result",
    "is_error": False,
    "result": "ok",
    "num_turns": 1,
    "safety_stops": 0,
    "modelUsage": {"m": {"inputTokens": 10, "outputTokens": 43}},
    "total_cost_usd": 0.0125621,
    "usage": {
        "input_tokens": 10,
        "cache_creation_input_tokens": 5735,
        "cache_read_input_tokens": 8671,
        "output_tokens": 43,
    },
}


def _cli(stdout: str, rc: int = 0):
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")

    return seen, (
        mock.patch.object(
            llm, "spec", typed(lambda alias: {"backend": "claude-cli", "model": "m"})
        ),
        mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
        mock.patch.object(llm.subprocess, "run", fake_run),
    )


class ClaudeCli(unittest.TestCase):
    def test_the_json_reply_gives_text_counts_and_cost(self):
        seen, patches = _cli(json.dumps(CLI_REPLY) + "\n")
        with _stack(patches):
            self.assertEqual(llm.complete("a", "p"), "ok")
        cmd = seen["cmd"]
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
        # the prompt is everything the model read: uncached + created + read from cache
        self.assertEqual(
            llm.last_usage(), llm_backends.Usage(10 + 5735 + 8671, 43, 8671, 0.0125621)
        )

    def test_plain_text_on_stdout_is_a_backend_failure_not_an_answer(self):
        _, patches = _cli("ok\n")
        with _stack(patches):
            with self.assertRaises(llm_backends.BackendError) as cm:
                llm.complete("a", "p", attempts=1)
        self.assertIn("the reply is not JSON", str(cm.exception))

    def test_is_error_is_a_backend_failure(self):
        _, patches = _cli(json.dumps({**CLI_REPLY, "is_error": True, "result": "boom"}))
        with _stack(patches):
            with self.assertRaises(llm_backends.BackendError) as cm:
                llm.complete("a", "p", attempts=1)
        self.assertIn("boom", str(cm.exception))


class UnprovenIsNotRetried(unittest.TestCase):
    def test_a_switched_model_ends_the_call_at_once(self):
        calls: list = []
        reply = json.dumps({**CLI_REPLY, "modelUsage": {"m": {}, "other": {}}})
        _, patches = _cli(reply)
        with _stack(patches), mock.patch.object(llm.time, "sleep", calls.append):
            with self.assertRaises(llm_backends.UnprovenAnswer):
                llm.complete("a", "p", attempts=6)
        self.assertEqual(calls, [])  # no backoff: no second try


class Describe(unittest.TestCase):
    def test_one_line_with_thousands_separators(self):
        self.assertEqual(
            llm_backends.Usage(61234, 1902, 8671, 0.414).describe(),
            "prompt 61,234 (8,671 cached) · output 1,902 · 0.41 USD",
        )
        self.assertEqual(llm_backends.NO_USAGE.describe(), "prompt n/a · output n/a")

    def test_a_new_call_never_inherits_the_previous_counts(self):
        reply = {
            "message": {"content": "yes"},
            "prompt_eval_count": 120,
            "eval_count": 7,
        }
        with _stack(_http("ollama", reply)):
            llm.complete("a", "p")
        with _stack(_http("ollama", {"message": {"content": "no"}})):
            llm.complete("a", "p")
        self.assertEqual(llm.last_usage(), llm_backends.NO_USAGE)


if __name__ == "__main__":
    unittest.main()
