"""The cache of raw model answers (`llm_cache`, stagekit plan step 2), one
test per rule: repeat never reads the cache, replay never calls the model,
an ollama model without a weights digest is not cached and the call says
why, a re-pointed alias misses, a hit is marked in the run record with its
origin and the original usage and adds no new usage, and the cache version
and mode stand in the run record. Beside them: the stored answer is the raw
response, the endpoint is not in the key, the first answer under a key
stays, and a damaged entry stops the call.

The model is a stand-in ollama server (`ollama_fixture`): its request count
says whether a call reached a model.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ollama_fixture
from llm_fixture import cli_reply, spec_of
from models_fixture import serve

from labkit.formats.files import write_once
from labkit.formats.runs import LLM_CACHE_FILE, LLM_CALLS_FILE
from labkit.run import llm, llm_backends, llm_cache, runlog


def ollama_toml(url: str, model: str = "m") -> str:
    return f'[models.o]\nbackend = "ollama"\nmodel = "{model}"\nendpoints = ["{url}"]\n'


class CacheCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name).resolve()
        self.root = self.area / "cache"
        self.server, self.url = ollama_fixture.start(self)
        self.toml = serve(self, ollama_toml(self.url))
        self.stderr = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(self.stderr))

    def run_once(
        self, *, replay: bool = False, repeat_of: str | None = None
    ) -> tuple[runlog.Run, llm_cache.Answer]:
        """One run asking the stand-in once through the cache."""
        answers: list[llm_cache.Answer] = []
        with runlog.run("e", {"model": "o"}, self.area, repeat_of=repeat_of) as run:
            cache = llm_cache.Cache(run, root=self.root, replay=replay)
            answers.append(cache.complete("o", "Is this a fallacy?", temperature=0))
        return run, answers[0]

    def calls(self, run: runlog.Run) -> list[dict]:
        text = (run.dir / LLM_CALLS_FILE).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]


class Rules(CacheCase):
    def test_a_repeat_never_reads_the_cache(self) -> None:
        first, _ = self.run_once()
        self.server.answer = "another answer"
        repeat, answer = self.run_once(repeat_of=first.run_id)
        self.assertEqual(self.server.chats, 2)
        self.assertEqual(
            (answer.response.text, answer.origin), ("another answer", None)
        )
        self.assertEqual(self.calls(repeat)[0]["hit"], False)
        replayed, _ = self.run_once(replay=True)
        self.assertEqual(self.calls(replayed)[0]["origin"]["run"], first.run_id)
        self.assertEqual(
            self.server.chats, 2, "the repeat stored nothing a replay reads"
        )

    def test_a_replay_never_calls_the_model(self) -> None:
        self.run_once()
        _, answer = self.run_once(replay=True)
        self.assertEqual(self.server.chats, 1)
        self.assertEqual(answer.response.text, "the answer")
        with runlog.run("e", {"model": "o"}, self.area) as run:
            cache = llm_cache.Cache(run, root=self.root, replay=True)
            with self.assertRaisesRegex(llm_cache.CacheMiss, "no stored answer"):
                cache.complete("o", "a prompt nobody asked", temperature=0)
        self.assertEqual(self.server.chats, 1)

    def test_an_ollama_model_without_a_digest_is_not_cached_and_says_why(self) -> None:
        self.server.digest = None
        llm._FROZEN.clear()
        run, answer = self.run_once()
        self.assertIn("not cached", self.stderr.getvalue())
        self.assertIn("unavailable", self.calls(run)[0]["uncached"])
        self.assertFalse(list(self.root.rglob("*.json")))
        self.assertEqual(answer.response.text, "the answer")
        with self.assertRaisesRegex(llm_cache.CacheMiss, "replay asks no model"):
            self.run_once(replay=True)
        self.assertEqual(self.server.chats, 1)

    def test_a_re_pointed_alias_misses(self) -> None:
        self.run_once()
        self.server.model = "other"  # the same weights digest, another model
        self.toml.write_text(ollama_toml(self.url, model="other"), encoding="utf-8")
        llm._FROZEN.clear()  # a new process reads the edited file
        run, answer = self.run_once()
        self.assertIsNone(answer.origin)
        self.assertEqual(self.server.chats, 2)
        self.assertIsNone(self.calls(run)[0]["uncached"], "a cacheable call missed")

    def test_a_hit_is_marked_with_its_origin_and_adds_no_usage(self) -> None:
        first, _ = self.run_once()
        second, answer = self.run_once()
        assert answer.origin is not None
        self.assertEqual(answer.origin.run, first.run_id)
        [line] = self.calls(second)
        self.assertEqual((line["hit"], line["origin"]["run"]), (True, first.run_id))
        self.assertEqual(line["usage"]["prompt_tokens"], 7)
        self.assertEqual(llm_cache.fresh_usage(second.dir), llm.NO_USAGE)
        self.assertEqual(llm_cache.fresh_usage(first.dir).prompt_tokens, 7)

    def test_the_cache_version_and_mode_stand_in_the_run_record(self) -> None:
        first, _ = self.run_once()
        replayed, _ = self.run_once(replay=True)
        for run, mode in ((first, "normal"), (replayed, "replay")):
            record = json.loads((run.dir / LLM_CACHE_FILE).read_text())
            self.assertEqual(
                record,
                {
                    "cache_version": llm_cache.CACHE_VERSION,
                    "mode": mode,
                    "root": str(self.root),
                },
            )


class Entries(CacheCase):
    def test_the_stored_answer_is_the_raw_response(self) -> None:
        self.server.answer = "  B) because the premise is false  "
        _, answer = self.run_once()
        [entry] = [json.loads(p.read_text()) for p in self.root.rglob("??/*.json")]
        stored = entry["response"]
        self.assertEqual(stored["text"], "B) because the premise is false")
        self.assertEqual(stored["thinking"], "because")
        self.assertEqual(stored["finish_reason"], "stop")
        self.assertEqual(stored["endpoint"], self.url)
        self.assertEqual(stored["body"]["eval_count"], 3)
        self.assertEqual(entry["inputs"]["prompt"], "Is this a fallacy?")
        self.assertNotIn("parser", json.dumps(entry["inputs"]))
        self.assertEqual(answer.response.finish_reason, "stop")

    def test_every_backend_hands_over_its_finish_reason_and_reply(self) -> None:
        openai = spec_of({"backend": "openai", "model": "m", "endpoint": "http://h:1"})
        body = {
            "choices": [{"message": {"content": "x"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with mock.patch.object(llm_backends, "_post_json", lambda *a, **k: body):
            llm_backends.complete_openai(
                openai,  # type: ignore[arg-type]
                "p",
                system=None,
                temperature=None,
                timeout=5,
                raw=False,
                stop=None,
                max_tokens=10,
            )
        state = llm_backends.CALL_STATE
        self.assertEqual((state.finish_reason, state.body), ("length", body))
        reply = cli_reply("claude-x", stop_reason="end_turn")
        llm_backends._cli_result(reply, "claude-x")
        self.assertEqual(state.finish_reason, "end_turn")
        self.assertEqual(state.body, json.loads(reply))

    def test_another_endpoint_serving_the_same_weights_hits(self) -> None:
        self.run_once()
        _, url = ollama_fixture.start(self)
        self.toml.write_text(ollama_toml(url), encoding="utf-8")
        llm._FROZEN.clear()
        _, answer = self.run_once(replay=True)
        self.assertIsNotNone(answer.origin)

    def test_the_first_answer_under_a_key_stays(self) -> None:
        path = self.area / "entry.json"
        self.assertTrue(write_once(path, "first"))
        self.assertFalse(write_once(path, "second"))
        self.assertEqual(path.read_text(), "first")
        self.assertEqual([p.name for p in self.area.iterdir()], ["entry.json"])

    def test_a_damaged_entry_stops_the_call(self) -> None:
        self.run_once()
        [path] = self.root.rglob("??/*.json")
        path.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(llm_cache.CacheCorruptionError, "move it aside"):
            self.run_once()
        self.assertEqual(self.server.chats, 1)

    def test_the_cache_directory_keeps_itself_out_of_git(self) -> None:
        self.run_once()
        self.assertEqual((self.root / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
