"""Tests for preflight — the read-only gate before freezing.

The individual checks (protocol-check, code-check, scope-sha) have their
own tests. These tests verify that preflight SEQUENCES them correctly and
that the exit code reflects the worst finding.
"""

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, promises  # noqa: E402
from labkit import preflight  # noqa: E402
from protocol_fixture import head  # noqa: E402

BODY = """\
- **Terms of this protocol:** n/a — standard vocabulary
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] p < .05
- **Admissibility condition:** [A1] parse yield above 80%
- **Model I/O:** in: text · out: a label, parsed by parse()
- **Prompt (verbatim, per variant):**

  ```text
  prompt
  ```

- **Null condition / anchors (in the same run):** [A2] shuffled labels stay at chance
- **Exclusions / filters:** none
- **Data / scope:** data/x.jsonl, 12 items
- **Model / tool:** n/a — deterministic
- **Unit:** one item
"""


def _protocol(**head_fields) -> str:
    return "# Experiment protocol: x\n\n" + head(**head_fields) + "\n" + BODY


CLEAN_PROTOCOL = _protocol()


def _area(d, protocol_text=CLEAN_PROTOCOL, scripts=True, git=True):
    area = Path(d)
    p = area / "PROTOCOL-x.md"
    p.write_text(protocol_text, encoding="utf-8")
    if scripts:
        (area / "scripts").mkdir(exist_ok=True)
        (area / "scripts" / "01_measure.py").write_text(
            'metrics = {"c1_pass": True, "a1_pass": True, "a2_pass": True}\n',
            encoding="utf-8",
        )
    if git:
        subprocess.run(["git", "init", "-q", "."], cwd=d, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t"], cwd=d, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=d, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=d, capture_output=True)
    return area, p


def _run_preflight(area, protocol=None):
    argv = [str(area)]
    if protocol:
        argv += ["--protocol", str(protocol)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
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
            self.assertIn("WARNING: no tests/test_", out)

    def test_missing_test_file_blocks_once_frozen(self):
        """frozen = true owes every gap; a missing resolution test is one
        (2026-10-07: it only warned, a protocol froze without any test)."""
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(
                d, _protocol(frozen=True, preflight_audit="2026-10-07 · scope sha 0")
            )
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn("BLOCKER: no tests/test_", out)
            self.assertIn("frozen = true owes it", out)

    def test_failing_area_test_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            name = self._with_test(
                d, "def test_resolution():\n    assert False, 'TODO'\n"
            )
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


class TestAreaTestNames(unittest.TestCase):
    """An area runs its own stamped test, not one whose name extends its own
    (uniagent 2026-10-07: area 08 ran area 09's test)."""

    def test_a_longer_name_is_not_this_areas_test(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "tests").mkdir()
            for name in (
                "test_08_profile.py",
                "test_08_profile_parser.py",
                "test_09_profile_after.py",
            ):
                (repo / "tests" / name).write_text("def test_x():\n    assert True\n")
            area = repo / "experiments" / "08-profile"
            area.mkdir(parents=True)
            found = preflight.area_tests(area, repo)
        self.assertEqual(
            [f.name for f in found.files],
            ["test_08_profile.py", "test_08_profile_parser.py"],
        )


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
                CLEAN_PROTOCOL.replace("p-0123456789abcdef", "p-fedcba9876543210"),
                encoding="utf-8",
            )
            code, out = _run_preflight(area)
        self.assertEqual(code, 2, out)
        self.assertIn("2 protocols", out)

    def test_explicit_protocol_flag(self):
        with tempfile.TemporaryDirectory() as d:
            area, p = _area(d)
            code, out = _run_preflight(area, protocol=p)
        self.assertEqual(code, 0, out)

    def test_protocol_blocker_makes_exit_one(self):
        unstamped = _protocol(id="<protocol-id>")
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=unstamped)
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("MISSING (must): [protocol] id", out)
        self.assertIn("blocker", out)

    def test_prose_head_is_rejected_loudly(self):
        """A protocol with the head as prose lines (Standard 0.16/0.17) is
        read by labkit 0.47; here it is a blocker naming the [protocol]
        table, not a protocol checked against guessed fields (TODO 8)."""
        prose = (
            "# Experiment protocol: x\n\n- **Standard:** 0.16\n"
            "- **Protocol id:** p-0123456789abcdef\n- **Frozen before run:** no\n"
            + BODY
        )
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=prose)
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("HEAD (must): no [protocol] table", out)

    def test_an_unreadable_head_ends_before_every_later_station(self):
        """The one early end: the later stations would read a head that is
        not there. The blocker is told, the summary follows, nothing else."""
        prose = "# Experiment protocol: x\n\n- **Standard:** 0.16\n" + BODY
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=prose)
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("BLOCKER: HEAD (must)", out)
        for station in (
            "── cost tier ──",
            "── audit findings ──",
            "── code-check",
            "── tests ──",
        ):
            self.assertNotIn(station, out)
        self.assertIn("preflight: 1 blocker(s), 0 warning(s)", out)

    def test_any_other_blocker_lets_the_later_stations_run(self):
        """A must gap in station 1 is a blocker, and stations 2–8 still run
        and tell what they found — only the summary ends the gate."""
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=_protocol(id="<protocol-id>"))
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("BLOCKER: MISSING (must): [protocol] id", out)
        for station in (
            "── cost tier ──",
            "── audit findings ──",
            "── code-check",
            "── scope-sha ──",
            "── working tree ──",
            "── hooks ──",
            "── tests ──",
        ):
            self.assertIn(station, out)
        self.assertIn("WARNING: no tests/test_", out)  # station 8 found its own

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


