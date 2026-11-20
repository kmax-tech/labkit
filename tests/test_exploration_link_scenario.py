"""A confirmation whose `[explored_in]` link names no one protocol is not
adopted: the whole adoption, through the commands a person runs.

The rule from data in memory: tests/test_rules_report_exploration.py; the
station of report-check's chain: tests/test_explored_in.py (`LaterUse`).
Here what the commands pass on, on two stamped count areas of one lab
(`test_end_to_end.stamp_count`): an exploratory protocol measured, audited,
adopted and committed; a confirmatory one that names it through
`protocol-fill --explored-in`, measured, finalized and audited. Then the
link is made unresolvable — the exploratory protocol gone from the working
tree, or a second file carrying its id — and `labkit-adopt` runs:

- it exits non-zero and prints the link's BLOCKER once, as "check not
  executable";
- nothing is written: the protocol's bytes, the area's files and
  `git status` are as before, and no copy of an unchecked proposal is left
  (`repo.pending_adoption`);
- `report-check AREA` names the same blocker, once;
- the link's blocker is printed first and is the step `labkit-next` owes;
  the analysis audit, which the broken link leaves uncovered, stays a
  blocker and offers no audit — one run now could not release;
- the way out the blocker prints, run, removes it, and the adoption then
  passes.

The twins: with the link resolvable, the same adoption succeeds; and an
analysis audit stale from a change of the area's code is told with the
audit as its next step.
"""

from __future__ import annotations

import contextlib
import re
import shlex
import shutil
from pathlib import Path

import pytest

import test_end_to_end as e2e
from command_fixture import run_main

from labkit.checks import protocol_report
from labkit.formats import protocol_block
from labkit.formats.repo import pending_adoption
from labkit.tools import (
    adopt,
    next_command,
    protocol_fill,
    report_command,
    scaffold,
)

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

NOT_EXECUTABLE = "BLOCKER (check not executable): exploration link: [explored_in]"
RESOLVE = "make the id name exactly one protocol of the repo: "
UNCOVERED = (
    "BLOCKER: analysis audit: no analysis audit covers the area as it is now, "
    "and none can until the exploration link resolves"
)
RESTAMP = "labkit-init exp <new-name> --kind …"


