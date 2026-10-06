"""One reading of `Protocol id:` for every consumer (review 2026-10-06).

runlog, intent-check and protocol-check each carried their own regex; they
already disagreed on a malformed id (raw value for a message, None, warning
and unbound run). Now `protocol_check.protocol_identity` reads the field
once: `raw` for the checker that must name a malformed value, `id` for
everything that binds.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import intent_check, protocol_check, runlog  # noqa: E402

GOOD = "p-0123456789abcdef"
CASES = {
    "absent": ("- **Standard:** 0.15\n", None, None),
    "good": (f"- **Protocol id:** {GOOD}\n", GOOD, GOOD),
    "backticked": (f"- **Protocol id:** `{GOOD}`\n", GOOD, GOOD),
    "malformed": ("- **Protocol id:** p-XYZ\n", "p-XYZ", None),
}


class Identity(unittest.TestCase):
    def test_raw_and_id(self):
        for name, (text, raw, pid) in CASES.items():
            with self.subTest(name):
                ident = protocol_check.protocol_identity(text)
                self.assertEqual(ident.raw, raw)
                self.assertEqual(ident.id, pid)
                self.assertEqual(ident.valid, pid is not None)

    def test_consumers_agree(self):
        for name, (text, raw, pid) in CASES.items():
            with self.subTest(name):
                self.assertEqual(protocol_check.protocol_id_of(text), raw)
                self.assertEqual(intent_check.protocol_id_of(text), pid)
                area = Path(tempfile.mkdtemp())
                (area / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    binding = runlog._protocol_binding(area, None)
                self.assertEqual(binding["id"], pid)

    def test_runlog_names_a_malformed_id(self):
        area = Path(tempfile.mkdtemp())
        (area / "PROTOCOL-x.md").write_text(CASES["malformed"][0], encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            runlog._protocol_binding(area, None)
        self.assertIn("malformed `Protocol id: p-XYZ`", buf.getvalue())

    def test_no_second_regex_left(self):
        for mod in (intent_check, runlog):
            with self.subTest(mod.__name__):
                self.assertFalse(hasattr(mod, "PROTOCOL_ID_IN_FILE"))


if __name__ == "__main__":
    unittest.main()