class TestNoScriptsDirectory(unittest.TestCase):
    def test_area_without_scripts_skips_scope_sha(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, scripts=False)
            code, out = _run_preflight(area)
        self.assertIn("no scripts matching", out)
        self.assertIn("skipped", out)


class GraduationGate(unittest.TestCase):
    """Frozen turns should-gaps into blockers — the same rule as in
    protocol-check, from the same function (2026-10-05)."""

    def test_frozen_protocol_with_should_gaps_has_blockers(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, _protocol(frozen=True))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = preflight.preflight_area(area)
            self.assertEqual(rc, 1)
            self.assertIn("MISSING (must): Problem in one sentence", buf.getvalue())

    def test_unfrozen_protocol_same_gaps_are_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = preflight.preflight_area(area)
            self.assertEqual(rc, 0)
            self.assertIn("missing (should): Problem in one sentence", buf.getvalue())


class TestCostTier(unittest.TestCase):
    """The tier names how much audit the run gets; preflight says it out loud."""

    def _out(self, protocol_text):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                preflight.preflight_area(area)
            return buf.getvalue()

    def test_seconds_makes_the_agent_audit_optional(self):
        out = self._out(_protocol(cost="seconds"))
        self.assertIn("OPTIONAL", out)

    def test_hours_asks_for_the_audit(self):
        out = self._out(_protocol(cost="hours"))
        self.assertIn("hours — the experiment-preflight audit is due", out)

    def test_an_unfilled_tier_counts_as_hours(self):
        out = self._out(_protocol(cost="<seconds | minutes | hours>"))
        self.assertIn("not filled — treated as `hours`", out)


