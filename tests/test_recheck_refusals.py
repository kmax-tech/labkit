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
        self.assertTrue(said.startswith("recheck: no [protocol] table"), said)

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
        self.assertIn("config.json: unreadable run metadata", said)

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

    def _bound_run(self) -> Path:
        run = runs.run_path(self.area, "r1")
        run.mkdir(parents=True)
        cfg = run_record(protocol={"id": PID, "path": "PROTOCOL-x.md"})
        (run / "config.json").write_text(json.dumps(cfg))
        return run

    def test_a_kept_table_that_does_not_read(self):
        compute = head(
            repeat_cost="low", kind="compute", promises=None, kept=("n", "1")
        )
        (self.area / "PROTOCOL-x.md").write_text(
            compute.replace('key = "n"', "key = 3", 1)
        )
        run = self._bound_run()
        said = self._refused(lambda: recheck.kept_keys(run, self.area))
        self.assertTrue(said.startswith("recheck: run r1: "), said)
        self.assertIn("[kept]", said)

    def test_no_protocol_carries_the_runs_id(self):
        run = self._bound_run()
        said = self._refused(lambda: recheck.kept_keys(run, self.area))
        self.assertTrue(said.startswith("recheck: run r1: "), said)

    def test_the_twin_a_kept_table_that_reads_names_its_key(self):
        compute = head(
            repeat_cost="low", kind="compute", promises=None, kept=("n", "1")
        )
        (self.area / "PROTOCOL-x.md").write_text(compute)
        self.assertEqual(
            recheck.kept_keys(self._bound_run(), self.area), frozenset({"n"})
        )


if __name__ == "__main__":
    unittest.main()
