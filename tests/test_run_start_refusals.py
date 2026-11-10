"""Run-start refusals no test named: an area of two protocols and none
named binds no run; a promise block that does not read at an
acknowledged full run's start refuses before any attempt is held to it."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from labkit.formats import protocol_block
from labkit.run import start_check
from protocol_fixture import head, scope_file

#: a promise table whose id is no id: the block does not read
BROKEN_BLOCK = (
    '[[promise]]\nid = 3\nkey = "criterion_1_pass"\nsentence = "x"\nscope = []\n'
)


class TheRunStartRefuses(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_two_protocols_and_none_named_bind_no_run(self):
        for name in ("PROTOCOL-a.md", "PROTOCOL-b.md"):
            (self.area / name).write_text(head(repeat_cost="low"))
        with self.assertRaises(SystemExit) as cm:
            start_check.protocol_binding(self.area, None)
        said = str(cm.exception)
        self.assertIn("2 protocols in", said)
        self.assertIn("nothing would say which one this run belongs to", said)
        self.assertIn("protocol=PROTOCOL", said)

    def test_the_twin_one_named_protocol_binds(self):
        for name in ("PROTOCOL-a.md", "PROTOCOL-b.md"):
            (self.area / name).write_text(head(repeat_cost="low"))
        bound = start_check.protocol_binding(self.area, "PROTOCOL-a.md")
        self.assertIsNotNone(bound.head)

    def test_a_promise_block_that_does_not_read_refuses_the_acknowledged_run(self):
        scope_file(self.area)
        text = head(repeat_cost="high", promises=BROKEN_BLOCK)
        bound = start_check._Bound(
            {"id": "x", "path": "P.md"}, text, protocol_block.head(text)
        )
        with self.assertRaises(SystemExit) as cm:
            start_check._audit_unavailable(self.area, bound)
        self.assertTrue(
            str(cm.exception).startswith("runlog: promise block: "), str(cm.exception)
        )


if __name__ == "__main__":
    unittest.main()
