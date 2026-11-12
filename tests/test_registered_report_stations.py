"""The registered report's branches no test reached below a whole command,
as gate tests: a first measurement lost, so the report binding cannot be
read; and discussion blocks of the registered report that do not read."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import report_blocks
from labkit.formats.area_state import Measured
from labkit.formats.gate import BLOCKER, OPEN_RULE, TECHNICAL_RULE
from labkit.gates import registered_report
from protocol_fixture import PID, head


class AReportBinding(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        self.protocol = root / "PROTOCOL-x.md"
        self.text = head(repeat_cost="low", report="REPORT.md")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _gap(self, lost: tuple[str, ...], text: str):
        measured = Measured(self.protocol.parent, PID, (), lost, (), ())
        return registered_report.report_binding_gap(
            self.protocol, text, measured=measured
        )

    def _commit(self) -> None:
        """The protocol registering REPORT.md, committed."""
        root = self.protocol.parent
        self.protocol.write_text(self.text, encoding="utf-8")
        for args in (
            ("add", "-A"),
            ("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "protocol"),
        ):
            subprocess.run(["git", *args], cwd=root, check=True)

    def test_a_committed_report_is_owed_once_the_area_measured(self):
        """A lost first measurement leaves no commit to read; the report
        HEAD registers binds, and a head without one drops it."""
        self._commit()
        lost = ("2026-11-10T10-00-00_lost",)
        gap = self._gap(lost, head(repeat_cost="low", report=None))
        assert gap is not None
        self.assertEqual((gap.grade, gap.rule), (BLOCKER, OPEN_RULE))
        self.assertIn("registered REPORT.md as its report in its last commit", gap.text)
        self.assertIn("name another file there", gap.fix or "")
        self.assertIn("--handover", gap.fix or "")
        # the twins: a head that registers a report, here or elsewhere
        self.assertIsNone(self._gap(lost, self.text))
        self.assertIsNone(
            self._gap(lost, head(repeat_cost="low", report="docs/OTHER.md"))
        )

    def test_the_twin_before_a_measurement_nothing_is_bound(self):
        self._commit()
        self.assertIsNone(self._gap((), head(repeat_cost="low", report=None)))

    def test_discussion_blocks_that_do_not_read_hold_the_report(self):
        broken = report_blocks.ReportBlockError(
            "line 4: the discussion head is no TOML"
        )
        with mock.patch.object(
            registered_report.report_blocks, "discussions", side_effect=broken
        ):
            gap = registered_report.registered_review(
                self.protocol.parent / "REPORT.md",
                "",
                self.protocol,
                self.text,
                mock.Mock(),
            )
        assert gap is not None
        self.assertIn("its discussion blocks do not read — line 4", gap.text)
        self.assertEqual(
            gap.rule,
            TECHNICAL_RULE,
        )


if __name__ == "__main__":
    unittest.main()
