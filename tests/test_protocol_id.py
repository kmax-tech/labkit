"""Tests for the protocol id — identity a run can bind to (`[protocol] id`).

Why this exists: nothing in a run said which protocol it belonged to, so in
a series area (`PROTOCOL-s1-*` ... `PROTOCOL-s13-*`) every automatic pairing
of protocol and run was a guess, and `code-check` silently checked s1 while
s13 was the protocol just built (2026-09-26). The id is what a run binds to;
the path only says where it was found.

The gates tested here: the field is due (a placeholder is a must gap), the
value has one shape, an id occurs once per repository, and an edit against HEAD is worth a
warning — never a proof, because after the commit the new id IS the state.
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import (  # noqa: E402
    protocol_block,
    protocol_check,
    protocol_history,
    protocol_report,
)
from protocol_fixture import PID, head  # noqa: E402

# Every must field of a pilot filled, so the id alone decides the verdict.
PILOT = """# Experiment protocol: x

{head}
- **Terms of this protocol:** n/a — standard vocabulary
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] p < .05
- **Admissibility condition:** [A1] fewer than 20% errors
- **Model I/O:** in: claim · out: yes/no, parsed by parse()
- **Prompt:** see block

  ```text
  prompt
  ```

- **Null condition / anchors:** [A2] shuffled labels
- **Exclusions / filters:** none
- **Data / scope:** data/x.jsonl, 12 items
- **Data profile:** 6 and 6 items, mean words 9 and 9; no marker only in one class
- **Model / tool:** n/a — deterministic
- **Unit:** one item
"""


def _protocol(dirpath, pid: str = PID, name="PROTOCOL-x.md", extra: str = ""):
    p = Path(dirpath) / name
    p.write_text(PILOT.format(head=head(id=pid)) + extra, encoding="utf-8")
    return p


def _check(paths):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = protocol_report.main([str(p) for p in paths])
    return code, buf.getvalue()


class TestFieldIsDue(unittest.TestCase):
    def test_unstamped_id_is_a_must_gap(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d, pid="<protocol-id>")
            code, out = _check([p])
        self.assertIn("MISSING (must): [protocol] id", out)
        self.assertEqual(code, 1)

    def test_prose_mentioning_protocol_id_does_not_satisfy_the_field(self):
        """'Protocol id will be added later' must not pass the must-check:
        the id is read from the head table, never from the prose."""
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(
                d,
                pid="<protocol-id>",
                extra="- **Protocol id:** p-0123456789abcdef\n"
                "Protocol id will be added later.\n",
            )
            _, out = _check([p])
        self.assertIn("MISSING (must): [protocol] id", out)

    def test_a_prose_head_is_rejected(self):
        """The id as a prose line (Standard 0.16/0.17) is read by labkit 0.47
        only; here the protocol fails on its missing head."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(
                "# x\n- **Standard:** 0.17\n- **Protocol id:** " + PID + "\n",
                encoding="utf-8",
            )
            code, out = _check([p])
        self.assertIn("HEAD (must): no [protocol] table", out)
        self.assertEqual(code, 1)

    def test_a_stamped_protocol_reports_nothing_about_its_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d)
            code, out = _check([p])
        self.assertNotIn("[protocol] id", out)
        self.assertEqual(code, 0, out)


class TestShape(unittest.TestCase):
    def test_wrong_shape_is_reported(self):
        for bad in ("p-NOTHEX", "p-0123", "0123456789abcdef", "p-0123456789ABCDEF"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                p = _protocol(d, pid=bad)
                code, out = _check([p])
                self.assertIn(f"HEAD (must): [protocol] id = '{bad}'", out)
                self.assertEqual(code, 1)

    def test_sixteen_lowercase_hex_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d, pid="p-9e2341c0390948dc")
            code, out = _check([p])
        self.assertNotIn("HEAD", out)
        self.assertEqual(code, 0, out)


