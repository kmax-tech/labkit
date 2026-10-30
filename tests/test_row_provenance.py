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

from protocol_fixture import run_record  # noqa: E402
from labkit.run import batch, runlog
from labkit.checks import run_record_check
from labkit.formats import runs

A = "2026-10-01T10-00-00_aaaa"


def _rows(
    path: Path, run_id: str | None, ids: list[str], *, code_sha: str | None = None
) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for i in ids:
            row: dict = {"id": i, "answer": "x"}
            if run_id:
                row["_prov"] = {"run": run_id}
            if code_sha:
                row["_instrument"] = {"code_sha": code_sha}
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
                    r.metrics(criterion_1_pass=True)
            entries = runs.read_outputs(r.dir) or []
            self.assertEqual(entries[0].continues, (A,))
            self.assertEqual(entries[0].rows_from, {A: 2, r.run_id: 1})
            completion = json.loads(
                (r.dir / "completion.json").read_text(encoding="utf-8")
            )
            self.assertEqual(completion["continues"], [A])
            # finalize: the continuation is named, nothing foreign
            blockers, notes = run_record_check.row_provenance_findings(r.dir)
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
                    r.metrics(criterion_1_pass=True)
            entries = runs.read_outputs(r.dir) or []
            self.assertEqual(entries[0].continues, ())
            self.assertEqual(run_record_check.row_provenance_findings(r.dir), ([], []))


class AFinishedRunIsContinuedOutLoud(unittest.TestCase):
    """A repair measured again into the faulty run's file appended nothing
    and reported the faulty rows as its own (repair case, 2026-10-28), and
    nothing said so. Continuing a finished run is said; continuing the run
    that broke off is the resume it is meant for."""

    def _measure(self, area: Path, out: Path, ids: list[str], *, crash: bool = False):
        said = io.StringIO()
        with (
            contextlib.redirect_stdout(said),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with runlog.run("t", {}, base_dir=area) as r:
                r.output(out)
                with batch.Store(out, prov={"run": r.run_id}) as store:
                    for rec in store.pending([{"id": i} for i in ids]):
                        store.append({**rec, "answer": "y"})
                if crash:
                    raise RuntimeError("broke off")
                r.metrics(criterion_1_pass=True)
        return r, said.getvalue()

    def test_continuing_a_finished_run_is_said_with_the_way_to_its_own_output(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "output" / "x.jsonl"
            out.parent.mkdir()
            first, _ = self._measure(area, out, ["1", "2"])
            again, said = self._measure(area, out, ["1", "2"])
            self.assertIn(
                f"x.jsonl holds the rows of the completed run(s) {first.run_id}: "
                f"this run continues it, and those rows count as its own",
                said,
            )
            self.assertIn("`x_v2.jsonl`", said)
            entries = runs.read_outputs(again.dir) or []
            self.assertEqual(entries[0].continues, (first.run_id,))

    def test_the_twin_a_run_that_broke_off_is_continued_without_a_word(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "output" / "x.jsonl"
            out.parent.mkdir()
            with self.assertRaises(RuntimeError):
                self._measure(area, out, ["1"], crash=True)
            (broke_id,) = batch.row_runs(out).runs
            again, said = self._measure(area, out, ["1", "2"])
            self.assertNotIn("holds the rows of the completed run", said)
            entries = runs.read_outputs(again.dir) or []
            self.assertEqual(entries[0].continues, (broke_id,))


class ForeignRowsDuringTheRun(unittest.TestCase):
    def test_rows_of_another_run_written_meanwhile_are_no_continuation(self):
        """The file is new at registration; rows of a run that does not
        exist appear during the run. They are foreign, not continued."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            out = area / "output" / "x.jsonl"
            out.parent.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                with runlog.run("t", {}, base_dir=area) as r:
                    r.output(out)
                    _rows(out, A, ["1", "2"])
                    r.metrics(criterion_1_pass=True)
            entries = runs.read_outputs(r.dir) or []
            self.assertEqual(entries[0].continues, ())
            self.assertEqual(entries[0].rows_from, {A: 2})
            blockers, _ = run_record_check.row_provenance_findings(r.dir)
            self.assertTrue(any(A in b.text for b in blockers), blockers)


class FinalizeHoldsRowsToTheRun(unittest.TestCase):
    def _run(
        self,
        area: Path,
        name: str,
        out: Path,
        *,
        continues: list[str] | None = None,
        derived_from: str | None = None,
        script_sha: str | None = None,
    ) -> Path:
        d = area / "runs" / name
        d.mkdir(parents=True)
        (d / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 4,
                        "run_kind": "measurement",
                        "derived_from": derived_from,
                        "config": {},
                        **({"script_sha": script_sha} if script_sha else {}),
                    }
                )
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
            blockers, _ = run_record_check.row_provenance_findings(run)
            self.assertEqual(len(blockers), 1)
            self.assertIn(f"2 row(s) from {A}", blockers[0].text)
            self.assertIn("file of two measurements", blockers[0].text)
            self.assertIn("measure anew", blockers[0].fix or "")

    def test_continued_rows_of_other_code_are_a_blocker(self) -> None:
        """The repair case: the run continues the faulty run's file, and
        that run's script was another."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            self._run(area, A, out, script_sha="a" * 12)
            run = self._run(
                area,
                "2026-10-02T10-00-00_bbbb",
                out,
                continues=[A],
                script_sha="b" * 12,
            )
            _rows(out, A, ["1", "2"], code_sha="c" * 12)
            blockers, notes = run_record_check.row_provenance_findings(run)
            self.assertEqual(len(blockers), 1, blockers)
            self.assertIn(
                f"2 row(s) come from {A}, which ran other code", blockers[0].text
            )
            self.assertIn("`x_v2.jsonl`", blockers[0].fix or "")
            self.assertTrue(any("continues " + A in n for n in notes), notes)

    def test_the_twin_continued_rows_of_the_same_code_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            self._run(area, A, out, script_sha="a" * 12)
            run = self._run(
                area,
                "2026-10-02T10-00-00_bbbb",
                out,
                continues=[A],
                script_sha="a" * 12,
            )
            _rows(out, A, ["1"], code_sha="c" * 12)
            _rows(out, run.name, ["2"], code_sha="c" * 12)
            blockers, _ = run_record_check.row_provenance_findings(run)
            self.assertEqual(blockers, [])

    def test_a_models_answers_reread_after_a_parser_fix_pass(self) -> None:
        """Rows that name no code — a model's answers — do not depend on the
        script: a parser fix measured again re-reads them (the counter
        cases' judge repair)."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            self._run(area, A, out, script_sha="a" * 12)
            run = self._run(
                area,
                "2026-10-02T10-00-00_bbbb",
                out,
                continues=[A],
                script_sha="b" * 12,
            )
            _rows(out, A, ["1", "2"])
            blockers, _ = run_record_check.row_provenance_findings(run)
            self.assertEqual(blockers, [])

    def test_a_derived_run_may_hold_its_parents_rows(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            self._run(area, A, out)
            child = self._run(area, "2026-10-02T10-00-00_bbbb", out, derived_from=A)
            _rows(out, A, ["1", "2"])
            self.assertEqual(run_record_check.row_provenance_findings(child), ([], []))

    def test_unstamped_rows_are_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            out = area / "x.jsonl"
            run = self._run(area, A, out)
            _rows(out, A, ["1"])
            _rows(out, None, ["2"])
            blockers, notes = run_record_check.row_provenance_findings(run)
            self.assertEqual(blockers, [])
            self.assertTrue(any("1 row(s) without _prov" in n for n in notes), notes)


if __name__ == "__main__":
    unittest.main()
