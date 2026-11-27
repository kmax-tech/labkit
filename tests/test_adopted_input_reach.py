"""`scope_sha.areas_touched` over the inputs an adopted run recorded: a data
file the number was measured on reopens that number when it changes,
wherever it lies — outside the area and outside every promise's scope too.

    .venv/bin/python -m pytest tests/test_adopted_input_reach.py
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.formats.scope_sha import adopted_inputs, areas_touched
from labkit.run import runlog
from protocol_fixture import head


class AdoptedInputs(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        # read by the run, outside the area and declared in no scope
        self.cases = self.root / "data" / "raw" / "cases.jsonl"
        self.docs = self.root / "data" / "raw" / "inputs"
        self.docs.mkdir(parents=True)
        self.cases.write_text('{"id": 1}\n', encoding="utf-8")
        (self.docs / "a.txt").write_text("a\n", encoding="utf-8")
        self.area = self.root / "experiments" / "01-a"
        self.area.mkdir(parents=True)
        with runlog.run(
            "m", {}, self.area, data={"cases": self.cases, "docs": self.docs}
        ) as r:
            r.metrics(n=1)
        self.run_id = r.run_id
        self.protocol = self.area / "PROTOCOL-a.md"

    def adopt(self, run_id: str | None) -> None:
        """The protocol of the area, adopting RUN_ID (None: nothing adopted)."""
        self.protocol.write_text(head(result=run_id), encoding="utf-8")

    def test_a_recorded_input_of_the_adopted_run_touches_its_area(self) -> None:
        self.adopt(self.run_id)
        self.assertEqual(
            adopted_inputs(self.area, [self.protocol]), [self.cases, self.docs]
        )
        self.assertEqual(
            areas_touched([self.cases], self.root, staged=False), [self.area]
        )
        # a file under a recorded directory, changed, added or deleted alike
        added = self.docs / "b.txt"
        self.assertEqual(areas_touched([added], self.root, staged=False), [self.area])

    def test_the_twin_nothing_adopted_touches_nothing(self) -> None:
        """A protocol that adopted no run holds no number to reopen: its
        run's inputs reach no area (the chain is not owed there)."""
        self.adopt(None)
        self.assertEqual(adopted_inputs(self.area, [self.protocol]), [])
        self.assertEqual(areas_touched([self.cases], self.root, staged=False), [])

    def test_a_file_no_adopted_run_read_touches_nothing(self) -> None:
        self.adopt(self.run_id)
        stray = self.root / "data" / "raw" / "other.jsonl"
        stray.write_text("{}\n", encoding="utf-8")
        self.assertEqual(areas_touched([stray], self.root, staged=False), [])

    def test_a_result_table_that_does_not_read_touches_its_area(self) -> None:
        """Which run the protocol adopted cannot be told, so neither can
        whether it read the path."""
        self.adopt(self.run_id)
        text = self.protocol.read_text(encoding="utf-8")
        self.protocol.write_text(
            text.replace(f'run = "{self.run_id}"', f'run = "{self.run_id}"\nstray = 1'),
            encoding="utf-8",
        )
        stray = self.root / "data" / "raw" / "other.jsonl"
        self.assertEqual(areas_touched([stray], self.root, staged=False), [self.area])

    def test_a_record_that_does_not_read_touches_its_area(self) -> None:
        """Whether the adopted run read the file cannot be told, so the area
        counts as touched — the gate is the safer answer."""
        self.adopt(self.run_id)
        config = self.area / "runs" / self.run_id / "config.json"
        config.write_text("{", encoding="utf-8")
        stray = self.root / "data" / "raw" / "other.jsonl"
        self.assertEqual(areas_touched([stray], self.root, staged=False), [self.area])


if __name__ == "__main__":
    unittest.main()
