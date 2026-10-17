"""A registered constant that no sentence names and no scope file reads (2026-10-17, plan P step C3).

Three Haiku protocols (labkit-paper area 09, 2026-10-16) kept the stamp's
`margin`, `max_empty` and `null_band_items` under sentences that never used
them, one of them with `margin = 0.70` re-read as a threshold. runlog holds a
constant to the run's config; this holds it to the sentence and the code —
static evidence, a warning, never a blocker.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import promises, protocol_check  # noqa: E402
from protocol_fixture import head  # noqa: E402
from test_protocol_check import PILOT_FIELDS  # noqa: E402

BLOCK = """\
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "accuracy is at least the null lane's plus margin"
scope = ["scripts/01_measure.py"]
constants = { margin = 0.25 }

[[promise]]
id = "A1"
key = "a1_pass"
sentence = "every item gets an answer"
scope = ["scripts/01_measure.py"]
constants = { max_empty = 0 }

[[promise]]
id = "A2"
key = "a2_pass"
sentence = "the null lane sits at chance"
scope = ["scripts/01_measure.py:evaluate_rows"]
constants = { null_band_items = 1 }
"""
SCRIPT = """\
def evaluate_rows(rows, cfg):
    empty = sum(1 for r in rows if not r["answer"])
    return {"a1_pass": empty <= cfg.max_empty, "c1_pass": True, "a2_pass": True}


def elsewhere(cfg):
    return cfg.null_band_items
"""


def area_with(script: str = SCRIPT) -> Path:
    area = Path(tempfile.mkdtemp())
    (area / "scripts").mkdir()
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    return area


def block() -> promises.PromiseTables:
    parsed = promises.parse_block(
        '```toml\n[protocol]\nid = "p-0123456789abcdef"\n' + BLOCK + "```\n"
    )
    assert parsed is not None
    return parsed


class UnmentionedConstants(unittest.TestCase):
    def test_named_by_the_sentence_or_read_by_the_scope_is_silent_else_named(self):
        # margin: in the sentence; max_empty: read by the scope file;
        # null_band_items: read only OUTSIDE the declared function → named
        [line] = promises.unmentioned_constants(block(), area_with())
        self.assertIn("A2: constant `null_band_items`", line)
        self.assertIn("scripts/01_measure.py:evaluate_rows", line)
        self.assertIn("static evidence", line)

    def test_read_inside_the_declared_function_is_silent(self):
        inside = SCRIPT.replace(
            '"a2_pass": True}', '"a2_pass": abs(len(rows) // 2) <= cfg.null_band_items}'
        )
        self.assertEqual(promises.unmentioned_constants(block(), area_with(inside)), [])

    def test_a_word_not_a_substring(self):
        """`margin` inside `margin_of_error` is another name."""
        text = BLOCK.replace("plus margin", "plus the margin_of_error")
        parsed = promises.parse_block(
            '```toml\n[protocol]\nid = "p-0123456789abcdef"\n' + text + "```\n"
        )
        assert parsed is not None
        lines = promises.unmentioned_constants(parsed, area_with())
        self.assertTrue(any("C1: constant `margin`" in ln for ln in lines))

    def test_a_missing_scope_file_is_loud(self):
        with self.assertRaises(promises.PromiseError):
            promises.unmentioned_constants(block(), Path(tempfile.mkdtemp()))

    def test_protocol_check_prints_the_warning_and_does_not_block(self):
        area = area_with()
        p = area / "PROTOCOL-x.md"
        p.write_text(
            "# x\n\n" + head(cost="minutes", promises=BLOCK) + "\n" + PILOT_FIELDS,
            encoding="utf-8",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_check.main([str(p)])
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn("WARNING: A2: constant `null_band_items`", out)
        self.assertNotIn("constant `margin`", out)
        # the twin: the sentence names it — silent
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                "the null lane sits at chance",
                "the null lane sits within null_band_items of chance",
            ),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            protocol_check.main([str(p)])
        self.assertNotIn("null_band_items", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
