"""gate_stations: which functions count as a gate and where a station ends,
which sites a station lists as at this station and as further down, what the
page says of a station that reaches none — on a synthetic module — and the
checked-in page held equal to what the command writes."""

from __future__ import annotations

import ast
import contextlib
import io
import tempfile
import textwrap
import unittest
from collections import defaultdict
from pathlib import Path
from unittest import mock

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.tools import check_inventory as inv
from labkit.tools import gate_stations as gs

REPO = PACKAGE_DIR.parent

SOURCE = textwrap.dedent(
    '''
    def hold_area(area, findings):
        """Hold the area. Second sentence."""
        # 0. protocol — the only early end
        if area is None:
            raise SystemExit(with_way_out("no area", "name one"))
        # 1. the run's code — only
        #    with a run
        check_code(findings, area)
        # one remark that numbers nothing
        check_scope(findings)
        # 2. the other gate
        hold_report(area)
        # 3. summary
        return 0


    def check_code(findings, area):
        """The run's code against what it ran."""
        findings.block("code changed", fix=f"measure anew: `{area}`", rule=OPEN_RULE)
        read_record(area)


    def check_scope(findings):
        """Reaches a finding only further down"""
        read_record(None)


    def read_record(area):
        if area is None:
            raise SystemExit("record unreadable")


    def hold_report(area):
        # 0. the report
        findings.block("no report", fix=WRITE_IT, rule=OPEN_RULE)
        # 1. the end
        read_record(area)


    def remark(area):
        # 1. a single numbered comment makes no gate
        return area


    def hook_script():
        return """
    # 1. a numbered line inside a string is no comment
    # 2. and so numbers no station
    """
    '''
)


def scan() -> tuple[list[inv.Module], dict[str, dict[int, str]]]:
    """The synthetic module `labkit.gates.g`, parsed, and its comments by path."""
    module = inv.Module("labkit.gates.g", "labkit/gates/g.py", ast.parse(SOURCE))
    return [module], {module.path: gs.comment_lines(SOURCE)}


def told_by(gate_name: str) -> dict[int, gs.StationSites]:
    """Station number → what it can tell, for the gate GATE_NAME of the
    synthetic module."""
    modules, comments = scan()
    found = gs.gates(modules, comments)
    sites_in: dict[str, list[inv.FindingSite]] = defaultdict(list)
    for s in inv.finding_sites(modules):
        sites_in[s.unit].append(s)
    gate = next(g for g in found if g.unit.endswith(gate_name))
    return {
        st.number: gs.station_sites(
            gate,
            st,
            inv.unit_references(modules),
            inv.call_graph(modules),
            sites_in,
            {g.unit for g in found},
        )
        for st in gate.stations
    }


class TheStationsOfAGate(unittest.TestCase):
    def test_only_a_function_with_two_numbered_comments_is_a_gate(self):
        found = gs.gates(*scan())
        self.assertEqual(
            [g.unit for g in found],
            ["labkit.gates.g.hold_area", "labkit.gates.g.hold_report"],
        )

    def test_a_station_takes_its_title_lines_and_ends_before_the_next(self):
        hold_area = gs.gates(*scan())[0]
        lines = SOURCE.splitlines()
        self.assertEqual([st.number for st in hold_area.stations], [0, 1, 2, 3])
        code = hold_area.stations[1]
        self.assertEqual(code.title, "the run's code — only with a run")
        self.assertIn("# 1. the run's code", lines[code.line - 1])
        # the unnumbered remark and the call below it belong to station 1
        self.assertIn("check_scope(findings)", lines[code.end_line - 1])
        self.assertIn("return 0", lines[hold_area.stations[3].end_line - 1])


class WhatAStationCanTell(unittest.TestCase):
    def test_a_site_in_the_gates_own_code_stands_at_its_station(self):
        told = told_by("hold_area")
        self.assertEqual(
            [(s.channel, s.way_out) for s in told[0].own], [("exit", "name one")]
        )
        self.assertEqual(told[1].own, ())

    def test_called_here_and_further_down_are_told_apart(self):
        """Station 1 calls `check_code`, which tells a finding itself, and
        `check_scope`, which only reaches one: both are its calls; the
        blocker is at this station, the exit both reach is further down, once."""
        told = told_by("hold_area")[1]
        self.assertEqual(
            told.called, ("labkit.gates.g.check_code", "labkit.gates.g.check_scope")
        )
        self.assertEqual(
            [(s.wording, s.way_out) for s in told.called_sites],
            [("code changed", "measure anew: `{…}`")],
        )
        self.assertEqual([s.wording for s in told.further], ["record unreadable"])

    def test_another_gate_is_named_and_its_sites_are_not_repeated(self):
        told = told_by("hold_area")[2]
        self.assertEqual(told.gates, ("labkit.gates.g.hold_report",))
        self.assertEqual((told.called, told.called_sites, told.further), ((), (), ()))

    def test_a_way_out_without_constant_text_names_its_expression(self):
        told = told_by("hold_report")
        self.assertEqual([s.way_out for s in told[0].own], ["`WRITE_IT`"])
        # a site that names no way out reads empty
        self.assertEqual([s.way_out for s in told[1].called_sites], [""])


