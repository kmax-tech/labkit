"""Digest pinning in llm.resolve (2026-08-18).

The model NAME is not the model: "qwen2.5:7b" can mean different weights in
three months. For ollama backends `resolve` pulls the digest from /api/tags
into the run config. The resolution is a pure function and is tested here
against a real /api/tags payload excerpt (gammaweb, 2026-08-18).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # the package under test
from labkit import llm  # noqa: E402

TAGS = {"models": [
    {"name": "llama2:7b-chat", "model": "llama2:7b-chat",
     "digest": "78e26419b4469263f75331927a00a0284ef6544c1975b826b15abdaef17bb962"},
    {"name": "gpt-oss:latest", "model": "gpt-oss:latest",
     "digest": "aa4295ac10c3b5e3b8b1d5c1c9f3f0a2ffffffffffffffffffffffffffffffff"},
]}


class TestDigestLookup(unittest.TestCase):

    def test_exakter_name(self):
        self.assertEqual(llm._digest_from_tags(TAGS, "llama2:7b-chat"), "78e26419b446")

    def test_blanker_name_matcht_latest(self):
        # models.toml sagt "gpt-oss:latest", aber auch der blanke Name muss treffen
        self.assertEqual(llm._digest_from_tags(TAGS, "gpt-oss"), "aa4295ac10c3")

    def test_unknown_model_is_not_guessed(self):
        self.assertEqual(llm._digest_from_tags(TAGS, "qwen2.5:7b"), "unavailable")

    def test_empty_payload(self):
        self.assertEqual(llm._digest_from_tags({}, "x"), "unavailable")


if __name__ == "__main__":
    unittest.main()


class TestPrefixedDigest(unittest.TestCase):
    """A proxy may send "sha256:<hex>"; the pin is the hex, not the prefix."""

    def test_algorithm_prefix_is_not_part_of_the_pin(self):
        from labkit import llm
        tags = {"models": [{"name": "gemma3-4b", "digest": "sha256:f8ceb1a2b3c4d5e6f7"}]}
        self.assertEqual(llm._digest_from_tags(tags, "gemma3-4b"), "f8ceb1a2b3c4")
