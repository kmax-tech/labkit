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
        its protocol's chain is held as for a block (here: a probe)."""
        area = self._area(
            f"c1_pass = True (run {self.RUN})", declared=self.RUN, run_kind="probe"
        )
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(f"the result (run {self.RUN})\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("its number cannot be reported", out)
        self.assertIn("REPORT.md: no generated result block", out)

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
            protocol_fill.path_from_report(
                root / "experiments/01-x/PROTOCOL-x.md", root / "notes/R.md"
            ),
            "../experiments/01-x/PROTOCOL-x.md",
        )
        with self.assertRaisesRegex(ValueError, "whitespace"):
            protocol_fill.path_from_report(root / "a b/PROTOCOL-x.md", root / "R.md")

    def test_an_untouched_report_reopens_nothing(self):
        root, report = self._reported()
        report.write_text("cites 2026-10-07T10-00-00_final\n", encoding="utf-8")
        self.assertEqual(self._gate(root), (0, ""))

    def test_into_refuses_without_a_declared_run(self):
        area = self._area(f"c1_pass = True (run {self.RUN})", declared=None)
        text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no \\[result\\] run declared"):
            protocol_fill.into_report(text, area, "", P)

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
