"""rules_map: the page of each rule of the standard and the code that holds
it — the gaps file's refusals, the chain's sections a site's function
names, the stations that can tell a site, what the page says of a rule no
site records and of a site whose basis is not settled, and the checked-in
page held equal to what the command writes."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.formats.gate import OPEN_ASSIGNMENT, TECHNICAL_CONTRACT
from labkit.tools import rules_map as rm
from labkit.tools import test_inventory as ti
from labkit.tools.check_inventory import FindingSite, RuleUse
from labkit.tools.gate_stations import Gate, Station, StationSites

REPO = PACKAGE_DIR.parent
HEADER = "\t".join(rm.GAP_COLUMNS) + "\n"


def site(
    line: int,
    assignment: str = "LAB-017",
    unit: str = "labkit.checks.c.held",
    wording: str = "output {…} is not yet tracked",
) -> FindingSite:
    return FindingSite(
        unit,
        "labkit/checks/c.py",
        line,
        line,
        "finding",
        "WARNING",
        "GUARANTEED",
        (),
        wording,
        assignment,
        "violated",
    )


class TheGapsFile(unittest.TestCase):
    SITES = [site(5)]
    TEXTS = {"LAB-017": "`finalize` refuses a run\n    whose output is outside git."}

    def read(self, rows: str) -> list[rm.RuleGap]:
        return rm.read_gaps(HEADER + rows, "gaps.tsv", self.SITES, self.TEXTS)

    def test_a_row_naming_a_function_that_records_the_rule_reads(self):
        quote = '"`finalize` refuses a run … outside git"'
        (gap,) = self.read(f"LAB-017\tchecks.c.held\t{quote}\twarns\tTODO.md\n")
        # the quotes are the rule's own quotation and stay
        self.assertEqual((gap.function, gap.text), ("checks.c.held", quote))

    def test_a_quotation_the_rules_text_does_not_hold_is_refused(self):
        """Each part around `…` must stand in the rule's text, in order:
        a part out of order or not there is refused."""
        for quote in ('"refuses a run … finalize"', '"finalize blocks"'):
            with self.subTest(quote=quote):
                with self.assertRaisesRegex(ValueError, "does not stand in LAB-017"):
                    self.read(f"LAB-017\tchecks.c.held\t{quote}\twarns\tTODO.md\n")

    def test_a_function_that_does_not_record_the_rule_is_refused(self):
        """The row would describe code that is not there: the site is gone,
        or records another rule now."""
        with self.assertRaisesRegex(ValueError, "gaps.tsv:2: no finding site"):
            self.read("LAB-017\tchecks.c.other\trefuses\twarns\tTODO.md\n")

    def test_a_rule_that_is_not_active_is_refused(self):
        with self.assertRaisesRegex(ValueError, "LAB-999 is no active rule"):
            self.read("LAB-999\tchecks.c.held\trefuses\twarns\tTODO.md\n")

    def test_an_empty_cell_and_another_header_are_refused(self):
        with self.assertRaisesRegex(ValueError, "5 non-empty cells"):
            self.read("LAB-017\tchecks.c.held\t\twarns\tTODO.md\n")
        with self.assertRaisesRegex(ValueError, "the header must be"):
            rm.read_gaps("rule\tfunction\n", "gaps.tsv", self.SITES, self.TEXTS)


class TheChain(unittest.TestCase):
    TEXT = (
        "# The chain\n\n## promise → code\n\nwhat\n\n"
        "- **Where:** `code_check.promise_block_findings`, `promises.parse_block`\n"
        "- **Tier:** guaranteed\n\n## run → number\n\n- **Tier:** guaranteed\n"
    )

    def test_a_section_names_the_functions_of_its_where_line(self):
        self.assertEqual(
            rm.chain_sections(self.TEXT),
            {
                "promise → code": (
                    "code_check.promise_block_findings",
                    "promises.parse_block",
                ),
                "run → number": (),
            },
        )

    def test_a_name_matches_the_unit_it_ends_and_no_other(self):
        sections = rm.chain_sections(self.TEXT)
        self.assertEqual(
            rm.chain_headings(
                {"labkit.checks.code_check.promise_block_findings"}, sections
            ),
            ["promise → code"],
        )
        # a unit whose name only ends in the same letters is not matched
        self.assertEqual(
            rm.chain_headings(
                {"labkit.checks.x_code_check.promise_block_findings"}, sections
            ),
            [],
        )


class TheStationsOfASite(unittest.TestCase):
    def test_a_station_reaching_a_site_only_further_down_is_marked(self):
        here, below = site(5), site(9)
        gate = Gate(
            "labkit.gates.g.hold_area", "labkit/gates/g.py", (Station(2, "t", 1, 9),)
        )
        told = {(gate.unit, 1): StationSites((here,), (), (), (below,), ())}
        stations = rm.site_stations([gate], told)
        self.assertEqual(
            stations[("labkit/checks/c.py", 5, "finding")], ["g.hold_area · 2"]
        )
        self.assertEqual(
            stations[("labkit/checks/c.py", 9, "finding")],
            [f"g.hold_area · 2 {rm.FURTHER}"],
        )


class ThePage(unittest.TestCase):
    def page(self, sites: list[FindingSite], gaps: list[rm.RuleGap]) -> str:
        uses = [
            RuleUse(
                "LAB-017 The number of audits follows the cost tier",
                tuple(s for s in sites if s.assignment == "LAB-017"),
                (),
                ("agents/experiment-preflight.agent.md",),
            ),
            RuleUse("LAB-001 A negative finding is a claim", (), (), ()),
        ]
        return rm.render_rules_map(
            rm.PageInputs(
                uses=uses,
                sites=sites,
                stations={},
                reach=ti.TracedReach("1 passed", {}),
                chain={},
                gaps=gaps,
                causes=[],
                names={},
            )
        )

    def test_a_rule_without_a_site_says_only_that(self):
        """No site records LAB-001: the page says so, and nothing about an
        agent checking it or a tool ruling it out."""
        text = self.page([site(5)], [])
        self.assertIn(rm.NO_SITE, text)
        self.assertIn("| LAB-001 A negative finding is a claim | — | — |", text)
        self.assertIn("nothing follows from that about an agent audit", text)

    def test_a_known_gap_stands_in_its_rules_section(self):
        gap = rm.RuleGap("LAB-017", "checks.c.held", '"refuses"', "warns", "TODO.md")
        text = self.page([site(5)], [gap])
        section = text.split("### LAB-017", 1)[1].split("## Rules no finding", 1)[0]
        self.assertIn(
            # the function as the table's rows name it, without its layer
            "**Known gap between text and code** (`c.held`): the rule's text "
            'above asks "refuses"; the code warns.',
            section,
        )
        self.assertIn("`labkit/agents/experiment-preflight.agent.md`", section)

    def test_a_contract_and_an_open_assignment_stand_in_their_groups(self):
        text = self.page(
            [
                site(5),
                site(7, TECHNICAL_CONTRACT, wording="does not read"),
                site(9, OPEN_ASSIGNMENT, wording="not decided"),
            ],
            [],
        )
        contracts = text.split("## Technical contracts", 1)[1].split("## Not settled")[
            0
        ]
        unsettled = text.split("### Open assignments", 1)[1].split("###")[0]
        self.assertIn("| does not read |", contracts)
        self.assertIn("| not decided |", unsettled)
        self.assertNotIn("not decided", contracts)
        self.assertIn("1 a technical contract, 1 an open assignment", text)


class TheCheckedInPage(unittest.TestCase):
    def test_the_page_is_what_the_command_writes_from_its_sources(self):
        """`docs/rules-map.md` is a view: a finding site added, removed,
        reworded or given another rule without writing the page anew fails
        here."""
        texts = [
            (REPO / p).read_text(encoding="utf-8")
            for p in (rm.REACH, rm.CHAIN, rm.GAPS)
        ]
        self.assertEqual(
            (REPO / rm.RULES_MAP).read_text(encoding="utf-8"),
            rm.rules_map(PACKAGE_DIR, *texts),
            "write it anew: python -m labkit.tools.rules_map",
        )

    def test_check_passes_on_the_page_as_written_and_tells_a_changed_one(self):
        """The command's plumbing: written, `--check` passes; one line
        changed, it exits 1 and names the command. The page's content is a
        fixed text here — the equality test above holds the real one."""
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "page.md"
            with (
                mock.patch.object(rm, "RULES_MAP", page),
                mock.patch.object(rm, "rules_map", return_value="# page\n"),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(rm.main([]), 0)
                    self.assertEqual(rm.main(["--check"]), 0)
                page.write_text(
                    page.read_text(encoding="utf-8") + "x\n", encoding="utf-8"
                )
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(rm.main(["--check"]), 1)
        self.assertIn("python -m labkit.tools.rules_map", err.getvalue())

    def test_an_unknown_argument_is_refused(self):
        with self.assertRaises(console.Refused):
            rm.main(["--out", "x"])


if __name__ == "__main__":
    unittest.main()
