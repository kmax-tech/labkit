"""An attempt journal git cannot read at HEAD or in the index is named as
such; it is never read as "no journal there".

The journal is appended to, never cut (`attempts.area_gaps`): its text at
HEAD and in the index is read through `repo.text_at`, whose None is both
"not there" and "git failed". With the journal's blob missing from the
object store and its copy in the git directory gone (a fresh clone), a
journal cut in the tree or in the commit is a blocker naming the unreadable
journal, and `expected_evidence` reports it as an error — the protection
never passes in silence. Each failure here is real: the blob removed. The
twin: the readable journal cut is held as cut; the recovery: the blob
restored, the cut is held again."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import test_end_to_end as e2e
from labkit.formats import attempts

UNREAD = "git cannot read the journal"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


class JournalAtHead(e2e.CountCommands):
    """One analysis attempt journaled and committed; the journal's copy in
    the git directory removed, as in a fresh clone; then its last line cut."""

    def setUp(self) -> None:
        super().setUp()
        self.measure()
        rc, out, _ = self.analysis(self.clean)
        self.assertEqual(rc, 0, out)
        self.lab.commit("the audit, journaled")
        shutil.rmtree(self.lab.root / ".git" / "labkit-attempts")
        self.journal = attempts.journal_path(self.area)
        self.whole = self.journal.read_text(encoding="utf-8")
        cut = "".join(self.whole.splitlines(keepends=True)[:-1])
        self.journal.write_text(cut, encoding="utf-8")
        self.kept = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.kept)

    def remove_blob(self, rev: str) -> tuple[Path, Path]:
        rel = self.journal.relative_to(self.lab.root).as_posix()
        blob = git(self.lab.root, "rev-parse", f"{rev}:{rel}")
        obj = self.lab.root / ".git" / "objects" / blob[:2] / blob[2:]
        kept = self.kept / blob
        shutil.move(str(obj), str(kept))
        return obj, kept

    def test_the_twin_a_readable_journal_cut_is_held(self):
        for staged in (False, True):
            with self.subTest(staged=staged):
                if staged:
                    self.lab.git("add", str(self.journal))
                (gap,) = attempts.evidence_gaps(self.area, staged=staged)
                self.assertIn("no longer starts with the lines HEAD holds", gap)

    def test_an_unreadable_head_journal_holds_and_restored_holds_the_cut(self):
        self.lab.git("add", str(self.journal))
        obj, kept = self.remove_blob("HEAD")
        for staged in (False, True):
            with self.subTest(staged=staged):
                (gap,) = attempts.evidence_gaps(self.area, staged=staged)
                self.assertIn(UNREAD, gap)
                self.assertIn("HEAD", gap)
                self.assertIn("git fsck", gap)
        shutil.move(str(kept), str(obj))
        (gap,) = attempts.evidence_gaps(self.area, staged=True)
        self.assertIn("no longer starts with the lines HEAD holds", gap)

    def test_expected_evidence_reports_the_unreadable_journal(self):
        self.remove_blob("HEAD")
        _, errors = attempts.expected_evidence(self.area)
        self.assertTrue(any(UNREAD in e for e in errors), errors)
