"""Stand-ins through real runs: fixed answers stored with
`llm_cache.store_stand_in`, read by a runlog run through the replay cache
(no model asked), then a run derived from it and a later replay. finalize's
model station (`run_record_check.model_provenance_findings`) and the result
label (`result_render.stand_in_label`) read the same call logs: the derived
run, which logs no call itself, is labelled and warned about through its
parent, and the warning says the uses are the parent's, not its own calls.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import pytest

import ollama_fixture
from models_fixture import serve

from labkit.checks import result_render, run_record_check
from labkit.formats.gate import WARNING
from labkit.run import llm_cache, runlog

pytestmark = pytest.mark.slow

PROMPTS = ("first prompt", "second prompt")


class StandInsThroughRealRuns(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lab = Path(tmp.name).resolve()
        self.area = self.lab / "exp"
        self.area.mkdir()
        self.handler, url = ollama_fixture.start(self)
        text = (
            f'[models.o]\nbackend = "ollama"\nmodel = "m"\nendpoints = ["{url}"]\n'
            "[llm_cache]\nenabled = true\n"
        )
        serve(self, text)
        (self.lab / "models.toml").write_text(text, encoding="utf-8")
        root = self.lab / "cache" / "llm"
        for prompt in PROMPTS:
            llm_cache.store_stand_in(root, "o", prompt, "fixed", temperature=0)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def replay(self) -> Path:
        """A run that names alias `o` and asks both prompts in replay mode."""
        with runlog.run("e", {"model": "o"}, self.area) as run:
            cache = llm_cache.Cache(run, replay=True)
            for prompt in PROMPTS:
                cache.complete("o", prompt, temperature=0)
        return run.dir

    LABEL = "fixed stand-in answers: 2 logged uses of alias o; not a measurement of o"

    def test_a_derived_run_and_a_replay_carry_the_stand_ins(self) -> None:
        parent = self.replay()
        with runlog.run("e", {}, self.area, derived_from=parent.name) as run:
            pass  # re-reads the parent's rows; logs no call of its own
        derived = run.dir
        later = self.replay()
        self.assertEqual(self.handler.chats, 0, "no model was asked")

        (own,) = run_record_check.model_provenance_findings(self.area, parent)
        (through,) = run_record_check.model_provenance_findings(self.area, derived)
        (again,) = run_record_check.model_provenance_findings(self.area, later)
        self.assertEqual({own.grade, through.grade, again.grade}, {WARNING})
        self.assertIn(
            f"{parent.name} read stand-in answers (2 logged uses of alias `o`):",
            own.text,
        )
        self.assertIn(
            f"{derived.name} read no stand-in itself; the runs it rests on "
            f"(derived_from, continued rows, input origins) logged stand-in "
            f"answers (2 logged uses of alias `o`) — uses those runs logged, "
            f"not calls of {derived.name}:",
            through.text,
        )
        self.assertIn(
            f"{later.name} read stand-in answers (2 logged uses of alias `o`):",
            again.text,
        )
        for run_dir in (parent, derived, later):
            self.assertEqual(result_render.stand_in_label(run_dir), self.LABEL)


if __name__ == "__main__":
    unittest.main()
