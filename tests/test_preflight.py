"""Tests for preflight — the read-only gate before freezing.

The individual checks (protocol-check, code-check, scope-sha) have their
own tests. These tests verify that preflight SEQUENCES them correctly and
that the exit code reflects the worst finding.
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import preflight  # noqa: E402

CLEAN_PROTOCOL = """\
# Experiment protocol: x

- **Standard:** 0.16
- **Protocol id:** p-0123456789abcdef
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [K1] p < .05
- **Stop rule:** [S1] abort above 20% errors
- **Type:** confirmatory
- **Terms of art:** none
- **Model I/O / prompt:** see below
- **Null condition:** [N1] shuffled labels
- **Raw output:** one real example
- **Exclusions / filters:** none
- **Frozen before run:** no

```text
prompt
```
"""


def _area(d, protocol_text=CLEAN_PROTOCOL, scripts=True, git=True):
    area = Path(d)
    p = area / "PROTOCOL-x.md"
    p.write_text(protocol_text, encoding="utf-8")
    if scripts:
        (area / "scripts").mkdir(exist_ok=True)
        (area / "scripts" / "01_measure.py").write_text(
            'metrics = {"k1_pass": True, "s1_hit": 0, "n1_pass": True}\n',
            encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", "."], cwd=d, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=d,
                       capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=d,
                       capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=d,
                       capture_output=True)
    return area, p


def _run_preflight(area, protocol=None):
    argv = [str(area)]
    if protocol:
        argv += ["--protocol", str(protocol)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = preflight.main(argv)
    return code, buf.getvalue()


class TestAreaTests(unittest.TestCase):
    """Station 5: the area's tests run; failing = blocker, missing = warning."""

    def _with_test(self, d, body) -> str:
        """The file name carries the area's slug — that is how station 5 finds it."""
        (Path(d) / "tests").mkdir()
        name = f"test_{Path(d).name}.py"
        (Path(d) / "tests" / name).write_text(body, encoding="utf-8")
        return name

    def test_missing_test_file_is_a_warning(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            code, out = _run_preflight(area)
            self.assertEqual(code, 0)
            self.assertIn("no tests/test_*", out)

    def test_failing_area_test_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            name = self._with_test(d, "def test_resolution():\n    assert False, 'TODO'\n")
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn(f"BLOCKER: {name} failed", out)

    def test_passing_area_test_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            name = self._with_test(d, "def test_resolution():\n    assert True\n")
            code, out = _run_preflight(area)
            self.assertEqual(code, 0, out)
            self.assertIn(f"ok — {name}", out)


class TestPreflight(unittest.TestCase):

    def test_clean_area_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            code, out = _run_preflight(area)
        self.assertEqual(code, 0, out)
        self.assertIn("0 blocker", out)

    def test_missing_protocol_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_preflight(Path(d))
        self.assertEqual(code, 2, out)
        self.assertIn("no PROTOCOL", out)

    def test_multiple_protocols_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, git=False)
            (area / "PROTOCOL-y.md").write_text(
                CLEAN_PROTOCOL.replace("p-0123456789abcdef",
                                       "p-fedcba9876543210"),
                encoding="utf-8")
            code, out = _run_preflight(area)
        self.assertEqual(code, 2, out)
        self.assertIn("2 protocols", out)

    def test_explicit_protocol_flag(self):
        with tempfile.TemporaryDirectory() as d:
            area, p = _area(d)
            code, out = _run_preflight(area, protocol=p)
        self.assertEqual(code, 0, out)

    def test_protocol_blocker_makes_exit_one(self):
        broken = CLEAN_PROTOCOL.replace(
            "- **Protocol id:** p-0123456789abcdef", "")
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=broken)
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("MISSING (must): Protocol id", out)
        self.assertIn("blocker", out)

    def test_dirty_tree_is_a_warning_not_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            (area / "new_file.txt").write_text("x", encoding="utf-8")
            code, out = _run_preflight(area)
        self.assertEqual(code, 0, out)
        self.assertIn("uncommitted changes", out)
        self.assertIn("warning", out.lower())

    def test_help_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = preflight.main(["--help"])
        self.assertEqual(code, 0)

    def test_no_args_exits_two(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = preflight.main([])
        self.assertEqual(code, 2)


MEASUREMENT_PROTOCOL = """\
# Measurement protocol: count things

- **Standard:** 0.16
- **Protocol id:** p-0123456789abcdef
- **Question:** how many X are there?
- **Data / scope:** all of them
- **Prior computation:** none
- **Method:** count
- **Exclusions / filters:** none
- **Result:** <pending>
- **Terms of art:** none
- **Type:** measurement

```text
prompt
```
"""


class TestMeasurementProtocol(unittest.TestCase):

    def test_measurement_uses_measurement_must_fields(self):
        """A measurement protocol must not be checked against experiment
        MUST fields (Success criterion, Stop rule, etc.)."""
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=MEASUREMENT_PROTOCOL,
                            scripts=False, git=False)
            code, out = _run_preflight(area)
        self.assertNotIn("MISSING (must): Success criterion", out)
        self.assertNotIn("MISSING (must): Stop rule", out)


class TestNoScriptsDirectory(unittest.TestCase):

    def test_area_without_scripts_skips_scope_sha(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, scripts=False)
            code, out = _run_preflight(area)
        self.assertIn("no scripts matching", out)
        self.assertIn("skipped", out)


if __name__ == "__main__":
    unittest.main()


class GraduationGate(unittest.TestCase):
    """Frozen turns should-gaps into blockers — the same rule as in
    protocol-check, from the same function (2026-10-05)."""

    def test_frozen_protocol_with_should_gaps_has_blockers(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, CLEAN_PROTOCOL.replace("** no", "** yes"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = preflight.run(area)
            self.assertEqual(rc, 1)
            self.assertIn("MISSING (must): Result / outcome (write back after the run) "
                          "(must once frozen: yes)", buf.getvalue())

    def test_unfrozen_protocol_same_gaps_are_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = preflight.run(area)
            self.assertEqual(rc, 0)
            self.assertIn("missing (should): Result", buf.getvalue())


class TestCostTier(unittest.TestCase):
    """The tier names how much audit the run gets; preflight says it out loud."""

    def _out(self, protocol_text):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                preflight.run(area)
            return buf.getvalue()

    def test_seconds_makes_the_agent_audit_optional(self):
        out = self._out(CLEAN_PROTOCOL + "- **Cost:** seconds\n")
        self.assertIn("OPTIONAL", out)

    def test_hours_asks_for_the_audit(self):
        out = self._out(CLEAN_PROTOCOL + "- **Cost:** hours\n")
        self.assertIn("hours — the experiment-preflight audit is due", out)

    def test_an_undeclared_tier_counts_as_hours(self):
        out = self._out(CLEAN_PROTOCOL)
        self.assertIn("not declared — treated as `hours`", out)

