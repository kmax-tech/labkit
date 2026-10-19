"""One reading of the protocol id for every consumer (review 2026-10-06).

runlog, intent-check and protocol-check each carried their own regex; they
already disagreed on a malformed id (raw value for a message, None, warning
and unbound run). Since the head is data (TODO 8) the id is `[protocol] id`,
read once by `protocol_block.head`: a malformed id is a BlockError naming
the field for every consumer, a placeholder reads as None (unbound).
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import intent_check  # noqa: E402
from labkit.run import runlog  # noqa: E402
from labkit.formats import protocol_block, protocol_check  # noqa: E402
from protocol_fixture import PID, head  # noqa: E402

# name -> (protocol text, id every consumer reads)
READABLE = {
    "good": (head(), PID),
    "placeholder": (head(id="<protocol-id>"), None),
}
# name -> protocol text every consumer must reject loudly
REJECTED = {
    "no block": "# x\n- **Protocol id:** p-0123456789abcdef\n",
    "malformed": head(id="p-XYZ"),
}


def _bind(text: str) -> dict:
    area = Path(tempfile.mkdtemp())
    (area / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return runlog._protocol_binding(area, None).binding


class Identity(unittest.TestCase):
    def test_consumers_agree_on_a_readable_head(self):
        for name, (text, pid) in READABLE.items():
            with self.subTest(name):
                self.assertEqual(protocol_block.head(text).id, pid)
                self.assertEqual(intent_check.protocol_id_of(text), pid)
                self.assertEqual(_bind(text)["id"], pid)

    def test_consumers_agree_on_rejecting(self):
        for name, text in REJECTED.items():
            with self.subTest(name):
                with self.assertRaises(protocol_block.BlockError):
                    protocol_block.head(text)
                with self.assertRaises(protocol_block.BlockError):
                    intent_check.protocol_id_of(text)
                with self.assertRaises(SystemExit):
                    _bind(text)

    def test_runlog_names_a_malformed_id(self):
        with self.assertRaises(SystemExit) as ctx:
            _bind(REJECTED["malformed"])
        self.assertIn("[protocol] id = 'p-XYZ'", str(ctx.exception))

    def test_runlog_warns_on_an_unstamped_id(self):
        area = Path(tempfile.mkdtemp())
        (area / "PROTOCOL-x.md").write_text(
            READABLE["placeholder"][0], encoding="utf-8"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            runlog._protocol_binding(area, None)
        self.assertIn("carries no stamped id", buf.getvalue())

    def test_no_second_reader_left(self):
        for mod, name in (
            (intent_check, "PROTOCOL_ID_IN_FILE"),
            (runlog, "PROTOCOL_ID_IN_FILE"),
            (protocol_check, "protocol_identity"),
            (protocol_check, "protocol_id_of"),
        ):
            with self.subTest(f"{mod.__name__}.{name}"):
                self.assertFalse(hasattr(mod, name))


if __name__ == "__main__":
    unittest.main()