class _Confirmation(e2e.CountCommands):
    """The count area as an exploration with run A adopted and committed,
    and a second count area, confirmatory, that names it as explored in,
    with run B measured, finalized, audited without findings, its
    Conclusion written and all of it committed: the state one
    `labkit-adopt` away from a result. A base without tests of its own."""

    def setUp(self) -> None:
        super().setUp()
        self.run_a = self.adopted_a()
        self.exploration = self.protocol
        self.exploration_id = self.id_of(self.exploration)
        self.area, self.protocol = e2e.stamp_count(
            self.lab, protocol_type="confirmatory", area_name="confirm"
        )
        self.clean = e2e.clean_answer(self.lab, self.area)
        rc, out = self.command(
            protocol_fill.main,
            self.rel(self.protocol),
            "--explored-in",
            self.rel(self.exploration),
        )
        self.assertEqual(rc, 0, out)
        self.lab.commit("the confirmation names its exploration")
        self.run_b = self.measure()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.lab.conclude(self.protocol)
        self.lab.commit(f"run {self.run_b}, audited")

    def rel(self, path: Path) -> str:
        return path.relative_to(self.lab.root).as_posix()

    @staticmethod
    def id_of(protocol: Path) -> str:
        pid = protocol_block.head(protocol.read_text(encoding="utf-8")).id
        assert pid is not None
        return pid

    def command(self, main, *argv: str) -> tuple[int, str]:
        """A console command called from the repo root, as its printed
        lines name their paths."""
        with contextlib.chdir(self.lab.root):
            return run_main(main, list(argv))

    def labkit_adopt(self, *more: str) -> tuple[int, str]:
        """`labkit-adopt AREA RUN_B MORE`."""
        return self.command(adopt.main, self.rel(self.area), self.run_b, *more)

    def report_check(self, *more: str) -> tuple[int, str]:
        """`report-check AREA MORE`."""
        return self.command(report_command.main, self.rel(self.area), *more)

    def labkit_next(self) -> str:
        """`labkit-next AREA`: what it prints."""
        rc, out = self.command(next_command.main, self.rel(self.area))
        self.assertEqual(rc, 0, out)
        return out

    @staticmethod
    def blockers(out: str) -> list[str]:
        """The BLOCKER lines of OUT, in the order printed."""
        return [
            ln.strip() for ln in out.splitlines() if ln.strip().startswith("BLOCKER")
        ]

    def link_first_and_no_audit_offered(self, out: str) -> None:
        """In OUT, a gate's lines on the broken link: the link's blocker
        is the first one printed, and the analysis audit it leaves
        uncovered is told once, as a blocker whose way out is the link's —
        no audit command, which could not release."""
        told = self.blockers(out)
        self.assertTrue(told[0].startswith(NOT_EXECUTABLE), told[0])
        (audit,) = [ln for ln in told if ln.startswith("BLOCKER: analysis audit:")]
        self.assertTrue(audit.startswith(UNCOVERED), audit)
        self.assertIn(
            f"Next: resolve the exploration link first, as its blocker names; "
            f"then `report-check {self.rel(self.area)}` names the audit where "
            f"one is still owed",
            audit,
        )
        self.assertNotIn("labkit-audit", audit)

    def link_blockers(self, out: str) -> list[str]:
        """The BLOCKER lines of the link in OUT, as the gate prints its
        findings (the closing summary lists each again without the word)."""
        return [
            ln.strip()
            for ln in out.splitlines()
            if ln.strip().startswith("BLOCKER") and "exploration link:" in ln
        ]

    def state(self) -> tuple[bytes, list[str], str, bool]:
        """What an adoption may not change when it is refused: the
        protocol's bytes, the area's files, what git sees as changed, and
        whether a copy of an unchecked proposal stands."""
        files = sorted(
            self.rel(p)
            for p in self.area.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        )
        return (
            self.protocol.read_bytes(),
            files,
            self.lab.git("status", "--porcelain"),
            pending_adoption(self.protocol).exists(),
        )

    def refused_once(self, named: str) -> str:
        """`labkit-adopt` and `report-check` on the broken link: the
        adoption exits non-zero with the link's one blocker, NAMED in it,
        and writes nothing; report-check names the same blocker once. The
        blocker line."""
        before = self.state()
        self.assertFalse(before[3])
        rc, out = self.labkit_adopt()
        self.assertNotEqual(rc, 0, out)
        (line,) = self.link_blockers(out)
        self.assertTrue(
            line.startswith(
                f"{NOT_EXECUTABLE} protocol = {self.exploration_id} names {named}"
            ),
            line,
        )
        self.assertIn("the result is not released over it", line)
        self.assertEqual(out.count("- (check not executable) exploration link:"), 1)
        self.link_first_and_no_audit_offered(out)
        self.assertIn("protocol-fill: not adopted", out)
        self.assertNotIn("labkit-adopt: 2.", out)
        self.assertEqual(self.state(), before)
        self.assertIsNone(self.declared())
        rc, checked = self.report_check()
        self.assertNotEqual(rc, 0, checked)
        self.assertEqual(self.link_blockers(checked), [line])
        self.assertEqual(checked.count("- (check not executable) exploration link:"), 1)
        self.link_first_and_no_audit_offered(checked)
        # the step labkit-next owes is the link's way out, not the audit
        step = self.labkit_next()
        self.assertIn(
            f"  where: exploration link: [explored_in] protocol = "
            f"{self.exploration_id} names {named}",
            step,
        )
        self.assertIn(f"  next:  {RESOLVE}", step)
        self.assertNotIn("--mode analysis", step)
        self.assertEqual(self.state(), before)
        return line

    def released(self, line: str) -> None:
        """After the way out: the gate line the blocker LINE names as its
        last step, run as printed, tells no blocker of the link, and the
        adoption passes."""
        check = f"report-check {self.rel(self.area)}"
        self.assertIn(f"then `{check}`", line)
        _, checked = self.command(report_command.main, *shlex.split(check)[1:])
        self.assertEqual(self.link_blockers(checked), [], checked)
        self.assertNotIn("exploration link", checked)
        rc, out = self.labkit_adopt()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.declared(), self.run_b)
        self.assertFalse(pending_adoption(self.protocol).exists())
        rc, checked = self.report_check()
        self.assertEqual(rc, 0, checked)


