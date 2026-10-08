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


class ReadmePlaceholders(unittest.TestCase):
    def test_a_stamped_blank_is_named_and_a_filled_readme_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "README.md").write_text(
                "# x\n\n**Die eine Frage.** <ein Satz — dieselbe Frage wie im\n"
                "PROTOCOL-Intent; braucht sie ein und, sind es zwei>\n\nok <3\n"
            )
            got = finalize.readme_placeholders(area)
            self.assertEqual(len(got), 1)
            self.assertIn("README.md:3", got[0])  # a blank that wraps lines
            (area / "README.md").write_text("# x\n\n**Die eine Frage.** Zählt es?\n")
            self.assertEqual(finalize.readme_placeholders(area), [])

    def test_no_readme_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(finalize.readme_placeholders(Path(d)), [])


if __name__ == "__main__":
    unittest.main()
