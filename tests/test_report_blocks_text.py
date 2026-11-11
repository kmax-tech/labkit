"""A report's blocks as text and files (`checks/report_blocks`): the
generated result blocks, the discussion blocks, the run ids cited and the
numbers without an assigned source; the result block that takes the place
of the progress account. The gate that holds a changed report at the stop
and the commit, in a repository: tests/test_report_blocks.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


from labkit.checks import report_blocks
from labkit.formats.gate import TECHNICAL_RULE

RUN = "2026-10-07T10-00-00_ab12"
P = "experiments/01-x/PROTOCOL-x.md"


class Blocks(unittest.TestCase):
    def test_withdrawal_keeps_other_protocols_and_prose(self):
        report = Path("/lab/reports/REPORT.md")
        owner = Path("/lab/experiments/01-x/PROTOCOL-x.md")
        mine = "../experiments/01-x/PROTOCOL-x.md"
        alias = "../experiments/01-x/../01-x/PROTOCOL-x.md"
        other = "../experiments/02-y/PROTOCOL-y.md"
        text = report_blocks.with_block("# Report\n\nProse.\n", mine, RUN, "a = 1")
        text = report_blocks.with_block(text, alias, RUN, "a = 2")
        text = report_blocks.with_block(text, other, RUN, "b = 1")
        kept = report_blocks.withdraw_result_blocks(text, owner, report)
        self.assertTrue(kept.startswith("# Report\n\nProse.\n"), kept)
        self.assertEqual(
            [(b.protocol, b.body) for b in report_blocks.blocks(kept)],
            [(other, "b = 1")],
        )
        self.assertEqual(
            report_blocks.withdraw_result_blocks(kept, owner, report), kept
        )

    def test_write_appends_then_replaces_in_place(self):
        text = "# Report\n\nprose\n"
        once = report_blocks.with_block(text, P, RUN, "a = 1 (run x)")
        self.assertEqual(
            [(b.protocol, b.run_id, b.body) for b in report_blocks.blocks(once)],
            [(P, RUN, "a = 1 (run x)")],
        )
        self.assertEqual(report_blocks.with_block(once, P, RUN, "a = 1 (run x)"), once)
        moved = once.replace("prose\n", "prose\n\nafter\n") + "tail\n"
        again = report_blocks.with_block(moved, P, RUN, "a = 2 (run x)")
        self.assertEqual(again, moved.replace("a = 1 (run x)", "a = 2 (run x)"))

    def test_a_new_run_replaces_the_protocols_block_and_no_other(self):
        """A run change: the protocol's block is replaced, not joined by a
        second; another protocol's block stays."""
        other = "experiments/02-y/PROTOCOL-y.md"
        text = report_blocks.with_block("", P, RUN, "a = 1")
        text = report_blocks.with_block(text, other, RUN, "b = 1")
        new = "2026-10-08T10-00-00_cd34"
        text = report_blocks.with_block(text, P, new, "a = 2")
        self.assertEqual(
            [(b.protocol, b.run_id, b.body) for b in report_blocks.blocks(text)],
            [(P, new, "a = 2"), (other, RUN, "b = 1")],
        )

    def test_a_block_that_does_not_read_raises_with_its_line(self):
        opened = report_blocks.block_lines(P, RUN, "a = 1")[0]
        for text, said in (
            (f"x\n{opened}\na = 1\n", "line 2: the result block for run"),
            (f"{report_blocks.CLOSE}\n", "line 1: <!-- /labkit result --> closes"),
            (f"{opened}\n{opened}\n", "line 2: a result block opens inside"),
        ):
            with self.assertRaisesRegex(report_blocks.ReportBlockError, said):
                report_blocks.blocks(text)

    def test_block_gaps_hold_the_declared_run_and_equality(self):
        found = report_blocks.blocks(report_blocks.with_block("", P, RUN, "a = 1"))
        BlockSource = report_blocks.BlockSource
        report = Path.cwd() / "REPORT.md"
        self.assertEqual(
            report_blocks.block_gaps(found, {P: BlockSource(RUN, "a = 1")}, report),
            [],
        )
        (gap,) = report_blocks.block_gaps(found, {P: BlockSource(RUN, "a = 2")}, report)
        self.assertIn("differs from the protocol's rendering", gap.line)
        (gap,) = report_blocks.block_gaps(
            found, {P: BlockSource("2026-10-08T10-00-00_cd34", "a = 2")}, report
        )
        self.assertIn(
            "the protocol has adopted run 2026-10-08T10-00-00_cd34 now", gap.line
        )
        # protocol and report as the working directory reaches them, runnable
        # from there
        self.assertIn(
            f"`protocol-fill {P} --into REPORT.md` replaces the block", gap.line
        )
        (gap,) = report_blocks.block_gaps(
            found,
            {P: BlockSource(None, None, "it has adopted no result", TECHNICAL_RULE)},
            report,
        )
        self.assertIn(
            "it has adopted no result — a block shows an adopted result only", gap.line
        )
        # the rule is the source's, whatever it names
        self.assertEqual(gap.rule, TECHNICAL_RULE)
        with self.assertRaises(ValueError):
            BlockSource(None, None, "it has adopted no result")

    def test_cited_ids_must_name_runs_of_the_repo(self):
        text = (
            f"see {RUN}\nand 2026-10-21T12-48-00_final\nand 2026-10-07T10-00-00_ffff\n"
        )
        cited = report_blocks.cited_run_ids(text)
        gaps = report_blocks.cited_gaps(cited, {RUN}, structured={2, 3})
        self.assertEqual(len(gaps), 2, gaps)
        self.assertIn(
            "line 2: 2026-10-21T12-48-00_final reads as a run id", gaps[0].line
        )
        self.assertIn(
            "line 3: cites run 2026-10-07T10-00-00_ffff — no runs/", gaps[1].line
        )
        self.assertEqual({g.grade for g in gaps}, {"BLOCKER"})
        # the same tokens in prose: a pattern over free text, a warning
        prose = report_blocks.cited_gaps(cited, {RUN}, structured=set())
        self.assertEqual(
            {(g.grade, g.evidence_kind) for g in prose},
            {("WARNING", "static evidence")},
        )

    def test_numbers_outside_blocks_are_named_and_ids_dates_versions_are_not(self):
        text = (
            "28 training samples, median 0.449\n"
            f"run {RUN} on 2026-10-22 with labkit 0.102.0\n"
            "1. step one of 5 folds\n"
            "see https://x.org/a/2024/12\n"
            "| 2464-18-8 | `experiments/01-x/runs/` `n=100` |\n"
            + report_blocks.with_block("", P, RUN, "auc = 0.69 (run x)")
        )
        self.assertEqual(report_blocks.unsourced_numbers(text), [(1, ["28", "0.449"])])


