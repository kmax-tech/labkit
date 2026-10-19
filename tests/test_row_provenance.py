"""A resumed output file names the run it continues, and finalize holds every
row to the run — rows of a run this run neither is, continues nor derives
from are a file of two measurements (2026-10-09).

    .venv/bin/python -m pytest tests/test_row_provenance.py
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from labkit.run import batch, runlog
from labkit import finalize
from labkit.formats import runs

A = "2026-10-01T10-00-00_aaaa"


def _rows(path: Path, run_id: str | None, ids: list[str]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for i in ids:
            row: dict = {"id": i, "answer": "x"}
            if run_id:
                row["_prov"] = {"run": run_id}
            fh.write(json.dumps(row) + "\n")


class RowRuns(unittest.TestCase):
    def test_counts_rows_per_run_and_unstamped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "out.jsonl"
            _rows(p, A, ["1", "2"])
            _rows(p, "2026-10-02T10-00-00_bbbb", ["3"])
            _rows(p, None, ["4"])
            p.write_text(
                p.read_text() + '{"id": "5", "ans', encoding="utf-8"
            )  # torn tail
            rr = batch.row_runs(p)
            self.assertEqual(rr.runs, {A: 2, "2026-10-02T10-00-00_bbbb": 1})
            self.assertEqual(rr.unstamped, 1)


class ResumedRunNamesWhatItContinues(unittest.TestCase):
    def test_outputs_and_completion_carry_continues(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            out = area / "output" / "x.jsonl"
            out.parent.mkdir()
            _rows(out, A, ["1", "2"])  # the run that broke off left these
            with contextlib.redirect_stdout(io.StringIO()):
                with runlog.run("t", {}, base_dir=area) as r:
                    r.output(out)
                    with batch.Store(out, prov={"run": r.run_id}) as store:
                        for rec in store.pending([{"id": i} for i in ("1", "2", "3")]):
                            store.append({**rec, "answer": "y"})
                    r.metrics(c1_pass=True)
            entries = runs.read_outputs(r.dir) or []
            self.assertEqual(entries[0].continues, (A,))
            self.assertEqual(entries[0].rows_from, {A: 2, r.run_id: 1})
            completion = json.loads(
                (r.dir / "completion.json").read_text(encoding="utf-8")
            )
            self.assertEqual(completion["continues"], [A])
            # finalize: the continuation is named, nothing foreign
            blockers, notes = finalize.row_provenance_findings(r.dir)
            self.assertEqual(blockers, [])
            self.assertTrue(any("continues " + A in n for n in notes), notes)

    def test_a_fresh_file_names_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            out = area / "output" / "x.jsonl"
            out.parent.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                with runlog.run("t", {}, base_dir=area) as r:
                    r.output(out)
                    _rows(out, r.run_id, ["1"])
                    r.metrics(c1_pass=True)
            entries = runs.read_outputs(r.dir) or []
            self.assertEqual(entries[0].continues, ())
            self.assertEqual(finalize.row_provenance_findings(r.dir), ([], []))


class FinalizeHoldsRowsToTheRun(unittest.TestCase):
    def _run(
        self,
        area: Path,
        name: str,
        out: Path,
        *,
        continues: list[str] | None = None,
        derived_from: str | None = None,
    ) -> Path:
        d = area / "runs" / name
        d.mkdir(parents=True)
        (d / "config.json").write_text(
            json.dumps(
                {"schema_version": 2, "derived_from": derived_from, "config": {}}
            ),
            encoding="utf-8",
        )
        (d / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": str(out),
                        "sha256": "ab",
                        "lines": 1,
                        "continues": continues or [],
                    }
                ]
            ),
            encoding="utf-8",
        )
        return d

    def test_rows_of_an_unnamed_run_are_a_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            run = self._run(area, "2026-10-02T10-00-00_bbbb", out)
            _rows(out, run.name, ["1"])
            _rows(out, A, ["2", "3"])  # from a run this one does not name
            blockers, _ = finalize.row_provenance_findings(run)
            self.assertEqual(len(blockers), 1)
            self.assertIn(f"2 row(s) from {A}", blockers[0])
            self.assertIn("file of two measurements", blockers[0])

    def test_a_derived_run_may_hold_its_parents_rows(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            self._run(area, A, out)
            child = self._run(area, "2026-10-02T10-00-00_bbbb", out, derived_from=A)
            _rows(out, A, ["1", "2"])
            self.assertEqual(finalize.row_provenance_findings(child), ([], []))

    def test_unstamped_rows_are_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            run = self._run(area, A, out)
            _rows(out, A, ["1"])
            _rows(out, None, ["2"])
            blockers, notes = finalize.row_provenance_findings(run)
            self.assertEqual(blockers, [])
            self.assertTrue(any("1 row(s) without _prov" in n for n in notes), notes)


if __name__ == "__main__":
    unittest.main()
