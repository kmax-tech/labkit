"""Rule tests of `run_record_check`'s pure checks: each condition from typed
data in memory, its violation and its valid twin (docs/architecture.md,
"Checks and their tests"). The gate that composes them is finalize
(`tests/test_finalize_steps.py` for its stations). The other checks of a
finished run have their own rule tests: `tests/test_rules_run_code_check.py`,
`tests/test_rules_model_check.py`, `tests/test_rules_row_check.py`,
`tests/test_rules_kept_number_check.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.checks.run_record_check import (
    output_record_findings,
    SourceNow,
    source_finding,
)
from labkit.formats.gate import (
    BLOCKER,
    DEVIATION,
    GUARANTEED,
    NOT_EXECUTABLE,
    OPEN_RULE,
    TECHNICAL_RULE,
    cited_rule,
    RuleAssignment,
)
from labkit.formats.runs import (
    OutputEntry,
    OutputNow,
)

pytestmark = pytest.mark.rule

LAB_017 = cited_rule("LAB-017 The number of audits follows the cost tier")


class AnOutputIsTheFileTheRunRecorded(unittest.TestCase):
    """A registered output whose file is gone, was never recorded, or holds
    other bytes than outputs.json records blocks (`output_record_findings`)."""

    AREA = Path("area")
    RECORDED = OutputEntry(Path("out/rows.jsonl"), "ab12", 4)

    def _held(
        self,
        now: str | None,
        recorded: str | None = "ab12",
        stands: bool | None = None,
    ):
        entry = OutputEntry(self.RECORDED.path, recorded, 4)
        if stands is None:
            stands = now is not None or recorded is None
        return pure_call(
            output_record_findings, [OutputNow(entry, stands, now)], "r1", self.AREA
        )

    def test_a_gone_an_unrecorded_and_a_changed_file_block(self):
        unrecorded = "outputs.json records no sha256 for it"
        # a comparison that cannot run is the technical contract and a check
        # not executable; only compared bytes that differ are a deviation
        cannot_compare = (TECHNICAL_RULE, NOT_EXECUTABLE)
        for now, recorded, stands, said, basis in (
            (None, "ab12", False, "the file is gone", cannot_compare),
            # nothing recorded to compare with: the file is not read, and
            # whether one stands at the path now does not change the cause
            (None, None, True, unrecorded, cannot_compare),
            (None, None, False, unrecorded, cannot_compare),
            (
                "cd34" + "0" * 60,
                "ab12",
                True,
                "its sha256 cd34 is not the recorded ab12",
                (OPEN_RULE, DEVIATION),
            ),
        ):
            with self.subTest(said=said, stands=stands):
                (f,) = self._held(now, recorded, stands)
                self.assertEqual((f.grade, f.evidence_kind), (BLOCKER, GUARANTEED))
                self.assertEqual((f.rule, f.outcome), basis)
                self.assertEqual(
                    f.text, f"out/rows.jsonl: not the file run r1 recorded — {said}"
                )
                self.assertIn("measure anew", f.fix or "")

    def test_only_a_gone_file_may_be_restored_and_only_to_the_recorded_bytes(self):
        """Restoring is a way out where nothing stands to be overwritten
        and a checksum holds the restored file; it is not told as a repair
        without loss."""
        (gone,) = self._held(None, "ab12", False)
        self.assertIn("restore the file", gone.fix or "")
        self.assertIn("sha256 ab12", gone.fix or "")
        self.assertIn("rows written to the file after the run", gone.fix or "")
        for now, recorded, stands in (
            (None, None, False),  # no checksum a restored file could be held to
            ("cd34" + "0" * 60, "ab12", True),  # a restore would overwrite it
        ):
            with self.subTest(recorded=recorded):
                (f,) = self._held(now, recorded, stands)
                self.assertNotIn("restore", f.fix or "")

    def test_why_no_sha256_was_recorded_is_the_records_note_not_the_checks_claim(self):
        """A missing sha256 alone does not show that the run ended without
        the file; where runlog noted it, the note is quoted."""
        entry = OutputEntry(
            self.RECORDED.path, None, None, "registered, but absent at end of run"
        )
        (f,) = pure_call(
            output_record_findings, [OutputNow(entry, False, None)], "r1", self.AREA
        )
        self.assertEqual(
            f.text,
            "out/rows.jsonl: not the file run r1 recorded — outputs.json records "
            'no sha256 for it; the record notes: "registered, but absent at end of run"',
        )

    def test_the_twin_the_recorded_bytes_pass(self):
        self.assertEqual(self._held("ab12" + "0" * 60), [])


class ASourceIsTheBytesTheRunRead(unittest.TestCase):
    """A run's source at low repeat cost: gone, neither tracked nor ignored,
    or other bytes than the record blocks; kept outside git by a rule or
    lying outside the repository is a note (`source_finding`, over the
    facts `source_now` reads)."""

    AREA = Path("area")
    SOURCE = Path("data/items.jsonl")
    SHA = "ab12"

    def _decided(self, **facts: object):
        now = SourceNow(self.SOURCE, self.SHA, **facts)  # type: ignore[arg-type] — the facts per case
        return pure_call(source_finding, now, self.AREA)

    def _blocker(self, rule: RuleAssignment, **facts: object):
        found, note = self._decided(**facts)
        assert found is not None
        self.assertIsNone(note)
        self.assertEqual(
            (found.grade, found.evidence_kind, found.rule),
            (BLOCKER, GUARANTEED, rule),
        )
        return found

    def test_a_gone_source_blocks(self):
        f = self._blocker(TECHNICAL_RULE, kind=None)
        self.assertIn("is not at its recorded path on this machine", f.text)
        self.assertIn("git checkout HEAD -- data/items.jsonl", f.fix or "")

    def test_an_untracked_file_blocks_though_its_bytes_match(self):
        f = self._blocker(LAB_017, kind="file", loose=(self.SOURCE,), untracked=True)
        self.assertIn("neither tracked in git nor ignored by a rule", f.text)
        self.assertIn("git add -- data/items.jsonl", f.fix or "")
        self.assertIn("sha256 ab12", f.fix or "")

    def test_an_untracked_directory_names_its_loose_files(self):
        loose = tuple(Path("data/d") / f"{n}.txt" for n in "abcd")
        f = self._blocker(LAB_017, kind="dir", loose=loose, untracked=True)
        self.assertIn("4 file(s) under it", f.text)
        self.assertIn(", …", f.text)
        self.assertIn(
            "git add -- data/d/a.txt data/d/b.txt data/d/c.txt data/d/d.txt",
            f.fix or "",
        )

    def test_other_bytes_block(self):
        f = self._blocker(
            LAB_017,
            kind="file",
            drift="its sha256 is now cd34",
        )
        self.assertIn("is not the bytes the run read: its sha256 is now cd34", f.text)

    def test_a_source_kept_out_by_a_rule_or_outside_the_repo_is_a_note(self):
        found, note = self._decided(
            kind="file", untracked=True, ignore_rules=(".gitignore:3:data/",)
        )
        self.assertIsNone(found)
        self.assertIn(
            "kept outside git by an ignore rule (.gitignore:3:data/)", note or ""
        )
        found, note = self._decided(kind="file", beyond=True)
        self.assertIsNone(found)
        self.assertIn("lies outside the repository", note or "")

    def test_the_twin_a_tracked_source_with_its_bytes_passes(self):
        self.assertEqual(self._decided(kind="file"), (None, None))
