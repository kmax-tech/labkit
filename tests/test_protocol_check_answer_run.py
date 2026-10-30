"""protocol-check: an `Recorded results` written while the head declares
no `[result] run` is a WARNING — the hint where the declaration of a reported
result is not unambiguous. The declaration is the head's table (`protocol-fill
--from-run` writes it with Recorded results; `report-check --if-reported` holds it at
the stop and the commit). Twins: an answer under a declared run, and the open
field of an exploration, are silent (TODO 2, 2026-10-19; phase 3, 2026-10-21).
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
from labkit.checks import protocol_report  # noqa: E402
from protocol_fixture import head  # noqa: E402

RUN = "2026-10-07T10-00-00_ab12"


def _protocol(answer: str, declared: str | None = None) -> str:
    return (
        head(repeat_cost="low", result=declared) + f"- **Recorded results:** {answer}\n"
    )


class AnswerWithoutRun(unittest.TestCase):
    def test_an_answer_naming_no_run_warns(self):
        warning = protocol_check.recorded_results_without_run(_protocol("AUC 0.91"))
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertTrue(warning.startswith("WARNING:"))
        self.assertIn("the head has adopted no run (`[result] run`)", warning)

    def test_an_answer_with_its_run_is_silent(self):
        self.assertIsNone(
            protocol_check.recorded_results_without_run(
                _protocol(f"AUC 0.91 ({RUN})", declared=RUN)
            )
        )

    def test_the_open_field_of_an_exploration_is_silent(self):
        self.assertIsNone(
            protocol_check.recorded_results_without_run(_protocol("<number + run_id>"))
        )
        self.assertIsNone(
            protocol_check.recorded_results_without_run(head(repeat_cost="low"))
        )

    def test_the_report_carries_it_as_a_warning_not_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(_protocol("AUC 0.91"), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_report.main([str(p)])
            report = protocol_report.check_protocol(
                p, p.read_text(encoding="utf-8"), set(), {}
            )
        self.assertIn(
            "WARNING: `Recorded results` is written but the head has adopted no",
            buf.getvalue(),
        )
        self.assertIsNotNone(report.answer_unbound)
        # the warning alone never blocks: `blocks` reads the musts and the head
        self.assertNotIn("declares no", "; ".join(report.musts))


if __name__ == "__main__":
    unittest.main()
