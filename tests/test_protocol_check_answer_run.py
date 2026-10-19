"""protocol-check: an `Answer to the question` written without a run_id is a
WARNING — the hint where the declaration of a reported result is not
unambiguous. The declaration is the run_id in that line (`protocol-fill
--from-run` writes it; `report-check --if-reported` holds it at the stop and
the commit). Twins: an answer with its run_id, and the open field of an
exploration, are silent (TODO 2, 2026-10-19).
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import protocol_check  # noqa: E402
from protocol_fixture import head  # noqa: E402

RUN = "2026-10-07T10-00-00_ab12"


def _protocol(answer: str) -> str:
    return head(cost="seconds") + f"- **Answer to the question:** {answer}\n"


class AnswerWithoutRun(unittest.TestCase):
    def test_an_answer_naming_no_run_warns(self):
        warning = protocol_check.answer_without_run(_protocol("AUC 0.91"))
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertTrue(warning.startswith("WARNING:"))
        self.assertIn("names no run_id", warning)

    def test_an_answer_with_its_run_is_silent(self):
        self.assertIsNone(
            protocol_check.answer_without_run(_protocol(f"AUC 0.91 ({RUN})"))
        )

    def test_the_open_field_of_an_exploration_is_silent(self):
        self.assertIsNone(
            protocol_check.answer_without_run(_protocol("<number + run_id>"))
        )
        self.assertIsNone(protocol_check.answer_without_run(head(cost="seconds")))

    def test_the_report_carries_it_as_a_warning_not_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(_protocol("AUC 0.91"), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_check.main([str(p)])
            report = protocol_check.check_protocol(
                p, p.read_text(encoding="utf-8"), set(), {}
            )
        self.assertIn(
            "WARNING: `Answer to the question` is written but names no run_id",
            buf.getvalue(),
        )
        self.assertIsNotNone(report.answer_unbound)
        # the warning alone never blocks: `blocks` reads the musts and the head
        self.assertNotIn("names no run_id", "; ".join(report.musts))


if __name__ == "__main__":
    unittest.main()
