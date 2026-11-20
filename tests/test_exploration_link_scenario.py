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
- the way out the blocker prints, run, removes it, and the adoption then
  passes.

The twin: with the link resolvable, the same adoption succeeds.
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
from labkit.tools import adopt, protocol_fill, report_command, scaffold

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

NOT_EXECUTABLE = "BLOCKER (check not executable): exploration link: [explored_in]"
RESTORE = "git checkout <commit> -- <EXPLORATION_PROTOCOL>"
RESTAMP = "labkit-init exp <name> --kind …"


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

    def labkit_adopt(self) -> tuple[int, str]:
        """`labkit-adopt AREA RUN_B`."""
        return self.command(adopt.main, self.rel(self.area), self.run_b)

    def report_check(self) -> tuple[int, str]:
        """`report-check AREA`."""
        return self.command(report_command.main, self.rel(self.area))

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
        self.assertIn("protocol-fill: not adopted", out)
        self.assertNotIn("labkit-adopt: 2.", out)
        self.assertEqual(self.state(), before)
        self.assertIsNone(self.declared())
        rc, checked = self.report_check()
        self.assertNotEqual(rc, 0, checked)
        self.assertEqual(self.link_blockers(checked), [line])
        self.assertEqual(checked.count("- (check not executable) exploration link:"), 1)
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


class TheLinkNamesNoProtocol(_Confirmation):
    """The exploratory protocol's file is gone from the working tree."""

    def test_the_adoption_is_refused_nothing_is_written_and_the_restore_releases_it(
        self,
    ) -> None:
        self.exploration.unlink()
        line = self.refused_once("no protocol of this repo")
        # the way out's first command, its two placeholders filled: the
        # commit that holds the file and the file
        self.assertIn(f"(`{RESTORE}`)", line)
        restore = RESTORE.replace("<commit>", "HEAD").replace(
            "<EXPLORATION_PROTOCOL>", shlex.quote(self.rel(self.exploration))
        )
        self.lab.git(*shlex.split(restore)[1:])
        self.released(line)


class TheLinkNamesTwoProtocols(_Confirmation):
    """A second file of the repo carries the exploratory protocol's id."""

    def test_the_adoption_is_refused_nothing_is_written_and_the_restamp_releases_it(
        self,
    ) -> None:
        copy = self.lab.root / "experiments" / "03-lines-copy" / self.exploration.name
        copy.parent.mkdir()
        shutil.copy(self.exploration, copy)
        line = self.refused_once("2 protocols (")
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
            self.assertIn(f"re-stamp the copy: `{RESTAMP}`", told)
        # the re-stamp, its placeholders filled; the copy's text moves into
        # the freshly stamped protocol by hand, under the fresh id
        restamp = RESTAMP.replace("<name>", "lines-again").replace("…", "compute")
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
