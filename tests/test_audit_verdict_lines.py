"""labkit-audit: the verdict and the finding lines are one result. A report
whose verdict counts other blockers or warnings than its lines is no audit
(exit 2, nothing recorded) — a line withdrawn in prose below it once gave
exit 0 and left an open blocker in the record (review 2026-10-20).

    .venv/bin/python -m pytest tests/test_audit_verdict_lines.py
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.gates import audit

PROTOCOL = "- **Protocol id:** p-0123456789abcdef\nCriterion [C1].\n"


def _area() -> Path:
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
    (area / "PROTOCOL-x.md").write_text(PROTOCOL, encoding="utf-8")
    return area


def _run(answer: str) -> tuple[int, str, list[Path]]:
    """(exit code, stderr, the records written)."""
    err = io.StringIO()
    area = _area()
    with (
        mock.patch.object(audit.llm, "complete", lambda *a, **k: answer),
        mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(err),
    ):
        rc = audit.main([str(area), "--mode", "preflight"])
    return rc, err.getvalue(), sorted((area / "audits").glob("*.toml"))


LINE = "BLOCKER · a.py:1 · x · y · LAB-015 Preflight audit before freezing · z\n"


class VerdictHeldToLines(unittest.TestCase):
    def test_a_blocker_withdrawn_in_prose_is_no_audit(self) -> None:
        for tail in ("", "Correction: no finding.\n"):
            with self.subTest(tail=tail):
                rc, err, records = _run(
                    LINE + tail + "verdict: 0 blockers, 0 warnings, 0 notes"
                )
                self.assertEqual((rc, records), (2, []))
                self.assertIn("the verdict counts 0 blocker(s) and 0 warning(s)", err)
                self.assertIn("lists 1 BLOCKER and 0 WARNING line(s)", err)

    def test_twin_verdict_and_lines_agree(self) -> None:
        rc, _, records = _run(LINE + "verdict: 1 blockers, 0 warnings, 0 notes")
        self.assertEqual((rc, len(records)), (1, 1))
        rc, _, records = _run(
            "NOTE · a.py:1 · x\nverdict: 0 blockers, 0 warnings, 1 notes"
        )
        self.assertEqual((rc, len(records)), (0, 1))


if __name__ == "__main__":
    unittest.main()
