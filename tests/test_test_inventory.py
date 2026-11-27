"""test_inventory: the layer a test entered through, the site a finding
belongs to, the reach and its standing, and the trace on a real site —
each with its twin."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import file_record_check
from labkit.formats import console
from labkit.formats.gate import GateFinding
from labkit.run import start_check
from labkit.tools import test_inventory as ti
from labkit.tools.check_inventory import NOT_RECORDED, FindingSite

COMMANDS = {"labkit.gates.finalize", "labkit.tools.adopt"}


def site(path: str, line: int, end: int, rule: str = NOT_RECORDED) -> FindingSite:
    """A gate-finding site recording RULE as its assignment (`FindingSite.assignment`)."""
    return FindingSite(
        "labkit.x.f", path, line, end, "finding", "BLOCKER", "guaranteed", (), "w", rule
    )


def end_exit_trace() -> None:
    """Take the trace of exits out of this process again: no events, no
    callback, the tool id free for the next test."""
    monitoring = sys.monitoring
    monitoring.set_events(ti.MONITOR_TOOL, 0)
    monitoring.register_callback(ti.MONITOR_TOOL, monitoring.events.RAISE, None)
    monitoring.free_tool_id(ti.MONITOR_TOOL)


def exit_site(path: str, line: int) -> FindingSite:
    """An exit site: a `raise SystemExit(<message>)` on one line."""
    return FindingSite(
        "labkit.x.g", path, line, line, "exit", "exit", "none", (), "w", NOT_RECORDED
    )


def event(
    test: str, path: str, line: int, entry: str, channel: str = ti.FINDING
) -> ti.Event:
    return ti.Event(test, path, line, entry, False, channel)


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
            ("labkit.gates.finalize.station_reference", "gate"),
            ("labkit.gates.report_check.Checked.text", "gate"),
            ("labkit.checks.recheck.require_agreement", "check"),
            ("labkit.formats.audit_records.read", "format"),
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
            self.sites,
            r,
            {"tests/test_e.py"},
            {"tests/test_a.py::T::t1"},
            "3 passed",
            ["tests/test_x.py::t"],
        )
        self.assertIn("| direct | 1 | 0 |", text)
        self.assertIn("| only through commands | 1 | 0 |", text)
        self.assertIn("| unreached | 1 | 0 |", text)
        self.assertIn("They reach 1 of 3 gate-finding sites and 0 of 0 exit", text)
        self.assertIn(
            "| `labkit/gates/g.py:5` | `labkit.x.f` | finding | direct | 2 | 1 | "
            "`tests/test_a.py` 1, `tests/test_e.py` 1 |",
            text,
        )
        self.assertIn(
            "| `labkit/checks/c.py:3` | `labkit.x.f` | finding | unreached | 0 | 0 | — |",
            text,
        )
        # the direct site, reached through a gate; no exit site here
        self.assertIn("| gate | 1 | 0 |", text)
        self.assertIn("| LAB-001 | 2 | 1 | 1 | 0 | 2 |", text)
        self.assertIn(f"| {NOT_RECORDED} | 1 | 0 | 0 | 1 | 0 |", text)
        self.assertIn(
            "Unmapped findings and exits (told where no site stands): 1.", text
        )
        self.assertIn("| `tests/test_e.py` | yes | 1 |", text)
        self.assertIn("| `labkit/gates/g.py:30` | finding | 1 |", text)
        self.assertIn("- `tests/test_x.py::t`", text)


class ExitsAreHeldToExitSites(unittest.TestCase):
    """An exit counts for the exit site on its line and a finding for the
    finding site on its: an event of one channel on the other's line is
    unmapped."""

    SITES = [site("labkit/run/s.py", 5, 6), exit_site("labkit/run/s.py", 9)]
    TEST = "tests/test_s.py::S::t"

    def reached(self, line: int, channel: str) -> tuple[list[tuple[str, int]], int]:
        """(the sites the one event reached, the unmapped count)."""
        r = ti.reach(
            [event(self.TEST, "labkit/run/s.py", line, "labkit.run.s.f", channel)],
            self.SITES,
            COMMANDS,
        )
        return [k for k, v in r.by_site.items() if any(v.values())], len(r.unmapped)

    def test_an_exit_on_an_exit_sites_line_reaches_it(self):
        self.assertEqual(self.reached(9, ti.EXIT), ([("labkit/run/s.py", 9)], 0))

    def test_the_twin_an_event_on_the_other_channels_line_is_unmapped(self):
        self.assertEqual(self.reached(5, ti.EXIT), ([], 1))
        self.assertEqual(self.reached(9, ti.FINDING), ([], 1))

    def test_the_counts_stand_by_channel_and_printed_sites_are_named(self):
        printed = FindingSite(
            "labkit.x.h",
            "labkit/run/s.py",
            20,
            20,
            "printed",
            "WARNING",
            "none",
            (),
            "w",
        )
        sites = [*self.SITES, printed]
        r = ti.reach(
            [event(self.TEST, "labkit/run/s.py", 9, "labkit.run.s.f", ti.EXIT)],
            sites,
            COMMANDS,
        )
        text = ti.render_test_inventory(sites, r, set(), set(), "1 passed", [])
        self.assertIn(
            "Traced sites: 1 gate findings and 1 exits of 3 finding sites; the 1 "
            "`printed` sites are not traced.",
            text,
        )
        self.assertIn("| direct | 0 | 1 |", text)
        self.assertIn("| unreached | 1 | 0 |", text)
        # the exit was reached below a command, in the run layer; the
        # gate finding by nothing, so it has no lowest layer
        self.assertIn("| run | 0 | 1 |", text)

    def test_every_unmapped_place_is_listed_the_exits_first(self):
        """An exit raised where the scan counts no site is told once among
        many findings rebuilt elsewhere: the table lists every place and
        opens with the exits, so the one exit is not cut off."""
        rebuilt = [
            event(self.TEST, "labkit/gates/g.py", 100 + n, "labkit.gates.g.f")
            for n in range(20)
            for _ in range(2)
        ]
        stray = event(self.TEST, "labkit/run/s.py", 40, "labkit.run.s.f", ti.EXIT)
        r = ti.reach([*rebuilt, stray], self.SITES, COMMANDS)
        text = ti.render_test_inventory(self.SITES, r, set(), set(), "1 passed", [])
        table = text.split("## Findings and exits told where no site stands")[1]
        rows = [ln for ln in table.splitlines() if ln.startswith("| `")]
        self.assertEqual(rows[0], "| `labkit/run/s.py:40` | exit | 1 |")
        self.assertEqual(len(rows), 21)
        self.assertIn("| `labkit/gates/g.py:119` | finding | 2 |", rows)

    def test_two_traced_sites_on_one_line_are_refused(self):
        with self.assertRaises(ValueError) as cm:
            ti.reach([], [site("labkit/run/s.py", 9, 9), self.SITES[1]], COMMANDS)
        self.assertIn("labkit/run/s.py:9: two traced finding sites", str(cm.exception))


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
                self.addCleanup(end_exit_trace)
                file_record_check._gone(source, Path(d))
            opened[1].close()
            (line,) = Path(d, f"{os.getpid()}.jsonl").read_text().splitlines()
        record = json.loads(line)
        self.assertEqual(record["path"], "labkit/checks/file_record_check.py")
        self.assertEqual(record["entry"], "labkit.checks.file_record_check._gone")
        self.assertIn(
            "Trace::test_a_finding_built_by_a_check_is_recorded", record["test"]
        )
        self.assertFalse(record["subprocess"])

    def test_the_twin_without_the_folder_nothing_is_wrapped(self):
        before = GateFinding.__init__
        tool = sys.monitoring.get_tool(ti.MONITOR_TOOL)
        with mock.patch.dict(os.environ, {ti.TRACE_ENV: ""}):
            ti.install_trace()
        self.assertIs(GateFinding.__init__, before)
        # no exit trace taken either: the tool id is held as before (by
        # nobody, or by the inventory's own trace this suite runs under)
        self.assertEqual(sys.monitoring.get_tool(ti.MONITOR_TOOL), tool)

    @unittest.skipIf(
        os.environ.get(ti.TRACE_ENV),
        "the suite runs under the inventory's own trace, which holds the tool id",
    )
    def test_an_exit_with_a_message_is_recorded_once_at_its_raise(self):
        """A refusal of the run's start, raised below a console entry of
        the package (`console.exit_with`): one line, at the raising frame,
        though Python reports the exception again in the entry's frame. The
        twin: an exit raised outside the package, here, is not recorded."""

        def main(argv: list[str]) -> int:
            start_check.require_valid_reseed(mock.sentinel.prepared, None, True)
            return 0

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ti, "_out", opened := []):
                ti.trace_exits(d)
                self.addCleanup(end_exit_trace)
                with self.assertRaises(SystemExit):
                    console.exit_with(main)
                with self.assertRaises(SystemExit):
                    raise SystemExit("an exit of the test's own")
            opened[1].close()
            (line,) = Path(d, f"{os.getpid()}.jsonl").read_text().splitlines()
        record = json.loads(line)
        self.assertEqual(
            (record["channel"], record["path"], record["entry"]),
            (ti.EXIT, "labkit/run/start_check.py", "labkit.formats.console.exit_with"),
        )
        self.assertIn("Trace::test_an_exit_with_a_message", record["test"])

    @unittest.skipIf(
        os.environ.get(ti.TRACE_ENV),
        "the suite runs under the inventory's own trace, which holds the tool id",
    )
    def test_a_process_whose_tool_id_is_taken_says_it_traced_no_exit(self):
        """Another tool holds the monitoring id: findings are traced, the
        exits are not, and the process leaves a marker the inventory counts.
        The twin: the trace installed in a free process leaves none."""
        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.object(GateFinding, "__init__", GateFinding.__init__),
            mock.patch.dict(os.environ, {ti.TRACE_ENV: d}),
        ):
            ti.install_trace()
            self.addCleanup(end_exit_trace)
            self.assertEqual(ti.exits_untraced(Path(d)), 0)
            ti.install_trace()  # the id is held now, by the first
            self.assertEqual(ti.exits_untraced(Path(d)), 1)
        text = ti.render_test_inventory([], ti.Reach({}, []), set(), set(), "", [])
        self.assertIn("Processes that traced no exit", text)
        told = ti.render_test_inventory(
            [], ti.Reach({}, []), set(), set(), "", [], exits_untraced=1
        )
        self.assertIn("held the monitoring id): 1.", told)


class ExitStatus(unittest.TestCase):
    """The command's exit status (`exit_status`): a reach file asked for and
    not written is no success."""

    def test_a_green_suite_with_every_exit_traced_is_0(self):
        self.assertEqual(ti.exit_status(0, reach_asked=True, untraced=0), 0)
        self.assertEqual(ti.exit_status(0, reach_asked=False, untraced=0), 0)

    def test_a_reach_file_asked_for_and_not_written_is_1(self):
        self.assertFalse(ti.reach_stands(0, 2))
        self.assertEqual(ti.exit_status(0, reach_asked=True, untraced=2), 1)

    def test_the_twin_untraced_exits_without_a_reach_file_stay_0(self):
        self.assertEqual(ti.exit_status(0, reach_asked=False, untraced=2), 0)

    def test_a_suite_not_green_is_1_either_way(self):
        self.assertFalse(ti.reach_stands(1, 0))
        self.assertEqual(ti.exit_status(1, reach_asked=False, untraced=0), 1)
        self.assertEqual(ti.exit_status(1, reach_asked=True, untraced=0), 1)


class CollectedIds(unittest.TestCase):
    """`collected_ids`: the node ids among the lines `pytest --collect-only
    -q` prints, the summary and blank lines left out."""

    def test_the_lines_naming_a_test_are_the_ids(self):
        output = (
            "tests/test_rules_x.py::A::test_one\n"
            "tests/test_rules_x.py::test_two[case]\n"
            "\n"
            "2/40 tests collected (38 deselected) in 0.12s\n"
        )
        self.assertEqual(
            ti.collected_ids(output),
            {
                "tests/test_rules_x.py::A::test_one",
                "tests/test_rules_x.py::test_two[case]",
            },
        )

    def test_the_twin_an_output_naming_no_test_gives_none(self):
        self.assertEqual(ti.collected_ids("no tests collected in 0.01s\n"), set())


class PerScenarioTest(unittest.TestCase):
    """Step 4's report: a scenario test is COVERED when a faster test
    reaches each of its sites below a command, HOLDS_A_SITE when one of
    them only scenarios reach, UNKNOWN when it reached none."""

    def test_covered_holds_and_unknown(self):
        slow = {"tests/test_e2e.py"}
        r = ti.Reach(
            {
                ("labkit/a.py", 1): {
                    "gate": {"tests/test_fast.py::T::t", "tests/test_e2e.py::E::one"},
                    ti.COMMAND: {"tests/test_e2e.py::E::two"},
                },
                ("labkit/b.py", 2): {
                    ti.COMMAND: {
                        "tests/test_e2e.py::E::two",
                        "tests/test_fast.py::T::u",
                    }
                },
            },
            [],
        )
        listed = ti.scenario_tests(r, slow)
        self.assertEqual(
            [(s.test, s.sites, s.held, s.standing) for s in listed],
            [
                ("tests/test_e2e.py::E::one", ("labkit/a.py:1",), (), ti.COVERED),
                (
                    "tests/test_e2e.py::E::two",
                    ("labkit/a.py:1", "labkit/b.py:2"),
                    ("labkit/b.py:2",),
                    ti.HOLDS_A_SITE,
                ),
            ],
        )
        self.assertEqual(
            ti.scenario_standing("tests/test_e2e.py::E::three", listed), ti.UNKNOWN
        )


if __name__ == "__main__":
    unittest.main()
