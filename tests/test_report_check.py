"""report-check: the last gate at minutes/hours — frozen, finalize clean, an
analysis audit of the code as it is now, `02_analyze.py --check` passing.

The cloud judge probe (2026-10-14, draw 3) skipped the analysis audit, the
check and the note, and finalize was green; finalize cannot ask for what
follows the analysis audit, so the end has its own gate. Each station is
tested where it lives (findings.audit_coverage, recheck.holds, finalize);
here: what is owed when, and that every station blocks on its own.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import head, scope_file

from labkit import findings, report_check, scope_sha


class ReportCheck(unittest.TestCase):
    def _area(self, cost: str = "minutes", frozen: bool = True) -> Path:
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(cost=cost, frozen=frozen, preflight_audit="n/a — test"),
            encoding="utf-8",
        )
        return area

    def _audited(self, area: Path) -> None:
        sha = scope_sha.area_stamp(area)[0]
        findings.write(area, "analysis", "opus", sha, (0, 0, 0), [])

    def _run(
        self,
        area: Path,
        finalize: int = 0,
        check: str | None = None,
        fields: bool = False,
    ) -> tuple[int, str]:
        """FINALIZE and CHECK stand in for their stations; the fixture's
        protocol is a bare head, so its field gaps count only with FIELDS."""
        out = io.StringIO()
        no_gaps = SimpleNamespace(missing_must=[], must_holes=[])
        with (
            contextlib.nullcontext()
            if fields
            else mock.patch.object(report_check, "check_fields", return_value=no_gaps),
            mock.patch.object(report_check, "finalize_area", return_value=finalize),
            mock.patch.object(
                report_check, "check_analysis_script", return_value=check
            ),
            contextlib.redirect_stdout(out),
        ):
            code = report_check.report_check(area)
        return code, out.getvalue()

    def test_the_twin_every_station_holds_is_clean(self):
        area = self._area()
        self._audited(area)
        code, out = self._run(area)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_a_freeze_with_a_must_gap_blocks(self):
        """Frozen with the stamp's `<…>` promise sentences: the flag is set,
        the freeze registers nothing (cloud judge probe, draw 4)."""
        area = self._area()
        self._audited(area)
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        start = text.index('sentence = "') + len('sentence = "')
        end = text.index('"', start)
        proto.write_text(
            text[:start] + "<the criterion in one sentence>" + text[end:],
            encoding="utf-8",
        )
        code, out = self._run(area, fields=True)
        self.assertEqual(code, 1, out)
        self.assertIn("still carries the stamp's", out)

    def test_a_must_field_still_a_placeholder_blocks(self):
        """Station 1 read `missing_must` only: a must field holding its
        stamped `<…>` passed the last gate while protocol-check and preflight
        refused it (audit 2026-10-15)."""
        area = self._area()
        self._audited(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            "- **Unit:** <the counted unit>\n\n" + proto.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        code, out = self._run(area, fields=True)
        self.assertEqual(code, 1, out)
        self.assertIn("Unit still a placeholder", out)

    def test_seconds_owes_nothing_here(self):
        code, out = self._run(self._area(cost="seconds", frozen=False), finalize=1)
        self.assertEqual(code, 0)
        self.assertIn("nothing owed here", out)

    def test_each_station_blocks_on_its_own(self):
        area = self._area(frozen=False)
        code, out = self._run(area, finalize=1, check="02_analyze.py --check exits 1")
        self.assertEqual(code, 1)
        for needle in (
            "not `frozen = true`",
            "finalize",
            "no analysis audit saw the code as it is now",
            "--check exits 1",
        ):
            self.assertIn(needle, out)
        self.assertIn("4 blocker(s)", out)

    def test_an_analysis_audit_of_older_code_blocks(self):
        area = self._area()
        self._audited(area)
        (area / "scripts" / "02_analyze.py").write_text(
            "print('changed')\n", encoding="utf-8"
        )
        code, out = self._run(area)
        self.assertEqual(code, 1)
        self.assertIn("a change after the audit owes a new one", out)

    def test_the_check_runs_the_areas_script(self):
        area = self._area()
        self.assertIsNone(report_check.check_analysis_script(area, area.parent.parent))
        (area / "scripts" / "02_analyze.py").write_text(
            "import sys\nprint('recheck: numbers not in PROTOCOL')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        failed = report_check.check_analysis_script(area, area.parent.parent) or ""
        self.assertIn("exits 1", failed)
        self.assertIn("numbers not in PROTOCOL", failed)


if __name__ == "__main__":
    unittest.main()
