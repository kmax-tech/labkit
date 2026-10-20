"""The backend specs (2026-10-20): one type per backend, its options and
nothing else, refused at load when models.toml says what the backend cannot
do; immutable all the way down; recorded in the shape runs have always
held."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.run import llm  # noqa: E402
from labkit.run.llm_specs import (  # noqa: E402
    ClaudeCliSpec,
    OllamaSpec,
    OpenAISpec,
    parse_spec,
    record,
)

NAMES = {"gamma1": "http://gamma.invalid:11490"}


class Parse(unittest.TestCase):
    def test_each_backend_parses_to_its_type(self):
        """The twins: a table its backend can hold passes."""
        self.assertEqual(
            parse_spec("h", {"backend": "claude-cli", "model": "haiku"}, NAMES),
            ClaudeCliSpec("h", "haiku"),
        )
        self.assertEqual(
            parse_spec(
                "o",
                {
                    "backend": "ollama",
                    "model": "qwen3:32b",
                    "endpoints": ["gamma1", "http://b.invalid:1"],
                    "num_ctx": 32768,
                    "api_key_env": "KEY",
                },
                NAMES,
            ),
            OllamaSpec(
                "o",
                "qwen3:32b",
                ("http://gamma.invalid:11490", "http://b.invalid:1"),
                num_ctx=32768,
                api_key_env="KEY",
            ),
        )
        self.assertEqual(
            parse_spec(
                "v",
                {
                    "backend": "openai",
                    "model": "openai/gpt-oss-20b",
                    "endpoints": ["gamma1"],
                    "reasoning": True,
                },
                NAMES,
            ),
            OpenAISpec(
                "v",
                "openai/gpt-oss-20b",
                ("http://gamma.invalid:11490",),
                reasoning=True,
            ),
        )

    def test_a_key_its_backend_does_not_read_is_refused(self):
        for table, word in (
            (
                {"backend": "claude-cli", "model": "m", "endpoints": ["gamma1"]},
                "endpoints",
            ),
            (
                {
                    "backend": "ollama",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "reasoning": True,
                },
                "reasoning",
            ),
            (
                {
                    "backend": "openai",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "num_ctx": 8,
                },
                "ollama option",
            ),
            (
                {
                    "backend": "openai",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "temprature": 0,
                },
                "temprature",
            ),
        ):
            with self.subTest(table=table):
                with self.assertRaises(ValueError) as cm:
                    parse_spec("a", table, NAMES)
                self.assertIn(word, str(cm.exception))

    def test_a_value_of_the_wrong_kind_is_refused(self):
        for table, word in (
            ({"backend": "gpt", "model": "m"}, "backend = 'gpt'"),
            ({"backend": "claude-cli", "model": ""}, "model = ''"),
            ({"backend": "ollama", "model": "m"}, "needs `endpoints"),
            ({"backend": "ollama", "model": "m", "endpoints": []}, "needs `endpoints"),
            (
                {"backend": "ollama", "model": "m", "endpoints": "gamma1"},
                "needs `endpoints",
            ),
            (
                {
                    "backend": "ollama",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "num_ctx": True,
                },
                "positive integer",
            ),
            (
                {
                    "backend": "openai",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "reasoning": "yes",
                },
                "not true or false",
            ),
            (
                {
                    "backend": "openai",
                    "model": "m",
                    "endpoints": ["gamma1"],
                    "api_key_env": 3,
                },
                "not a string",
            ),
            (
                {"backend": "openai", "model": "m", "endpoint": "gamma1"},
                "not read since labkit 0.89.0",
            ),
        ):
            with self.subTest(table=table):
                with self.assertRaises(ValueError) as cm:
                    parse_spec("a", table, NAMES)
                self.assertIn(word, str(cm.exception))
        with self.assertRaises(KeyError):
            parse_spec(
                "a", {"backend": "ollama", "model": "m", "endpoints": ["gamma9"]}, NAMES
            )


class Frozen(unittest.TestCase):
    def test_the_spec_and_its_values_cannot_be_edited(self):
        spec = OllamaSpec("o", "m", ("http://a.invalid:1",))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.model = "other"  # type: ignore[misc]
        self.assertIsInstance(spec.endpoints, tuple)

    def test_a_record_is_a_fresh_dict_every_time(self):
        spec = OpenAISpec("v", "m", ("http://a.invalid:1",))
        first = record(spec)
        first["endpoints"].append("http://edited.invalid:2")
        self.assertEqual(record(spec)["endpoints"], ["http://a.invalid:1"])
        self.assertEqual(spec.endpoints, ("http://a.invalid:1",))


class Record(unittest.TestCase):
    def test_the_record_keeps_the_shape_runs_hold(self):
        """models_resolved in config.json is a format: the typed spec writes
        the keys the dict spec wrote — options only where models.toml set them."""
        self.assertEqual(
            record(ClaudeCliSpec("h", "haiku")),
            {
                "backend": "claude-cli",
                "model": "haiku",
                "alias": "h",
                "controls_temperature": False,
            },
        )
        self.assertEqual(
            record(
                OllamaSpec(
                    "o",
                    "q",
                    ("http://a:1", "http://b:2"),
                    num_ctx=8,
                    model_digest="abc",
                )
            ),
            {
                "backend": "ollama",
                "model": "q",
                "alias": "o",
                "endpoints": ["http://a:1", "http://b:2"],
                "endpoint": "http://a:1",
                "num_ctx": 8,
                "model_digest": "abc",
                "controls_temperature": True,
            },
        )
        self.assertEqual(
            record(
                OpenAISpec("v", "m", ("http://a:1",), api_key_env="K", reasoning=False)
            ),
            {
                "backend": "openai",
                "model": "m",
                "alias": "v",
                "endpoints": ["http://a:1"],
                "endpoint": "http://a:1",
                "api_key_env": "K",
                "reasoning": False,
                "controls_temperature": True,
            },
        )


class CallOptions(unittest.TestCase):
    """claude-cli dropped `raw` and `stop` without a word; now refused
    before any process starts."""

    def call(self, **kw) -> list:
        started: list = []

        def fake_run(cmd, **_):
            started.append(cmd)
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"result": "Yes"}\n', stderr=""
            )

        with (
            mock.patch.object(llm, "spec", lambda alias: ClaudeCliSpec(alias, "m")),
            mock.patch.object(llm.endpoint_lease, "acquire", lambda *a, **k: None),
            mock.patch.object(llm.subprocess, "run", fake_run),
        ):
            llm.complete("h", "p", attempts=1, **kw)
        return started

    def test_raw_or_stop_on_claude_cli_is_refused(self):
        for kw, word in (
            ({"raw": True}, "raw=True"),
            ({"stop": ["\n"]}, "stop sequences"),
        ):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError) as cm:
                    self.call(**kw)
                self.assertIn(word, str(cm.exception))

    def test_a_plain_call_runs(self):
        """The twin: nothing the CLI cannot honour, one process."""
        self.assertEqual(len(self.call()), 1)


if __name__ == "__main__":
    unittest.main()
