"""The public API in docs/architecture.md, held to the code.

The section "Public API" is the one home of the list: this test reads its
two tables. A listed name that is gone, a changed signature or default,
or a `models.toml` key a backend no longer reads fails here; each contract
in the third column has a behaviour test below. A deliberate change goes
through the release rule stated beside the tables.

The model calls go to a local stand-in for an ollama server, so the
contract is tested through the real wire path, not a patched backend.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib
import inspect
import io
import json
import re
import tempfile
import threading
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

import ollama_fixture
from models_fixture import serve, toml

from labkit.run import batch, llm, llm_backends, llm_cache, llm_specs, runlog
from labkit.checks import prompt_check, recheck
from labkit.formats import runs
from protocol_fixture import (
    completion_record,
    PID,
    head,
    recheck_without_git,
    run_record,
)

ROOT = Path(__file__).resolve().parents[1]


def _section() -> str:
    """The text of the doc's "Public API" section."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    m = re.search(r"^## Public API\n(.*?)(?=^## )", doc, re.M | re.S)
    if m is None:
        raise AssertionError("docs/architecture.md has no '## Public API' section")
    return m.group(1)


def listed() -> dict[str, str]:
    """Listed name (`llm.complete`) → the signature its row states."""
    rows = re.findall(
        r"^\|[ \t]*`([\w.]+)`[ \t]*\|[ \t]*`([^`]+)`[ \t]*\|",
        _section(),
        re.M,
    )
    out: dict[str, str] = {}
    for name, signature in rows:
        if name in out:
            raise AssertionError(f"{name} stands twice in the public API table")
        out[name] = signature.replace("\\|", "|")  # a table cell escapes its pipes
    return out


def listed_keys() -> dict[str, frozenset[str]]:
    """Backend → the `[models.<alias>]` keys the doc's schema table states."""
    rows = re.findall(
        r'^\|[ \t]*`\[models\.<alias>\]` with `backend = "([\w-]+)"`[ \t]*\|[ \t]*([^|]+)\|',
        _section(),
        re.M,
    )
    return {b: frozenset(re.findall(r"`(\w+)`", keys)) for b, keys in rows}


#: the listed modules outside `labkit.run`, as the section's first sentence names them
PACKAGE_OF = {"recheck": "labkit.checks", "prompt_check": "labkit.checks"}


def resolve_name(name: str) -> object:
    """`llm.complete` → the object; the first part is a module of `labkit.run`,
    or of the package `PACKAGE_OF` names for it."""
    module, *attrs = name.split(".")
    package = PACKAGE_OF.get(module, "labkit.run")
    obj: object = importlib.import_module(f"{package}.{module}")
    for attr in attrs:
        obj = getattr(obj, attr)
    return obj


def rendered(name: str, obj: object) -> str:
    """The call form of OBJ as the table writes it: parameter names, the
    keyword-only star and defaults; no annotations, no `self`."""
    params = []
    star = False
    for p in inspect.signature(obj).parameters.values():  # type: ignore[arg-type]
        if p.name == "self":
            continue
        if p.kind is p.KEYWORD_ONLY and not star:
            params.append("*")
            star = True
        if p.kind is p.VAR_POSITIONAL:
            params.append(f"*{p.name}")
            star = True
        elif p.kind is p.VAR_KEYWORD:
            params.append(f"**{p.name}")
        elif p.default is p.empty:
            params.append(p.name)
        else:
            params.append(f"{p.name}={p.default!r}")
    return f"{name.rsplit('.', 1)[-1]}({', '.join(params)})"


class Listed(unittest.TestCase):
    def test_the_table_is_read(self) -> None:
        """The parse finds what is known to stand there (a parse that
        found nothing would pass every check below)."""
        names = listed()
        self.assertIn("llm.complete", names)
        self.assertEqual(names["runlog.Run.draw"], "draw: int | None")
        self.assertIn("runlog.Run.output", names)
        self.assertEqual(listed_keys().keys(), {"claude-cli", "ollama", "openai"})

    def test_every_listed_name_exists_with_its_signature(self) -> None:
        for name, signature in listed().items():
            with self.subTest(name=name):
                if "(" not in signature:  # an attribute, held by its annotation
                    owner, attr = name.rsplit(".", 1)
                    hints = getattr(resolve_name(owner), "__annotations__", {})
                    self.assertEqual(f"{attr}: {hints.get(attr)}", signature)
                    continue
                try:
                    obj = resolve_name(name)
                except (ImportError, AttributeError) as exc:
                    self.fail(f"{name} is listed public but does not import: {exc}")
                self.assertEqual(rendered(name, obj), signature)

    def test_the_models_toml_keys_are_what_the_backends_read(self) -> None:
        self.assertEqual(listed_keys(), dict(llm_specs.OPTIONS))


