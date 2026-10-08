"""finalize's named decisions, each testable alone (CS-006 One function, one thing)."""

import tempfile
import unittest
from pathlib import Path

from labkit import finalize


class Steps(unittest.TestCase):
    def test_a_cited_run_that_is_not_the_answering_one_blocks(self):
        run = Path("/x/runs/2026-10-07T10-00-00_aa11")
        text = "- **Answer to the question:** 0.91 (2026-10-07T09-00-00_bb22)\n"
        mismatch = finalize.cited_run_mismatch(text, run)
        assert mismatch is not None
        self.assertIn("2026-10-07T09-00-00_bb22", mismatch)

    def test_citing_the_answering_run_or_none_passes(self):
        run = Path("/x/runs/2026-10-07T10-00-00_aa11")
        cites_it = "- **Answer to the question:** 0.91 (2026-10-07T10-00-00_aa11)\n"
        self.assertIsNone(finalize.cited_run_mismatch(cites_it, run))
        self.assertIsNone(finalize.cited_run_mismatch("no run cited\n", run))

    def test_two_protocols_and_none_named_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-a.md").write_text("x")
            (area / "PROTOCOL-b.md").write_text("x")
            self.assertIsNone(finalize.choose_protocol(area, None))
            self.assertEqual(
                finalize.choose_protocol(area, area / "PROTOCOL-a.md"),
                area / "PROTOCOL-a.md",
            )


if __name__ == "__main__":
    unittest.main()
