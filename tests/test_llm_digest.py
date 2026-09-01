"""Digest-Pinning in llm.resolve (2026-08-18).

Der Modell-NAME ist nicht das Modell: "qwen2.5:7b" kann in drei Monaten andere
Gewichte meinen. `resolve` holt fuer ollama-Backends den Digest aus /api/tags
in die Run-Config. Die Aufloesung ist eine pure Funktion und wird hier an einem
echten /api/tags-Payload-Ausschnitt getestet (gammaweb, 2026-08-18).
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

    def test_unbekanntes_modell_wird_nicht_geraten(self):
        self.assertEqual(llm._digest_from_tags(TAGS, "qwen2.5:7b"), "unavailable")

    def test_leerer_payload(self):
        self.assertEqual(llm._digest_from_tags({}, "x"), "unavailable")


if __name__ == "__main__":
    unittest.main()
