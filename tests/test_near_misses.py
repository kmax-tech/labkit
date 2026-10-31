"""A label typed short and a flag from another command name what is meant.

In the Qwen pilot's stage C, 23 of 39 `protocol-fill` calls failed on a
shortened label (`Terms` for `Terms of this protocol`) although `--list`
had been read, and `labkit-init exp --type` got argparse's bare line. An
unambiguous prefix now names its field; an ambiguous one and a near miss
are named; an unknown flag is told with the flag meant. Each with its twin:
the full label, and the flag taken.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats.protocol_check import fields  # noqa: E402
from labkit.tools import protocol_fill, scaffold  # noqa: E402
from labkit.tools import protocol_edit


def stamped(kind: str = "compute", model: bool | str = False) -> str:
    """A fresh protocol of KIND as `labkit-init exp` stamps it."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        scaffold.stamp_lab(root, "lab")
        area, _ = scaffold.stamp_area(
            root, "x", repeat_cost="low", kind=kind, model=model
        )
        return next(area.glob("PROTOCOL-*.md")).read_text(encoding="utf-8")


def value_of(text: str, name: str) -> str:
    (f,) = [f for f in fields(text) if f.name == name]
    return f.value


class ShortLabels(unittest.TestCase):
    text = stamped()

    def test_an_unambiguous_prefix_fills_its_field(self):
        short = protocol_edit.fill(self.text, "Terms", "n/a — no coinage")
        full = protocol_edit.fill(
            self.text, "Terms of this protocol", "n/a — no coinage"
        )
        self.assertEqual(short, full)  # the twin: the full label
        self.assertEqual(value_of(short, "terms of this protocol"), "n/a — no coinage")

    def test_the_fill_line_says_which_field_a_prefix_named(self):
        self.assertEqual(
            protocol_edit.as_filled(self.text, "Terms"),
            "Terms → terms of this protocol",
        )
        self.assertEqual(protocol_edit.as_filled(self.text, "Unit"), "Unit")

    def test_a_prefix_of_several_fields_names_them_and_fills_nothing(self):
        text = stamped("apply", "haiku")
        begun = {f.name for f in fields(text) if f.name.startswith("data")}
        self.assertGreater(len(begun), 1, begun)
        with self.assertRaisesRegex(ValueError, r"begins \d+ fields: .*data / scope"):
            protocol_edit.fill(text, "Data", "x")

    def test_a_near_miss_is_named(self):
        with self.assertRaisesRegex(ValueError, "did you mean terms of this protocol"):
            protocol_edit.fill(self.text, "Terms of this protocl", "x")

    def test_the_command_line_fills_by_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(self.text, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = protocol_fill.main([str(p), "Terms=n/a — no coinage"])
            self.assertEqual(rc, 0)
            self.assertIn("filled: Terms → terms of this protocol", out.getvalue())


class UnknownFlags(unittest.TestCase):
    def refusal(self, *argv: str) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            scaffold.main(list(argv))
        self.assertEqual(cm.exception.code, 2)
        return err.getvalue()

    def test_type_is_told_as_a_protocol_field_and_kind_named(self):
        said = self.refusal("exp", "foo", "--type", "exploratory")
        self.assertIn("protocol-fill <PROTOCOL> type=exploratory", said)
        self.assertIn("--kind compute|fit|apply", said)

    def test_a_near_miss_names_the_flag(self):
        self.assertIn(
            "did you mean --kind?", self.refusal("exp", "foo", "--knd", "fit")
        )

    def test_the_flag_meant_is_taken(self):
        """The twin: `--kind` stamps."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scaffold.stamp_lab(root, "lab")
            out = io.StringIO()
            old = Path.cwd()
            os.chdir(root)
            try:
                with contextlib.redirect_stdout(out):
                    rc = scaffold.main(
                        ["exp", "foo", "--kind", "compute", "--repeat-cost", "low"]
                    )
            finally:
                os.chdir(old)
            self.assertEqual(rc, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
