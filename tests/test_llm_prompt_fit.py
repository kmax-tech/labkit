"""ollama must not answer a cut prompt as if it had read it all.

Why this file exists: ollama fits a prompt longer than its context window by
dropping tokens and answers the rest; the reply looks like any other. The
ollama paths set no `num_ctx` until 0.83.0, so the server's default window
applied — and an audit prompt of tens of kB would have
reached a local auditor with its protocol cut off, and come back clean
(found 2026-10-11 while asking whether the auditor can run on a local
model). Each blocking check has its twin: the whole prompt passes.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test
from llm_fixture import spec_of  # noqa: E402

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


def _call(spec: dict, prompt: str, reply: dict, *, raw: bool = False) -> dict:
    """One llm.complete against a fake ollama; returns the payload sent."""
    sent: dict = {}

    def fake_urlopen(req, timeout=None):
        sent.update(json.loads(req.data.decode("utf-8")))
        return _FakeResponse(reply)

    with (
        mock.patch.object(llm, "spec", lambda alias: spec_of(spec)),
        mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
        mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen),
    ):
        llm.complete("local", prompt, raw=raw, stop=["\n"] if raw else None, attempts=1)
    return sent


SPEC = {
    "alias": "local",
    "backend": "ollama",
    "model": "qwen3:32b",
    "endpoint": "http://example.invalid:11434",
}
PROMPT = "word " * 4000  # 20,000 characters, ~4,000 tokens when read whole


def _chat(prompt_tokens: int) -> dict:
    return {"message": {"content": "ok"}, "prompt_eval_count": prompt_tokens}


class NumCtxIsSent(unittest.TestCase):
    def test_chat_path_sends_num_ctx(self):
        sent = _call({**SPEC, "num_ctx": 32768}, "p", _chat(5))
        self.assertEqual(sent["options"]["num_ctx"], 32768)

    def test_raw_path_sends_num_ctx(self):
        reply = {"response": "B", "prompt_eval_count": 5}
        sent = _call({**SPEC, "num_ctx": 32768}, "p", reply, raw=True)
        self.assertEqual(sent["options"]["num_ctx"], 32768)

    def test_unset_num_ctx_is_not_sent(self):
        sent = _call(SPEC, "p", _chat(5))
        self.assertNotIn("num_ctx", sent["options"])


class CutPromptRaises(unittest.TestCase):
    def test_count_far_below_length_raises_without_num_ctx(self):
        # 20,000 characters read as 1,500 tokens: ~13 per token
        with self.assertRaisesRegex(llm_backends.PromptTruncated, "no num_ctx is set"):
            _call(SPEC, PROMPT, _chat(1500))

    def test_whole_prompt_passes_without_num_ctx(self):
        _call(SPEC, PROMPT, _chat(4010))

    def test_count_reaching_num_ctx_raises(self):
        # a cut to a 16k window: the ratio alone (~1.2) would pass it
        with self.assertRaisesRegex(llm_backends.PromptTruncated, "num_ctx"):
            _call({**SPEC, "num_ctx": 16384}, "x" * 20000, _chat(16384))

    def test_count_below_num_ctx_passes(self):
        _call({**SPEC, "num_ctx": 16384}, "x" * 20000, _chat(16000))

    def test_raw_path_checks_too(self):
        reply = {"response": "B", "prompt_eval_count": 1000}
        with self.assertRaises(llm_backends.PromptTruncated):
            _call(SPEC, PROMPT, reply, raw=True)

    def test_system_text_counts_toward_the_prompt(self):
        spec = dict(SPEC)

        def run(system: str) -> None:
            with (
                mock.patch.object(llm, "spec", lambda alias: spec_of(spec)),
                mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
                mock.patch.object(
                    llm.urllib.request,
                    "urlopen",
                    lambda req, timeout=None: _FakeResponse(_chat(1500)),
                ),
            ):
                llm.complete("local", "short", system=system, attempts=1)

        with self.assertRaises(llm_backends.PromptTruncated):
            run(PROMPT)

    def test_short_prompt_is_not_judged_by_ratio(self):
        # template tokens dominate a short prompt; it fits every window
        _call(SPEC, "x" * 3000, _chat(10))

    def test_reply_without_count_passes(self):
        _call(SPEC, PROMPT, {"message": {"content": "ok"}})

    def test_not_retried(self):
        self.assertNotIn(llm_backends.PromptTruncated, llm._TRANSIENT)


class NumCtxIsValidated(unittest.TestCase):
    def _resolve(self, body: str) -> dict:
        with (
            mock.patch.object(llm, "_find_models_toml") as find,
            mock.patch.object(llm, "_ollama_digest", lambda *a: "abc"),
            mock.patch.dict(llm._FROZEN, clear=True),
        ):
            find.return_value.read_text.return_value = body
            return llm.resolve("m")

    def test_ollama_with_num_ctx_resolves(self):
        spec = self._resolve(
            '[models.m]\nbackend = "ollama"\nmodel = "q"\nendpoints = ["http://h:1"]\n'
            "num_ctx = 32768\n"
        )
        self.assertEqual(spec["num_ctx"], 32768)

    def test_num_ctx_on_another_backend_raises(self):
        with self.assertRaisesRegex(ValueError, "ollama option"):
            self._resolve('[models.m]\nbackend = "openai"\nmodel = "q"\nnum_ctx = 8\n')

    def test_non_integer_num_ctx_raises(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self._resolve(
                '[models.m]\nbackend = "ollama"\nmodel = "q"\nendpoints = ["http://h:1"]\n'
                'num_ctx = "32k"\n'
            )


if __name__ == "__main__":
    unittest.main()