class TheFirstSentence(unittest.TestCase):
    def sentence(self, docstring: str) -> str:
        node = ast.parse(f'def f():\n    """{docstring}"""\n').body[0]
        return gs.first_sentence(node)

    def test_it_ends_at_the_first_full_stop_that_ends_a_sentence(self):
        self.assertEqual(self.sentence("Hold the area. Then more."), "Hold the area.")
        self.assertEqual(
            self.sentence("Reads `runs.tsv` of v0.1 and\n    stops. `x` next."),
            "Reads `runs.tsv` of v0.1 and stops.",
        )

    def test_without_a_full_stop_it_is_the_first_paragraph(self):
        self.assertEqual(self.sentence("One line\n\n    Args: none."), "One line")

    def test_a_colon_that_closes_the_paragraph_is_dropped(self):
        self.assertEqual(
            self.sentence("The stations in order:\n\n    0 first"),
            "The stations in order",
        )

    def test_a_unit_without_a_docstring_reads_empty(self):
        self.assertEqual(
            gs.first_sentence(ast.parse("def f():\n    pass\n").body[0]), ""
        )
        self.assertEqual(gs.first_sentence(None), "")


class ThePage(unittest.TestCase):
    def page(self) -> str:
        modules, comments = scan()
        found = gs.gates(modules, comments)
        sites_in: dict[str, list[inv.FindingSite]] = defaultdict(list)
        for s in inv.finding_sites(modules):
            sites_in[s.unit].append(s)
        gate_units = {g.unit for g in found}
        told = {
            (g.unit, st.line): gs.station_sites(
                g,
                st,
                inv.unit_references(modules),
                inv.call_graph(modules),
                sites_in,
                gate_units,
            )
            for g in found
            for st in g.stations
        }
        purposes = {
            "labkit.gates.g.hold_area": "Hold the area.",
            "labkit.gates.g.check_code": "The run's code against what it ran.",
        }
        commands = {"labkit.gates.g.hold_area": {"finalize", "report-check"}}
        return gs.render_stations(found, told, purposes, commands, {})

    def test_a_station_reads_with_its_calls_its_sites_and_their_way_out(self):
        text = self.page()
        self.assertIn("## `g.hold_area` — `labkit/gates/g.py`", text)
        self.assertIn(
            "Commands whose code reaches it: `finalize`, `report-check`.", text
        )
        self.assertIn("### g.hold_area · 1. the run's code — only with a run", text)
        self.assertIn("- `g.check_code` — The run's code against what it ran.", text)
        self.assertIn("- `g.check_scope` — —", text)
        self.assertIn("**At this station:**", text)
        self.assertIn(
            "## `g.hold_report` — `labkit/gates/g.py`\n\n—\n\nCommands whose code reaches it: no console script.",
            text,
        )
        self.assertIn(
            "| `g.check_code` | BLOCKER | GUARANTEED | open assignment "
            "| code changed | measure anew: `{…}` |",
            text,
        )
        self.assertIn(
            f"| `g.read_record` | exit | none | {inv.NOT_RECORDED} "
            "| record unreadable | — |",
            text,
        )

    def test_a_station_that_reaches_nothing_and_one_that_runs_a_gate_say_so(self):
        text = self.page()
        summary = text.split("### g.hold_area · 3. summary")[1].split("##")[0]
        self.assertEqual(summary.strip(), "Reaches no finding site.")
        other = text.split("### g.hold_area · 2. the other gate")[1].split("###")[0]
        self.assertEqual(
            other.strip(), "Runs another gate of this page: `g.hold_report`."
        )


class TheCheckedInPage(unittest.TestCase):
    def test_the_page_is_what_the_command_writes_from_the_source(self):
        """`docs/gate-stations.md` is a view of the source: a station or a
        finding site added, removed or reworded without writing the page
        anew fails here."""
        self.assertEqual(
            (REPO / gs.STATIONS).read_text(encoding="utf-8"),
            gs.stations_page(PACKAGE_DIR),
            "write it anew: python -m labkit.tools.gate_stations",
        )

    def test_the_page_holds_a_station_and_a_site_known_to_be_there(self):
        """The known positive: finalize's station of the intent keys, the
        function it calls and that function's blocker with its way out."""
        page = (REPO / gs.STATIONS).read_text(encoding="utf-8")
        station = page.split("### finalize.finalize_area · 3. intent-check — always")[1]
        station = station.split("\n### ")[0]
        self.assertIn("- `finalize.check_intent_keys_in_metrics` — ", station)
        self.assertRegex(
            station,
            r"\| `finalize.check_intent_keys_in_metrics` \| BLOCKER \| GUARANTEED \| "
            r"[^|]+ \| [^|]+ \| repair what the sentence names; `\{…\}` holds it alone \|",
        )

    def test_check_passes_on_the_page_as_written_and_tells_a_changed_one(self):
        """The command on the checkout's source, the page in a temporary
        folder: written, `--check` passes; with one line changed it exits 1
        and names the command that writes the page anew."""
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "page.md"
            # an absolute path stands for itself when joined to the checkout
            with mock.patch.object(gs, "STATIONS", page):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(gs.main([]), 0)
                    self.assertEqual(gs.main(["--check"]), 0)
                page.write_text(
                    page.read_text(encoding="utf-8") + "| edited |\n", encoding="utf-8"
                )
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(gs.main(["--check"]), 1)
        self.assertIn("python -m labkit.tools.gate_stations", err.getvalue())

    def test_an_unknown_argument_is_refused(self):
        with self.assertRaises(console.Refused):
            gs.main(["--out", "x"])


if __name__ == "__main__":
    unittest.main()