class AreaTestPython(unittest.TestCase):
    """The interpreter for an area's tests has a name of its own (CODE-015)."""

    def test_the_repo_venv_wins(self):
        with tempfile.TemporaryDirectory() as d:
            own = Path(d) / ".venv" / "bin" / "python"
            own.parent.mkdir(parents=True)
            own.write_text("")
            self.assertEqual(preflight.area_test_python(Path(d)), str(own))

    def test_without_a_venv_the_running_python(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(preflight.area_test_python(Path(d)), sys.executable)


if __name__ == "__main__":
    unittest.main()


def _block(area: Path) -> str:
    """The promise block the area's protocol carries, as a record names it."""
    return promises.block_stamp((area / "PROTOCOL-x.md").read_text(encoding="utf-8"))


class TestAuditFindings(unittest.TestCase):
    """Station 2b: findings files are read; open = warning, blocker once frozen; deferred elsewhere = reminder."""

    ROW = [
        (
            "WARNING",
            "WARNING · scripts/01_measure.py:1 · x · y · LAB-019 The stamp covers everything · z",
        )
    ]

    def _recorded(self, d, frozen=False):
        text = _protocol(frozen=True) if frozen else CLEAN_PROTOCOL
        area, _ = _area(d, text)
        path = findings.write(
            area, "preflight", "opus", "abc", _block(area), (0, 1, 0), self.ROW
        )
        return area, path

    def test_open_finding_is_a_warning_before_the_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = self._recorded(d)
            code, out = _run_preflight(area)
            self.assertEqual(code, 0, out)
            self.assertIn("WARNING: undecided in", out)
            self.assertIn("1 finding(s) still `open`", out)

    def test_open_finding_blocks_once_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = self._recorded(d, frozen=True)
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn("BLOCKER: undecided in", out)

    def test_decided_findings_pass_and_an_unreadable_file_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            area, path = self._recorded(d)
            text = path.read_text().replace('status = "open"', 'status = "fixed"')
            path.write_text(text)
            code, out = _run_preflight(area)
            self.assertEqual(code, 0, out)
            self.assertIn("all decided (1 audit(s) recorded)", out)
            path.write_text(
                text.replace('status = "fixed"', 'status = "accepted"')
            )  # no reason
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn("BLOCKER: ", out)
            self.assertIn("owes a reason", out)

    def test_a_stale_audit_line_blocks_once_frozen(self):
        """The line names a sha, a decided record carries that sha, the code
        stamps another: preflight said "all decided" and passed the state
        runlog refuses at the run (audit 2026-10-15). The twin, the code's
        own sha, is clean."""
        from labkit.formats import scope_sha

        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(
                d, _protocol(frozen=True, preflight_audit="scope sha 000000000000")
            )
            path = findings.write(
                area, "preflight", "opus", "000000000000", _block(area), (0, 0, 0), []
            )
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn(
                "BLOCKER: preflight_audit: the audit saw scope sha 000000000000", out
            )
            sha = scope_sha.area_stamp(area)[0]
            p = area / "PROTOCOL-x.md"
            p.write_text(
                p.read_text().replace("scope sha 000000000000", f"scope sha {sha}")
            )
            path.unlink()
            findings.write(area, "preflight", "opus", sha, _block(area), (0, 0, 0), [])
            code, out = _run_preflight(area)
            self.assertNotIn("preflight_audit:", out)
            # the promises rewritten after the audit: the record named the
            # code only until 0.97.1 (review 2026-10-18)
            p.write_text(
                p.read_text().replace(
                    "the criterion holds", "the criterion holds twice"
                )
            )
            code, out = _run_preflight(area)
            self.assertEqual(code, 1, out)
            self.assertIn("no preflight audit saw the area as it is now", out)

    def test_deferred_in_another_area_is_a_reminder_not_a_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "experiments"
            (root / "17-here").mkdir(parents=True)
            area, _ = _area(root / "17-here")
            other = root / "16-there"
            other.mkdir()
            path = findings.write(
                other, "preflight", "opus", "abc", "b", (0, 1, 0), self.ROW
            )
            path.write_text(
                path.read_text()
                .replace('status = "open"', 'status = "deferred"')
                .replace('reason = ""', 'reason = "own task"')
            )
            code, out = _run_preflight(area)
            self.assertEqual(code, 0, out)
            self.assertIn("deferred in 16-there", out)
            self.assertIn("own task", out)
            self.assertIn("1 deferred finding(s) elsewhere", out)
            # a reminder, not a count: the summary line is the same without it
            shutil.rmtree(other / "audits")
            _, alone = _run_preflight(area)
            self.assertEqual(out.splitlines()[-1], alone.splitlines()[-1])
