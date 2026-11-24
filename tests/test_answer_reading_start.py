"""A derived run that declares its answer reading (`runlog.run(...,
derived_from=ID, answer_reading=MODULE)`): the start writes the
declaration beside the record and refuses a declaration that cannot be
held; while the run is open every model call through `llm` is refused, in
every thread, and after it calls go through again. A derived run without
the declaration starts as before.

    .venv/bin/python -m pytest tests/test_answer_reading_start.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from unittest import mock

from llm_fixture import typed
from protocol_fixture import DEFAULT_BLOCK, head, scope_file
from repo_fixture import git

from labkit.formats.answer_reading import ANSWER_READING_FILE, read_answer_reading
from labkit.run import llm, runlog

SCRIPT = "from lib import reading\n\n\ndef evaluate_rows(rows):\n    return {}\n"
SPECS = {"local": {"backend": "ollama", "model": "m", "endpoint": "http://h:1"}}


class Sent(Exception):
    """The fake backend was reached: the call would have been sent."""


class AnswerReadingStart(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-q")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.script = scope_file(self.area)
        self.script.write_text(SCRIPT, encoding="utf-8")
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "__init__.py").write_text("", encoding="utf-8")
        self.reading = self.repo / "lib" / "reading.py"
        self.reading.write_text(
            "def letter(a):\n    return a.strip()\n", encoding="utf-8"
        )
        (self.repo / "lib" / "other.py").write_text("X = 1\n", encoding="utf-8")
        (self.area / "PROTOCOL-x.md").write_text(
            head(promises=DEFAULT_BLOCK) + "\n- **Question / hypothesis:** q\n",
            encoding="utf-8",
        )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "the area")
        argv = mock.patch.object(sys, "argv", [str(self.script)])
        argv.start()
        self.addCleanup(argv.stop)
        self.parent = self._run()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _open(self, **kw: object) -> runlog.run:
        return runlog.run("m", config={"k": 1}, base_dir=self.area, **kw)  # type: ignore[arg-type]

    def _run(self, **kw: object) -> str:
        with contextlib.redirect_stdout(io.StringIO()), self._open(**kw) as run:
            run.metrics(n=1)
        return run.run_id

    def _runs(self) -> set[str]:
        return {p.name for p in (self.area / "runs").iterdir()}

    def test_the_declaration_is_written_beside_the_record(self) -> None:
        derived = self._run(derived_from=self.parent, answer_reading="lib/reading.py")
        run_dir = self.area / "runs" / derived
        reading = read_answer_reading(run_dir)
        assert reading is not None
        self.assertEqual(reading.module, "lib/reading.py")
        self.assertEqual(reading.labkit, version("labkit"))
        # an absolute path is recorded under the repository root as well
        again = self._run(derived_from=self.parent, answer_reading=self.reading)
        reading = read_answer_reading(self.area / "runs" / again)
        assert reading is not None
        self.assertEqual(reading.module, "lib/reading.py")

    def test_a_derived_run_without_it_starts_as_before(self) -> None:
        # the twin: no declaration, no file, no refusal of calls
        derived = self._run(derived_from=self.parent)
        self.assertFalse((self.area / "runs" / derived / ANSWER_READING_FILE).exists())
        spec = mock.patch.object(llm, "spec", typed(lambda alias: SPECS[alias]))
        send = mock.patch.object(llm, "_complete_once", side_effect=Sent)
        with spec, send, contextlib.redirect_stdout(io.StringIO()):
            with self._open(derived_from=self.parent) as run:
                with self.assertRaises(Sent):
                    llm.complete("local", "p", attempts=1)
                run.metrics(n=1)

    def test_every_call_is_refused_while_the_run_is_open_in_every_thread(self) -> None:
        spec = mock.patch.object(llm, "spec", typed(lambda alias: SPECS[alias]))
        send = mock.patch.object(llm, "_complete_once", side_effect=Sent)
        with spec, send as sent, contextlib.redirect_stdout(io.StringIO()):
            with self._open(
                derived_from=self.parent, answer_reading="lib/reading.py"
            ) as run:
                with self.assertRaises(llm.CallRefused) as cm:
                    llm.complete("local", "p")
                self.assertIn(f"run {run.run_id} is open", str(cm.exception))
                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures = [
                        pool.submit(llm.complete, "local", "p") for _ in range(6)
                    ]
                for f in futures:
                    self.assertIsInstance(f.exception(), llm.CallRefused)
                run.metrics(n=1)
            sent.assert_not_called()
            with self.assertRaises(Sent):  # released with the run
                llm.complete("local", "p", attempts=1)

    def test_the_refusal_ends_with_a_run_that_broke_off(self) -> None:
        spec = mock.patch.object(llm, "spec", typed(lambda alias: SPECS[alias]))
        send = mock.patch.object(llm, "_complete_once", side_effect=Sent)
        with spec, send, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyError):
                with self._open(
                    derived_from=self.parent, answer_reading="lib/reading.py"
                ):
                    raise KeyError("broke off")
            with self.assertRaises(Sent):
                llm.complete("local", "p", attempts=1)

    def test_a_declaration_that_cannot_be_held_is_refused_before_the_run(self) -> None:
        outside = Path(self._tmp.name).parent / "reading-outside.py"
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        outside.write_text("X = 1\n", encoding="utf-8")
        cases = {
            "it goes with derived_from": {"answer_reading": "lib/reading.py"},
            "no such file": {
                "derived_from": self.parent,
                "answer_reading": "lib/gone.py",
            },
            "lies outside the repository": {
                "derived_from": self.parent,
                "answer_reading": outside,
            },
            "does not import it": {
                "derived_from": self.parent,
                "answer_reading": "lib/other.py",
            },
        }
        for needle, kw in cases.items():
            with self.subTest(needle=needle):
                before = self._runs()
                with self.assertRaises(SystemExit) as cm:
                    self._open(**kw)
                self.assertIn(needle, str(cm.exception))
                self.assertEqual(self._runs(), before)  # no run directory left

    def test_a_declaration_that_does_not_read_is_named(self) -> None:
        derived = self._run(derived_from=self.parent, answer_reading="lib/reading.py")
        path = self.area / "runs" / derived / ANSWER_READING_FILE
        for text in ("{", json.dumps({"module": "/abs.py", "labkit": "1"})):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(Exception) as cm:
                    read_answer_reading(path.parent)
                self.assertIn(ANSWER_READING_FILE, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
