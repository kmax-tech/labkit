"""repeat_of: the same measurement drawn again, never the answer.

`derived_from` re-reads a parent's rows without a model call; `repeat_of`
asks the model again with the same instrument on the same items, so the
spread of the number becomes visible (TODO item 4: every audit of the cloud
judge probe named "one unseeded draw", 2026-10-14). A repeat is supporting
evidence: the primary run keeps answering the protocol in every default
choice, and a run that differs in protocol, block, config or inputs is no
repeat at all.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import DEFAULT_BLOCK, PID, head, scope_file

from labkit import recheck, runlog, runs


class Repeats(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        (self.area / "PROTOCOL-x.md").write_text(
            head(promises=DEFAULT_BLOCK) + "\n- **Question / hypothesis:** q\n",
            encoding="utf-8",
        )
        self.data = self.area / "items.jsonl"
        self.data.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")

    def _run(
        self,
        config: dict | None = None,
        repeat_of: str | None = None,
        derived_from: str | None = None,
    ) -> str:
        cfg = config or {"prompt_sha": "aaaaaaaaaaaa", "model_alias": "x"}
        r = runlog.run(
            "m",
            config=cfg,
            base_dir=self.area,
            data={"items": self.data},
            repeat_of=repeat_of,
            derived_from=derived_from,
        )
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            run.metrics(c1_pass=True, a1_pass=True, a2_pass=True)
        return run.run_id

    def _cfg(self, run_id: str) -> dict:
        return json.loads((self.area / "runs" / run_id / "config.json").read_text())

    def test_a_repeat_records_its_parent_and_counts_its_draw(self):
        first = self._run()
        second = self._run(repeat_of=first)
        third = self._run(repeat_of=first)
        self.assertEqual(
            [
                (self._cfg(r)["repeat_of"], self._cfg(r)["draw"])
                for r in (first, second, third)
            ],
            [(None, None), (first, 2), (first, 3)],
        )
        self.assertEqual(
            [p.name for p in runs.repeats_of(self.area, first)], [second, third]
        )

    def test_the_primary_keeps_answering_and_rechecking(self):
        first = self._run()
        self._run(repeat_of=first)
        choice = runs.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir.name if choice.run_dir else None, first)
        self.assertIn("a repeat of", " ".join(e.why for e in choice.exclusions))
        self.assertEqual(recheck.run_dir(self.area).name, first)
        self.assertEqual(len(runs.completed_runs(self.area, with_repeats=True)), 2)
        self.assertEqual(len(runs.completed_runs(self.area, with_repeats=False)), 1)

    def test_a_run_that_measures_something_else_is_no_repeat(self):
        first = self._run()
        with self.assertRaises(SystemExit) as cm:
            self._run(
                {"prompt_sha": "bbbbbbbbbbbb", "model_alias": "x"}, repeat_of=first
            )
        self.assertIn("config prompt_sha", str(cm.exception))
        self.data.write_text('{"id": "a"}\n', encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self._run(repeat_of=first)
        self.assertIn("the inputs (data=) differ", str(cm.exception))
        self.assertEqual(
            len(runs.completed_runs(self.area, with_repeats=True)), 1
        )  # nothing made

    def test_no_repeat_of_a_repeat_a_missing_run_or_with_derived_from(self):
        first = self._run()
        second = self._run(repeat_of=first)
        for kw, needle in (
            ((second, None), "is itself a repeat"),
            (("2026-01-01T00-00-00_0000", None), "names no completed run"),
            ((first, first), "exclude each other"),
        ):
            with self.subTest(kw=kw), self.assertRaises(SystemExit) as cm:
                self._run(repeat_of=kw[0], derived_from=kw[1])
            self.assertIn(needle, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
