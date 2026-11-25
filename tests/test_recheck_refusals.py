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
from protocol_fixture import PID, head, recheck_without_git, run_record


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
            json.dumps({"schema_version": 5, "finished": "x"})
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

    def test_an_output_the_run_did_not_register_is_not_looked_for_in_history(self):
        """The same refusal where the recorded bytes of an output are asked
        for (`output_as_recorded`), before those bytes are looked for."""
        run = self._run()

        def ask() -> None:
            with recheck.output_as_recorded(run, self.area / "rows.jsonl", self.area):
                self.fail("an output the run did not register was handed out")

        self.assertEqual(
            self._refused(ask),
            "recheck: run r1 did not register rows.jsonl as an output",
        )

    def _run(self, config: str | None = None, **fields: object) -> Path:
        """Run r1 of the area with a complete record, FIELDS replaced, or
        with CONFIG as the text of its config.json."""
        run = runs.run_path(self.area, "r1")
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(run_record(fields)) if config is None else config
        )
        return run

    def test_a_record_that_does_not_read_ends_every_reading_of_it(self):
        run = self._run(config="{not json")
        for name, call in (
            (
                "the protocol as the run saw it",
                lambda: recheck.protocol_as_run_saw(run, self.area),
            ),
            ("the script the run ran", lambda: recheck.script_module(self.area, run)),
        ):
            with self.subTest(name):
                said = self._refused(call)
                self.assertTrue(said.startswith("recheck: "), said)
                self.assertIn("config.json: unreadable run metadata", said)

    def test_an_input_record_that_does_not_read_ends_every_reading_of_it(self):
        # an input entry without its rows field: `runs.data_entries` refuses it
        run = self._run(data={"cases": {"path": ""}})
        for name, call in (
            ("does it read another run", lambda: recheck.reads_another_run(run)),
            ("its inputs", lambda: recheck.inputs_pinned(run, self.area)),
        ):
            with self.subTest(name):
                said = self._refused(call)
                self.assertTrue(said.startswith("recheck: run r1: "), said)
                self.assertIn("cases", said)

    def test_the_twin_a_record_that_reads_is_read(self):
        # for the protocol read-back and the origin question; the script and
        # the inputs of a readable record are read in tests/test_recheck_inputs.py
        run = self._run()
        self.assertIsNone(recheck.protocol_as_run_saw(run, self.area))  # unbound
        self.assertFalse(recheck.reads_another_run(run))

    def test_a_script_python_cannot_import_is_refused_by_name(self):
        """A file of the recorded name that is no Python module."""
        (self.area / "measure.txt").write_text("not a module\n")
        run = self._run(script="measure.txt", command=["measure.txt"])
        said = self._refused(lambda: recheck.script_module(self.area, run))
        self.assertTrue(said.startswith("recheck: run r1: "), said)
        self.assertTrue(said.endswith("measure.txt does not import"), said)

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
        recheck_without_git(self)  # the text the run saw: the one written here
        said = self._refused(lambda: recheck.kept_keys(run, self.area))
        self.assertTrue(said.startswith("recheck: run r1: "), said)
        self.assertIn("[kept]", said)

    def test_a_protocol_that_cannot_be_read_back_is_named_never_read_as_now(self):
        """The run recorded no commit: what it was measured under cannot be
        read back, and the `[kept]` of the protocol as it reads now is not
        taken in its place. In a repository: tests/test_recheck_own_text.py."""
        compute = head(
            repeat_cost="low", kind="compute", promises=None, kept=("n", "1")
        )
        (self.area / "PROTOCOL-x.md").write_text(compute)
        run = self._bound_run()
        said = self._refused(lambda: recheck.kept_keys(run, self.area))
        self.assertTrue(
            said.startswith(
                "recheck: the protocol run r1 was measured under cannot be read back"
            ),
            said,
        )
        self.assertIn("not taken from the protocol as it reads now", said)

    def test_the_twin_a_kept_table_that_reads_names_its_key(self):
        compute = head(
            repeat_cost="low", kind="compute", promises=None, kept=("n", "1")
        )
        (self.area / "PROTOCOL-x.md").write_text(compute)
        recheck_without_git(self)
        self.assertEqual(
            recheck.kept_keys(self._bound_run(), self.area), frozenset({"n"})
        )


if __name__ == "__main__":
    unittest.main()