class Calls(unittest.TestCase):
    """`llm.complete`, `complete_many`, `complete_response`, `resolve`,
    `spec`, `identity`, `last_usage`, `last_endpoint` and
    `llm_backends.Response` against one stand-in server."""

    def setUp(self) -> None:
        self.handler, self.url = ollama_fixture.start(self)
        serve(
            self,
            f'[endpoints]\nlocal = "{self.url}"\n'
            f'[models.o]\nbackend = "ollama"\nmodel = "m"\nendpoints = ["local"]\n'
            + toml("cli", "claude-x"),
        )
        self.enterContext(mock.patch.object(llm.time, "sleep", lambda _s: None))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def test_complete_returns_the_answer_text_and_records_the_call(self) -> None:
        self.assertEqual(llm.complete("o", "q", temperature=0), "the answer")
        self.assertEqual(llm.last_endpoint(), self.url)
        usage = llm.last_usage()
        self.assertEqual((usage.prompt_tokens, usage.output_tokens), (7, 3))

    def test_complete_many_keeps_the_input_order(self) -> None:
        self.assertEqual(
            llm.complete_many("o", ["a", "b", "c"], workers=3), ["the answer"] * 3
        )
        self.assertEqual(self.handler.chats, 3)

    def test_an_http_4xx_raises_backend_error_without_a_retry(self) -> None:
        self.handler.status = 404
        with self.assertRaises(llm.BackendError) as cm:
            llm.complete("o", "q", attempts=3)
        self.assertIn("HTTP 404", str(cm.exception))
        self.assertEqual(self.handler.chats, 1)

    def test_exhausted_retries_raise_backend_error_a_runtime_error(self) -> None:
        self.handler.status = 503
        with self.assertRaises(RuntimeError) as cm:
            llm.complete("o", "q", attempts=2)
        self.assertIsInstance(cm.exception, llm.BackendError)
        self.assertEqual(self.handler.chats, 2)

    def test_an_unknown_alias_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            llm.complete("nope", "q")

    def test_an_unhonoured_setting_raises_value_error_before_any_call(self) -> None:
        with mock.patch("subprocess.run") as cli:
            with self.assertRaisesRegex(ValueError, "temperature"):
                llm.complete("cli", "q", temperature=0.0)
            with self.assertRaisesRegex(ValueError, "token cap"):
                llm.complete("cli", "q", max_tokens=10)
        cli.assert_not_called()

    def test_resolve_records_the_spec_as_a_new_dict(self) -> None:
        first = llm.resolve("o")
        self.assertEqual(
            (first["backend"], first["model"], first["endpoint"]),
            ("ollama", "m", self.url),
        )
        first["model"] = "edited"
        self.assertEqual(llm.resolve("o")["model"], "m")

    def test_spec_is_typed_and_frozen_for_the_process(self) -> None:
        typed = llm.spec("o")
        assert isinstance(typed, llm_specs.OllamaSpec)
        self.assertEqual(typed.endpoints, (self.url,))
        self.assertIs(llm.spec("o"), typed)

    def test_identity_names_the_weights_and_no_endpoint(self) -> None:
        self.assertEqual(
            llm.identity("o"), {"backend": "ollama", "model": "m@0123456789ab"}
        )
        self.assertEqual(
            llm.identity("cli"), {"backend": "claude-cli", "model": "claude-x"}
        )

    def test_last_endpoint_is_empty_after_a_cli_call(self) -> None:
        llm.complete("o", "q")
        self.assertEqual(llm.last_endpoint(), self.url)
        with mock.patch.object(
            llm, "complete_claude_cli", lambda *a, **k: "cli answer"
        ):
            llm.complete("cli", "q")
        self.assertEqual(llm.last_endpoint(), "")

    def test_retries_counts_the_transport_retries(self) -> None:
        before = llm.retries()
        self.handler.status = 503
        with self.assertRaises(llm.BackendError):
            llm.complete("o", "q", attempts=3)
        self.assertEqual(llm.retries() - before, 2)

    def test_provenance_stamps_model_and_the_answering_endpoint(self) -> None:
        stamp = llm.provenance("o")
        self.assertEqual(stamp["model"], "m@0123456789ab")
        llm.complete("o", "q")
        self.assertEqual(stamp["endpoint"](), self.url)
        cli = llm.provenance("cli")
        self.assertEqual(cli["model"], "claude-x")
        self.assertEqual(cli["cli_input"], "harness")

    def test_usage_before_any_call_is_no_usage(self) -> None:
        result: list[object] = []
        thread = threading.Thread(
            target=lambda: result.extend([llm.last_usage(), llm.last_endpoint()])
        )
        thread.start()
        thread.join()
        self.assertEqual(result, [llm.NO_USAGE, ""])

    def test_complete_response_carries_everything_the_call_returned(self) -> None:
        response = llm.complete_response("o", "q", temperature=0)
        self.assertIsInstance(response, llm_backends.Response)
        self.assertEqual(response.text, llm.complete("o", "q", temperature=0))
        self.assertEqual(
            (response.thinking, response.finish_reason, response.endpoint),
            ("because", "stop", self.url),
        )
        usage = response.usage
        self.assertEqual((usage.prompt_tokens, usage.output_tokens), (7, 3))
        assert response.body is not None
        self.assertEqual(response.body["eval_count"], 3)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            response.text = "edited"  # type: ignore[misc]

    def test_a_response_without_trace_reason_or_reply_says_so(self) -> None:
        with mock.patch.object(
            llm, "complete_claude_cli", lambda *a, **k: "cli answer"
        ):
            response = llm.complete_response("cli", "q")
        self.assertEqual(
            (response.text, response.thinking, response.endpoint),
            ("cli answer", "", ""),
        )
        self.assertEqual((response.finish_reason, response.body), (None, None))

    def test_complete_response_fails_as_complete_does(self) -> None:
        self.handler.status = 404
        with self.assertRaisesRegex(llm.BackendError, "HTTP 404"):
            llm.complete_response("o", "q", attempts=3)
        self.assertEqual(self.handler.chats, 1)
        self.handler.status = 503
        with self.assertRaises(llm.BackendError):
            llm.complete_response("o", "q", attempts=2)
        self.assertEqual(self.handler.chats, 3)
        with self.assertRaises(KeyError):
            llm.complete_response("nope", "q")


