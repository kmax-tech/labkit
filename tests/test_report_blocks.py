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
import unittest
from pathlib import Path

import test_report_check
from protocol_fixture import completed_run

from labkit.checks import report_blocks
from labkit.gates import report_check
from labkit.tools import protocol_fill

RUN = "2026-10-07T10-00-00_ab12"
P = "experiments/01-x/PROTOCOL-x.md"


class Blocks(unittest.TestCase):
    def test_write_appends_then_replaces_in_place(self):
        text = "# Report\n\nprose\n"
        once = report_blocks.write_block(text, P, RUN, "a = 1 (run x)")
        self.assertEqual(
            [(b.protocol, b.run_id, b.body) for b in report_blocks.blocks(once)],
            [(P, RUN, "a = 1 (run x)")],
        )
        self.assertEqual(report_blocks.write_block(once, P, RUN, "a = 1 (run x)"), once)
        moved = once.replace("prose\n", "prose\n\nafter\n") + "tail\n"
        again = report_blocks.write_block(moved, P, RUN, "a = 2 (run x)")
        self.assertEqual(again, moved.replace("a = 1 (run x)", "a = 2 (run x)"))

    def test_a_new_run_replaces_the_protocols_block_and_no_other(self):
        """A run change: the protocol's block is replaced, not joined by a
        second (review 2026-10-22); another protocol's block stays."""
        other = "experiments/02-y/PROTOCOL-y.md"
        text = report_blocks.write_block("", P, RUN, "a = 1")
        text = report_blocks.write_block(text, other, RUN, "b = 1")
        new = "2026-10-08T10-00-00_cd34"
        text = report_blocks.write_block(text, P, new, "a = 2")
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
        found = report_blocks.blocks(report_blocks.write_block("", P, RUN, "a = 1"))
        BlockSource = report_blocks.BlockSource
        self.assertEqual(
            report_blocks.block_gaps(found, {P: BlockSource(RUN, "a = 1")}), []
        )
        (gap,) = report_blocks.block_gaps(found, {P: BlockSource(RUN, "a = 2")})
        self.assertIn("differs from the protocol's rendering", gap)
        (gap,) = report_blocks.block_gaps(
            found, {P: BlockSource("2026-10-08T10-00-00_cd34", "a = 2")}
        )
        self.assertIn("the protocol declares run 2026-10-08T10-00-00_cd34 now", gap)
        self.assertIn(f"`protocol-fill {P} --into <FILE>` replaces the block", gap)
        (gap,) = report_blocks.block_gaps(
            found, {P: BlockSource(None, None, "it declares no result")}
        )
        self.assertIn(
            "it declares no result — a block shows a declared result only", gap
        )

    def test_cited_ids_must_name_runs_of_the_repo(self):
        text = (
            f"see {RUN}\nand 2026-10-21T12-48-00_final\nand 2026-10-07T10-00-00_ffff\n"
        )
        gaps = report_blocks.cited_gaps(report_blocks.cited_run_ids(text), {RUN})
        self.assertEqual(len(gaps), 2, gaps)
        self.assertIn("line 2: 2026-10-21T12-48-00_final reads as a run id", gaps[0])
        self.assertIn("line 3: cites run 2026-10-07T10-00-00_ffff — no runs/", gaps[1])

    def test_numbers_outside_blocks_are_named_and_ids_dates_versions_are_not(self):
        text = (
            "28 training samples, median 0.449\n"
            f"run {RUN} on 2026-10-22 with labkit 0.102.0\n"
            "1. step one of 5 folds\n"
            "see https://x.org/a/2024/12\n"
            "| 2464-18-8 | `experiments/01-x/runs/` `n=100` |\n"
            + report_blocks.write_block("", P, RUN, "auc = 0.69 (run x)")
        )
        self.assertEqual(report_blocks.unsourced_numbers(text), [(1, ["28", "0.449"])])


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
            f"c1_pass = True (run {self.RUN})", declared=self.RUN, git=git
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
            text.replace("c1_pass = True", "c1_pass = False"), encoding="utf-8"
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
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            report_blocks.write_block(
                "", P, self.RUN, f"c1_pass = True (run {self.RUN})"
            ),
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "it declares no result — a block shows a declared result only", out
        )

    def test_the_declaring_protocol_is_held_though_no_path_touches_its_area(self):
        """A block of an area whose chain fails blocks the report: here the
        run is a probe, and the report lies outside every area."""
        area = self._area(
            f"c1_pass = True (run {self.RUN})", declared=self.RUN, run_kind="probe"
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            report_blocks.write_block(
                "", P, self.RUN, f"c1_pass = True (run {self.RUN})"
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
            f"c1_pass = True (run {self.RUN})", declared=self.RUN, run_kind="probe"
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
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=self.RUN)
        root = area.parent.parent
        report = root / "notes" / "REPORT.md"
        report.parent.mkdir()
        report.write_text(f"c1_pass = True (run {self.RUN})\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"notes/REPORT.md: line 1: cites run {self.RUN}, the declared result of "
            f"../experiments/01-x/PROTOCOL-x.md, without its generated block",
            out,
        )
        self.assertIn(
            "`protocol-fill ../experiments/01-x/PROTOCOL-x.md --into notes/REPORT.md` "
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
            f"c1_pass = True (run {self.RUN})", declared=None, run_kind="probe"
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"a look at run {self.RUN}\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(
            f"REPORT.md: cites {self.RUN}, which no protocol declares as its result",
            out,
        )
        self.assertNotIn("without its generated block", out)
        self.assertNotIn("the answering run of", out)

    def test_the_twin_an_older_run_cited_beside_the_answering_one_is_looked_at(self):
        """A run that is not the one every gate holds the protocol to — here
        an older full run — is an exploration's run: the warning, no block."""
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        older = "2026-10-06T10-00-00_aa11"
        completed_run(area, older, metrics={"c1_pass": False})
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"the first try, run {older}, was dropped\n", encoding="utf-8"
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(f"REPORT.md: cites {older}, which no protocol declares", out)

    def test_the_answering_run_cited_unadopted_blocks_and_names_both_ways_out(self):
        """Sixth haiku round (2026-10-23, t3 and t18): `--from-run` refused,
        REPORT.md written from the run's metrics.json by hand, the hook
        warned of an exploration's citation and let the commit pass — at
        low repeat cost the report is the promotion. The citation of a protocol's
        answering run that declares no result blocks, wherever the report
        lies; the sentence names the adoption and the marker."""
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        root = area.parent.parent
        report = root / "notes" / "REPORT.md"
        report.parent.mkdir()
        report.write_text(
            f"# Report\n\nC1 passed: c1_pass = True (run {self.RUN})\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"notes/REPORT.md: cites {self.RUN}, the answering run of "
            f"../experiments/01-x/PROTOCOL-x.md, which declares no result",
            out,
        )
        self.assertIn(f"PROTOCOL-x.md --from-run {self.RUN}` (it names what the", out)
        self.assertIn(
            f"`run {self.RUN} (not reported: <what refused the adoption, "
            f"what you found>)`",
            out,
        )
        self.assertNotIn("which no protocol declares as its result", out)

    def test_the_twin_the_answering_run_cited_as_not_reported_with_its_why_passes(
        self,
    ):
        """The way out for a looked-at run: the marker with the why beside
        the id. No blocker, no exploration warning — the report says so."""
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"Run {self.RUN} (not reported: adoption refused — target leakage "
            f"through G_VRH, two accepted blockers unreviewed); the question "
            f"stays open.\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertNotIn("BLOCKER", out)
        self.assertNotIn("which no protocol declares", out)
        self.assertNotIn("beside a run cited as not reported", out)

    def test_a_marker_without_its_why_blocks(self):
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"run {self.RUN} (not reported)\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"REPORT.md: line 1: run {self.RUN} is cited as not reported without "
            f"the why",
            out,
        )

    def test_numbers_beside_a_run_cited_as_not_reported_are_a_hint(self):
        """Static evidence: the paragraph of a marked citation is named when
        it states numbers; a number in another paragraph is only among the
        unsourced ones. Nothing blocks."""
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"# Report\n\nRun {self.RUN} (not reported: adoption refused — leakage).\n"
            f"Its AUC was 0.80 all the same.\n\nElsewhere 0.99 is stated.\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "REPORT.md: numbers on 1 line(s) beside a run cited as not reported", out
        )
        self.assertIn("    REPORT.md:4: 0.80\n", out)
        self.assertIn("no assigned source found for the numbers on 2 line(s)", out)

    def test_a_marker_on_a_declared_run_blocks(self):
        """`not reported` beside a run a protocol declares as its result is
        a false claim the gate can read: the block shows the number."""
        root, report = self._reported()
        with report.open("a", encoding="utf-8") as f:
            f.write(f"\nrun {self.RUN} (not reported: just a look)\n")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"run {self.RUN} is cited as not reported, but "
            f"experiments/01-x/PROTOCOL-x.md declares it as its result",
            out,
        )

    def test_a_marker_reads_its_why_and_owes_one(self):
        text = (
            f"a look at run {RUN} (not reported: adoption refused — leakage)\n"
            f"and run {RUN} (not reported)\n"
            f"and run {RUN} plain\n"
        )
        marked = report_blocks.not_reported(text)
        self.assertEqual(
            [(m.line, m.why) for m in marked],
            [(1, "adoption refused — leakage"), (2, "")],
        )
        self.assertEqual(
            report_blocks.marker_gaps(marked),
            [
                f"line 2: run {RUN} is cited as not reported without the why — write "
                f"`run {RUN} (not reported: <what refused the adoption, what you found>)`"
            ],
        )

    def test_numbers_beside_a_marker_stop_at_a_blank_line_and_a_block(self):
        block = report_blocks.write_block("", P, RUN, "auc = 0.69")
        text = (
            f"# Report\n\nstated 12 before\nrun {RUN} (not reported: a look)\n"
            f"AUC 0.80 after\n{block}\n0.99 far away\n"
        )
        marked = report_blocks.not_reported(text)
        self.assertEqual(
            report_blocks.numbers_beside_not_reported(text, marked),
            [(3, ["12"]), (5, ["0.80"])],
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
        completed_run(area, new, metrics={"c1_pass": False})
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8").replace(
            f'run = "{self.RUN}"', f'run = "{new}"'
        )
        proto.write_text(text, encoding="utf-8")
        _, out = self._gate(root, report)
        self.assertIn(f"the protocol declares run {new} now", out)
        self.assertNotIn(f"--from-run {self.RUN}", out)
        written, _ = protocol_fill.into_report(
            text, area, report.read_text(encoding="utf-8"), P
        )
        report.write_text(written, encoding="utf-8")
        self.assertEqual(
            [(b.run_id, b.body) for b in report_blocks.blocks(written)],
            [(new, f"c1_pass = False (run {new})")],
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
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no \\[result\\] run declared"):
            protocol_fill.into_report(text, area, "", P)

    def test_the_two_step_commit_reaches_the_committed_report(self):
        """Sixth haiku round (2026-10-23, t5, commits b47f915 and b629ddd):
        REPORT.md citing the run was committed while the protocol with the
        declaration stayed unstaged — the index's protocol declared nothing,
        the hook warned of an exploration's citation and let it pass; the
        next commit staged the protocol, and the untouched report was not
        held again. Now a protocol whose declaration differs from HEAD's
        reaches the committed reports citing that run."""
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None, git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"c1_pass = True (run {self.RUN})\n", encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        # step one, as t5 wrote it: the answering run's number without the
        # adoption — held at this commit already (the t3/t18 case)
        self.assertEqual(code, 1, out)
        self.assertIn("the answering run of experiments/01-x/PROTOCOL-x.md", out)
        # step one as an exploration would write it passes
        report.write_text(
            f"c1_pass = True (run {self.RUN} (not reported: adoption pending))\n",
            encoding="utf-8",
        )
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self._git(root, "commit", "-qm", "report")
        # step two: the protocol declares the run; the report is untouched
        proto = area / "PROTOCOL-x.md"
        declaring = protocol_fill.fill_result_run(
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
            "PROTOCOL-x.md newly declares as its result) ═══",
            out,
        )
        self.assertIn(
            f"REPORT.md: line 1: cites run {self.RUN}, the declared result of "
            f"experiments/01-x/PROTOCOL-x.md, without its generated block",
            out,
        )
        self.assertIn(
            "is cited as not reported, but experiments/01-x/PROTOCOL-x.md "
            "declares it as its result",
            out,
        )
        # the twin: the block written into the report, the marker dropped,
        # staged with the protocol — one consistent commit — passes, the
        # report held once
        written, _ = protocol_fill.into_report(
            declaring, area, f"c1_pass = True (run {self.RUN})\n", P
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
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        declaring = protocol_fill.fill_result_run(
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

    def test_staged_reads_the_report_as_the_index_holds_it(self):
        root, report = self._reported(git=True)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        # only the tree retypes the number: the commit carries the rendered block
        text = report.read_text(encoding="utf-8")
        report.write_text(
            text.replace("c1_pass = True", "c1_pass = False"), encoding="utf-8"
        )
        self.assertEqual(self._gate(root, report, staged=True)[0], 0)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn("differs from the protocol's rendering", out)


if __name__ == "__main__":
    unittest.main()
