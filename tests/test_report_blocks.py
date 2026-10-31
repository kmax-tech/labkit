"""A report outside the protocol: generated result blocks, cited run ids,
numbers without an assigned source (`checks/report_blocks`), and the gate
that holds a changed report at the stop and the commit
(`report_check.if_reported`).

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): the protocol's
Answer was held exactly while REPORT.md at the repository root stated
counts and a median no run produced, and no gate read the file.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import test_report_check
from protocol_fixture import completed_run

from labkit.checks import report_blocks
from labkit.formats import report_reviews
from labkit.gates import report_check, report_hold, report_review
from labkit.tools import protocol_fill
from labkit.tools import protocol_result

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
        second (review 2026-10-22); another protocol's block stays."""
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
        # from there (audit 2026-10-27, third, S2)
        self.assertIn(
            f"`protocol-fill {P} --into REPORT.md` replaces the block", gap.line
        )
        (gap,) = report_blocks.block_gaps(
            found, {P: BlockSource(None, None, "it has adopted no result")}, report
        )
        self.assertIn(
            "it has adopted no result — a block shows an adopted result only", gap.line
        )

    def test_cited_ids_must_name_runs_of_the_repo(self):
        text = (
            f"see {RUN}\nand 2026-10-21T12-48-00_final\nand 2026-10-07T10-00-00_ffff\n"
        )
        gaps = report_blocks.cited_gaps(report_blocks.cited_run_ids(text), {RUN})
        self.assertEqual(len(gaps), 2, gaps)
        self.assertIn(
            "line 2: 2026-10-21T12-48-00_final reads as a run id", gaps[0].line
        )
        self.assertIn(
            "line 3: cites run 2026-10-07T10-00-00_ffff — no runs/", gaps[1].line
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
        line came back split, differed from its head, and writing it again
        wrote the same split line (audit 2026-10-27, step 1.4). It is
        refused as more than one line; the twin, every other control
        character, reads back (`test_control_characters_…`)."""
        for why in ("carriage\rreturn", "trailing\r inside"):
            with self.subTest(why=why):
                with self.assertRaisesRegex(ValueError, "one line"):
                    report_blocks.discussion_lines(P, RUN, why)

    def test_control_characters_in_the_why_read_back_from_the_file(self):
        """The head's strings are written by `protocol_block.toml_string`,
        the one TOML string writer: json.dumps here left DEL raw, a head
        tomllib refuses, so the report no longer read (audit 2026-10-27,
        criterion-15). Each why reads back unchanged, through the file as the gate
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
        report then ended in a traceback. The refusal names the field."""
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


class ReportFiles(unittest.TestCase):
    """The gate: a changed report citing runs is held — its blocks to the
    declaring protocol (which the stations hold too), its run ids to the
    repo's runs; its other numbers are hints. An untouched report is not."""

    RUN = test_report_check.IfReported.RUN
    _area = test_report_check.IfReported._area
    _git = staticmethod(test_report_check.IfReported._git)

    def _gate(self, root: Path, *paths: Path, staged: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.if_reported(list(paths), root, staged=staged)
        return code, buf.getvalue()

    def _reported(self, git: bool = False) -> tuple[Path, Path]:
        """(the repo root, its REPORT.md with the declared result's block)."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN, git=git
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        new, _ = protocol_fill.into_report(text, area, "# Report\n\n28 samples\n", P)
        report.write_text(new, encoding="utf-8")
        return root, report

    def test_the_twin_a_rendered_block_passes_and_prose_numbers_are_hints(self):
        root, report = self._reported()
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn("finalized, audited, checked", out)  # its protocol held too
        self.assertIn(
            "REPORT.md: no assigned source found for the numbers on 1 line(s)", out
        )
        self.assertIn("    REPORT.md:3: 28\n", out)

    def test_a_retyped_number_in_the_block_blocks(self):
        root, report = self._reported()
        text = report.read_text(encoding="utf-8")
        report.write_text(
            text.replace("criterion-1 met", "criterion-1 missed"), encoding="utf-8"
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("differs from the protocol's rendering", out)

    def test_an_invented_run_id_blocks(self):
        root, report = self._reported()
        with report.open("a", encoding="utf-8") as f:
            f.write("best run 2026-10-07T10-00-00_final\n")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("reads as a run id but is not one runlog writes", out)

    def test_a_block_of_a_run_no_protocol_declares_blocks(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            report_blocks.with_block(
                "", P, self.RUN, f"criterion-1 met · recorded: (run {self.RUN})"
            ),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "it has adopted no result — a block shows an adopted result only", out
        )

    def test_the_declaring_protocol_is_held_though_no_path_touches_its_area(self):
        """A block of an area whose chain fails blocks the report: here the
        run is a probe, and the report lies outside every area."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})",
            declared=self.RUN,
            run_kind="probe",
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            report_blocks.with_block(
                "", P, self.RUN, f"criterion-1 met · recorded: (run {self.RUN})"
            ),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("its number cannot be reported", out)

    def test_a_cited_declared_run_holds_its_protocol_without_a_block(self):
        """A report that cites the declared run in prose shows that result:
        its protocol's chain is held as for a block (here: a probe), and the
        block it owes is named."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})",
            declared=self.RUN,
            run_kind="probe",
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"the result (run {self.RUN})\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("its number cannot be reported", out)
        self.assertIn("without its generated block", out)

    def test_a_cited_declared_result_without_its_block_blocks(self):
        """Fifth haiku round (2026-10-22): all three labkit reports retyped
        the declared number in prose; 0.103.0 warned. The chain is clean
        here — the missing block alone blocks, and the sentence carries the
        command with the paths as the report names them."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN
        )
        root = area.parent.parent
        report = root / "notes" / "REPORT.md"
        report.parent.mkdir()
        report.write_text(
            f"criterion_1_pass = True (run {self.RUN})\n", encoding="utf-8"
        )
        with contextlib.chdir(root):  # where AGENTS.md runs every command
            code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"notes/REPORT.md: line 1: cites run {self.RUN}, the adopted result of "
            f"../experiments/01-x/PROTOCOL-x.md, without its generated block",
            out,
        )
        # the command runs from there: it named the protocol relative to the
        # report and the report relative to the repo (audit 2026-10-27, S2)
        self.assertIn(
            "`protocol-fill experiments/01-x/PROTOCOL-x.md --into notes/REPORT.md` "
            "writes it",
            out,
        )
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        written, _ = protocol_fill.into_report(
            text,
            area,
            report.read_text(encoding="utf-8"),
            "../experiments/01-x/PROTOCOL-x.md",
        )
        report.write_text(written, encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)  # the twin: the block written, the prose stays

    def test_the_twin_a_cited_probe_no_protocol_declares_owes_no_block(self):
        """An exploration's run is cited, not reported: a warning says no
        protocol declares it; nothing is owed, nothing blocks. A probe's
        number could not be reported, so its citation is no promotion."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})",
            declared=None,
            run_kind="probe",
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"a look at run {self.RUN}\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(
            f"REPORT.md: cites {self.RUN}, which no protocol has adopted as its result",
            out,
        )
        self.assertNotIn("without its generated block", out)
        self.assertNotIn("the answering run of", out)

    def test_the_twin_an_older_run_cited_beside_the_answering_one_is_looked_at(self):
        """A run that is not the one every gate holds the protocol to — here
        an older full run — is an exploration's run: the warning, no block."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        older = "2026-10-06T10-00-00_aa11"
        completed_run(area, older, metrics={"criterion_1_pass": False})
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"the first try, run {older}, was dropped\n", encoding="utf-8"
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(f"REPORT.md: cites {older}, which no protocol has adopted", out)

    def _discussed(self, report: Path, area: Path, why: str, before: str = "") -> None:
        """REPORT with BEFORE and the discussion block of RUN, as `--discuss`
        writes it."""
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        report.write_text(
            protocol_fill.discuss_into(
                text,
                area,
                before,
                report_blocks.path_from_report(area / "PROTOCOL-x.md", report),
                self.RUN,
                why,
            ),
            encoding="utf-8",
        )

    def _reviewed(
        self,
        report: Path,
        area: Path,
        claims: tuple[report_reviews.ReportClaim, ...] = (),
        *,
        again: bool = False,
        text: str | None = None,
    ) -> None:
        """A report review of REPORT (TEXT, else as the tree holds it) in its
        state now, naming CLAIMS — what `--report-review` writes."""
        proto = area / "PROTOCOL-x.md"
        text = text if text is not None else report.read_text(encoding="utf-8")
        discussed = report_review.discussed_under(report, text, proto)
        pieces = report_review.review_pieces(
            area, report, text, proto, proto.read_text(encoding="utf-8"), discussed
        )
        whole, parts = report_reviews.fingerprint(pieces)
        rkey, pkey = report_review.review_keys(area, report, proto)
        report_reviews.write_report_review(
            area,
            model="m",
            report=rkey,
            protocol=pkey,
            whole=whole,
            parts=parts,
            claims=list(claims),
            again=again,
        )

    def test_the_answering_run_cited_unadopted_blocks_and_names_both_ways_out(self):
        """Sixth haiku round (2026-10-23, t3 and t18): `--from-run` refused,
        REPORT.md written from the run's metrics.json by hand, the hook
        warned of an exploration's citation and let the commit pass — at
        low repeat cost the report is the promotion. The citation of a protocol's
        answering run that declares no result blocks, wherever the report
        lies; the sentence names the adoption and the discussion block."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "notes" / "REPORT.md"
        report.parent.mkdir()
        report.write_text(
            f"# Report\n\ncriterion-1 passed: criterion_1_pass = True (run {self.RUN})\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"notes/REPORT.md: cites {self.RUN}, the answering run of "
            f"../experiments/01-x/PROTOCOL-x.md, which has adopted no result",
            out,
        )
        self.assertIn("`labkit-adopt ", out)
        self.assertIn(f" {self.RUN}` (it names what the", out)
        self.assertIn(
            f'PROTOCOL-x.md --discuss {self.RUN} --why "<what refused the adoption, '
            f'what you found>" --into notes/REPORT.md`',
            out,
        )
        self.assertNotIn("which no protocol has adopted as its result", out)

    def test_the_prose_marker_is_not_read_eighth_round_t3(self):
        """Eighth haiku round (2026-10-26, t3): the agent wrote the prose
        marker with backticks around the id; the old pattern did not read it,
        the gate held twice and the agent committed with `--no-verify`. The
        prose marker is no form the gate reads any more, backticks or not:
        the citation is held as the promotion, the sentence names the
        discussion block."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        for cited in (f"`{self.RUN}`", self.RUN):
            report.write_text(
                f"# Report\n\nRun {cited} (not reported: adoption refused — the "
                f"analysis remains unresolved).\n\nout-of-fold R² = 0.726\n",
                encoding="utf-8",
            )
            code, out = self._gate(root, report)
            self.assertEqual(code, 1, out)
            self.assertIn(f"REPORT.md: cites {self.RUN}, the answering run of", out)
            self.assertIn(f"--discuss {self.RUN} --why", out)
            self.assertNotIn("--report-review", out)  # nothing is discussed

    def test_the_twin_the_answering_run_in_a_discussion_block_passes(self):
        """The way out for a looked-at run: the discussion block with the
        why. No blocker, no exploration warning — the report says so; the
        review is named."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(
            report,
            area,
            "adoption refused — target leakage through G_VRH, two accepted "
            "blockers unreviewed",
            "# Report\n\nThe question stays open.\n",
        )
        # eighth haiku round (t18): the review was a hint and was passed
        # over — now the report is held until a review of its state is done
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"REPORT.md: discusses {self.RUN} as not reported and has no clean "
            f"report review of this state (one naming no claim)",
            out,
        )
        self.assertRegex(out, r"--report-review \S*REPORT\.md` \(one model call\)")
        self._reviewed(report, area)
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertNotIn("BLOCKER", out)
        self.assertNotIn("which no protocol has adopted", out)
        self.assertNotIn("in or beside a discussed run", out)

    def test_a_claim_holds_and_a_later_clean_draw_does_not_release(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "audit failed", "# Report\n\ncriterion-1 PASS\n")
        claim = report_reviews.ReportClaim(
            3, "result", "criterion-1 PASS of the discussed run"
        )
        self._reviewed(report, area, (claim,))
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("the report review holds this state on the discussion of", out)
        self.assertIn("line 3 (result): criterion-1 PASS of the discussed run", out)
        self._reviewed(report, area)  # a clean draw on the same state
        self._reviewed(report, area, again=True)
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("CLAIM in ", out)
        # the way out: the report changes, and a review of that state is clean
        report.write_text(
            report.read_text(encoding="utf-8").replace(
                "criterion-1 PASS", "No result."
            ),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"changed since: REPORT \S*REPORT\.md —")
        self._reviewed(report, area)
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)

    def test_a_clean_review_of_the_tree_does_not_release_another_staged_report(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None, git=True
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "audit failed", "# Report\n\ncriterion-1 PASS\n")
        self._git(root, "add", "REPORT.md")
        honest = report.read_text(encoding="utf-8").replace(
            "criterion-1 PASS", "No result."
        )
        report.write_text(honest, encoding="utf-8")
        self._reviewed(report, area)  # reviewed the tree, not what is staged
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)  # its record not staged: the area differs
        self.assertIn("whose working tree differs from the index", out)
        self._git(root, "add", str(area / "audits"))
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)  # the record staged, the report not
        self.assertIn("has no clean report review of this state", out)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)

    def test_a_review_of_unstaged_sources_releases_no_commit(self):
        """Review 2026-10-26: the review read a run's metrics from the tree
        while the commit carried others — the gate released a state the
        commit did not hold. At the commit the area's tree must be the
        index's."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None, git=True
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "audit failed", "# Report\n\nNo result.\n")
        self._reviewed(report, area)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        metrics = area / "runs" / self.RUN / "metrics.json"
        metrics.write_text('{"criterion_1_pass": false}', encoding="utf-8")
        self._reviewed(report, area)  # a review of the unstaged metrics
        self._git(root, "add", str(area / "audits"))
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("whose working tree differs from the index", out)
        self.assertIn("metrics.json", out)

    def test_a_source_change_reaches_the_untouched_discussing_report(self):
        """Review 2026-10-26: only a source of the review changed — the
        report untouched — and the commit passed with a stale review."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None, git=True
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "audit failed", "# Report\n\nNo result.\n")
        self._reviewed(report, area)
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "report and its review")
        metrics = area / "runs" / self.RUN / "metrics.json"
        metrics.write_text('{"criterion_1_pass": false}', encoding="utf-8")
        self._git(root, "add", str(metrics))
        code, out = self._gate(root, metrics, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"═══ report-check REPORT.md ({report_hold.DISCUSSES_TOUCHED}) ═══", out
        )
        self.assertIn("has no clean report review of this state", out)
        self.assertRegex(out, r"changed since: FILE: \S*metrics\.json")
        # the twin: a review of the new state, staged with it, passes
        self._reviewed(report, area)
        self._git(root, "add", str(area / "audits"))
        code, out = self._gate(root, metrics, staged=True)
        self.assertEqual(code, 0, out)

    def test_a_discussion_without_its_why_or_edited_by_hand_blocks(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "a look")
        text = report.read_text(encoding="utf-8")
        report.write_text(text.replace('why = "a look"', 'why = ""'), encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(f"REPORT.md: line 2: the discussion of run {self.RUN}", out)
        self.assertIn("has no why", out)
        report.write_text(
            text.replace("not reported: a look", "not reported: a better look"),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("its line differs from its head", out)

    def test_a_discussion_of_a_run_its_protocols_area_lacks_blocks(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        other = "2026-10-06T10-00-00_aa11"
        (root / "experiments" / "02-y" / "runs" / other).mkdir(parents=True)
        report.write_text(
            "\n".join(
                report_blocks.discussion_lines(
                    "experiments/01-x/PROTOCOL-x.md", other, "a look"
                )
            )
            + "\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"experiments/01-x/PROTOCOL-x.md's area has no runs/{other}/", out
        )

    def test_numbers_in_and_beside_a_discussion_are_a_hint(self):
        """Static evidence: the discussion and the paragraphs around it are
        named when they state numbers; a number in another paragraph is only
        among the unsourced ones. Nothing blocks."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        self._discussed(report, area, "adoption refused — leakage", "# Report\n")
        with report.open("a", encoding="utf-8") as f:
            f.write("Its AUC was 0.80 all the same.\n\nElsewhere 0.99 is stated.\n")
        self._reviewed(report, area)
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "REPORT.md: numbers on 1 line(s) in or beside a discussed run", out
        )
        self.assertIn("    REPORT.md:10: 0.80\n", out)
        self.assertIn("no assigned source found for the numbers on 2 line(s)", out)

    def test_a_discussion_of_a_declared_run_blocks(self):
        """ "not reported" beside a run a protocol declares as its result is
        a false claim the gate can read: the result block shows the number."""
        root, report = self._reported()
        with report.open("a", encoding="utf-8") as f:
            f.write(
                "\n".join(report_blocks.discussion_lines(P, self.RUN, "just a look"))
                + "\n"
            )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"run {self.RUN} is discussed as not reported, but "
            f"experiments/01-x/PROTOCOL-x.md has adopted it as its result",
            out,
        )

    def test_discuss_refuses_a_declared_run_and_a_run_the_area_lacks(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=self.RUN
        )
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "is the protocol's adopted result"):
            protocol_fill.discuss_into(text, area, "", P, self.RUN, "a look")
        other = "2026-10-06T10-00-00_aa11"
        with self.assertRaisesRegex(ValueError, f"no runs/{other}/"):
            protocol_fill.discuss_into(text, area, "", P, other, "a look")

    def test_discuss_needs_why_and_into(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        proto = str(area / "PROTOCOL-x.md")
        for argv in (
            [proto, "--discuss", self.RUN, "--into", "R.md"],
            [proto, "--discuss", self.RUN, "--why", "x"],
            [proto, "--why", "x", "--into", "R.md"],
        ):
            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                protocol_fill.main(argv)

    def test_discuss_writes_then_replaces_its_block_and_keeps_others(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        proto = str(area / "PROTOCOL-x.md")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                protocol_fill.main(
                    [
                        proto,
                        "--discuss",
                        self.RUN,
                        "--why",
                        "one",
                        "--into",
                        str(report),
                    ]
                ),
                0,
            )
            self.assertEqual(
                protocol_fill.main(
                    [
                        proto,
                        "--discuss",
                        self.RUN,
                        "--why",
                        "two",
                        "--into",
                        str(report),
                    ]
                ),
                0,
            )
        found = report_blocks.discussions(report.read_text(encoding="utf-8"))
        self.assertEqual([(d.run_id, d.why) for d in found], [(self.RUN, "two")])

    def test_discuss_with_a_control_character_writes_a_block_that_reads_back(self):
        """A DEL in `--why` wrote a head tomllib refuses: the next `--discuss`
        and the gate refused the report (audit 2026-10-27, C15). A lone
        surrogate ended in a traceback; it is refused, nothing written."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        proto = str(area / "PROTOCOL-x.md")

        def discuss(why: str) -> tuple[int, str]:
            err = io.StringIO()
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err),
            ):
                rc = protocol_fill.main(
                    [proto, "--discuss", self.RUN, "--why", why, "--into", str(report)]
                )
            return rc, err.getvalue()

        rc, err = discuss("bad \udcff byte")
        self.assertEqual(rc, 2, err)
        self.assertIn("--why: a lone surrogate U+DCFF", err)
        self.assertFalse(report.exists())
        for why in ("del\x7f one", "del\x7f two"):
            self.assertEqual(discuss(why), (0, ""))
        found = report_blocks.discussions(report.read_text(encoding="utf-8"))
        self.assertEqual(
            [(d.run_id, d.why) for d in found], [(self.RUN, "del\x7f two")]
        )

    def test_blocks_owed_names_each_declaring_protocol_once(self):
        other = "2026-10-08T10-00-00_cd34"
        cited = [(3, RUN), (5, RUN), (7, other), (9, "2026-10-09T10-00-00_ef56")]
        declaring = {RUN: [P], other: [P, "x/PROTOCOL-y.md"]}
        self.assertEqual(
            report_blocks.blocks_owed(cited, declaring, set()),
            [(3, RUN, P), (7, other, "x/PROTOCOL-y.md")],
        )
        self.assertEqual(
            report_blocks.blocks_owed(cited, declaring, {P}),
            [(7, other, "x/PROTOCOL-y.md")],
        )

    def test_a_run_change_names_the_new_run_and_into_replaces_the_block(self):
        """Review 2026-10-22: after a new run was adopted, `--into` appended
        a second block, the old one blocked as undeclared, and the message
        offered to adopt the old run again."""
        root, report = self._reported()
        area = root / "experiments" / "01-x"
        new = "2026-10-08T10-00-00_cd34"
        completed_run(area, new, metrics={"criterion_1_pass": False})
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8").replace(
            f'run = "{self.RUN}"', f'run = "{new}"'
        )
        proto.write_text(text, encoding="utf-8")
        _, out = self._gate(root, report)
        self.assertIn(f"the protocol has adopted run {new} now", out)
        self.assertNotIn(f" {self.RUN}` (it names what the", out)
        written, _ = protocol_fill.into_report(
            text, area, report.read_text(encoding="utf-8"), P
        )
        report.write_text(written, encoding="utf-8")
        self.assertEqual(
            [(b.run_id, b.body) for b in report_blocks.blocks(written)],
            [(new, f"criterion-1 missed · recorded: (run {new})")],
        )
        _, out = self._gate(root, report)
        self.assertNotIn("the result block of", out)

    def test_path_from_report_names_the_protocol_from_the_reports_directory(self):
        root = Path("/r")
        self.assertEqual(
            report_blocks.path_from_report(
                root / "experiments/01-x/PROTOCOL-x.md", root / "notes/R.md"
            ),
            "../experiments/01-x/PROTOCOL-x.md",
        )
        with self.assertRaisesRegex(ValueError, "whitespace"):
            report_blocks.path_from_report(root / "a b/PROTOCOL-x.md", root / "R.md")

    def test_an_untouched_report_reopens_nothing(self):
        root, report = self._reported()
        report.write_text("cites 2026-10-07T10-00-00_final\n", encoding="utf-8")
        self.assertEqual(self._gate(root), (0, ""))

    def test_into_refuses_without_a_declared_run(self):
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None
        )
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError, "no run adopted \\(\\[result\\] run\\)"
        ):
            protocol_fill.into_report(text, area, "", P)

    def test_the_two_step_commit_reaches_the_committed_report(self):
        """Sixth haiku round (2026-10-23, t5, commits b47f915 and b629ddd):
        REPORT.md citing the run was committed while the protocol with the
        declaration stayed unstaged — the index's protocol declared nothing,
        the hook warned of an exploration's citation and let it pass; the
        next commit staged the protocol, and the untouched report was not
        held again. Now a protocol whose declaration differs from HEAD's
        reaches the committed reports citing that run."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None, git=True
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"criterion_1_pass = True (run {self.RUN})\n", encoding="utf-8"
        )
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        # step one, as t5 wrote it: the answering run's number without the
        # adoption — held at this commit already (the t3/t18 case)
        self.assertEqual(code, 1, out)
        self.assertIn("the answering run of experiments/01-x/PROTOCOL-x.md", out)
        # step one as an exploration would write it passes
        self._discussed(report, area, "adoption pending")
        self._reviewed(report, area)
        # the review's record is evidence the commit carries with the report
        self._git(root, "add", "REPORT.md", str(area / "audits"))
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self._git(root, "commit", "-qm", "report")
        # step two: the protocol declares the run; the report is untouched
        proto = area / "PROTOCOL-x.md"
        declaring = protocol_result.fill_result_run(
            proto.read_text(encoding="utf-8"), self.RUN
        )
        proto.write_text(declaring, encoding="utf-8")
        code, out = self._gate(root, proto)  # the stop hears it first…
        self.assertEqual(code, 1, out)
        self._git(root, "add", str(proto))
        code, out = self._gate(root, proto, staged=True)  # …the commit holds
        self.assertEqual(code, 1, out)
        self.assertIn(
            "═══ report-check REPORT.md (a committed report citing a run "
            "PROTOCOL-x.md newly adopts as its result) ═══",
            out,
        )
        self.assertIn(
            f"REPORT.md: line 4: cites run {self.RUN}, the adopted result of "
            f"experiments/01-x/PROTOCOL-x.md, without its generated block",
            out,
        )
        self.assertIn(
            "is discussed as not reported, but experiments/01-x/PROTOCOL-x.md "
            "has adopted it as its result",
            out,
        )
        # the twin: the result block written into the report, the discussion
        # dropped,
        # staged with the protocol — one consistent commit — passes, the
        # report held once
        written, _ = protocol_fill.into_report(
            declaring, area, f"criterion_1_pass = True (run {self.RUN})\n", P
        )
        report.write_text(written, encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, proto, report, staged=True)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("═══ report-check REPORT.md"), 1)
        self.assertIn("(a report citing runs)", out)

    def test_the_twin_a_committed_report_with_its_block_passes_the_declaring_commit(
        self,
    ):
        """The consistent state reached the other way round: the committed
        report already carries the generated block of the run the staged
        protocol now declares — held, and clean. A protocol staged again
        with the declaration HEAD already holds reaches nothing."""
        area = self._area(
            f"criterion-1 met · recorded: (run {self.RUN})", declared=None, git=True
        )
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        declaring = protocol_result.fill_result_run(
            proto.read_text(encoding="utf-8"), self.RUN
        )
        written, _ = protocol_fill.into_report(declaring, area, "# Report\n\n", P)
        (root / "REPORT.md").write_text(written, encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        self._git(root, "commit", "-qm", "report with its block")
        proto.write_text(declaring, encoding="utf-8")
        self._git(root, "add", str(proto))
        code, out = self._gate(root, proto, staged=True)
        self.assertEqual(code, 0, out)
        self.assertIn("a committed report citing a run PROTOCOL-x.md newly", out)
        self.assertNotIn("without its generated block", out)
        self._git(root, "commit", "-qm", "declared")
        proto.write_text(declaring + "\nmore prose\n", encoding="utf-8")
        self._git(root, "add", str(proto))
        code, out = self._gate(root, proto, staged=True)
        self.assertEqual(code, 0, out)
        self.assertNotIn("REPORT.md", out)  # the declaration is HEAD's: nothing reached

    def _linked(self, git: bool = False) -> tuple[Path, Path]:
        """(the repo root, REPORT.md) where REPORT.md is a symbolic link to
        data/REPORT.md, the rendered report with its number retyped — the
        red team's s1 (audit 2026-10-27, A10)."""
        root, report = self._reported(git=git)
        (root / "data").mkdir()
        target = root / "data" / "REPORT.md"
        text = report.read_text(encoding="utf-8")
        target.write_text(
            text.replace("criterion-1 met", "criterion-1 missed"), encoding="utf-8"
        )
        report.unlink()
        report.symlink_to(Path("data") / "REPORT.md")
        return root, report

    def test_a_report_linked_into_data_is_refused_naming_the_copy(self):
        """quality-check-10: the link was resolved before the data/ test, so the forged
        block behind it passed the stop and the commit."""
        root, report = self._linked()
        code, out = self._gate(root, report, root / "data" / "REPORT.md")
        self.assertEqual(code, 1, out)
        self.assertIn("REPORT.md: a symbolic link to data/REPORT.md", out)
        self.assertIn("`rm REPORT.md && cp data/REPORT.md REPORT.md`", out)
        # the copy in its place is held as any report: the retyped number
        report.unlink()
        report.write_text(
            (root / "data" / "REPORT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertNotIn("symbolic link", out)
        self.assertIn("differs from the protocol's rendering", out)

    def test_a_staged_link_is_refused_until_the_index_holds_the_copy(self):
        root, report = self._linked(git=True)
        self._git(root, "add", "REPORT.md", "data/REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "`rm REPORT.md && cp data/REPORT.md REPORT.md && git add REPORT.md`", out
        )
        # copied in the tree, not staged: the commit still carries the link
        report.unlink()
        report.write_text(
            (root / "data" / "REPORT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("a symbolic link to data/REPORT.md", out)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertNotIn("symbolic link", out)
        self.assertIn("differs from the protocol's rendering", out)

    def test_a_staged_chain_of_links_is_followed_and_refused(self):
        """REPORT.md -> B.md -> data/REPORT.md: the index holds two links;
        the report the chain ends at is read, and the first link refused.
        A chain in a circle reads as nothing, and stops."""
        root, report = self._linked(git=True)
        report.unlink()
        report.symlink_to("B.md")
        (root / "B.md").symlink_to(Path("data") / "REPORT.md")
        self._git(root, "add", "REPORT.md", "B.md", "data/REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("REPORT.md: a symbolic link to B.md", out)
        own = root.resolve() / "REPORT.md"
        circle = {own: "B.md", root.resolve() / "B.md": "REPORT.md"}
        self.assertEqual(
            report_hold.report_entry(root, own, staged=True, index_links=circle),
            ("B.md", None),
        )

    def test_staged_reads_the_reports_own_entry_not_a_link_in_the_tree(self):
        """The index holds the retyped report as a file, the tree a link to
        a file that cites nothing: the commit carries the retyped number."""
        root, report = self._reported(git=True)
        text = report.read_text(encoding="utf-8")
        report.write_text(
            text.replace("criterion-1 met", "criterion-1 missed"), encoding="utf-8"
        )
        self._git(root, "add", "REPORT.md")
        (root / "NOTE.md").write_text("nothing cited\n", encoding="utf-8")
        report.unlink()
        report.symlink_to("NOTE.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("differs from the protocol's rendering", out)

    def test_the_twin_a_link_that_cites_no_run_is_no_report(self):
        """CLAUDE.md -> AGENTS.md, as labkit-init stamps it, is no report:
        neither the stop nor the commit names it."""
        root, _ = self._reported(git=True)
        (root / "AGENTS.md").write_text("# Agents\n\nRead TODO.md.\n", encoding="utf-8")
        (root / "CLAUDE.md").symlink_to("AGENTS.md")
        self._git(root, "add", "AGENTS.md", "CLAUDE.md")
        for staged in (False, True):
            code, out = self._gate(root, root / "CLAUDE.md", staged=staged)
            self.assertEqual((code, out), (0, ""))

    def test_a_link_to_a_held_report_is_read_where_the_report_lies(self):
        """CLAUDE.md -> AGENTS.md was refused once AGENTS.md cited a run, and
        the printed way out replaced the link with a copy — the convention
        the twin above protects (cold review 2026-10-27). A link ending at
        a place a report is held is no report itself: the file it points to
        is held where it lies. The twin: a link into data/ is refused
        (above)."""
        root, report = self._reported(git=True)
        (root / "AGENTS.md").write_text(
            report.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (root / "CLAUDE.md").symlink_to("AGENTS.md")
        self._git(root, "add", "AGENTS.md", "CLAUDE.md")
        for staged in (False, True):
            code, out = self._gate(root, root / "CLAUDE.md", staged=staged)
            self.assertEqual((code, out), (0, ""))
            code, out = self._gate(root, root / "AGENTS.md", staged=staged)
            self.assertNotIn("symbolic link", out)
            self.assertIn("AGENTS.md", out)

    def test_staged_reads_the_report_as_the_index_holds_it(self):
        root, report = self._reported(git=True)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        # only the tree retypes the number: the commit carries the rendered block
        text = report.read_text(encoding="utf-8")
        report.write_text(
            text.replace("criterion-1 met", "criterion-1 missed"), encoding="utf-8"
        )
        self.assertEqual(self._gate(root, report, staged=True)[0], 0)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("differs from the protocol's rendering", out)


if __name__ == "__main__":
    unittest.main()