class FindModelsToml(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lab = Path(tmp.name).resolve()
        (self.lab / "models.toml").write_text(toml("a", "m"))
        (self.lab / "exp").mkdir()
        self.enterContext(mock.patch("sys.argv", [""]))
        self.enterContext(contextlib.chdir(self.lab / "exp"))

    def test_it_finds_the_lab_s_file_above_the_working_directory(self) -> None:
        self.assertEqual(llm.find_models_toml(), self.lab / "models.toml")

    def test_without_one_it_raises_file_not_found(self) -> None:
        (self.lab / "models.toml").unlink()
        with self.assertRaises(FileNotFoundError):
            llm.find_models_toml()

    def test_the_former_name_is_gone(self) -> None:
        # no alias under the private name
        self.assertFalse(hasattr(llm, "_find_models_toml"))


class ModelsToml(unittest.TestCase):
    """The schema: each backend's full key set resolves, anything else is
    refused with the field named."""

    FULL = {
        "claude-cli": 'backend = "claude-cli"\nmodel = "c"\ninput = "prompt"\n',
        "ollama": (
            'backend = "ollama"\nmodel = "m"\nendpoints = ["local"]\nnum_ctx = 8192\n'
            'api_key_env = "K"\napi_key = "k"\n'
        ),
        "openai": (
            'backend = "openai"\nmodel = "m"\nendpoints = ["http://h:1"]\n'
            'api_key_env = "K"\napi_key = "k"\nreasoning = true\n'
        ),
    }

    def setUp(self) -> None:
        self.enterContext(mock.patch.object(llm, "_ollama_digest", lambda *a: "d"))
        self.enterContext(mock.patch.dict("os.environ", {"K": "key"}))

    def _spec(self, table: str) -> llm_specs.BackendSpec:
        serve(self, f'[endpoints]\nlocal = "http://h:1"\n[models.a]\n{table}')
        return llm.spec("a")

    def test_every_listed_key_is_accepted(self) -> None:
        for backend, table in self.FULL.items():
            with self.subTest(backend=backend):
                self.assertEqual(self._spec(table).backend, backend)

    def test_a_key_the_backend_does_not_read_is_refused(self) -> None:
        for backend, table in self.FULL.items():
            with self.subTest(backend=backend):
                with self.assertRaisesRegex(ValueError, "temperature"):
                    self._spec(table + "temperature = 0\n")

    def test_a_served_backend_without_endpoints_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "endpoints"):
            self._spec('backend = "ollama"\nmodel = "m"\n')

    def test_an_endpoint_name_the_file_lacks_raises_key_error(self) -> None:
        with self.assertRaisesRegex(KeyError, "elsewhere"):
            self._spec('backend = "ollama"\nmodel = "m"\nendpoints = ["elsewhere"]\n')

    def test_an_unknown_backend_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "backend"):
            self._spec('backend = "vllm"\nmodel = "m"\n')


