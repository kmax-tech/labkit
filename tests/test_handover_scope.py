"""What a handover binds and where it writes, without a lab: the journal
lines a report review appends are left out of the binding
(`handovers.review_trace`, `journal_digest`), and the handover's report is
a file report-check holds (`handovers.report_destination`). The handover
written through the commands: tests/test_handovers.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from labkit.formats import handovers, repo


class ReportDestination(unittest.TestCase):
    def test_the_handover_writes_only_where_report_check_looks(self):
        # REPORT.MD is refused: report-check never holds that file
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()  # as git_root gives it
            with self.assertRaises(handovers.HandoverError):
                handovers.report_destination(root, root / "REPORT.MD")
            report = root / "REPORT.md"
            self.assertEqual(handovers.report_destination(root, report), report)


class ReviewTrace(unittest.TestCase):
    """What a report review writes is not handover evidence
    (`handovers.review_trace`, `journal_digest`): the review a registered
    report owes after its handover block must not void the handover."""

    ANALYSIS = '{"event": "started", "id": "2026-11-02T10-00-analysis-ab12", "mode": "analysis"}\n'
    REVIEW = (
        '{"event": "started", "id": "2026-11-02T10-05-report-review-cd34", "mode": "report-review"}\n'
        '{"event": "ended", "id": "2026-11-02T10-05-report-review-cd34", "outcome": "record"}\n'
    )

    ANALYSIS_2 = '{"event": "started", "id": "2026-11-02T10-10-analysis-ef56", "mode": "analysis"}\n'

    def digest(self, text: str) -> str | None:
        """The binding of a journal holding TEXT, as written and as checked."""
        path = Path(tempfile.mkdtemp()) / "attempts.jsonl"
        path.write_text(text, encoding="utf-8")
        (sha,) = repo.blobs_now(path.parent, [path]).values()
        return handovers.journal_digest(path.parent, path, sha, staged=False)

    @staticmethod
    def blob(text: str) -> str:
        """git's blob id of a file holding TEXT."""
        path = Path(tempfile.mkdtemp()) / "attempts.jsonl"
        path.write_text(text, encoding="utf-8")
        (sha,) = repo.blobs_now(path.parent, [path]).values()
        return sha

    def test_the_journal_is_bound_without_the_report_reviews_lines(self):
        """One computation when the handover is written and when it is
        checked: the review's lines added after the handover leave the
        binding as it was (bound by blob id and checked by a digest of
        another kind, every handover after an analysis audit would be void)."""
        bound = self.digest(self.ANALYSIS)
        self.assertEqual(bound, self.blob(self.ANALYSIS))  # the file's own id
        self.assertEqual(self.digest(self.ANALYSIS + self.REVIEW), bound)
        self.assertEqual(self.digest(self.REVIEW + self.ANALYSIS), bound)
        self.assertIsNone(self.digest(self.REVIEW))  # a journal the review began
        torn = "{not json\n"
        self.assertEqual(self.digest(torn + self.REVIEW), self.digest(torn))

    def test_the_twin_other_attempts_move_the_binding(self):
        """Lines of another attempt, before or after the review, are new
        evidence: the binding moves."""
        bound = self.digest(self.ANALYSIS)
        for later in (
            self.ANALYSIS + self.ANALYSIS_2,
            self.ANALYSIS + self.REVIEW + self.ANALYSIS_2,
        ):
            with self.subTest(later=later):
                self.assertNotEqual(self.digest(later), bound)

    def test_only_the_review_record_and_its_answer_are_left_out(self):
        for rel, left_out in (
            ("report-reviews/2026-11-02T10-05-review.toml", True),
            ("answers/2026-11-02T10-05-report-review-cd34.txt", True),
            ("answers/2026-11-02T10-00-analysis-ab12.txt", False),
            ("2026-11-02T10-00-analysis.toml", False),
            ("reviews/2026-11-02T10-05-review.toml", False),
        ):
            with self.subTest(rel=rel):
                self.assertEqual(handovers.review_trace(rel), left_out)