class TestUniqueness(unittest.TestCase):
    """The stamp alone cannot settle uniqueness: a protocol copied as the
    starting point for the next one carries the id along."""

    def test_the_same_id_twice_in_one_repo_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            _protocol(d, name="PROTOCOL-s1-a.md")
            second = _protocol(d, name="PROTOCOL-s2-b.md")
            code, out = _check([second])
        self.assertIn("DUPLICATE protocol id", out)
        self.assertIn("PROTOCOL-s1-a.md", out)
        self.assertEqual(code, 1)

    def test_a_copy_made_later_in_the_same_process_is_seen(self):
        """The index was a module-level cache cleared only by `main`: a
        caller of the API checked, copied the protocol, checked again, and
        the duplicate stayed invisible (review 2026-10-14)."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            first = _protocol(d, name="PROTOCOL-s1-a.md")
            head = protocol_check.check_fields(first.read_text()).head
            assert head is not None
            ids = protocol_block.repo_protocol_ids(first)
            self.assertEqual(protocol_history.check_protocol_id(first, head, ids), [])
            _protocol(d, name="PROTOCOL-s2-b.md")
            ids = protocol_block.repo_protocol_ids(first)
            found = protocol_history.check_protocol_id(first, head, ids)
        self.assertTrue(any("DUPLICATE" in f.text for f in found), found)

    def test_a_file_name_does_not_grade_a_duplicate(self):
        """The grade was read from the finding's text, and the text carries
        the path: PROTOCOL-WARNING.md turned the doubled id into a warning in
        protocol-check and in preflight. The twin: the same doubled id under
        another name blocks too."""
        from labkit.formats.gate import BLOCKER, Findings
        from labkit.gates import preflight

        for name in ("PROTOCOL-WARNING.md", "PROTOCOL-normal.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                (Path(d) / ".git").mkdir()
                first = _protocol(d, name=name)
                _protocol(d, name="PROTOCOL-copy.md")
                code, out = _check([first])
                self.assertEqual(code, 1, out)
                report = protocol_check.check_fields(first.read_text())
                assert report.head is not None
                found = Findings(tell=None)
                preflight.check_protocol_fields(found, first, report, report.head)
                grades = [f.grade for f in found.found if "DUPLICATE" in f.line]
                self.assertEqual(grades, [BLOCKER], found.found)

    def test_no_ok_line_beside_a_finding(self):
        """`clean` ignored the findings printed before it: a doubled id stood
        above "OK — must fields filled". The twin: nothing found, OK."""
        from dataclasses import replace

        from labkit.formats.gate import BLOCKER, GUARANTEED, GateFinding

        base = protocol_report.FileReport(path=Path("P.md"), head_error=None)
        self.assertTrue(base.clean)
        for name, r in (
            ("audit_drift", replace(base, audit_drift="the code now stamps abc")),
            (
                "id_findings",
                replace(
                    base,
                    id_findings=[
                        GateFinding(
                            BLOCKER, "P.md: DUPLICATE", evidence_kind=GUARANTEED
                        )
                    ],
                ),
            ),
            (
                "repeat_cost_lowered",
                replace(base, repeat_cost_lowered="P.md: WARNING: repeat cost lowered"),
            ),
            (
                "answer_unbound",
                replace(base, answer_unbound="WARNING: Answer without run_id"),
            ),
        ):
            with self.subTest(finding=name):
                self.assertFalse(r.clean)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            first = _protocol(d)
            _, alone = _check([first])
            _protocol(d, name="PROTOCOL-copy.md")
            _, doubled = _check([first])
        self.assertIn(": OK —", alone)
        self.assertNotIn(": OK —", doubled)

    def test_distinct_ids_side_by_side_are_fine(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            _protocol(d, pid="p-1111111111111111", name="PROTOCOL-s1-a.md")
            second = _protocol(d, pid="p-2222222222222222", name="PROTOCOL-s2-b.md")
            _, out = _check([second])
        self.assertNotIn("DUPLICATE", out)


class TestDivergenceAgainstHead(unittest.TestCase):
    """A warning, never a proof of immutability — after the next commit the
    changed id is the state. It catches the edit in the working tree."""

    def _repo(self, d):
        run = lambda *a: subprocess.run(a, cwd=d, capture_output=True)  # noqa: E731
        run("git", "init", "-q", ".")
        run("git", "config", "user.email", "t@t")
        run("git", "config", "user.name", "t")
        return run

    def test_changed_id_against_head_warns_without_failing(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(d)
            p = _protocol(d, pid="p-1111111111111111")
            run("git", "add", "-A")
            run("git", "commit", "-qm", "init")
            before, _ = _check([p])
            p.write_text(
                p.read_text(encoding="utf-8").replace(
                    "p-1111111111111111", "p-2222222222222222"
                ),
                encoding="utf-8",
            )
            after, out = _check([p])
        self.assertIn("WARNING: protocol id changed against HEAD", out)
        self.assertIn("p-1111111111111111 -> p-2222222222222222", out)
        # the warning says something, it does not change the verdict
        self.assertEqual(after, before)

    def test_a_new_file_does_not_warn(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(d)
            (Path(d) / "seed.txt").write_text("x", encoding="utf-8")
            run("git", "add", "-A")
            run("git", "commit", "-qm", "init")
            p = _protocol(d)
            _, out = _check([p])
        self.assertNotIn("WARNING: protocol id", out)

    def test_no_git_no_check(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d)
            _, out = _check([p])
        self.assertNotIn("WARNING: protocol id", out)


if __name__ == "__main__":
    unittest.main()