class Runs(unittest.TestCase):
    """`runlog.run(data=…)` as a context manager, `Run.output`, and
    `batch.Store` inside a run."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def _jsonl(self, name: str, ids: list[str]) -> Path:
        path = self.area / name
        path.write_text("".join(json.dumps({"id": i}) + "\n" for i in ids))
        return path

    def test_a_clean_run_records_inputs_outputs_metrics_and_its_index_row(self) -> None:
        train, test = (
            self._jsonl("train.jsonl", ["a", "b"]),
            self._jsonl("test.jsonl", ["c"]),
        )
        out = self.area / "output" / "answers.jsonl"
        with runlog.run(
            "e", {"seed": 1}, self.area, data={"train": train, "test": test}
        ) as run:
            run.output(out, self.area / "never-written.txt")
            with batch.Store(out, prov={"run": run.run_id}) as store:
                for record in store.pending([{"id": "c"}, {"id": "d"}]):
                    store.append({**record, "answer": 1})
            run.metrics(n=2)
        config = json.loads((run.dir / "config.json").read_text())
        self.assertEqual(config["config"], {"seed": 1})
        self.assertEqual(config["data"]["train"]["rows"], 2)
        self.assertEqual(len(config["data"]["test"]["sha256"]), runs.RECORD_SHA_CHARS)
        outputs = json.loads((run.dir / "outputs.json").read_text())
        self.assertEqual(outputs[0]["lines"], 2)
        self.assertIsNotNone(outputs[0]["sha256"])
        self.assertIn("absent", outputs[1]["note"])
        self.assertEqual(json.loads((run.dir / "metrics.json").read_text())["n"], 2)
        self.assertTrue((run.dir / "completion.json").exists())
        self.assertIn(run.run_id, (self.area / "runs.tsv").read_text())

    def test_no_inputs_is_recorded_apart_from_data_left_out(self) -> None:
        """`data=runlog.NO_INPUTS` records the author's declaration; a run
        whose data= is left out records an empty table."""
        with runlog.run("e", {}, self.area, data=runlog.NO_INPUTS) as declared:
            declared.metrics(n=1)
        with runlog.run("e", {}, self.area) as left_out:
            left_out.metrics(n=1)
        record = json.loads((declared.dir / "config.json").read_text())["data"]
        self.assertEqual(record, {runs.NO_INPUTS_KEY: runs.NO_INPUTS_DECLARED})
        self.assertEqual(
            json.loads((left_out.dir / "config.json").read_text())["data"], {}
        )

    def test_store_resumes_by_id_and_holds_its_rows(self) -> None:
        out = self.area / "answers.jsonl"
        with batch.Store(out) as store:
            store.append({"id": "a"})
        with batch.Store(out) as store:
            self.assertEqual(
                [r["id"] for r in store.pending([{"id": "a"}, {"id": "b"}])], ["b"]
            )
            self.assertEqual(store.records(), [{"id": "a"}])

    def test_store_refuses_to_resume_rows_of_another_instrument(self) -> None:
        out = self.area / "answers.jsonl"
        with batch.Store(out, instrument={"prompt": "v1"}) as store:
            store.append({"id": "a"})
        with batch.Store(out, instrument={"prompt": "v2"}) as store:
            with self.assertRaises(batch.InstrumentError):
                list(store.pending([{"id": "b"}]))

    def test_split_leakage_is_refused_before_a_run_directory_exists(self) -> None:
        train, test = (
            self._jsonl("train.jsonl", ["a"]),
            self._jsonl("test.jsonl", ["a"]),
        )
        with self.assertRaisesRegex(RuntimeError, "leakage"):
            with runlog.run("e", {}, self.area, data={"train": train, "test": test}):
                self.fail("the body ran")
        self.assertFalse((self.area / "runs").exists())

    def test_write_dataset_writes_its_legend_first_and_refuses_drift(self) -> None:
        out = self.area / "prepared" / "items.jsonl"
        fields = {"id": "item id", "text": "the argument"}
        batch.write_dataset(
            out, [{"id": "a", "text": "t"}], about="items", fields=fields, producer="p"
        )
        lines = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(lines[0]["_meta"]["fields"], fields)
        self.assertEqual(lines[1:], [{"id": "a", "text": "t"}])
        with self.assertRaisesRegex(ValueError, "missing"):
            batch.write_dataset(
                out, [{"id": "b"}], about="items", fields=fields, producer="p"
            )
        self.assertEqual(len(out.read_text().splitlines()), 2, "nothing written")

    def test_metrics_refuses_a_value_json_cannot_hold(self) -> None:
        with runlog.run("e", {}, self.area) as run:
            with self.assertRaisesRegex(TypeError, "flag"):
                run.metrics(flag=object())
            run.metrics(n=1)
        self.assertEqual(json.loads((run.dir / "metrics.json").read_text())["n"], 1)

    def test_run_id_names_the_directory_and_draw_numbers_a_repeat(self) -> None:
        with runlog.run("e", {}, self.area) as first:
            pass
        with runlog.run("e", {}, self.area, repeat_of=first.run_id) as repeat:
            pass
        self.assertEqual(first.dir.name, first.run_id)
        self.assertIn(first.run_id, (self.area / "runs.tsv").read_text())
        self.assertEqual((first.draw, repeat.draw), (None, 2))

    def test_run_output_names_the_writer_and_a_wrong_one_refuses_the_start(
        self,
    ) -> None:
        out = self.area / "out.jsonl"
        with runlog.run("e", {}, self.area, data=runlog.NO_INPUTS) as writer:
            writer.output(out)
            out.write_text('{"id": 1}\n', encoding="utf-8")
        chosen = runlog.RunOutput(out, run=writer.run_id)
        with runlog.run("e", {}, self.area, data={"items": chosen}) as reader:
            pass
        recorded = json.loads((reader.dir / "config.json").read_text())["data"]
        self.assertEqual(recorded["items"]["origin_run"], writer.run_id)
        self.assertIs(recorded["items"]["origin_chosen"], True)
        before = sorted((self.area / "runs").iterdir())
        with self.assertRaises(SystemExit):
            with runlog.run(
                "e",
                {},
                self.area,
                data={"items": runlog.RunOutput(out, run=reader.run_id)},
            ):
                self.fail("the body ran")
        self.assertEqual(sorted((self.area / "runs").iterdir()), before)
        with self.assertRaisesRegex(ValueError, r"data\['items'\]"):
            nested = runlog.RunOutput(chosen, run=writer.run_id)  # type: ignore[arg-type]  # the wrong nesting under test
            runlog.run("e", {}, self.area, data={"items": nested})

    def test_an_exception_is_recorded_and_re_raised_without_an_index_row(self) -> None:
        context = runlog.run("e", {}, self.area)
        run = context.__enter__()
        with self.assertRaisesRegex(ZeroDivisionError, "boom"):
            with context:
                raise ZeroDivisionError("boom")
        self.assertIn("boom", json.dumps(runs.read_failure(run.dir)))
        self.assertFalse((run.dir / "completion.json").exists())
        self.assertFalse((self.area / "runs.tsv").exists())


class CachedCalls(unittest.TestCase):
    """`llm_cache.Cache`, `Cache.complete`, `Answer`, `Origin` and
    `store_stand_in`: runs in
    an area of a lab whose `models.toml` the cache finds, asking one
    stand-in server through the cache."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lab = Path(tmp.name).resolve()
        self.area = self.lab / "exp"
        self.area.mkdir()
        self.handler, self.url = ollama_fixture.start(self)
        self.other, other_url = ollama_fixture.start(self)
        text = (
            f'[models.o]\nbackend = "ollama"\nmodel = "m"\nendpoints = ["{self.url}"]\n'
            f'[models.o2]\nbackend = "ollama"\nmodel = "m"\n'
            f'endpoints = ["{other_url}"]\n'
            "[llm_cache]\nenabled = true\n"
        )
        serve(self, text)
        (self.lab / "models.toml").write_text(text, encoding="utf-8")
        self.root = self.lab / "cache" / "llm"
        self.stderr = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(self.stderr))

    def ask(
        self,
        prompt: str = "q",
        *,
        alias: str = "o",
        replay: bool = False,
        repeat_of: str | None = None,
    ) -> tuple[runlog.Run, llm_cache.Answer]:
        """One run asking ALIAS once through the cache at its default root."""
        answers: list[llm_cache.Answer] = []
        with runlog.run("e", {}, self.area, repeat_of=repeat_of) as run:
            cache = llm_cache.Cache(run, replay=replay)
            answers.append(cache.complete(alias, prompt, temperature=0))
        return run, answers[0]

    def record(self, run: runlog.Run) -> tuple[dict, list[dict]]:
        """The run's `llm-cache.json` and the lines of its `llm-calls.jsonl`."""
        opened = json.loads((run.dir / runs.LLM_CACHE_FILE).read_text())
        calls = (run.dir / runs.LLM_CALLS_FILE).read_text().splitlines()
        return opened, [json.loads(line) for line in calls]

    def test_normal_stores_an_answer_a_later_run_reads(self) -> None:
        first, asked = self.ask()
        second, hit = self.ask()
        self.assertEqual(self.handler.chats, 1)
        self.assertIsNone(asked.origin)
        assert hit.origin is not None
        self.assertIsInstance(hit.origin, llm_cache.Origin)
        self.assertEqual(hit.origin.run, first.run_id)
        self.assertIsInstance(hit.origin.written, str)
        self.assertEqual(hit.response, asked.response)
        opened, [line] = self.record(second)
        self.assertEqual(
            opened,
            {
                "cache_version": llm_cache.CACHE_VERSION,
                "mode": "normal",
                "root": str(self.root),
            },
        )
        self.assertEqual((line["alias"], line["hit"]), ("o", True))
        self.assertEqual(line["origin"]["run"], first.run_id)
        self.assertEqual((line["usage"]["prompt_tokens"], line["uncached"]), (7, None))
        self.assertEqual((self.root / ".gitignore").read_text(), "*\n")

    def test_the_key_is_the_model_and_the_call_not_alias_or_endpoint(self) -> None:
        self.ask(alias="o")
        _, hit = self.ask(alias="o2")
        self.assertIsNotNone(hit.origin)
        self.assertEqual(self.other.chats, 0)
        _, asked = self.ask("another prompt")
        self.assertIsNone(asked.origin)
        self.assertEqual(self.handler.chats, 2)

    def test_replay_asks_no_model(self) -> None:
        self.ask()
        replayed, hit = self.ask(replay=True)
        self.assertIsNotNone(hit.origin)
        self.assertEqual(self.record(replayed)[0]["mode"], "replay")
        with self.assertRaises(LookupError) as cm:
            self.ask("a prompt nobody asked", replay=True)
        self.assertIsInstance(cm.exception, llm_cache.CacheMiss)
        self.assertEqual(self.handler.chats, 1)

    def test_repeat_asks_anew_and_neither_reads_nor_stores(self) -> None:
        first, _ = self.ask()
        self.handler.answer = "another answer"
        repeat, asked = self.ask(repeat_of=first.run_id)
        self.assertEqual((asked.response.text, asked.origin), ("another answer", None))
        self.assertEqual(self.record(repeat)[0]["mode"], "repeat")
        _, hit = self.ask()
        self.assertEqual(hit.response.text, "the answer")
        self.assertEqual(self.handler.chats, 2)
        with runlog.run("e", {}, self.area, repeat_of=first.run_id) as run:
            with self.assertRaisesRegex(ValueError, "repeats another run"):
                llm_cache.Cache(run, replay=True)

    def test_without_models_toml_above_the_run_the_root_must_be_given(self) -> None:
        (self.lab / "models.toml").unlink()
        with runlog.run("e", {}, self.area) as run:
            with self.assertRaises(FileNotFoundError):
                llm_cache.Cache(run)
            given = llm_cache.Cache(run, root=self.lab / "elsewhere")
            self.assertIsNone(given.complete("o", "q").origin)
        self.assertTrue((self.lab / "elsewhere" / ".gitignore").exists())

    def test_ollama_without_a_weights_digest_is_not_cached(self) -> None:
        self.handler.digest = None
        llm._FROZEN.clear()
        run, _ = self.ask()
        self.assertIn("not cached", self.stderr.getvalue())
        self.assertIn("unavailable", self.record(run)[1][0]["uncached"])
        self.assertIsNone(self.ask()[1].origin)
        with self.assertRaises(llm_cache.CacheMiss):
            self.ask(replay=True)
        self.assertEqual(self.handler.chats, 2)

    def test_a_damaged_entry_raises_cache_corruption_error(self) -> None:
        self.ask()
        [entry] = self.root.rglob("??/*.json")
        entry.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            self.ask()
        self.assertIsInstance(cm.exception, llm_cache.CacheCorruptionError)
        self.assertEqual(self.handler.chats, 1)

    def test_a_stand_in_answers_a_replay_of_exactly_its_call(self) -> None:
        """`llm_cache.store_stand_in` and `Origin.stand_in`: the stand-in is
        stored under the key the real call gets, marked, the directory kept
        out of git; a replay of another prompt misses, never hits."""
        path = llm_cache.store_stand_in(self.root, "o", "q", "fixed", temperature=0)
        self.assertTrue(path.is_file())
        self.assertEqual((self.root / ".gitignore").read_text(), "*\n")
        replayed, hit = self.ask("q", replay=True)
        self.assertEqual(hit.response.text, "fixed")
        assert hit.origin is not None
        self.assertEqual(hit.origin, llm_cache.Origin(None, hit.origin.written, True))
        self.assertTrue(self.record(replayed)[1][0]["origin"]["stand_in"])
        with self.assertRaises(llm_cache.CacheMiss):
            self.ask("q ", replay=True)
        self.assertEqual(self.handler.chats, 0)

    def test_complete_fails_as_llm_complete_does(self) -> None:
        self.handler.status = 404
        with self.assertRaisesRegex(llm.BackendError, "HTTP 404"):
            self.ask()
        with self.assertRaises(KeyError):
            self.ask(alias="nope")


