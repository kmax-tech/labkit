"""A server reply of the wrong shape fails as one ReplyError naming the
backend, the route and the field — not as the KeyError, AttributeError,
TypeError or JSONDecodeError it raised deep in each parser, and not as a
string count stored as a token number (review 2026-10-20). A reply of the
right shape is read as before.

    .venv/bin/python -m pytest tests/test_llm_replies.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_fixture import cli_reply, spec_of  # noqa: E402

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
            B._cli_result(cli_reply(result="ok", usage={"input_tokens": "many"}), "m")

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
            B._cli_result(cli_reply(result=" r ", total_cost_usd=0.01), "m"), "r"
        )


class ClaudeCliProvenance(unittest.TestCase):
    """The reply names who wrote the answer; anything but the requested
    model alone, whole, is no answer of it. The stop and the switch are the
    shapes a safety classifier left in the fit probes' audits (round
    de663ed, 2026-10-22): `claude-opus-5-5` stopped, `claude-opus-4-8`
    continued, `result` held only the continuation."""

    def test_the_requested_model_alone_in_one_turn_is_its_answer(self) -> None:
        self.assertEqual(
            B._cli_result(cli_reply("claude-opus-5-5"), "claude-opus-5-5"), "Yes"
        )

    def test_a_switched_model_is_refused_naming_both(self) -> None:
        reply = cli_reply(modelUsage={"claude-opus-5-5": {}, "claude-opus-4-8": {}})
        with self.assertRaisesRegex(
            B.UnprovenAnswer, "requested claude-opus-5-5.*claude-opus-4-8"
        ):
            B._cli_result(reply, "claude-opus-5-5")
        other = cli_reply(modelUsage={"claude-opus-4-8": {}})
        with self.assertRaisesRegex(B.UnprovenAnswer, "written by claude-opus-4-8"):
            B._cli_result(other, "claude-opus-5-5")

    def test_a_safety_stop_is_refused_even_under_one_model(self) -> None:
        reply = cli_reply("claude-opus-5-5", safety_stops=1)
        with self.assertRaisesRegex(B.UnprovenAnswer, "1 safety stop"):
            B._cli_result(reply, "claude-opus-5-5")

    def test_more_than_one_turn_is_refused(self) -> None:
        with self.assertRaisesRegex(B.UnprovenAnswer, "2 turns"):
            B._cli_result(cli_reply(num_turns=2), "m")

    def test_a_stopped_answer_flagged_as_error_is_unproven_not_retried(self) -> None:
        """fit-1 on 4f4f238: every audit try was stopped and continued, and
        the call was retried — the stop must win over `is_error`."""
        reply = cli_reply(
            "claude-opus-5-5",
            is_error=True,
            subtype="error_during_execution",
            safety_stops=1,
            modelUsage={"claude-opus-5-5": {}, "claude-opus-4-8": {}},
        )
        with self.assertRaises(B.UnprovenAnswer) as cm:
            B._cli_result(reply, "claude-opus-5-5")
        self.assertIn("safety_stops=1", str(cm.exception))
        self.assertIn(
            "models=['claude-opus-4-8', 'claude-opus-5-5']", str(cm.exception)
        )

    def test_an_error_without_a_stop_stays_retryable_and_names_the_fields(self) -> None:
        reply = cli_reply(is_error=True, result="overloaded", modelUsage={})
        with self.assertRaises(B.BackendError) as cm:
            B._cli_result(reply, "m")
        self.assertNotIsInstance(cm.exception, B.UnprovenAnswer)
        self.assertIn("is_error=True", str(cm.exception))

    def test_the_stop_as_cli_2_1_285_reported_it_is_unproven(self) -> None:
        """The reply of a stopped audit in the fit probe on 97e6470, field
        for field: a success, no error, no `safety_stops` at all."""
        reply = cli_reply(
            "claude-opus-5-5",
            without="safety_stops",
            subtype="success",
            is_error=False,
            num_turns=2,
            modelUsage={"claude-opus-4-8": {}, "claude-opus-5-5": {}},
        )
        with self.assertRaisesRegex(B.UnprovenAnswer, "written by claude-opus-4-8"):
            B._cli_result(reply, "claude-opus-5-5")

    def test_a_cli_without_safety_stops_answers_when_one_model_wrote_it(self) -> None:
        self.assertEqual(B._cli_result(cli_reply(without="safety_stops"), "m"), "Yes")
        with self.assertRaisesRegex(B.UnprovenAnswer, "2 turns"):
            B._cli_result(cli_reply(without="safety_stops", num_turns=2), "m")

    def test_a_reply_without_the_proof_is_refused(self) -> None:
        for key in ("num_turns", "modelUsage"):
            with self.subTest(key):
                with self.assertRaisesRegex(B.ReplyError, f"no `{key}`.*subtype="):
                    B._cli_result(cli_reply(without=key), "m")


if __name__ == "__main__":
    unittest.main()
