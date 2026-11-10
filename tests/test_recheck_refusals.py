"""recheck's refusals no other test names: a head that does not read, a
named run whose record does not read, an output the run did not register,
a note that is not there. Each ends the recomputation with its sentence —
a refusal, exit 1, never a number held to the wrong run."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks import recheck
from labkit.formats import runs
from protocol_fixture import PID, head, run_record


class RecheckRefuses(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _refused(self, call) -> str:
        with self.assertRaises(SystemExit) as cm:
            call()
        return str(cm.exception)

    def test_a_head_that_does_not_read(self):
        said = self._refused(lambda: recheck.chosen_run(self.area, "# no head\n"))
        self.assertTrue(said.startswith("recheck: "), said)

    def test_a_named_run_whose_record_does_not_read(self):
        run = runs.run_path(self.area, "r1")
        run.mkdir(parents=True)
        (run / "completion.json").write_text(
            json.dumps({"schema_version": 4, "finished": "x"})
        )
        (run / "config.json").write_text("{not json")
        said = self._refused(
            lambda: recheck.chosen_run(self.area, head(repeat_cost="low"), run_id="r1")
        )
        self.assertTrue(said.startswith("recheck: "), said)

    def test_an_output_the_run_did_not_register(self):
        run = runs.run_path(self.area, "r1")
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(run_record(protocol={"id": PID, "path": "P.md"}))
        )
        said = self._refused(lambda: recheck.pin(run, self.area / "rows.jsonl"))
        self.assertEqual(
            said, "recheck: run r1 did not register rows.jsonl as an output"
        )

    def test_a_note_that_is_not_there(self):
        note = self.area / "NOTE.md"
        said = self._refused(lambda: recheck.cited(note, ["0.5"], "r1"))
        self.assertEqual(said, f"recheck: {note}: no such note")

    def test_the_twin_a_note_with_the_number_and_the_run_passes(self):
        note = self.area / "NOTE.md"
        note.write_text("accuracy 0.5 from run r1\n")
        recheck.cited(note, ["0.5"], "r1")


if __name__ == "__main__":
    unittest.main()