class AnsweringRun(unittest.TestCase):
    """`recheck.answering_run_dir`: the adopted run stays chosen though a newer
    run of the protocol completed; without the adoption the newer one
    answers — the choice every gate makes, no rule of its own."""

    OLDER = "2026-11-20T10-00-00_aaaa"
    NEWER = "2026-11-20T11-00-00_bbbb"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name)
        self.protocol = self.area / "PROTOCOL-x.md"
        for run_id in (self.OLDER, self.NEWER):
            d = runs.run_path(self.area, run_id)
            d.mkdir(parents=True)
            cfg = run_record(protocol={"id": PID, "path": self.protocol.name})
            (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            # both report an intent key: the choice is the main rule, not the
            # fallback to the newest run when none does
            (d / "metrics.json").write_text(
                json.dumps({"criterion_1_pass": True}), encoding="utf-8"
            )
            (d / "completion.json").write_text(
                json.dumps(completion_record()), encoding="utf-8"
            )

    def chosen(self, adopted: str | None) -> str:
        self.protocol.write_text(head(result=adopted), encoding="utf-8")
        return recheck.answering_run_dir(self.area, self.protocol).name

    def test_a_newer_run_does_not_replace_the_adopted_one(self) -> None:
        self.assertEqual(self.chosen(self.OLDER), self.OLDER)

    def test_the_twin_without_an_adoption_the_newest_answers(self) -> None:
        self.assertEqual(self.chosen(None), self.NEWER)

    def test_no_run_that_answers_is_refused_with_the_reason(self) -> None:
        for run_id in (self.OLDER, self.NEWER):
            (runs.run_path(self.area, run_id) / "completion.json").unlink()
        with self.assertRaises(SystemExit) as cm:
            self.chosen(None)
        told = str(cm.exception)
        self.assertIn("recheck:", told)
        self.assertIn("unfinalized", told)


class HoldsOutputs(unittest.TestCase):
    """`recheck.holds_outputs`: the rows of every registered file reach
    RECOMPUTE by their key and the recorded metrics hold; a file whose
    bytes are not the ones the run recorded ends the check (the cases in
    full: tests/test_recheck.py)."""

    ROWS = [{"case": "a", "n": 4}, {"case": "b", "n": 3}]
    LABELS = [{"case": "a", "label": "x"}, {"case": "b", "label": "y"}]

    def setUp(self) -> None:
        recheck_without_git(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name)
        self.outs = {
            "counted": self.area / "output" / "counted.jsonl",
            "labels": self.area / "output" / "labels.jsonl",
        }
        self.outs["counted"].parent.mkdir()
        for key, rows in (("counted", self.ROWS), ("labels", self.LABELS)):
            self.outs[key].write_text(
                "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
            )
        run = runs.run_path(self.area, "2026-10-05T19-00-00_ab12")
        run.mkdir(parents=True)
        cfg = run_record(
            {
                "schema_version": runs.RUN_SCHEMA,
                "run_kind": "measurement",
                "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
            }
        )
        (run / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (run / "completion.json").write_text(
            json.dumps(completion_record()), encoding="utf-8"
        )
        (run / "metrics.json").write_text(
            json.dumps({"mean_n": 3.5, "n_labels": 2, "duration_s": 0.1}),
            encoding="utf-8",
        )
        (run / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": str(p),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16],
                    }
                    for p in self.outs.values()
                ]
            ),
            encoding="utf-8",
        )
        self.note = self.area / "PROTOCOL-x.md"
        self.note.write_text(
            "- **Conclusion:** 3.5 over 2 labelled cases, run 2026-10-05T19-00-00_ab12\n\n"
            + head(),
            encoding="utf-8",
        )

    @staticmethod
    def recompute(rows: Mapping[str, list[dict]]) -> dict:
        counted = rows["counted"]
        return {
            "mean_n": sum(r["n"] for r in counted) / len(counted),
            "n_labels": len(rows["labels"]),
        }

    def test_the_rows_of_each_file_reach_recompute_and_hold(self) -> None:
        verdict = recheck.holds_outputs(self.area, self.outs, self.recompute, self.note)
        self.assertEqual(verdict.outs, self.outs)

    def test_the_twin_a_file_changed_since_the_run_ends_the_check(self) -> None:
        self.outs["labels"].write_text(
            json.dumps({"case": "a", "label": "x"}) + "\n", encoding="utf-8"
        )
        with self.assertRaises(SystemExit):
            recheck.holds_outputs(self.area, self.outs, self.recompute, self.note)


