"""Branches of code-check and notes-check no test reached, as tests of the
function that holds them: a scope file that does not parse leaves the
quality-check read check undone (a warning, not executed); the bundle
names a file it could not read; a note that cannot be opened warns,
check not executable."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import code_check, notes_check
from labkit.formats import promises
from labkit.formats.gate import NOT_EXECUTABLE, OPEN_RULE, VIOLATED, WARNING, Findings
from protocol_fixture import head


class QualityCheckReadsNotDone(unittest.TestCase):
    def test_a_file_that_does_not_parse_leaves_the_check_undone(self):
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        key = next(p.key for p in block.promises if p.kind == "quality-check")
        with (
            mock.patch.object(code_check, "area_files", return_value=[Path("x.py")]),
            mock.patch.object(code_check, "imported_repo_helpers", return_value=[]),
            mock.patch.object(
                code_check, "_key_reads", side_effect=ValueError("x.py: invalid syntax")
            ),
        ):
            (f,) = code_check.quality_check_reads(
                Path("area"),
                Path("area/PROTOCOL-x.md"),
                block,
                {key: ("scripts/01_measure.py:3",)},
            )
        self.assertEqual(
            (f.grade, f.check_outcome, f.rule), (WARNING, VIOLATED, OPEN_RULE)
        )
        self.assertIn(
            "quality-check keys: read check not done — x.py: invalid syntax", f.text
        )

    def test_the_twin_no_quality_check_key_written_owes_nothing(self):
        block = promises.parse_block(head(repeat_cost="low"))
        assert block is not None
        self.assertEqual(
            code_check.quality_check_reads(Path("area"), Path("area/P.md"), block, {}),
            [],
        )


class TheBundleNamesWhatItCouldNotRead(unittest.TestCase):
    def test_an_unreadable_file_of_the_bundle_warns_at_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(head(repeat_cost="low"))
            bundle = area / "bundle.md"
            bundle.write_text("x")
            with (
                mock.patch.object(code_check, "code_findings", return_value=[]),
                mock.patch.object(
                    code_check, "write_bundle", return_value=(1, ["scripts/x.py"])
                ),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                code_check.main([str(area), "--bundle", str(bundle)])
        self.assertIn(
            "bundle: scripts/x.py could not be read — the reader sees", out.getvalue()
        )


class ANoteThatCannotBeOpened(unittest.TestCase):
    def test_it_warns_not_executable_and_the_others_are_checked(self):
        told: list[str] = []
        with mock.patch.object(
            notes_check, "check_file", side_effect=PermissionError("refused")
        ):
            code = notes_check.check_notes([Path("notes/a.md")], tell=told.append)
        self.assertEqual(code, 0)
        self.assertTrue(
            any("notes/a.md: not readable (refused)" in t for t in told), told
        )
        found = Findings(tell=None)
        with (
            mock.patch.object(notes_check, "Findings", return_value=found),
            mock.patch.object(
                notes_check, "check_file", side_effect=PermissionError("refused")
            ),
        ):
            notes_check.check_notes([Path("notes/a.md")], tell=lambda _: None)
        (f,) = found.found
        self.assertEqual(
            (f.grade, f.check_outcome, f.rule), (WARNING, NOT_EXECUTABLE, OPEN_RULE)
        )


if __name__ == "__main__":
    unittest.main()
