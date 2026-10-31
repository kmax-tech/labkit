"""The deliverable of an external task is a registered output of the
answering run (2026-10-29): the stamped skeleton names it (DELIVERABLES),
writes it from the kept rows and registers it, so outputs.json pins it by
path and sha256, and finalize (report-check through it) holds the file in
the tree to that record — swapped or gone is a blocker, untouched passes.
An injection benchmark swapped `pred_results/*.csv` in seven delivered
states and no gate noticed (docs/usability/2026-10-29-injection-ab4ce6d.md,
M7).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_end_to_end as e2e  # noqa: E402  the stamped lab and the count

from labkit.formats import deliverable, runs, scope_sha, standard_contract  # noqa: E402
from labkit.gates import report_check  # noqa: E402
from labkit.tools import scaffold  # noqa: E402

DELIVERABLE = "pred_results/lines.csv"


class RenderCsv(unittest.TestCase):
    def test_the_first_rows_keys_are_the_header_in_their_order(self):
        text = deliverable.render_csv([{"b": 1, "a": "x"}, {"b": 2, "a": "y"}])
        self.assertEqual(text, "b,a\n1,x\n2,y\n")

    def test_no_rows_and_a_row_with_other_columns_are_refused(self):
        with self.assertRaisesRegex(deliverable.DeliverableError, "no rows"):
            deliverable.render_csv([])
        with self.assertRaisesRegex(
            deliverable.DeliverableError, "row 2 has the columns a"
        ):
            deliverable.render_csv([{"a": 1, "b": 2}, {"a": 1}])

    def test_the_columns_the_task_names_pass_and_a_gap_is_refused_by_name(self):
        """Task 34 of the pressure pilot: both arms dropped a column the task
        names, and the evaluation could not read the file (2026-10-29)."""
        columns = ("person_id", "probability", "flag")
        row = {"person_id": "p1", "probability": 0.5, "flag": 1}
        self.assertEqual(
            deliverable.render_csv([row], columns),
            "person_id,probability,flag\np1,0.5,1\n",
        )
        self.assertEqual(
            deliverable.render_csv([row]), deliverable.render_csv([row], ())
        )
        cases = {
            "missing the column(s) flag": {"person_id": "p1", "probability": 0.5},
            "carrying the column(s) site the task does not name": {**row, "site": "a"},
            "ordered flag, person_id, probability, the task orders person_id, "
            "probability, flag": {"flag": 1, "person_id": "p1", "probability": 0.5},
        }
        for why, bad in cases.items():
            with self.subTest(why):
                with self.assertRaisesRegex(
                    deliverable.DeliverableError, re.escape(why)
                ):
                    deliverable.render_csv([bad], columns)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.csv"
            with self.assertRaises(deliverable.DeliverableError):
                deliverable.write_csv(path, [{"person_id": "p1"}], columns)
            self.assertFalse(path.exists())  # refused: nothing written

    def test_write_csv_returns_the_path_it_wrote(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pred_results" / "x.csv"
            self.assertEqual(deliverable.write_csv(path, [{"a": 1}]), path)
            self.assertEqual(path.read_text(encoding="utf-8"), "a\n1\n")


class Stamp(unittest.TestCase):
    """`labkit-init exp --deliverable` stamps the measure script's constant."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "lab"
        scaffold.stamp_lab(self.root, "lab")

    def test_both_skeletons_carry_the_constant_and_the_other_scripts_do_not(self):
        area = self.root / "experiments" / "01-x"
        line = f"DELIVERABLES: tuple[str, ...] = ({DELIVERABLE!r},)"
        for kind in ("compute", "apply"):
            sk = standard_contract.skeleton("low", kind, False)
            stamps = scaffold.script_stamps(
                self.root, area, "01", "x", sk, False, (DELIVERABLE,), ("a", "b")
            )
            for path, text in stamps.items():
                if path.name == standard_contract.MEASURE_SCRIPT.name:
                    self.assertIn(line, text, kind)
                    self.assertNotIn("DELIVERABLES: tuple[str, ...] = ()", text)
                    self.assertIn(
                        "DELIVERABLE_COLUMNS: tuple[str, ...] = ('a', 'b')", text
                    )
                else:
                    self.assertNotIn("DELIVERABLE", text, path)
            # the twin: without a deliverable the stamp keeps the empty tuple
            plain = scaffold.script_stamps(self.root, area, "01", "x", sk, False)
            self.assertIn(
                "DELIVERABLES: tuple[str, ...] = ()",
                plain[area / "scripts" / "01_measure.py"],
            )

    def test_a_text_without_the_line_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no single `DELIVERABLES"):
            scaffold.stamp_constant("X = 1\n", "DELIVERABLES", ("a",))

    def test_columns_without_a_deliverable_are_refused(self):
        sk = standard_contract.skeleton("low", "compute", False)
        with self.assertRaisesRegex(ValueError, "columns without a deliverable"):
            scaffold.script_stamps(
                self.root,
                self.root / "experiments" / "01-x",
                "01",
                "x",
                sk,
                False,
                (),
                ("a",),
            )

    def test_the_command_line_flag_is_repeatable(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rc = scaffold.main(
                [
                    "exp",
                    "x",
                    "--repo",
                    str(self.root),
                    "--repeat-cost",
                    "low",
                    "--kind",
                    "compute",
                    "--deliverable",
                    "pred_results/a.csv",
                    "--deliverable",
                    "pred_results/b.csv",
                    "--deliverable-columns",
                    "id, p_active",
                ]
            )
        self.assertEqual(rc, 0)
        script = self.root / "experiments" / "01-x" / "scripts" / "01_measure.py"
        text = script.read_text(encoding="utf-8")
        self.assertIn(
            "DELIVERABLES: tuple[str, ...] = ('pred_results/a.csv', 'pred_results/b.csv')",
            text,
        )
        self.assertIn("DELIVERABLE_COLUMNS: tuple[str, ...] = ('id', 'p_active')", text)


class EstimatorWrites(unittest.TestCase):
    """The estimator skeleton's `write_deliverables`: every DELIVERABLES file
    from `deliverable_rows`, registered with the run; a repeat's draw none."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # resolved: the script's REPO is, and the written path is compared to it
        self.root = Path(self.tmp.name).resolve() / "lab"
        scaffold.stamp_lab(self.root, "lab")
        with contextlib.redirect_stdout(io.StringIO()):
            area, _ = scaffold.stamp_area(
                self.root,
                "screen",
                repeat_cost="low",
                kind="apply",
                deliverables=(DELIVERABLE,),
            )
        name = f"deliverable_apply_{id(self)}"
        spec = importlib.util.spec_from_file_location(
            name, area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        self.measure = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.measure
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(self.measure)

    def test_the_full_run_writes_and_registers_a_repeat_draw_does_not(self):
        m = self.measure
        self.assertEqual(m.DELIVERABLES, (DELIVERABLE,))
        rows = [
            {"lane": "registered", "id": "a", "pred": 1},
            {"lane": "test", "id": "u", "pred": 0.25},
        ]
        run = mock.Mock(draw=None)
        with mock.patch.object(
            m,
            "deliverable_rows",
            lambda path, rows, metrics: [
                {"id": r["id"], "p": r["pred"]} for r in rows if r["lane"] == "test"
            ],
        ):
            m.write_deliverables(run, rows, {})
            written = self.root / DELIVERABLE
            self.assertEqual(written.read_text(encoding="utf-8"), "id,p\nu,0.25\n")
            run.output.assert_called_once_with(written)
            written.unlink()
            m.write_deliverables(mock.Mock(draw=2), rows, {})
            self.assertFalse(written.exists())

    def test_the_skeleton_refuses_a_column_the_task_names_and_the_rows_lack(self):
        """The check is the skeleton's, at the write: the stamped
        DELIVERABLE_COLUMNS against the rows deliverable_rows() gives."""
        m = self.measure
        rows = [{"lane": "test", "id": "u", "pred": 0.25}]
        written = self.root / DELIVERABLE
        with mock.patch.object(
            m, "deliverable_rows", lambda path, rows, metrics: [{"id": "u", "p": 0.25}]
        ):
            with mock.patch.object(m, "DELIVERABLE_COLUMNS", ("id", "p")):
                m.write_deliverables(mock.Mock(draw=None), rows, {})
                self.assertTrue(written.is_file())
                written.unlink()
            with mock.patch.object(m, "DELIVERABLE_COLUMNS", ("id", "p", "flag")):
                run = mock.Mock(draw=None)
                with self.assertRaisesRegex(
                    deliverable.DeliverableError, "missing the column\\(s\\) flag"
                ):
                    m.write_deliverables(run, rows, {})
                self.assertFalse(written.exists())
                run.output.assert_not_called()

    def test_without_the_todo_filled_the_run_refuses(self):
        with self.assertRaisesRegex(NotImplementedError, "deliverable_rows"):
            self.measure.write_deliverables(mock.Mock(draw=None), [], {})


class CountDelivers(unittest.TestCase):
    """The compute skeleton's real run: the deliverable in outputs.json with
    the sha256 the run took; finalize and report-check hold the tree to it."""

    run_id = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = e2e.Lab()
        cls.area, cls.protocol = e2e.stamp_count(cls.lab, deliverables=(DELIVERABLE,))
        cls.run_id = cls.lab.run_id_of(cls.lab.script(cls.area, "01_measure.py"))
        cls.delivered = cls.lab.root / DELIVERABLE

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def _entry(self) -> runs.OutputEntry:
        outputs = runs.read_outputs(self.area / "runs" / self.run_id) or []
        (entry,) = [o for o in outputs if o.path.resolve() == self.delivered.resolve()]
        return entry

    def test_the_run_registers_the_deliverable_with_its_sha256(self):
        entry = self._entry()
        self.assertEqual(
            self.delivered.read_text(encoding="utf-8"), "lines_mean\n3.0\n"
        )
        self.assertEqual(
            entry.sha256, scope_sha.file_digest(self.delivered)[: runs.RECORD_SHA_CHARS]
        )
        self.assertEqual(entry.lines, 2)
        raw = json.loads(
            (self.area / "runs" / self.run_id / "outputs.json").read_text()
        )
        self.assertIn(DELIVERABLE, [e["path"] for e in raw])  # relative to the repo

    def test_a_swapped_or_missing_deliverable_holds_finalize_and_report_check(self):
        lab = self.lab
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn("2 registered output(s) as the run recorded them", out)
        as_written = self.delivered.read_bytes()
        try:
            self.delivered.write_text("lines_mean\n4.0\n", encoding="utf-8")
            rc, out = lab.finalize(self.area)
            self.assertEqual(rc, 1, out)
            entry = self._entry()  # the path as the record resolves it
            held = (
                f"BLOCKER: {entry.path}: not the file run {self.run_id} recorded"
                f" — its sha256 "
            )
            self.assertIn(held, out)
            self.assertIn(
                f"is not the recorded {entry.sha256}. Next: "
                "measure anew (`.venv/bin/python ",
                out,
            )
            checked = io.StringIO()
            with contextlib.redirect_stdout(checked):
                self.assertEqual(report_check.report_check(self.area), 1)
            self.assertIn(
                f"finalize: {entry.path}: not the file run", checked.getvalue()
            )
            self.delivered.unlink()
            rc, out = lab.finalize(self.area)
            self.assertEqual(rc, 1, out)
            self.assertIn(
                f"{entry.path}: not the file run {self.run_id} recorded — "
                "the file is gone",
                out,
            )
        finally:
            self.delivered.write_bytes(as_written)
        # the twin: restored as written, the run carries its number again
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
