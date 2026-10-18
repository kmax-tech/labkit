"""Tests for finalize — the read-only gate after a run.

The individual checks (intent-check, protocol-fill) have their own tests.
These tests verify that finalize sequences them correctly and that the
exit code reflects the worst finding.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import finalize, promises  # noqa: E402
from protocol_fixture import PID, head, scope_file  # noqa: E402

BODY = """\
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] p < .05
- **Admissibility condition:** [A1] parse yield above 80%
- **Null condition / anchors (in the same run):** [A2] shuffled labels stay at chance
- **Raw output:** one real example
- **Outcome:** 0.03

```text
prompt
```
"""


def _protocol(**head_fields) -> str:
    return (
        "# Experiment protocol: x\n\n" + head(frozen=True, **head_fields) + "\n" + BODY
    )


CLEAN_PROTOCOL = _protocol()
CLEAN_METRICS = {"c1_pass": True, "a1_pass": True, "a2_pass": True}

PROTOCOL_WITH_HOLES = CLEAN_PROTOCOL.replace(
    "- **Outcome:** 0.03", "- **Outcome:** <result here>"
)


def _run(area, name, *, pid=PID, metrics=None, completion=True, repeat_of=None):
    d = area / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    # a run under a frozen protocol recorded its block (0.71): the snapshot
    # of the area's protocol, whose scopes name the fixture's script
    scope_file(area)
    block = promises.parse_block((area / "PROTOCOL-x.md").read_text(encoding="utf-8"))
    cfg = {
        "script": "01_measure.py",
        "pid": 1,
        "schema_version": 2,
        "protocol": {"id": pid, "path": "PROTOCOL-x.md"},
        "instrument": "apply",  # the fixture head's, as runlog records it (0.20)
        "models_resolved": {"model": {"alias": "haiku"}},  # a model run names its model
        "promises": promises.snapshot(block, area) if block is not None else None,
    }
    if repeat_of is not None:  # a second draw of REPEAT_OF, never the answer
        cfg["repeat_of"], cfg["draw"] = repeat_of, 2
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics is not None:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
    return d


def _run_finalize(area, protocol=None):
    argv = [str(area)]
    if protocol:
        argv += ["--protocol", str(protocol)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = finalize.main(argv)
    return code, buf.getvalue()


class TestOneRunForEveryStation(unittest.TestCase):
    """A probe run after the measurement must not become the run finalize
    judges: intent-check skips it (no intent keys), so the other stations
    must too (review 2026-10-07: scope drift and the c1_n check ran on the
    probe and finalize said all clear)."""

    def test_stations_check_the_run_intent_check_chose(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "2026-10-07T10-00-00_meas", metrics={**CLEAN_METRICS, "c1_n": 7})
            _run(area, "2026-10-07T11-00-00_prob", metrics={"rows_seen": 2})
            code, out = _run_finalize(area)
        self.assertIn("2026-10-07T10-00-00_meas: completed (skipped 1 newer", out)
        self.assertIn("c1_n", out)  # the warning names the measurement's key
        self.assertNotIn("2026-10-07T11-00-00_prob: completed", out)


class TestFinalize(unittest.TestCase):
    def test_clean_area_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            # a model area is clean with its spread drawn: one draw is a
            # warning, read from the run's recorded instrument (0.20); a
            # repeat names its primary by run id, so both carry one here
            primary = "2026-10-07T10-00-00_aa11"
            _run(area, primary, metrics=CLEAN_METRICS)
            _run(
                area,
                "2026-10-07T10-01-00_bb22",
                metrics=CLEAN_METRICS,
                repeat_of=primary,
            )
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("all clear", out)

    def test_no_completed_run_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "r1", metrics={"c1_pass": True}, completion=False)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no completed run bound to", out)
        self.assertIn("blocker", out)

    def test_the_summary_repeats_each_blocker_last(self):
        """Inside a commit hook the blocker sat among 20 lines (probe 2026-10-07)."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        recap = out.split("fix the blockers before reporting:")[1]
        self.assertIn("  - no completed run bound to", recap)

    def test_no_runs_dir_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no runs/", out)

    def test_missing_intent_key_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "r1", metrics={"c1_pass": True, "a1_pass": True})
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("[A2] registered", out)

    def test_open_fields_are_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(PROTOCOL_WITH_HOLES)
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("Outcome", out)
        self.assertIn("warning", out.lower())

    def test_no_protocol_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(Path(d))
        self.assertEqual(code, 2, out)
        self.assertIn("no PROTOCOL", out)

    def test_help_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = finalize.main(["--help"])
        self.assertEqual(code, 0)

    def test_no_args_exits_two(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = finalize.main([])
        self.assertEqual(code, 2)

    def test_no_intent_ids_skips_check(self):
        proto = (
            CLEAN_PROTOCOL.replace("[C1] ", "")
            .replace("[A1] ", "")
            .replace("[A2] ", "")
        )
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(proto)
            _run(area, "r1", metrics={"something": 1})
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("no intent ids registered", out)

    def test_unreadable_head_exits_two(self):
        """A prose head (Standard 0.16/0.17) is read by labkit 0.47; here it
        is a usage error naming the [protocol] table (TODO 8)."""
        prose = (
            "# Experiment protocol: x\n\n- **Standard:** 0.16\n"
            f"- **Protocol id:** {PID}\n- **Frozen before run:** yes\n" + BODY
        )
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(prose)
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 2, out)
        self.assertIn("no [protocol] table", out)

    def test_unstamped_id_is_a_blocker(self):
        """No stamped id binds no run: a number cannot be traced to this
        protocol, so finalize blocks instead of skipping the completion check."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(_protocol(id="<protocol-id>"))
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no stamped protocol id", out)


class AreaTestsBeforeReporting(unittest.TestCase):
    """finalize runs the area's tests on every tier: a later edit of
    evaluate() that mutes the criterion is caught before a number leaves
    (2026-10-07); no test is no finding here."""

    def area(self, d: str, test_body: str | None) -> Path:
        area = Path(d)
        (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
        _run(area, "r1", metrics={"c1_pass": True})
        if test_body is not None:
            (area / "tests").mkdir()
            (area / "tests" / f"test_{area.name}.py").write_text(test_body)
        return area

    def test_a_failing_area_test_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(self.area(d, "def test_r():\n    assert False\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("evaluate() no longer holds its resolution check", out)

    def test_a_passing_area_test_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(self.area(d, "def test_r():\n    assert True\n"))
        self.assertIn("── area tests ──\n  ok — ", out)
        self.assertNotIn("resolution check", out)

    def test_no_area_test_is_no_finding(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(self.area(d, None))
        self.assertIn("── area tests ──\n  none", out)


if __name__ == "__main__":
    unittest.main()


class TestCommitGate(unittest.TestCase):
    """`finalize --if-reported`: the pre-commit gate — a number written back
    into "Answer to the question" does not enter the history unchecked, and
    it must cite the run the checks hold (review 2026-10-07)."""

    RUN = "2026-10-07T10-00-00_ab12"

    def _area(self, d: str, answer: str) -> Path:
        area = Path(d)
        (area / "PROTOCOL-x.md").write_text(
            CLEAN_PROTOCOL + f"- **Answer to the question:** {answer}\n"
        )
        _run(area, self.RUN, metrics=CLEAN_METRICS)
        return area

    def _gate(self, area: Path) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = finalize.main(["--if-reported", str(area / "PROTOCOL-x.md")])
        return code, buf.getvalue()

    def test_an_unreported_protocol_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._gate(self._area(d, "<number + run_id>"))
        self.assertEqual((code, out), (0, ""))

    def test_a_reported_protocol_is_finalized(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._gate(self._area(d, f"AUC 0.91 ({self.RUN})"))
        self.assertEqual(code, 0, out)
        self.assertIn("its answer cites a run", out)

    def test_citing_another_run_than_the_one_that_answers_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._gate(self._area(d, "AUC 0.91 (2026-10-01T09-00-00_ffff)"))
        self.assertEqual(code, 1, out)
        self.assertIn("but the run that answers is", out)

    def test_a_blocker_fails_the_gate(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, f"AUC 0.91 ({self.RUN})")
            (area / "runs" / self.RUN / "metrics.json").write_text(
                json.dumps({"c1_pass": True})
            )
            code, out = self._gate(area)
        self.assertEqual(code, 1, out)