class RowsOf(unittest.TestCase):
    """`recheck.rows_of`: the data rows of a row file, in order — every
    non-empty line an object, `_meta` lines left out; a line that is not
    JSON or no object raises naming file and line."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "rows.jsonl"

    def test_the_rows_come_without_the_header(self) -> None:
        rows = [{"id": "a", "n": 4}, {"id": "b", "n": 3}]
        batch.write_dataset(
            self.out,
            rows,
            about="one item per row",
            fields={"id": "unique per row", "n": "a count"},
            producer="t",
        )
        self.assertEqual(recheck.rows_of(self.out), rows)

    def test_blank_lines_and_a_meta_line_anywhere_are_left_out(self) -> None:
        self.out.write_text(
            '{"id": "a"}\n\n{"_meta": {"about": "x"}}\n{"id": "b"}\n',
            encoding="utf-8",
        )
        self.assertEqual(recheck.rows_of(self.out), [{"id": "a"}, {"id": "b"}])

    def test_a_line_that_is_no_row_raises_naming_file_and_line(self) -> None:
        where = re.escape(f"{self.out}:2:")
        for second in ("[1, 2]", '{"id": "b", "n":'):  # no object; torn
            with self.subTest(second=second):
                self.out.write_text(f'{{"id": "a"}}\n{second}', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, where):
                    recheck.rows_of(self.out)

    def test_bytes_that_are_not_utf8_raise_valueerror(self) -> None:
        self.out.write_bytes(b'{"id": "\xff"}\n')
        with self.assertRaises(ValueError):
            recheck.rows_of(self.out)

    def test_a_missing_file_raises_oserror(self) -> None:
        with self.assertRaises(OSError):
            recheck.rows_of(self.out)


class RegisteredTemplates(unittest.TestCase):
    """`prompt_check.require_registered_templates`: a template registered
    verbatim passes; one that differs, and one no block is named after,
    refuse the start (the cases in full: tests/test_prompt_templates.py)."""

    def test_verbatim_passes_and_drift_or_no_block_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            protocol = Path(d) / "PROTOCOL-x.md"
            protocol.write_text(
                "- **Prompt:** x\n\n  `judge` — it\n\n  ```text\n  Q: $q\n  ```\n",
                encoding="utf-8",
            )
            prompt_check.require_registered_templates(protocol, {"judge": "Q: $q\n"})
            for templates in ({"judge": "Q: $x\n"}, {"other": "Q: $q\n"}):
                with self.subTest(templates=templates):
                    with self.assertRaises(SystemExit):
                        prompt_check.require_registered_templates(protocol, templates)
            with self.assertRaises(ValueError):
                prompt_check.require_registered_templates(protocol, {})


if __name__ == "__main__":
    unittest.main()
