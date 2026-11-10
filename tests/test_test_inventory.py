"""test_inventory: the layer a test entered through, the site a finding
belongs to, the reach and its standing, and the trace on a real site —
each with its twin."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import run_record_check
from labkit.formats.gate import GateFinding
from labkit.tools import test_inventory as ti
from labkit.tools.check_inventory import NOT_RECORDED, FindingSite

COMMANDS = {"labkit.gates.finalize", "labkit.tools.adopt"}


def site(path: str, line: int, end: int, rule: str = NOT_RECORDED) -> FindingSite:
    """A gate-finding site recording RULE as its assignment (`FindingSite.assignment`)."""
    return FindingSite(
        "labkit.x.f", path, line, end, "finding", "BLOCKER", "guaranteed", (), "w", rule
    )


def event(test: str, path: str, line: int, entry: str) -> ti.Event:
    return ti.Event(test, path, line, entry, False)


class EntryLayer(unittest.TestCase):
    def test_a_console_scripts_main_or_cli_is_a_command(self):
        for entry in ("labkit.gates.finalize.main", "labkit.tools.adopt.cli"):
            self.assertEqual(ti.entry_layer(entry, COMMANDS), ti.COMMAND, entry)

    def test_a_module_run_as_a_script_is_a_command(self):
        self.assertEqual(
            ti.entry_layer("labkit.formats.scope_sha.<module>", COMMANDS), ti.COMMAND
        )

    def test_the_twin_any_other_function_is_its_folders_layer(self):
        for entry, layer in (
            ("labkit.gates.finalize.check_reference", "gate"),
            ("labkit.gates.report_check.Checked.text", "gate"),
            ("labkit.checks.recheck.agree", "check"),
            ("labkit.formats.findings.read", "format"),
            ("labkit.run.runlog.Run.__init__", "run"),
            ("labkit.console_line", "other"),
        ):
            self.assertEqual(ti.entry_layer(entry, COMMANDS), layer, entry)


class SiteAt(unittest.TestCase):
    def test_the_innermost_call_spanning_the_line(self):
        outer = site("labkit/a.py", 10, 20)
        inner = site("labkit/a.py", 12, 14)
        self.assertEqual(ti.site_at("labkit/a.py", 13, [outer, inner]), inner)
        self.assertEqual(ti.site_at("labkit/a.py", 18, [outer, inner]), outer)

    def test_the_twin_another_file_or_line_is_no_site(self):
        s = site("labkit/a.py", 10, 12)
        self.assertIsNone(ti.site_at("labkit/b.py", 11, [s]))
        self.assertIsNone(ti.site_at("labkit/a.py", 13, [s]))


class ReachAndStanding(unittest.TestCase):
    def setUp(self) -> None:
        self.direct = site("labkit/gates/g.py", 5, 6, "LAB-001")
        self.command = site("labkit/gates/g.py", 20, 20, "LAB-001")
        self.unreached = site("labkit/checks/c.py", 3, 3)
        self.sites = [self.direct, self.command, self.unreached]
        self.events = [
            event("tests/test_a.py::T::t1", "labkit/gates/g.py", 6, "labkit.gates.g.f"),
            event(
                "tests/test_e.py::E::t2",
                "labkit/gates/g.py",
                5,
                "labkit.gates.finalize.main",
            ),
            event(
                "tests/test_e.py::E::t2",
                "labkit/gates/g.py",
                20,
                "labkit.gates.finalize.main",
            ),
            event(
                "tests/test_a.py::T::t1", "labkit/gates/g.py", 30, "labkit.gates.g.f"
            ),
        ]

    def test_each_event_counts_for_its_site_and_layer(self):
        r = ti.reach(self.events, self.sites, COMMANDS)
        self.assertEqual(
            {k: v for k, v in r.by_site[("labkit/gates/g.py", 5)].items() if v},
            {
                "gate": {"tests/test_a.py::T::t1"},
                ti.COMMAND: {"tests/test_e.py::E::t2"},
            },
        )
        self.assertEqual(len(r.unmapped), 1)  # line 30 is no site

    def test_the_standing_of_each_site(self):
        r = ti.reach(self.events, self.sites, COMMANDS)
        self.assertEqual(
            [ti.site_standing(r.by_site[(s.path, s.line)]) for s in self.sites],
            ["direct", "only through commands", "unreached"],
        )

    def test_the_lowest_layer_is_the_narrowest_reached(self):
        self.assertEqual(
            ti.lowest_layer({ti.COMMAND: {"a"}, "gate": {"b"}, "check": {"c"}}), "check"
        )
        self.assertEqual(ti.lowest_layer({ti.COMMAND: {"a"}}), ti.COMMAND)
        self.assertIsNone(ti.lowest_layer({"gate": set()}))

    def test_the_rendered_counts(self):
        r = ti.reach(self.events, self.sites, COMMANDS)
        text = ti.render_test_inventory(
            self.sites, r, {"tests/test_e.py"}, "3 passed", ["tests/test_x.py::t"]
        )
        self.assertIn("| direct | 1 |", text)
        self.assertIn("| only through commands | 1 |", text)
        self.assertIn("| unreached | 1 |", text)
        self.assertIn("| gate | 1 |", text)  # the direct site, reached through a gate
        self.assertIn("| LAB-001 | 2 | 1 | 1 | 0 | 2 |", text)
        self.assertIn(f"| {NOT_RECORDED} | 1 | 0 | 0 | 1 | 0 |", text)
        self.assertIn("Unmapped findings (built where no site stands): 1.", text)
        self.assertIn("| `tests/test_e.py` | yes | 1 |", text)
        self.assertIn("| `labkit/gates/g.py:30` | 1 |", text)
        self.assertIn("- `tests/test_x.py::t`", text)


class Trace(unittest.TestCase):
    """The trace on a real site: a finding a check builds is recorded with
    this test's name, the check's line and the entry the test called; the
    twin: without the folder named nothing is wrapped."""

    @unittest.skipIf(
        os.environ.get(ti.TRACE_ENV),
        "the suite runs under the inventory's own trace: the wrapper would wrap itself",
    )
    def test_a_finding_built_by_a_check_is_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "data.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            with (
                mock.patch.object(GateFinding, "__init__", GateFinding.__init__),
                mock.patch.dict(os.environ, {ti.TRACE_ENV: d}),
                mock.patch.object(ti, "_out", opened := []),
            ):
                ti.install_trace()
                run_record_check._gone(source, Path(d))
            opened[1].close()
            (line,) = Path(d, f"{os.getpid()}.jsonl").read_text().splitlines()
        record = json.loads(line)
        self.assertEqual(record["path"], "labkit/checks/run_record_check.py")
        self.assertEqual(record["entry"], "labkit.checks.run_record_check._gone")
        self.assertIn(
            "Trace::test_a_finding_built_by_a_check_is_recorded", record["test"]
        )
        self.assertFalse(record["subprocess"])

    def test_the_twin_without_the_folder_nothing_is_wrapped(self):
        before = GateFinding.__init__
        with mock.patch.dict(os.environ, {ti.TRACE_ENV: ""}):
            ti.install_trace()
        self.assertIs(GateFinding.__init__, before)


if __name__ == "__main__":
    unittest.main()
