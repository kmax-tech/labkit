"""Tests for finalize — the read-only gate after a run.

The individual checks (intent-check, protocol-fill) have their own tests.
These tests verify that finalize sequences them correctly and that the
exit code reflects the worst finding.
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.gates import finalize  # noqa: E402
from labkit.formats import gate  # noqa: E402
from protocol_fixture import PID, completed_run, head  # noqa: E402

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
            completed_run(
                area, "2026-10-07T10-00-00_meas", metrics={**CLEAN_METRICS, "c1_n": 7}
            )
            completed_run(area, "2026-10-07T11-00-00_prob", metrics={"rows_seen": 2})
            code, out = _run_finalize(area)
        self.assertIn("2026-10-07T10-00-00_meas: completed (skipped 1 newer", out)
        self.assertIn("c1_n", out)  # the warning names the measurement's key
        self.assertNotIn("2026-10-07T11-00-00_prob: completed", out)


class TestFinalize(unittest.TestCase):
    def test_protocol_choice_errors_follow_the_supplied_channel(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            for choice in ("none", "missing", "ambiguous"):
                with self.subTest(choice=choice):
                    protocol = area / "absent.md" if choice == "missing" else None
                    if choice == "ambiguous":
                        for name in ("a", "b"):
                            (area / f"PROTOCOL-{name}.md").write_text(CLEAN_PROTOCOL)
                    for silent in (True, False):
                        lines: list[str] = []
                        findings = gate.Findings(tell=None if silent else lines.append)
                        out, err = io.StringIO(), io.StringIO()
                        with (
                            contextlib.redirect_stdout(out),
                            contextlib.redirect_stderr(err),
                        ):
                            code = finalize.finalize_area(area, protocol, findings)
                        self.assertEqual(
                            (code, out.getvalue(), err.getvalue()), (2, "", "")
                        )
                        self.assertEqual(len(lines), 0 if silent else 1)
                        if lines:
                            self.assertIn("finalize:", lines[0])

    def test_protocol_choice_errors_still_use_stderr_on_the_console(self):
        with tempfile.TemporaryDirectory() as d:
            out, err = io.StringIO(), io.StringIO()
            with (
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                code = finalize.finalize_area(Path(d))
            self.assertEqual((code, out.getvalue()), (2, ""))
            self.assertIn("finalize: no PROTOCOL-*.md", err.getvalue())

    def test_clean_area_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            completed_run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("all clear", out)

    def test_no_completed_run_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            completed_run(area, "r1", metrics={"c1_pass": True}, completion=False)
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
            completed_run(area, "r1", metrics={"c1_pass": True, "a1_pass": True})
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("[A2] registered", out)

    def test_open_fields_are_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(PROTOCOL_WITH_HOLES)
            completed_run(area, "r1", metrics=CLEAN_METRICS)
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
            completed_run(area, "r1", metrics={"something": 1})
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
            completed_run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 2, out)
        self.assertIn("no [protocol] table", out)

    def test_unstamped_id_is_a_blocker(self):
        """No stamped id binds no run: a number cannot be traced to this
        protocol, so finalize blocks instead of skipping the completion check."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(_protocol(id="<protocol-id>"))
            completed_run(area, "r1", metrics=CLEAN_METRICS)
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
        completed_run(area, "r1", metrics={"c1_pass": True})
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
