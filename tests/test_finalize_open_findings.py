"""finalize names undecided audit findings and an answering run whose number
cannot be reported; report-check refuses that number (plan 2026-10-17, A3).

Benchmark rounds (labkit-paper area 09): the leakage BLOCKER lay undecided
in audits/ and nothing between it and the reported number said so; in the
second haiku round on 0.98.0 the answering runs were probes (run_kind='probe') or
acknowledged runs (LABKIT_UNFROZEN=1), and both gates were silent. finalize
warns about such a run and blocks on an open BLOCKER; report-check blocks
the run (`runs.unreportable`, one telling).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, promises, runs  # noqa: E402
from labkit.gates import finalize, report_check  # noqa: E402
from protocol_fixture import registration_of, completed_run, head, run_record  # noqa: E402

BODY = """\
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [criterion-1] p < .05
- **Quality check:** [quality-check-1] parse yield above 80%
- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels stay at chance
- **Raw output:** one real example
- **Outcome:** 0.03

```text
prompt
```
"""
PROTOCOL = "# Experiment protocol: x\n\n" + head(frozen=True) + "\n" + BODY
METRICS = {
    "criterion_1_pass": True,
    "quality_check_1_pass": True,
    "quality_check_2_pass": True,
}
BLOCKER = ("BLOCKER", "BLOCKER · scripts/01_measure.py:3 · the target leaks")
WARNING = ("WARNING", "WARNING · scripts/01_measure.py:9 · the seed is not recorded")


def _finalize(area: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = finalize.main([str(area)])
    return code, buf.getvalue()


def _report_check(area: Path) -> tuple[int, str]:
    """The other stations stand in: the run station is the one under test."""
    buf = io.StringIO()
    no_gaps = SimpleNamespace(missing_must=[], must_holes=[])
    with (
        mock.patch.object(report_check, "check_fields", return_value=no_gaps),
        mock.patch.object(report_check, "finalize_area", return_value=0),
        mock.patch.object(report_check, "analysis_audit_gap", return_value=None),
        mock.patch.object(report_check, "check_analysis_script", return_value=None),
        contextlib.redirect_stdout(buf),
    ):
        code = report_check.report_check(area)
    return code, buf.getvalue()


class OpenFindings(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        (self.area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
        completed_run(self.area, "r1", metrics=METRICS)

    def _record(self, rows, mode: str = "preflight") -> Path:
        return findings.write(
            self.area,
            mode,
            "haiku",
            "0123456789ab",
            promises.block_stamp(PROTOCOL),
            (
                sum(g == "BLOCKER" for g, _ in rows),
                sum(g == "WARNING" for g, _ in rows),
                0,
            ),
            rows,
            run_id="r1" if mode == "analysis" else None,
            shown_sha="0" * 12 if mode == "analysis" else None,
            registration=registration_of(self.area),
        )

    def test_an_open_blocker_blocks_with_its_file(self):
        path = self._record([BLOCKER])
        code, out = _finalize(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"{path.name}: BLOCKER · scripts/01_measure.py:3", out)
        self.assertIn("undecided", out)

    def test_an_open_warning_of_an_analysis_record_warns(self):
        path = self._record([WARNING], mode="analysis")
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn(f"WARNING: {path.name}: WARNING · scripts/01_measure.py:9", out)

    def test_every_finding_decided_is_silent(self):
        path = self._record([BLOCKER])
        path.write_text(
            path.read_text(encoding="utf-8")
            .replace('status = "open"', 'status = "limit"')
            .replace('reason = ""', 'reason = "the leak is the measured quantity"'),
            encoding="utf-8",
        )
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("every finding decided (1 record(s))", out)
        self.assertIn("all clear", out)

    def test_an_unreadable_record_is_a_blocker(self):
        (self.area / findings.DIR).mkdir()
        (self.area / findings.DIR / "2026-10-20T14-03-preflight.toml").write_text(
            "no = [toml\n"
        )
        code, out = _finalize(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("not TOML", out)

    def test_a_record_of_a_deleted_run_is_a_blocker(self):
        """Fifth haiku round (labkit-paper area 09, t18, 2026-10-22): two
        measured runs removed with `rm -rf runs/…` after their audits; the
        records stayed and finalize read "every finding decided"."""
        path = self._record([], mode="analysis")
        path.write_text(
            path.read_text(encoding="utf-8").replace('run_id = "r1"', 'run_id = "r0"'),
            encoding="utf-8",
        )
        code, out = _finalize(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"{path.name}: names r0 as the run it read, and there is no runs/r0/", out
        )
        self.assertIn("a run an audit read is a kept run", out)

    def test_the_twin_a_record_of_a_kept_run_and_of_no_run_pass(self):
        self._record([], mode="analysis")  # names r1, which stands
        none = self._record([], mode="analysis")
        none.write_text(
            none.read_text(encoding="utf-8").replace(
                'run_id = "r1"', f'run_id = "{findings.NO_RUN}"'
            ),
            encoding="utf-8",
        )
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("every finding decided (2 record(s))", out)


class UnreportableRun(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        (self.area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")

    def test_a_full_run_is_silent_in_both(self):
        completed_run(self.area, "r1", metrics=METRICS)
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("all clear", out)
        code, out = _report_check(self.area)
        self.assertEqual(code, 0, out)

    def test_an_acknowledged_run_warns_in_finalize_and_blocks_in_report_check(self):
        completed_run(self.area, "r1", metrics=METRICS, unfrozen_ack=True)
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "WARNING: the answering run r1: a full run acknowledged over", out
        )
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("unfrozen protocol with LABKIT_UNFROZEN=1", out)
        self.assertIn("a reported number owes a full run", out)

    def test_a_probe_warns_in_finalize_and_blocks_in_report_check(self):
        """Haiku t3 and t18 on 0.98.0: measured without run_kind='measurement', reported."""
        completed_run(self.area, "r1", metrics=METRICS, run_kind="probe")
        code, out = _finalize(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("a probe (run_kind='probe')", out)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)
        self.assertIn("its number cannot be reported", out)

    def test_a_record_without_run_kind_is_refused_at_the_read_boundary(self):
        run = completed_run(self.area, "r1", metrics=METRICS)
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        del data["run_kind"]
        cfg.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(runs.RunConfigError, "run_kind"):
            runs.read_run_config(run)

    def test_the_marks_are_one_telling(self):
        def record(**fields: object) -> runs.RunConfig:
            return runs.parse_run_config(run_record(fields))

        self.assertEqual(
            runs.unreportable(record(run_kind="measurement", unfrozen_ack=False)), []
        )
        both = runs.unreportable(record(run_kind="probe", unfrozen_ack=True))
        self.assertEqual(len(both), 2)
        with self.assertRaises(runs.RunConfigError):  # refused where it is read
            record(run_kind="yes")

    def test_without_an_answering_run_report_check_leaves_it_to_finalize(self):
        code, out = _report_check(self.area)
        self.assertEqual(code, 0, out)  # finalize (stood in) is the station that blocks


if __name__ == "__main__":
    unittest.main()