class TheLinkResolves(_Confirmation):
    """The twin: the id names the one exploratory protocol."""

    def test_the_adoption_succeeds_and_no_link_blocker_is_told(self) -> None:
        _, checked = self.report_check()
        self.assertNotIn("exploration link", checked)
        rc, out = self.labkit_adopt()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("exploration link", out)
        self.assertIn("labkit-adopt: 3. check", out)
        self.assertEqual(self.declared(), self.run_b)
        self.assertFalse(pending_adoption(self.protocol).exists())
        rc, checked = self.report_check()
        self.assertEqual(rc, 0, checked)

    def test_an_audit_stale_from_the_area_s_own_change_is_told_with_the_audit(
        self,
    ) -> None:
        """A stale analysis audit with a cause of its own, the link
        resolving: the measuring script changed after the audit. The
        blocker names the audit as its next step, and no link finding
        stands beside it."""
        measure = self.area / "scripts" / "01_measure.py"
        measure.write_text(
            measure.read_text(encoding="utf-8") + "\n# a later change\n",
            encoding="utf-8",
        )
        rc, checked = self.report_check()
        self.assertEqual(rc, 1, checked)
        self.assertNotIn("exploration link", checked)
        (audit,) = [
            ln
            for ln in self.blockers(checked)
            if ln.startswith("BLOCKER: analysis audit:")
        ]
        self.assertIn("no analysis audit saw the area as it is now", audit)
        self.assertIn(
            f"Next: audit the answering run as it stands: `labkit-audit "
            f"{self.rel(self.area)} --mode analysis`, then decide its findings",
            audit,
        )


class TheLinkNamesNoProtocol(_Confirmation):
    """The exploratory protocol's file is gone — from the working tree
    only, or by a commit. The blocker prints the restore the history
    gives: the file and the last commit that held it, no slot left open."""

    def restore_as_printed(self, line: str, commit: str) -> None:
        """Run the way out's first command as the blocker LINE prints it:
        the checkout of the exploratory protocol's file from COMMIT."""
        restore = f"git checkout {commit} -- {shlex.quote(self.rel(self.exploration))}"
        self.assertIn(
            f"{RESOLVE}bring the exploratory protocol back from the last "
            f"commit that held it (`{restore}`), then ",
            line,
        )
        self.assertNotIn("<commit>", line)
        self.assertNotIn("<EXPLORATION_PROTOCOL>", line)
        self.lab.git(*shlex.split(restore)[1:])

    def test_the_adoption_is_refused_nothing_is_written_and_the_restore_releases_it(
        self,
    ) -> None:
        self.exploration.unlink()
        line = self.refused_once("no protocol of this repo")
        # the deletion is not committed: HEAD holds the file
        self.restore_as_printed(line, self.lab.git("rev-parse", "HEAD"))
        self.released(line)

    def test_a_committed_deletion_is_restored_from_the_commit_before_it(self) -> None:
        held = self.lab.git("rev-parse", "HEAD")
        self.lab.git("rm", "-q", self.rel(self.exploration))
        self.lab.commit("the exploratory protocol removed")
        line = self.refused_once("no protocol of this repo")
        self.restore_as_printed(line, held)
        self.released(line)


