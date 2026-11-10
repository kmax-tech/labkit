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


class ARepeatWhoseParentDoesNotCompare(unittest.TestCase):
    """`runlog._repeat_draw`: when the comparison with the parent run
    cannot read a record (`answering_run.repeat_mismatch` raises
    RunConfigError), the repeat is refused naming the parent — never drawn
    against a parent nobody could compare. The parent, its draw number and
    the comparison are stubbed: the refusal is what is under test."""

    def test_an_unreadable_record_refuses_the_repeat(self):
        from types import SimpleNamespace
        from unittest import mock

        from labkit.formats.runs import RunConfigError
        from labkit.run import runlog

        prepared = SimpleNamespace(
            derived_from=None,
            config={},
            bound=SimpleNamespace(binding={}),
            promises=None,
        )
        with (
            mock.patch.object(runlog, "_repeat_parent", return_value=object()),
            mock.patch.object(runlog, "next_draw", return_value=2),
            mock.patch.object(runlog, "script_sha", return_value="ab12"),
            mock.patch.object(
                runlog,
                "repeat_mismatch",
                side_effect=RunConfigError("r1/config.json: not JSON"),
            ),
            self.assertRaises(SystemExit) as cm,
        ):
            runlog._repeat_draw(Path("area"), "r1", False, prepared, {}, {})  # type: ignore[arg-type] — a stand-in for Prepared
        said = str(cm.exception)
        self.assertTrue(
            said.startswith("runlog: repeat_of='r1': r1/config.json: not JSON"), said
        )
        self.assertIn("git checkout", said)


class TheDetachedSupervisorsUsage(unittest.TestCase):
    """`detached.main`, started by `runlog start` only: a command line
    without its four arguments and the `--` before the command is refused
    with the usage, before anything is supervised."""

    def test_a_command_line_without_the_separator_is_refused(self):
        from labkit.run import detached

        for argv in ([], ["3", "area", "u", "log", "python", "x.py"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as cm:
                detached.main(argv)
            self.assertTrue(
                str(cm.exception).startswith("usage: python -P -m labkit.run.detached")
            )


if __name__ == "__main__":
    unittest.main()
