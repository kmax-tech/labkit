"""The cache of raw model answers (`llm_cache`), one
test per rule: repeat never reads the cache, replay never calls the model,
an ollama model without a weights digest is not cached and the call says
why, a re-pointed alias misses, a hit is marked in the run record with its
origin and the original usage and adds no new usage, and the cache version
and mode stand in the run record. Beside them: the stored answer is the raw
response, the endpoint is not in the key, the first answer under a key
stays, and a damaged entry stops the call. Stand-ins (`store_stand_in`):
stored under the key the real call path builds, so a replay of exactly
that call hits and any other misses; marked as stand-ins in the entry and
the call log; the cache directory keeps itself out of git.

The model is a stand-in ollama server (`ollama_fixture`): its request count
says whether a call reached a model.
"""

from __future__ import annotations

import contextlib
import inspect
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
from labkit.formats import runs
from labkit.formats.runs import LLM_CACHE_FILE, LLM_CALLS_FILE
from labkit.run import llm, llm_backends, llm_cache, runlog


#: the lab's declaration every cache needs (LAB-069 No LLM cache unless the
#: lab declares one)
DECLARED = "[llm_cache]\nenabled = true\n"


def ollama_toml(url: str, model: str = "m", *, declared: bool = True) -> str:
    table = (
        f'[models.o]\nbackend = "ollama"\nmodel = "{model}"\nendpoints = ["{url}"]\n'
    )
    return table + (DECLARED if declared else "")


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


class CallLog(CacheCase):
    """The reader of a run's `llm-calls.jsonl` (`runs.read_model_calls`): what the
    cache wrote reads back, no file is no calls, a line that is not one
    raises naming the file, the line and the field."""

    def test_the_lines_the_cache_wrote_read_back(self) -> None:
        first, _ = self.run_once()
        replayed, _ = self.run_once(replay=True)
        [asked] = runs.read_model_calls(first.dir)
        self.assertEqual((asked.alias, asked.hit, asked.origin_run), ("o", False, None))
        self.assertEqual(asked.usage["prompt_tokens"], 7)
        [hit] = runs.read_model_calls(replayed.dir)
        self.assertEqual((hit.hit, hit.origin_run), (True, first.run_id))

    def test_a_hit_line_without_stand_in_is_not_marked_as_a_stand_in(self) -> None:
        # a line written before 0.115.0 carries no `stand_in`
        (self.area / LLM_CALLS_FILE).write_text(
            '{"alias": "o", "hit": true, "origin": {"run": null, "written": "t"}, '
            '"usage": {}}\n',
            encoding="utf-8",
        )
        [hit] = runs.read_model_calls(self.area)
        self.assertEqual((hit.hit, hit.origin_run, hit.stand_in), (True, None, False))

    def test_a_line_separator_inside_a_value_stays_in_its_line(self) -> None:
        # `json.dumps(..., ensure_ascii=False)` leaves U+2028 raw; JSONL
        # splits at "\n" only, so the line reads as one call
        (self.area / LLM_CALLS_FILE).write_text(
            '{"alias": "o\u2028x", "hit": false, "origin": null, "usage": {}}\n',
            encoding="utf-8",
        )
        [call] = runs.read_model_calls(self.area)
        self.assertEqual(call.alias, "o\u2028x")

    def test_a_run_without_a_call_log_made_no_call(self) -> None:
        self.assertEqual(runs.read_model_calls(self.area), [])

    def test_a_line_that_is_not_one_names_its_place(self) -> None:
        path = self.area / LLM_CALLS_FILE
        for bad, field in (
            ("not json", "not JSON"),
            ('{"alias": "o"}', "hit"),
            ('{"alias": "o", "hit": "yes", "origin": null, "usage": {}}', "hit"),
            ('{"alias": "o", "hit": true, "origin": null, "usage": {}}', "origin"),
            ('{"alias": "o", "hit": false, "origin": null, "usage": 3}', "usage"),
            (
                '{"alias": "o", "hit": true, "origin": {"run": null, "written": "t", '
                '"stand_in": "yes"}, "usage": {}}',
                "stand_in",
            ),
            (
                '{"alias": "o", "hit": true, "origin": {"run": "r", "written": "t", '
                '"stand_in": true}, "usage": {}}',
                "stand-in names a run",
            ),
        ):
            with self.subTest(bad):
                path.write_text(bad + "\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, f"{LLM_CALLS_FILE}:1: .*{field}"
                ):
                    runs.read_model_calls(self.area)