class TheLinkNamesTwoProtocols(_Confirmation):
    """A second file of the repo carries the exploratory protocol's id. No
    command gives it a fresh id: the blocker names the step by hand — the
    copy removed, or its text carried into a freshly stamped protocol —
    and how to tell the copy from the exploration (the area that holds
    the linked run)."""

    def copied(self) -> tuple[Path, str]:
        """The exploratory protocol copied into a third area: the copy and
        the blocker line the refused adoption prints, which names the step
        by hand."""
        copy = self.lab.root / "experiments" / "03-lines-copy" / self.exploration.name
        copy.parent.mkdir()
        shutil.copy(self.exploration, copy)
        line = self.refused_once("2 protocols (")
        self.assertIn(
            f"{RESOLVE}one of these files is the exploration the link means — "
            f"the one whose area holds its run, runs/{self.run_a}/ —; each other "
            f"file is a copy, and no command gives it a fresh id. Remove the "
            f"copy from the repo; or, to keep it as a protocol of its own, stamp "
            f"one (`{RESTAMP}` writes a fresh id), carry the copy's text into "
            f"the new PROTOCOL-*.md by hand — every line but the `id` in its "
            f"head —, and then remove the copy",
            line,
        )
        self.assertTrue((self.exploration.parent / "runs" / self.run_a).is_dir())
        self.assertFalse((copy.parent / "runs").exists())
        return copy, line

    def test_removing_the_copy_releases_it(self) -> None:
        copy, line = self.copied()
        copy.unlink()
        copy.parent.rmdir()
        self.released(line)

    def test_the_adoption_is_refused_nothing_is_written_and_the_restamp_releases_it(
        self,
    ) -> None:
        copy, line = self.copied()
        # the way out's first commands, run as printed: protocol-check on
        # each file that carries the id names the duplicate and the re-stamp
        checks = [
            c for c in re.findall(r"`([^`]+)`", line) if c.startswith("protocol-check ")
        ]
        named = {(self.lab.root / shlex.split(c)[1]).resolve() for c in checks}
        self.assertEqual(named, {copy.resolve(), self.exploration.resolve()})
        for check in checks:
            rc, told = self.command(protocol_report.main, *shlex.split(check)[1:])
            self.assertEqual(rc, 1, told)
            self.assertIn(f"DUPLICATE protocol id {self.exploration_id}", told)
        # the stamp, its placeholders filled; the copy's text moves into
        # the freshly stamped protocol by hand, under the fresh id
        restamp = RESTAMP.replace("<new-name>", "lines-again").replace("…", "compute")
        rc, told = self.command(scaffold.main, *shlex.split(restamp)[1:])
        self.assertEqual(rc, 0, told)
        (fresh,) = (self.lab.root / "experiments").glob("*-lines-again/PROTOCOL-*.md")
        fresh_id = self.id_of(fresh)
        self.assertNotEqual(fresh_id, self.exploration_id)
        fresh.write_text(
            copy.read_text(encoding="utf-8").replace(self.exploration_id, fresh_id),
            encoding="utf-8",
        )
        copy.unlink()
        copy.parent.rmdir()
        self.released(line)


class TheCopyLiesInTheConfirmationsOwnArea(_Confirmation):
    """The exploratory protocol copied into the confirmation's own area.
    Before the link is read, the area holds two protocols: labkit-adopt
    and report-check refuse with exit 2, name the two files and the way
    out (`--protocol`), and write nothing. Named with `--protocol`, the
    link's blocker follows, once — the refusal comes first and is not
    moved behind the link."""

    def test_two_protocols_are_refused_first_and_the_named_one_holds_the_link(
        self,
    ) -> None:
        copy = self.area / "PROTOCOL-copy.md"
        shutil.copy(self.exploration, copy)
        before = self.state()
        refusal = (
            f"2 protocols in {self.rel(self.area)} — name one with --protocol FILE:"
        )
        rc, out = self.labkit_adopt()
        self.assertEqual(rc, 2, out)
        self.assertIn(f"labkit-adopt: {refusal}", out)
        self.assertIn(f"  {self.rel(self.protocol)}\n", out)
        self.assertIn(f"  {self.rel(copy)}\n", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(self.link_blockers(out), [])
        self.assertEqual(self.state(), before)
        rc, checked = self.report_check()
        self.assertEqual(rc, 2, checked)
        self.assertIn("report-check: 2 protocols in ", checked)
        self.assertIn("name one with --protocol FILE:", checked)
        # the way out the refusal names, taken: the link's blocker, once
        named = ("--protocol", self.rel(self.protocol))
        rc, out = self.labkit_adopt(*named)
        self.assertEqual(rc, 1, out)
        (line,) = self.link_blockers(out)
        self.assertIn(
            f"{NOT_EXECUTABLE} protocol = {self.exploration_id} names 2 protocols (",
            line,
        )
        self.assertIn(str(copy), line)
        self.assertIn("protocol-fill: not adopted", out)
        self.assertEqual(self.state(), before)
        self.assertIsNone(self.declared())
        rc, checked = self.report_check(*named)
        self.assertEqual(rc, 1, checked)
        self.assertEqual(self.link_blockers(checked), [line])