class Discussions(unittest.TestCase):
    """The discussion block: TOML head, the line written from it."""

    def test_write_appends_then_replaces_and_keeps_other_discussions(self):
        other = "2026-10-08T10-00-00_cd34"
        text = report_blocks.with_discussion("# R\n", P, RUN, "one")
        text = report_blocks.with_discussion(text, P, other, "other")
        text = report_blocks.with_discussion(text, P, RUN, "two — 12 of 30")
        found = report_blocks.discussions(text)
        self.assertEqual(
            [(d.protocol, d.run_id, d.why) for d in found],
            [(P, RUN, "two — 12 of 30"), (P, other, "other")],
        )
        self.assertEqual(
            found[0].body, f"Run {RUN} — discussed, not reported: two — 12 of 30"
        )
        self.assertEqual(report_blocks.discussion_gaps(found), [])

    def test_quotes_in_the_why_survive_the_head(self):
        why = 'the "best" fold \\ backslash'
        (d,) = report_blocks.discussions(report_blocks.with_discussion("", P, RUN, why))
        self.assertEqual(d.why, why)

    def test_a_why_that_cannot_stand_is_refused(self):
        for why in ("", "  ", "two\nlines", "closes --> early"):
            with self.assertRaises(ValueError):
                report_blocks.discussion_lines(P, RUN, why)

    def test_a_carriage_return_in_the_why_is_a_second_line(self):
        """A text-mode read turns a lone `\\r` into a line break: the block's
        line would come back split, differ from its head, and be written
        again split. It is refused as more than one line; the twin, every other control
        character, reads back (`test_control_characters_…`)."""
        for why in ("carriage\rreturn", "trailing\r inside"):
            with self.subTest(why=why):
                with self.assertRaisesRegex(ValueError, "one line"):
                    report_blocks.discussion_lines(P, RUN, why)

    def test_control_characters_in_the_why_read_back_from_the_file(self):
        """The head's strings are written by `protocol_block.toml_string`,
        the one TOML string writer: json.dumps leaves DEL raw, a head
        tomllib refuses. Each why reads back unchanged, through the file as the gate
        reads it, and its line equals its head."""
        for why in (
            "del\x7fx",
            "nul\x00x",
            "bell\x07 esc\x1b",
            "tab\there",
            "vt\x0bff\x0cx",
            "nel\x85x",
            "ls x ps y",
            'quote " and back\\slash',
        ):
            with self.subTest(why=why), tempfile.TemporaryDirectory() as d:
                report = Path(d) / "REPORT.md"
                text = report_blocks.with_discussion("# R\n", P, RUN, why)
                report.write_text(text, encoding="utf-8")
                found = report_blocks.discussions(report.read_text(encoding="utf-8"))
                self.assertEqual([x.why for x in found], [why])
                self.assertEqual(report_blocks.discussion_gaps(found), [])

    def test_a_lone_surrogate_in_the_why_is_refused_naming_it(self):
        """An argument not decoded as UTF-8 reaches `--why` — or the
        protocol's path, or the run id — as a lone surrogate; writing the
        report must not end in a traceback. The refusal names the field."""
        for args, field in (
            ((P, RUN, "bad \udcff byte"), "--why"),
            (("experiments/01-\udcff/PROTOCOL-x.md", RUN, "a look"), "protocol path"),
            ((P, "2026-10-07T10-00-00_\udcff", "a look"), "run id"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    ValueError, f"{field}: a lone surrogate U\\+DCFF"
                ):
                    report_blocks.discussion_lines(*args)

    def test_two_blocks_of_one_protocol_and_run_are_a_gap_and_refuse_a_write(self):
        one = "\n".join(report_blocks.discussion_lines(P, RUN, "a"))
        text = f"{one}\n\n{one}\n"
        (gap,) = report_blocks.discussion_gaps(report_blocks.discussions(text))
        self.assertIn("line 9: the discussion of run", gap.line)
        self.assertIn("repeats the block at line 1", gap.line)
        with self.assertRaisesRegex(report_blocks.ReportBlockError, "in 2 blocks"):
            report_blocks.with_discussion(text, P, RUN, "b")

    def test_a_block_that_does_not_read_raises_with_its_line(self):
        lines = report_blocks.discussion_lines(P, RUN, "a")
        for text, said in (
            (
                "\n".join(lines[:-1]) + "\n",
                "line 1: the discussion block opened there is never closed",
            ),
            ("\n".join(lines[:3]) + "\n", "head is never closed"),
            (report_blocks.DISCUSS_CLOSE + "\n", "line 1: .* closes no discussion"),
            (
                "\n".join([lines[0], 'protocol = "x"', 'run = "y"', "-->", "z"]),
                "missing why",
            ),
            (
                "\n".join([lines[0], *lines[1:4], 'extra = "1"', *lines[4:]]),
                "unknown extra",
            ),
            ("\n".join([lines[0], "protocol = ", *lines[4:]]), "is not TOML"),
            (
                "\n".join([*lines[:5], lines[0], *lines[1:]]),
                "opens inside the one opened at line 1",
            ),
        ):
            with self.assertRaisesRegex(report_blocks.ReportBlockError, said):
                report_blocks.discussions(text)

    def test_a_head_lacking_a_key_is_told_apart_from_one_that_does_not_read(self):
        lines = report_blocks.discussion_lines(P, RUN, "a")
        lacking = "\n".join([lines[0], 'protocol = "x"', 'run = "y"', "-->", "z"])
        with self.assertRaises(report_blocks.DiscussionKeyMissing) as caught:
            report_blocks.discussions(lacking)
        self.assertEqual(
            report_blocks.unread_rule(caught.exception), report_blocks.LAB_104
        )
        # the twin: a head that is no TOML is a block that does not read
        broken = "\n".join([lines[0], "protocol = ", *lines[4:]])
        with self.assertRaises(report_blocks.ReportBlockError) as caught:
            report_blocks.discussions(broken)
        self.assertNotIsInstance(caught.exception, report_blocks.DiscussionKeyMissing)
        self.assertEqual(report_blocks.unread_rule(caught.exception), TECHNICAL_RULE)

    def test_numbers_in_and_beside_stop_at_a_blank_line_and_a_block(self):
        result = report_blocks.with_block("", P, RUN, "auc = 0.69")
        block = "\n".join(report_blocks.discussion_lines(P, RUN, "12 of 30 kept"))
        text = (
            f"# Report\n\nstated 12 before\n{block}\nAUC 0.80 after\n"
            f"{result}\n0.99 far away\n"
        )
        found = report_blocks.discussions(text)
        self.assertEqual(
            report_blocks.numbers_beside_discussed(text, found),
            [(3, ["12"]), (9, ["12", "30"]), (11, ["0.80"])],
        )
        # the block's own lines are generated: no unsourced number there
        self.assertNotIn(9, [n for n, _ in report_blocks.unsourced_numbers(text)])


class AdoptionReplacesTheAccount(unittest.TestCase):
    """`with_block` after a progress account: the result
    block takes the place of the discussion of the same protocol and run;
    other protocols' blocks, other runs' discussions and the prose stay."""

    P, Q, RUN, OLD = (
        "a/PROTOCOL-a.md",
        "b/PROTOCOL-b.md",
        "2026-11-02T00-00-00_aaaa",
        "2026-11-01T00-00-00_bbbb",
    )

    def text(self) -> str:
        return "\n".join(
            [
                "# Report",
                "",
                "Intro.",
                *report_blocks.discussion_lines(self.P, self.OLD, "an earlier run"),
                *report_blocks.discussion_lines(
                    self.P, self.RUN, "measured, audit open"
                ),
                "Middle.",
                *report_blocks.block_lines(self.Q, self.OLD, "other protocol's result"),
                "End.",
                "",
            ]
        )

    def test_the_result_block_stands_where_the_account_stood(self):
        new = report_blocks.with_block(self.text(), self.P, self.RUN, "the result")
        (mine,) = [b for b in report_blocks.blocks(new) if b.protocol == self.P]
        self.assertEqual((mine.run_id, mine.body), (self.RUN, "the result"))
        self.assertEqual(
            [(d.protocol, d.run_id) for d in report_blocks.discussions(new)],
            [(self.P, self.OLD)],
        )
        self.assertTrue(any(b.protocol == self.Q for b in report_blocks.blocks(new)))
        self.assertLess(new.index("Intro."), new.index("the result"))
        self.assertLess(new.index("the result"), new.index("Middle."))
        self.assertIn("End.", new)

    def test_beside_an_existing_result_block_the_account_is_removed(self):
        # OLD adopted first: its result block takes its discussion's place
        text = report_blocks.with_block(self.text(), self.P, self.OLD, "old result")
        new = report_blocks.with_block(
            text + "\n".join(report_blocks.discussion_lines(self.P, self.RUN, "again")),
            self.P,
            self.RUN,
            "new result",
        )
        mine = [b for b in report_blocks.blocks(new) if b.protocol == self.P]
        self.assertEqual([(b.run_id, b.body) for b in mine], [(self.RUN, "new result")])
        self.assertEqual(report_blocks.discussions(new), [])

    def test_the_twin_without_an_account_the_block_is_appended(self):
        text = "# Report\n\nIntro.\n"
        new = report_blocks.with_block(text, self.P, self.RUN, "the result")
        self.assertTrue(new.startswith(text.rstrip("\n")))
        self.assertEqual(report_blocks.blocks(new)[0].run_id, self.RUN)