class Declaration(CacheCase):
    """The lab allows the cache in models.toml; without it the cache
    refuses to open, and a malformed table raises."""

    def test_a_declared_cache_opens(self) -> None:
        _, answer = self.run_once()
        self.assertIsNone(answer.origin)

    def test_an_undeclared_cache_refuses_before_it_writes(self) -> None:
        self.toml.write_text(ollama_toml(self.url, declared=False), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, r"\[llm_cache\] enabled = true"):
            self.run_once()
        self.assertFalse(self.root.exists())

    def test_enabled_false_is_not_declared(self) -> None:
        self.toml.write_text(
            ollama_toml(self.url, declared=False) + "[llm_cache]\nenabled = false\n",
            encoding="utf-8",
        )
        self.assertFalse(llm.cache_declared())

    def test_a_malformed_declaration_names_the_table(self) -> None:
        for bad in (
            '[llm_cache]\nenabled = "yes"\n',
            "[llm_cache]\nenabled = true\ndir = 1\n",
            "llm_cache = true\n",
        ):
            with self.subTest(bad):
                self.toml.write_text(
                    bad + ollama_toml(self.url, declared=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, r"\[llm_cache\]"):
                    llm.cache_declared()


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


class StandIns(CacheCase):
    """`store_stand_in`: a fixed answer under the key the real call path
    builds (`key_inputs`, `cache_key`), marked as a stand-in."""

    PROMPT = "Rank these arguments.\n"

    def store(self, prompt: str = PROMPT, answer: str = '["A1"]', **kw) -> Path:
        return llm_cache.store_stand_in(self.root, "o", prompt, answer, **kw)

    def replay(self, prompt: str = PROMPT, **kw) -> tuple[runlog.Run, llm_cache.Answer]:
        answers: list[llm_cache.Answer] = []
        with runlog.run("e", {"model": "o"}, self.area) as run:
            cache = llm_cache.Cache(run, root=self.root, replay=True)
            answers.append(cache.complete("o", prompt, **kw))
        return run, answers[0]

    def test_a_replay_of_the_same_call_answers_from_the_stand_in(self) -> None:
        path = self.store(temperature=0.0)
        run, answer = self.replay(temperature=0.0)
        self.assertEqual(answer.response.text, '["A1"]')
        assert answer.origin is not None
        self.assertEqual((answer.origin.run, answer.origin.stand_in), (None, True))
        [line] = self.calls(run)
        self.assertEqual(line["origin"]["stand_in"], True)
        [call] = runs.read_model_calls(run.dir)
        self.assertEqual((call.hit, call.origin_run, call.stand_in), (True, None, True))
        entry = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((entry["stand_in"], entry["run"]), (True, None))
        self.assertEqual(entry["inputs"]["prompt"], self.PROMPT)
        self.assertEqual(
            (entry["response"]["finish_reason"], entry["response"]["usage"]),
            (None, llm.NO_USAGE._asdict()),
        )
        self.assertEqual(self.server.chats, 0)

    def test_the_twin_a_call_that_differs_misses_and_never_hits(self) -> None:
        self.store(temperature=0.0)
        for prompt, kw in (
            ("Rank these arguments.", {"temperature": 0.0}),  # one line end fewer
            ("Rank these arguments!\n", {"temperature": 0.0}),
            (self.PROMPT, {"temperature": 0.7}),
            (self.PROMPT, {"temperature": 0.0, "system": "Be brief."}),
        ):
            with self.subTest(prompt=prompt, kw=kw):
                with self.assertRaisesRegex(llm_cache.CacheMiss, "no stored answer"):
                    self.replay(prompt, **kw)
        self.assertEqual(self.server.chats, 0)

    def test_the_key_is_the_one_the_real_call_path_builds(self) -> None:
        path = self.store(temperature=0.0)
        inputs = llm_cache.key_inputs(
            "o",
            self.PROMPT,
            system=None,
            temperature=0.0,
            max_tokens=None,
            raw=False,
            stop=None,
        )
        key = llm_cache.cache_key(inputs)
        self.assertEqual(path, llm_cache.entry_path(self.root.resolve(), key))

    def test_its_defaults_are_those_of_the_real_call(self) -> None:
        # a default that drifted would store under a key no default call gets
        stored = inspect.signature(llm_cache.store_stand_in).parameters
        called = inspect.signature(llm_cache.Cache.complete).parameters
        for name in ("system", "temperature", "max_tokens", "raw", "stop"):
            with self.subTest(name):
                self.assertEqual(stored[name].default, called[name].default)

    def test_the_cache_directory_keeps_itself_out_of_git(self) -> None:
        self.store()
        self.assertEqual((self.root / ".gitignore").read_text(), "*\n")

    def test_the_same_stand_in_again_is_left_as_it_is(self) -> None:
        path = self.store()
        before = path.read_text(encoding="utf-8")
        self.assertEqual(self.store(), path)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_another_entry_under_the_key_is_refused(self) -> None:
        self.store()
        with self.assertRaisesRegex(ValueError, "a stand-in with another answer"):
            self.store(answer="other")
        with runlog.run("e", {"model": "o"}, self.area) as run:
            llm_cache.Cache(run, root=self.root).complete("o", "asked", temperature=0)
        with self.assertRaisesRegex(
            ValueError, f"a model's answer stored by run {run.run_id}"
        ):
            self.store("asked", temperature=0)

    def test_an_undeclared_cache_refuses_before_it_writes(self) -> None:
        self.toml.write_text(ollama_toml(self.url, declared=False), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, r"\[llm_cache\] enabled = true"):
            self.store()
        self.assertFalse(self.root.exists())

    def test_an_uncacheable_alias_is_refused(self) -> None:
        self.server.digest = None
        llm._FROZEN.clear()
        with self.assertRaisesRegex(ValueError, "no single weights digest"):
            self.store()
        self.assertFalse(self.root.exists())

    def test_entries_read_with_their_mark(self) -> None:
        # an entry written before 0.115.0 has no `stand_in`: not marked as one;
        # a stand-in that names a run is no entry labkit writes
        path = self.store()
        entry = json.loads(path.read_text(encoding="utf-8"))
        key = entry["key"]
        del entry["stand_in"]
        path.write_text(json.dumps(entry), encoding="utf-8")
        old = llm_cache.read_entry(path, key)
        assert old is not None and old.origin is not None
        self.assertFalse(old.origin.stand_in)
        entry.update(stand_in=True, run="2026-11-21T10-55-52_a997")
        path.write_text(json.dumps(entry), encoding="utf-8")
        with self.assertRaisesRegex(llm_cache.CacheCorruptionError, "names run"):
            llm_cache.read_entry(path, key)


if __name__ == "__main__":
    unittest.main()
