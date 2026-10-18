"""The promise tables of a stamped protocol come from one home per kind
(standard 0.20): `scaffold.PROMISE_TABLES`, written into the template's
marker line. The sentences name their constants and the stamped skeleton
reads them, so `unmentioned_constants` is silent on a fresh stamp (Haiku left
`margin`, `max_empty`, `null_band_items` as leftovers under sentences that
never used them, labkit-paper 09, 2026-10-16); a count carries no table."""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import promises, scaffold  # noqa: E402


class PromiseBlock(unittest.TestCase):
    def stamp(self, **kw) -> tuple[Path, str]:
        """A fresh lab repo with one area stamped under KW."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "probe"
        with contextlib.redirect_stdout(io.StringIO()):
            scaffold.stamp_lab(root, "probe", ref=None)
            area, _ = scaffold.stamp_area(root, "foo-bar", **kw)
        return area, (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")

    def test_model_and_estimator_carry_their_tables_and_the_skeleton_reads_them(
        self,
    ) -> None:
        for kw, kind in (
            ({"cost": "minutes", "model": "haiku"}, "apply"),
            ({"cost": "minutes"}, "fit"),
            ({"cost": "seconds", "model": "haiku"}, "apply"),
        ):
            with self.subTest(kind=kind, **kw):
                area, proto = self.stamp(**kw)
                self.assertNotIn(scaffold.PROMISE_MARK, proto)
                block = promises.parse_block(proto)
                assert block is not None
                expected = {
                    k: v
                    for *_, constants in scaffold.PROMISE_TABLES[kind]
                    for k, v in constants.items()
                }
                self.assertEqual(promises.all_constants(block), expected)
                self.assertEqual(promises.unmentioned_constants(block, area), [])
                script = (area / "scripts" / "01_measure.py").read_text(
                    encoding="utf-8"
                )
                for name in expected:
                    self.assertRegex(
                        script, rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])"
                    )

    def test_a_count_carries_no_table_and_no_sentence_owing_one(self) -> None:
        _, proto = self.stamp(cost="seconds")
        self.assertIsNone(promises.parse_block(proto))
        self.assertNotIn("[[promise]]", proto)
        self.assertNotIn("The promises as data", proto)
        self.assertNotIn(scaffold.PROMISE_MARK, proto)
        block = re.search(r"```toml\n(.*?)```", proto, re.S)
        assert block is not None
        self.assertTrue(block.group(1).rstrip().endswith('preflight_audit = ""'))

    def test_the_tables_are_the_one_home(self) -> None:
        """The template holds the marker, never a table of its own."""
        tmpl = scaffold.template(scaffold.PROTOCOL_TEMPLATE.name)
        self.assertNotIn("[[promise]]\n", tmpl)
        self.assertIn(scaffold.PROMISE_MARK, tmpl)
        self.assertEqual(scaffold.promise_tables("count"), "")
        for kind in ("apply", "fit"):
            self.assertEqual(scaffold.promise_tables(kind).count("[[promise]]"), 3)

    def test_a_template_without_the_marker_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            scaffold.promise_block_for("```toml\n[protocol]\n```\n", "apply")


if __name__ == "__main__":
    unittest.main()
