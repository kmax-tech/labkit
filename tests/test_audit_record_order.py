"""The audit records and failed attempts of an area in the order they were
written: minute, then the number `_create` gave within the minute — by
name, `-2` and `-3` sorted before the minute's first file, and the newest
failed attempt read as the oldest (review 2026-10-20).

    .venv/bin/python -m pytest tests/test_audit_record_order.py
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from labkit.formats import findings

NOW = time.mktime((2026, 10, 20, 14, 3, 0, 0, 0, -1))


class WrittenOrder(unittest.TestCase):
    def setUp(self) -> None:
        self.area = Path(tempfile.mkdtemp())

    def test_three_failed_attempts_of_one_minute_read_in_the_order_written(
        self,
    ) -> None:
        for n in (1, 2, 3):
            findings.write_failed(
                self.area,
                "preflight",
                "opus",
                "s" * 12,
                "b" * 12,
                findings.ATTEMPT_TIMEOUT_S,
                f"attempt {n}",
                "labkit-audit x",
                now=NOW,
            )
        self.assertEqual(
            [f.error for f in findings.failed_attempts(self.area)],
            ["attempt 1", "attempt 2", "attempt 3"],
        )
        newest = findings.audit_unavailable(self.area, "s" * 12, "preflight", "b" * 12)
        assert newest is not None
        self.assertEqual(newest.error, "attempt 3")

    def test_records_of_one_minute_read_in_the_order_written(self) -> None:
        for n in (1, 2, 3, 10):
            findings.write(
                self.area,
                "preflight",
                "opus",
                f"{n:012d}",
                "b" * 12,
                (0, 0, 0),
                [],
                now=NOW,
            )
        self.assertEqual(
            [r.scope_sha for r in findings.area_records(self.area)],
            [f"{n:012d}" for n in (1, 2, 3, 10)],
        )

    def test_a_file_of_another_name_is_said_not_placed(self) -> None:
        (self.area / "audits").mkdir()
        (self.area / "audits" / "my-notes.toml").write_text("x = 1\n")
        with self.assertRaisesRegex(findings.FindingsError, "my-notes.toml"):
            findings.area_records(self.area)


class Counts(unittest.TestCase):
    """blockers = -1 wrote, read and passed the coverage check (review
    2026-10-20): a count is a non-negative integer, held alike on write and
    read."""

    def setUp(self) -> None:
        self.area = Path(tempfile.mkdtemp())

    def test_a_negative_count_is_refused_on_write(self) -> None:
        for verdict in ((-1, 0, 0), (0, -2, 0), (0, 0, -3)):
            with self.subTest(verdict=verdict):
                with self.assertRaisesRegex(ValueError, "non-negative"):
                    findings.write(
                        self.area,
                        "preflight",
                        "opus",
                        "s" * 12,
                        "b" * 12,
                        verdict,
                        [],
                        now=NOW,
                    )

    def test_a_negative_count_is_refused_on_read(self) -> None:
        path = findings.write(
            self.area, "preflight", "opus", "s" * 12, "b" * 12, (0, 0, 0), [], now=NOW
        )
        path.write_text(path.read_text().replace("blockers = 0", "blockers = -1"))
        with self.assertRaisesRegex(findings.FindingsError, "non-negative"):
            findings.area_records(self.area)

    def test_twin_zero_counts_write_and_read(self) -> None:
        findings.write(
            self.area, "preflight", "opus", "s" * 12, "b" * 12, (0, 0, 2), [], now=NOW
        )
        self.assertEqual(len(findings.area_records(self.area)), 1)


if __name__ == "__main__":
    unittest.main()
