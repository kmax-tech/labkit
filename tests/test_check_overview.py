"""check_overview: the page of every finding site without line numbers —
the key that names a site across the scan and the traced run, the reach
file's round trip and its refusals, what the page says of a site the trace
does not hold, and the checked-in page held equal to what the command
writes."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import PACKAGE_DIR
from labkit.formats import console
from labkit.tools import check_overview as co
from labkit.tools import test_inventory as ti
from labkit.tools.check_inventory import NOT_RECORDED, FindingSite

REPO = PACKAGE_DIR.parent


def site(
    line: int, wording: str, channel: str = "finding", unit: str = "labkit.gates.g.hold"
) -> FindingSite:
    grade = {"finding": "BLOCKER", "exit": "exit", "printed": "WARNING"}[channel]
    return FindingSite(
        unit,
        "labkit/gates/g.py",
        line,
        line,
        channel,
        grade,
        "GUARANTEED" if channel == "finding" else "none",
        (),
        wording,
        "LAB-003" if channel == "finding" else NOT_RECORDED,
    )


def event(test: str, line: int, entry: str, channel: str = ti.FINDING) -> ti.Event:
    return ti.Event(test, "labkit/gates/g.py", line, entry, False, channel)


class TheKeyOfASite(unittest.TestCase):
    def test_the_key_holds_no_line_and_counts_equal_wordings(self):
        """Two sites of one function with one wording are told apart by
        their order, and a site keeps its key when lines above it move."""
        sites = [site(5, "{…}: not frozen"), site(9, "{…}: not frozen")]
        keys = ti.site_keys(sites)
        self.assertEqual(
            keys[("labkit/gates/g.py", 9, "finding")],
            ti.SiteKey("labkit.gates.g.hold", "finding", "{…}: not frozen", 2),
        )
        moved = ti.site_keys([site(15, "{…}: not frozen"), site(19, "{…}: not frozen")])
        self.assertEqual(set(moved.values()), set(keys.values()))

    def test_equal_wordings_are_numbered_by_line_not_by_the_order_given(self):
        """The scan walks a function breadth-first: the site on the later
        line may come first. The count follows the line."""
        keys = ti.site_keys([site(9, "w"), site(5, "w")])
        self.assertEqual(keys[("labkit/gates/g.py", 5, "finding")].nth, 1)
        self.assertEqual(keys[("labkit/gates/g.py", 9, "finding")].nth, 2)

    def test_the_twin_another_channel_or_wording_starts_its_own_count(self):
        keys = ti.site_keys([site(5, "w"), site(6, "w", "exit"), site(7, "other")])
        self.assertEqual({k.nth for k in keys.values()}, {1})


class TheReachOfATracedRun(unittest.TestCase):
    SITES = [site(5, "not frozen"), site(9, "no area", "exit"), site(12, "unreached")]
    COMMANDS = {"labkit.gates.finalize"}

    def reach(self) -> ti.TracedReach:
        events = [
            event("tests/test_rules_g.py::T::t1", 5, "labkit.gates.g.hold"),
            event("tests/test_e.py::S::t", 5, "labkit.gates.finalize.main"),
            event("tests/test_e.py::S::t", 9, "labkit.gates.finalize.main", ti.EXIT),
        ]
        r = ti.reach(events, self.SITES, self.COMMANDS)
        return ti.traced_reach(
            self.SITES, r, {"tests/test_rules_g.py::T::t1"}, "3 passed"
        )

    def test_each_traced_site_has_its_standing_counts_and_files(self):
        found = {k.wording: v for k, v in self.reach().by_site.items()}
        self.assertEqual(
            found,
            {
                "not frozen": ti.SiteReach(
                    "direct", 2, 1, ("tests/test_e.py", "tests/test_rules_g.py")
                ),
                "no area": ti.SiteReach(
                    "only through commands", 1, 0, ("tests/test_e.py",)
                ),
                "unreached": ti.SiteReach("unreached", 0, 0, ()),
            },
        )

    def test_the_file_reads_back_as_it_was_written(self):
        reach = self.reach()
        text = ti.render_reach(reach)
        self.assertTrue(text.startswith("# traced: 3 passed\nunit\tchannel\tnth\t"))
        self.assertEqual(ti.read_reach(text, "reach.tsv"), reach)

    def test_a_file_that_does_not_read_is_refused_by_its_line(self):
        good = ti.render_reach(self.reach()).splitlines()
        row = good[2].split("\t")
        cases = {
            "reach.tsv:1: no head line": good[1:],
            "reach.tsv:2: the column line": [good[0], "unit\tchannel", *good[2:]],
            "reach.tsv:3: 7 fields, not 8": [*good[:2], "\t".join(row[:-1])],
            "reach.tsv:3: standing 'sometimes'": [
                *good[:2],
                "\t".join([*row[:4], "sometimes", *row[5:]]),
            ],
            "reach.tsv:3: a count is no integer": [
                *good[:2],
                "\t".join([*row[:5], "two", *row[6:]]),
            ],
            "reach.tsv:3: nth below 1, a count below 0, or more rule tests": [
                *good[:2],
                "\t".join([*row[:5], "1", "2", row[7]]),
            ],
            "reach.tsv:4: the site stands in an earlier row too": [
                *good[:3],
                good[2],
            ],
        }
        for said, lines in cases.items():
            with self.subTest(said), self.assertRaises(ValueError) as cm:
                ti.read_reach("\n".join(lines) + "\n", "reach.tsv")
            self.assertIn(said, str(cm.exception))

    def test_a_field_with_a_separator_is_not_written(self):
        reach = ti.TracedReach(
            "1 passed",
            {
                ti.SiteKey("labkit.x.f", "exit", "a\tb", 1): ti.SiteReach(
                    "unreached", 0, 0, ()
                )
            },
        )
        with self.assertRaises(ValueError) as cm:
            ti.render_reach(reach)
        self.assertIn("labkit.x.f", str(cm.exception))


class ThePage(unittest.TestCase):
    SITES = TheReachOfATracedRun.SITES

    def page(self, sites: list[FindingSite], reach: ti.TracedReach) -> str:
        commands = {"labkit.gates.g.hold": {"finalize", "report-check"}}
        return co.render_overview(sites, commands, {"LAB-003": "No run"}, reach)

    def test_a_site_reads_with_its_rule_its_reach_and_no_line(self):
        reach = TheReachOfATracedRun().reach()
        text = self.page(self.SITES, reach)
        self.assertIn(
            "| `hold` | not frozen | finding | BLOCKER | GUARANTEED | LAB-003 No run "
            "| direct | 2 | 1 | `tests/test_e.py`, `tests/test_rules_g.py` |",
            text,
        )
        self.assertIn(
            f"| `hold` | no area | exit | exit | none | {NOT_RECORDED} "
            "| only through commands | 1 | 0 | `tests/test_e.py` |",
            text,
        )
        self.assertIn("| unreached | 0 | 0 | — |", text)
        self.assertIn("| `finalize` | `labkit/gates/g.py` (3) |", text)
        self.assertIn("Reach as traced: 3 passed. 0 sites are not in that", text)
        self.assertNotIn("g.py:", text)  # no line number anywhere

    def test_a_site_the_trace_lacks_and_a_row_without_a_site_are_counted(self):
        """Since the traced run one site was reworded and a printed line
        added: the reworded site is not in the trace, its old row names a
        site that is gone, and a printed line is never traced."""
        reach = TheReachOfATracedRun().reach()
        now = [
            site(5, "not frozen yet"),
            *self.SITES[1:],
            site(20, "{…}: WARNING: left", "printed"),
        ]
        text = self.page(now, reach)
        self.assertIn(
            "1 sites are not in that trace (added or reworded since, or the reach "
            "file holds no row yet), 1 rows of the trace name a site that is gone "
            "and are left out, the 1 printed lines are never traced.",
            text,
        )
        self.assertIn(f"| LAB-003 No run | {co.NOT_IN_TRACE} | — | — | — |", text)
        self.assertIn(f"| {co.NEVER_TRACED} | — | — | — |", text)
        self.assertNotIn("| not frozen |", text)


class TheCheckedInPage(unittest.TestCase):
    def test_the_page_is_what_the_command_writes_from_the_source_and_the_reach(self):
        """`docs/checks-overview.md` is a view of the source and of
        `docs/checks-reach.tsv`: a finding site added, removed or reworded
        without writing the page anew fails here."""
        reach = (REPO / co.REACH).read_text(encoding="utf-8")
        self.assertEqual(
            (REPO / co.OVERVIEW).read_text(encoding="utf-8"),
            co.overview(PACKAGE_DIR, reach, str(co.REACH)),
            "write it anew: python -m labkit.tools.check_overview",
        )

    def test_every_rule_the_page_names_carries_its_name(self):
        """A site that records a rule of the code standard reads with the
        rule's name, as one of the lab standard does."""
        page = (REPO / co.OVERVIEW).read_text(encoding="utf-8")
        self.assertIn("| CODE-016 The experiment area reconstructs itself |", page)
        self.assertIn("| LAB-003 No run without an intent paragraph |", page)

    def test_check_passes_on_the_page_as_written_and_tells_a_changed_one(self):
        """The command on the checkout's source and reach, the page in a
        temporary folder: written, `--check` passes; with one line changed
        it exits 1 and names the command that writes the page anew. The
        page's real place is held by the equality test above, not here."""
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "page.md"
            # an absolute path stands for itself when joined to the checkout
            with mock.patch.object(co, "OVERVIEW", page):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(co.main([]), 0)
                    self.assertEqual(co.main(["--check"]), 0)
                page.write_text(
                    page.read_text(encoding="utf-8") + "| edited |\n", encoding="utf-8"
                )
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(co.main(["--check"]), 1)
        self.assertIn("python -m labkit.tools.check_overview", err.getvalue())

    def test_an_unknown_argument_is_refused(self):
        with self.assertRaises(console.Refused):
            co.main(["--out", "x"])


if __name__ == "__main__":
    unittest.main()
