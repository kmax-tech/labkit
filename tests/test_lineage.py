"""`answering_run.lineage` — the whole `derived_from` chain, validated once,
and its three readers: the model's run, the params rows, the rows a
measurement file may hold.

    .venv/bin/python -m pytest tests/test_lineage.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit.checks.run_record_check import row_provenance_findings
from labkit.formats import answering_run, runs
from labkit.tools import params

A, B, C = (f"2026-10-0{i}T10-00-00_{c * 4}" for i, c in ((1, "a"), (2, "b"), (3, "c")))


def _run(
    area: Path,
    name: str,
    *,
    derived_from: str | None = None,
    models_resolved: dict | None = None,
) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg = {
        "schema_version": 3,
        "run_kind": "measurement",
        "script": "01_measure.py",
        "protocol": {"id": "p-0001", "path": "x.md"},
        "derived_from": derived_from,
        "models_resolved": models_resolved or {},
        "config": {},
    }
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return d


MODEL = {"m": {"model": "A"}}


class Lineage(unittest.TestCase):
    def setUp(self) -> None:
        self.area = Path(tempfile.mkdtemp())

    def test_the_run_comes_first_then_its_ancestors(self) -> None:
        a = _run(self.area, A)
        b = _run(self.area, B, derived_from=A)
        c = _run(self.area, C, derived_from=B)
        self.assertEqual(answering_run.lineage(c), [c, b, a])
        self.assertEqual(answering_run.lineage(a), [a])

    def test_each_break_is_loud_naming_what_broke(self) -> None:
        cases = {
            "loop": ((A, B), (B, A)),
            "not under": ((B, "2026-09-01T10-00-00_dead"),),
            "must name a run": ((B, ""),),
        }
        for needle, links in cases.items():
            with self.subTest(needle=needle):
                area = Path(tempfile.mkdtemp())
                for name, parent in links:
                    _run(area, name, derived_from=parent)
                c = _run(area, C, derived_from=links[0][0])
                with self.assertRaisesRegex(ValueError, needle):
                    answering_run.lineage(c)

    def test_a_path_instead_of_a_run_name_is_refused_where_it_is_read(self) -> None:
        """`./<own run>` is the run itself under another spelling, and the
        name comparison let the walk loop forever; `../../<elsewhere>`
        left the runs/ directory (review 2026-10-20). Both are refused as
        the config is read, before any walk."""
        for parent in (f"./{C}", f"../../other/runs/{A}"):
            with self.subTest(parent=parent):
                area = Path(tempfile.mkdtemp())
                _run(area / "other", A)
                c = _run(area, C, derived_from=parent)
                with self.assertRaisesRegex(ValueError, "must name a run"):
                    answering_run.lineage(c)
                with self.assertRaises(runs.RunConfigError):
                    runs.read_run_config(c)

    def test_a_parent_directory_without_config_is_loud(self) -> None:
        (self.area / "runs" / B).mkdir(parents=True)
        c = _run(self.area, C, derived_from=B)
        with self.assertRaisesRegex(ValueError, "no config.json"):
            answering_run.lineage(c)


class BreaksAboveTheFirstModelRecord(unittest.TestCase):
    """B recorded the model, so the walk to the model's run stops at B; a
    loop or a missing run above B was never looked at, and the params rows
    walked on past B without a loop check of their own."""

    def _area(self, above_b: str) -> Path:
        area = Path(tempfile.mkdtemp())
        _run(area, B, derived_from=above_b, models_resolved=MODEL)
        if above_b == A:
            _run(area, A, derived_from=B)  # A -> B -> A
        return _run(area, C, derived_from=B)

    def test_every_reader_refuses_a_loop_or_a_missing_run_above_it(self) -> None:
        for above_b, needle in ((A, "loop"), ("2026-09-01T10-00-00_dead", "not under")):
            with self.subTest(needle=needle):
                c = self._area(above_b)
                with self.assertRaisesRegex(ValueError, needle):
                    answering_run.model_provenance_run(c)
                with self.assertRaisesRegex(ValueError, needle):
                    params.model_rows(c)
                blockers, _ = row_provenance_findings(c)
                self.assertEqual(len(blockers), 1, blockers)
                self.assertIn("lineage", blockers[0])
                self.assertIn(needle, blockers[0])

    def test_a_whole_chain_passes_every_reader(self) -> None:
        area = Path(tempfile.mkdtemp())
        _run(area, A)
        b = _run(area, B, derived_from=A, models_resolved=MODEL)
        c = _run(area, C, derived_from=B)
        self.assertEqual(answering_run.model_provenance_run(c), b)
        rows = params.model_rows(c)
        self.assertIn(f"models_resolved of {B}, inherited through {C}", rows[0].home)
        self.assertEqual(row_provenance_findings(c), ([], []))


if __name__ == "__main__":
    unittest.main()
