"""finalize's named decisions, each testable alone (CS-006 One function, one thing)."""

import tempfile
import unittest
from pathlib import Path

from labkit import finalize, repo


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
            self.assertIsNone(repo.choose_protocol(area, None, "finalize"))
            self.assertEqual(
                repo.choose_protocol(area, area / "PROTOCOL-a.md", "finalize"),
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


ROUTE = (
    "<!-- labkit:route -->\n**Nachvollziehen.**\n"
    "- Vertrag und berichtete Antwort: `PROTOCOL-a.md`\n"
    "- Läufe und Herkunft: `runlog .`\n"
    "- Wirksame Werte: `labkit-params .`\n"
    "- Entscheidung der Kennungen: `scripts/01_measure.py:evaluate_rows`\n"
    "- Unveränderlicher Beleg: `config.json` des gewählten Laufs unter `runs/`\n"
    "<!-- /labkit:route -->\n"
)


class ReadmeRoute(unittest.TestCase):
    def _area(
        self,
        d: str,
        readme: str,
        script: str = "def evaluate_rows(rows):\n    return {}\n",
    ) -> Path:
        area = Path(d)
        (area / "README.md").write_text(readme, encoding="utf-8")
        (area / "scripts").mkdir()
        (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
        return area

    def test_the_stamped_route_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, "# x\n\n" + ROUTE)
            self.assertEqual(finalize.readme_route(area, "PROTOCOL-a.md"), [])
            # the markers are HTML comments, not stamped blanks
            self.assertEqual(finalize.readme_placeholders(area), [])

    def test_no_block_is_one_warning(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, "# x\n\nDie Zahlen entstehen in comparison.py.\n")
            got = finalize.readme_route(area, "PROTOCOL-a.md")
            self.assertEqual(len(got), 1)
            self.assertIn("no <!-- labkit:route -->", got[0])

    def test_a_missing_station_or_wrong_protocol_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE.replace("`labkit-params .`", "`params`"))
            self.assertEqual(
                finalize.readme_route(area, "PROTOCOL-b.md"),
                [
                    "README.md route: does not name PROTOCOL-b.md",
                    "README.md route: does not name labkit-params",
                ],
            )

    def test_a_script_without_evaluate_rows_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE, script="def evaluate(rows):\n    return {}\n")
            self.assertEqual(
                finalize.readme_route(area, "PROTOCOL-a.md"),
                ["README.md route: scripts/01_measure.py defines no evaluate_rows"],
            )

    def test_no_readme_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(finalize.readme_route(Path(d), "PROTOCOL-a.md"), [])


if __name__ == "__main__":
    unittest.main()
