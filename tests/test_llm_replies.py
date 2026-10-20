"""A server reply of the wrong shape fails as one ReplyError naming the
backend, the route and the field — not as the KeyError, AttributeError,
TypeError or JSONDecodeError it raised deep in each parser, and not as a
string count stored as a token number (review 2026-10-20). A reply of the
right shape is read as before.

    .venv/bin/python -m pytest tests/test_llm_replies.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_fixture import spec_of  # noqa: E402

from labkit.run import llm_backends as B  # noqa: E402

OLLAMA = spec_of({"backend": "ollama", "model": "m", "endpoint": "http://h:1"}, "o")
OPENAI = spec_of({"backend": "openai", "model": "m", "endpoint": "http://h:1"}, "a")
KW = dict(system=None, temperature=None, timeout=5, stop=None, max_tokens=10)


def _reply(body: object):
    return mock.patch.object(B, "_post_json", lambda *a, **k: body)


def raw() -> str:
    return B.complete_ollama_raw(OLLAMA, "p", **KW)  # type: ignore[arg-type]


def chat() -> str:
    return B.complete_ollama_chat(OLLAMA, "p", **KW)  # type: ignore[arg-type]


def openai() -> str:
    return B.complete_openai(OPENAI, "p", raw=False, **KW)  # type: ignore[arg-type]


class WrongShapes(unittest.TestCase):
    def test_each_backend_names_the_field(self) -> None:
        answer = {"content": "x", "reasoning_content": "r"}
        for call, body, needle in (
            (raw, {"done": True}, "/api/generate: the reply has no `response`"),
            (raw, {"response": 3}, "`response` = 3, not str"),
            (
                raw,
                {"response": "ok", "eval_count": "many"},
                "`eval_count` = 'many', not int",
            ),
            (chat, {"message": "hi"}, "/api/chat: `message` = 'hi', not dict"),
            (
                chat,
                {"message": {"content": ["a"]}},
                "message: `content` = ['a'], not str",
            ),
            (openai, {"choices": "x"}, "`choices` = 'x', not list"),
            (openai, {"choices": ["x"]}, "not a list of objects"),
            (
                openai,
                {"choices": [{"message": answer}], "usage": {"prompt_tokens": "9"}},
                "usage: `prompt_tokens` = '9', not int",
            ),
        ):
            with self.subTest(needle=needle), _reply(body):
                with self.assertRaises(B.ReplyError) as cm:
                    call()
                self.assertIn(needle, str(cm.exception))

    def test_a_reply_that_is_no_json_object_is_said(self) -> None:
        for raw_reply, needle in (
            (b"<html>502 Bad Gateway</html>", "the reply is not JSON"),
            (b'{"response": "ok"', "the reply is not JSON"),  # cut in transit
            (b"[1]", "a JSON list, not an object"),
        ):
            with self.subTest(needle=needle):
                with self.assertRaisesRegex(B.ReplyError, needle):
                    B.json_reply(raw_reply, "o /api/generate")

    def test_claude_cli_counts_are_counts(self) -> None:
        with self.assertRaisesRegex(B.ReplyError, "`input_tokens` = 'many', not int"):
            B._cli_result(
                json.dumps({"result": "ok", "usage": {"input_tokens": "many"}})
            )

    def test_a_reply_error_is_retried_like_any_backend_error(self) -> None:
        self.assertTrue(issubclass(B.ReplyError, B.BackendError))


class RightShapes(unittest.TestCase):
    """The twins: replies as the APIs define them are read as before."""

    def test_each_backend_reads_its_answer_and_counts(self) -> None:
        with _reply({"response": " ok ", "prompt_eval_count": 3, "eval_count": 1}):
            self.assertEqual(raw(), "ok")
        self.assertEqual(
            (B.CALL_STATE.usage.prompt_tokens, B.CALL_STATE.usage.output_tokens), (3, 1)
        )
        with _reply({"message": {"content": "yes", "thinking": "t"}}):
            self.assertEqual(chat(), "yes")
        with _reply(
            {"choices": [{"message": {"content": "no"}}], "usage": {"prompt_tokens": 4}}
        ):
            self.assertEqual(openai(), "no")
        self.assertEqual(B.CALL_STATE.usage.prompt_tokens, 4)
        self.assertEqual(
            B._cli_result(json.dumps({"result": " r ", "total_cost_usd": 0.01})), "r"
        )


if __name__ == "__main__":
    unittest.main()
