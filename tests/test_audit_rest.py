"""The remaining audit points of 0.48 (review 2026-10-07), one test each."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit import code_check, promises, protocol_block, protocol_check, usability
from protocol_fixture import head

C1 = """[[promise]]
id = "C1"
key = "c1_pass"
sentence = "mean >= min_mean"
scope = ["scripts/m.py:evaluate"]
constants = { min_mean = 1.5 }
"""


class Parser(unittest.TestCase):
    def test_numbered_items_are_fields(self):
        names = [
            f.name
            for f in protocol_check.fields(
                "1. **Unit:** one file\n2) **Data / scope:** d\n"
            )
        ]
        self.assertEqual(names, ["unit", "data / scope"])

    def test_a_field_inside_a_comment_is_not_present(self):
        text = "<!--\n- **Question / hypothesis:** hidden\n-->\n- **Unit:** u\n"
        self.assertEqual([f.name for f in protocol_check.fields(text)], ["unit"])


class Head(unittest.TestCase):
    def test_a_numeric_standard_says_string(self):
        with self.assertRaises(protocol_block.BlockError) as cm:
            protocol_block.head(head().replace('standard = "0.19"', "standard = 0.18"))
        self.assertIn('a string, "0.19"', str(cm.exception))


class Scopes(unittest.TestCase):
    def test_an_absolute_scope_is_refused(self):
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_block(
                head(promises=C1.replace("scripts/m.py:evaluate", "/etc/hosts"))
            )
        self.assertIn("absolute", str(cm.exception))

    def test_a_relative_scope_outside_the_area_stays_allowed(self):
        block = promises.parse_block(
            head(promises=C1.replace("scripts/m.py", "../../lib/m.py"))
        )
        assert block is not None
        self.assertEqual(block.promises[0].scope, ("../../lib/m.py:evaluate",))


class ConstantCopies(unittest.TestCase):
    """Static evidence: a literal copy of a declared constant warns; reading
    it from the block does not (Durchstich 2026-10-07)."""

    def findings(self, source: str) -> list[str]:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "scripts").mkdir()
            (area / "scripts" / "m.py").write_text(source)
            block = promises.parse_block(head(promises=C1))
            assert block is not None
            return code_check.constant_copies(
                area, area / "PROTOCOL-x.md", block.promises[0]
            )

    def test_a_literal_copy_warns_and_names_the_way_out(self):
        (f,) = self.findings(
            "min_mean = 1.4\n\ndef evaluate(r):\n    return r >= min_mean\n"
        )
        self.assertTrue(f.startswith("WARNING"), f)
        self.assertIn("min_mean = 1.4", f)
        self.assertIn("the block says 1.5", f)
        self.assertIn("promises.constants", f)

    def test_reading_the_block_is_silent(self):
        self.assertEqual(
            self.findings(
                "from labkit import promises\n"
                "min_mean = promises.constants(PROTOCOL, 'C1')['min_mean']\n"
            ),
            [],
        )

    def test_an_equal_copy_still_warns(self):
        (f,) = self.findings("min_mean = 1.5\n")
        self.assertIn("the same value", f)


class Usability(unittest.TestCase):
    def test_an_unreadable_run_is_a_sentence(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "runs" / "2026-10-07T10-00-00_ab12"
            run.mkdir(parents=True)
            (run / "config.json").write_text("{")
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stdout(io.StringIO()):
                    usability.latest_run(Path(d))
            self.assertIn("unreadable run metadata", str(cm.exception))


class ReadLines(unittest.TestCase):
    """The analysis audit's READ lines (protocol readability) are printed
    with the report but are no findings and enter no verdict."""

    def test_read_lines_are_not_findings(self):
        from labkit import audit

        report = (
            "WARNING · scripts/m.py:3 · x · y · new class · z\n"
            "READ · PROTOCOL-x.md:70 · beschaffung-09 and beschaffungsantrag-09 · one spelling\n"
            "verdict: 0 blockers, 1 warnings, 0 notes\n"
            "scope:\nscripts/m.py\n"
        )
        parsed = audit.parse(report)
        self.assertEqual([g for g, _ in parsed["findings"]], ["WARNING"])
        self.assertEqual(parsed["verdict"], (0, 1, 0))


if __name__ == "__main__":
    unittest.main()
