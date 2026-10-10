"""labkit-audit (0.74.0): the verdict line decides (an auditor may correct
itself — tests/test_audit.py), and a report that lists a BLOCKER or WARNING
line while summing to zero says so on stderr, so exit 0 is not read as "no
line was there".

    .venv/bin/python -m pytest tests/test_audit_verdict_lines.py
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import audit

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"


def _area() -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
    (area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
    return area


def _run(answer: str) -> tuple[int, str]:
    err = io.StringIO()
    with (
        mock.patch.object(audit.llm, "complete", lambda *a, **k: answer),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(err),
    ):
        rc = audit.main([str(_area()), "--mode", "preflight"])
    return rc, err.getvalue()


class VerdictHeldToLines(unittest.TestCase):
    def test_a_blocker_line_under_a_zero_verdict_is_named(self) -> None:
        rc, err = _run(
            "BLOCKER · a.py:1 · x · y · AS-015 Preflight-Audit vor dem Einfrieren · z\n"
            "verdict: 0 blockers, 0 warnings, 0 notes"
        )
        self.assertEqual(rc, 0)  # the verdict line decides
        self.assertIn("the report lists 1 BLOCKER/WARNING line(s)", err)

    def test_twin_notes_only_under_a_zero_verdict_is_exit_0(self) -> None:
        rc, err = _run("NOTE · a.py:1 · x\nverdict: 0 blockers, 0 warnings, 1 notes")
        self.assertEqual(rc, 0)
        self.assertNotIn("verdict NOTE", err)


if __name__ == "__main__":
    unittest.main()
