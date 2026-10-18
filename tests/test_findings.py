"""Audit findings as data (2026-10-12): written by labkit-audit, decided by the person, read by preflight."""

import tempfile
import unittest
from pathlib import Path

from labkit import findings

TWO = [
    ("BLOCKER", "BLOCKER · a.py:1 · x · y · LAB-038 What the prompt demands · z"),
    ("WARNING", "WARNING · b.py:2 · x · y · LAB-019 The stamp covers everything · z"),
]


def area_with(
    records: list[tuple[str, list[tuple[str, str]]]], at: Path | None = None
) -> Path:
    area = at or Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    area.mkdir(parents=True, exist_ok=True)
    for i, (mode, rows) in enumerate(records):
        findings.write(
            area,
            mode,
            "opus",
            "abc123def456",
            (
                sum(1 for g, _ in rows if g == "BLOCKER"),
                sum(1 for g, _ in rows if g == "WARNING"),
                0,
            ),
            rows,
            now=1_700_000_000 + 60 * i,
        )
    return area


def set_status(path: Path, n: int, status: str, reason: str = "") -> None:
    """Edit the n-th finding the way the person does: status and reason."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("[[finding]]")
    block = (
        parts[n]
        .replace('status = "open"', f'status = "{status}"')
        .replace('reason = ""', f'reason = "{reason}"')
    )
    parts[n] = block
    path.write_text("[[finding]]".join(parts), encoding="utf-8")


class WriteRead(unittest.TestCase):
    def test_roundtrip_every_finding_starts_open(self):
        area = area_with([("preflight", TWO)])
        files = sorted((area / "audits").glob("*.toml"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith("-preflight.toml"))
        rec = findings.read(files[0])
        self.assertEqual(
            (rec.mode, rec.model, rec.scope_sha, rec.verdict),
            ("preflight", "opus", "abc123def456", (1, 1, 0)),
        )
        self.assertEqual([f.grade for f in rec.findings], ["BLOCKER", "WARNING"])
        self.assertEqual([f.status for f in rec.findings], ["open", "open"])
        self.assertEqual(rec.findings[0].text, TWO[0][1])
        self.assertEqual(len(rec.open), 2)

    def test_quotes_and_unicode_survive(self):
        area = area_with(
            [("analysis", [("NOTE", 'NOTE · x · "quoted" · ä · \\ backslash')])]
        )
        rec = findings.area_records(area)[0]
        self.assertEqual(rec.findings[0].text, 'NOTE · x · "quoted" · ä · \\ backslash')

    def test_a_second_audit_in_the_same_minute_does_not_overwrite(self):
        area = Path(tempfile.mkdtemp())
        a = findings.write(
            area, "preflight", "m", "s", (0, 0, 0), [], now=1_700_000_000
        )
        b = findings.write(
            area, "preflight", "m", "s", (0, 0, 0), [], now=1_700_000_000
        )
        self.assertNotEqual(a, b)
        self.assertEqual(len(findings.area_records(area)), 2)

    def test_wrong_mode_or_grade_refuses_to_write(self):
        area = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            findings.write(area, "clarity", "m", "s", (0, 0, 0), [])
        with self.assertRaises(ValueError):
            findings.write(area, "preflight", "m", "s", (0, 0, 0), [("READ", "x")])

    def test_a_verdict_counting_more_than_the_lines_is_refused(self):
        """Two blockers in the verdict, none readable as a line: written, the
        record read as covered with nothing open (audit 2026-10-15)."""
        area = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as cm:
            findings.write(area, "preflight", "m", "s", (2, 0, 0), [])
        self.assertIn("counts 2 blocker(s)", str(cm.exception))
        self.assertEqual(list(area.glob("audits/*")), [])
        # notes are not held; a warning line under a 1-warning verdict is
        findings.write(area, "preflight", "m", "s", (0, 1, 2), [("WARNING", "w")])


class Decisions(unittest.TestCase):
    def test_decided_findings_leave_open(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "fixed")
        set_status(path, 2, "deferred", "own task: the reference line")
        rec = findings.read(path)
        self.assertEqual(len(rec.open), 0)
        self.assertEqual([f.text for f in rec.deferred], [TWO[1][1]])
        self.assertEqual(rec.deferred[0].reason, "own task: the reference line")

    def test_a_decided_status_without_reason_is_loud(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "accepted")
        with self.assertRaises(findings.FindingsError) as cm:
            findings.read(path)
        self.assertIn("owes a reason", str(cm.exception))
        self.assertIn(path.name, str(cm.exception))

    def test_counts_outrunning_the_tables_are_loud_on_read(self):
        """The writer refuses `blockers = 2` without a table; a person editing
        the file can write the same — the reader holds the same line, or the
        record reads as covered with nothing open (review 2026-10-18)."""
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("blockers = 1", "blockers = 2"), encoding="utf-8")
        with self.assertRaises(findings.FindingsError) as cm:
            findings.read(path)
        self.assertIn("counts 2 blocker(s) and 1 warning(s)", str(cm.exception))
        self.assertIn("carries 1 BLOCKER and 1 WARNING", str(cm.exception))
        self.assertIn(path.name, str(cm.exception))
        with self.assertRaises(findings.FindingsError):
            findings.audit_coverage(area, "abc123def456", "preflight")
        # a table cut out of the file is the same loss
        head, _, _ = text.partition("\n[[finding]]")
        path.write_text(head + "\n", encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "carries 0 BLOCKER"):
            findings.read(path)
        # notes are not held, on read as on write
        path.write_text(text.replace("notes = 0", "notes = 5"), encoding="utf-8")
        self.assertEqual(findings.read(path).verdict, (1, 1, 5))

    def test_unknown_status_missing_table_and_bad_toml_are_loud(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "done", "x")
        with self.assertRaisesRegex(findings.FindingsError, "status 'done'"):
            findings.read(path)
        path.write_text(
            '[[finding]]\ngrade = "NOTE"\ntext = "t"\nstatus = "open"\nreason = ""\n'
        )
        with self.assertRaisesRegex(findings.FindingsError, r"no \[audit\] table"):
            findings.read(path)
        path.write_text("not = [toml\n")
        with self.assertRaisesRegex(findings.FindingsError, "not TOML"):
            findings.read(path)
        with self.assertRaises(findings.FindingsError):
            findings.area_records(area)  # the loud file stays loud through the listing


class Repo(unittest.TestCase):
    def test_deferred_elsewhere_names_the_other_area_only(self):
        root = Path(tempfile.mkdtemp()) / "experiments"
        here = area_with([("preflight", TWO)], at=root / "17-here")
        there = area_with([("preflight", TWO)], at=root / "16-there")
        for area in (here, there):
            set_status(
                next((area / "audits").glob("*.toml")), 2, "deferred", "own task"
            )
        found = findings.deferred_elsewhere(here, root)
        self.assertEqual(
            [(a.name, f.text) for a, _, f in found], [("16-there", TWO[1][1])]
        )
        self.assertEqual(findings.deferred_elsewhere(there, root)[0][0].name, "17-here")
        self.assertEqual(findings.area_records(root / "99-none"), [])


class AuditCoverage(unittest.TestCase):
    """A full run at minutes/hours owes a preflight record of the code as it
    is now, every finding decided (2026-10-14: a stamp no audit had seen)."""

    SHA = "abc123def456"

    def test_a_decided_preflight_record_of_the_stamp_covers_it(self):
        area = area_with([("preflight", TWO)])
        (path,) = sorted((area / findings.DIR).glob("*.toml"))
        set_status(path, 1, "fixed")
        set_status(path, 2, "accepted", "spread is a limit")
        self.assertIsNone(findings.audit_coverage(area, self.SHA, "preflight"))

    def test_no_record_another_sha_or_only_an_analysis_record_does_not(self):
        empty = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        empty.mkdir(parents=True)
        self.assertIn(
            "audited: none", findings.audit_coverage(empty, self.SHA, "preflight") or ""
        )
        area = area_with([("preflight", []), ("analysis", [])])
        gap = findings.audit_coverage(area, "0123456789ab", "preflight") or ""
        self.assertIn("no preflight audit saw the code as it is now", gap)
        self.assertIn(f"audited: {self.SHA}", gap)
        analysis_only = area_with([("analysis", [])])
        self.assertIn(
            "audited: none",
            findings.audit_coverage(analysis_only, self.SHA, "preflight") or "",
        )

    def test_an_open_finding_of_the_covering_record_is_named(self):
        area = area_with([("preflight", TWO)])
        self.assertIn(
            "2 finding(s)", findings.audit_coverage(area, self.SHA, "preflight") or ""
        )
