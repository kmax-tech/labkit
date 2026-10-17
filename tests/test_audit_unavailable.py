"""labkit-audit leaves a trace of every call it starts (2026-10-17).

Before the model call a `.running` marker; after it either the findings
record or, when the call got no result, an `unavailable` record — so a
failed audit never looks like one nobody started (Haiku on bulk modulus (labkit-paper 09, Haiku round, t3-labkit-r1, 2026-10-16)). The model call is faked, as in test_audit.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import audit, findings  # noqa: E402

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"
SCRIPT = "import scoring\nfrom labkit import runlog\nprint(scoring.X)\n"
CLEAN = "verdict: 0 blockers, 0 warnings, 2 notes\nscope:\nscripts/01_measure.py"
MISCOUNTED = "verdict: 2 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"


def repo_with() -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
    (area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
    (repo / "lib").mkdir()
    (repo / "lib" / "scoring.py").write_text("X = 0.7\n", encoding="utf-8")
    return area


def run(area: Path, fake) -> tuple[int, str]:
    err = io.StringIO()
    with (
        mock.patch.object(audit.llm, "complete", fake),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(err),
    ):
        rc = audit.main([str(area), "--mode", "preflight"])
    return rc, err.getvalue()


class Unavailable(unittest.TestCase):
    def test_a_backend_error_leaves_an_unavailable_record_and_no_marker(self):
        area = repo_with()

        def down(alias, prompt, **kw):
            raise audit.llm.BackendError("claude-cli: not logged in")

        rc, err = run(area, down)
        self.assertEqual(rc, 2)
        self.assertIn("NO RESULT", err)
        [r] = findings.area_records(area)
        self.assertEqual(r.unavailable, "claude-cli: not logged in")
        self.assertEqual(r.mode, "preflight")
        self.assertEqual(findings.area_running(area), [])
        [stop] = findings.audit_stops(area)
        self.assertIn("not logged in", stop)

    def test_a_result_leaves_a_record_and_no_marker(self):
        """The twin: the call answers, the marker goes, nothing is unavailable."""
        area = repo_with()
        rc, _ = run(area, lambda alias, prompt, **kw: CLEAN)
        self.assertEqual(rc, 0)
        [r] = findings.area_records(area)
        self.assertIsNone(r.unavailable)
        self.assertEqual(findings.area_running(area), [])
        self.assertEqual(findings.audit_stops(area), [])

    def test_the_marker_stands_during_the_call_and_names_this_process(self):
        area = repo_with()
        seen: list[findings.Running] = []

        def look(alias, prompt, **kw):
            seen.extend(findings.area_running(area))
            return CLEAN

        run(area, look)
        [m] = seen
        self.assertEqual(m.pid, os.getpid())
        self.assertEqual(m.mode, "preflight")
        self.assertEqual(m.script, Path(sys.argv[0]).name)

    def test_a_report_the_lines_do_not_carry_is_no_result_either(self):
        area = repo_with()
        rc, err = run(area, lambda alias, prompt, **kw: MISCOUNTED)
        self.assertEqual(rc, 2)
        [r] = findings.area_records(area)
        self.assertIsNotNone(r.unavailable)
        assert r.unavailable is not None
        self.assertIn("not readable as findings", r.unavailable)
        self.assertEqual(findings.area_running(area), [])

    def test_a_report_without_a_verdict_line_is_no_result(self):
        area = repo_with()
        rc, _ = run(area, lambda alias, prompt, **kw: "I looked and all is well.")
        self.assertEqual(rc, 2)
        [r] = findings.area_records(area)
        assert r.unavailable is not None
        self.assertIn("verdict", r.unavailable)

    def test_an_area_that_cannot_be_read_leaves_nothing(self):
        """Before the stamp nothing has started: no marker, no record."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        rc, _ = run(area, lambda alias, prompt, **kw: CLEAN)
        self.assertEqual(rc, 2)
        self.assertFalse((area / findings.DIR).exists())


if __name__ == "__main__":
    unittest.main()
