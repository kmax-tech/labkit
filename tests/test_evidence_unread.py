"""A change of committed evidence that git cannot compare is held with its
source, reason and way back; it is never a traceback.

`evidence.change_findings` (the tree or the index against HEAD) and
`commit_changes` (each commit against its parent) compare through git.
When git could not read an object they need, GitError went up through
report-check and labkit-next as a traceback: nothing passed, but no way
out was named. Each failure here is real: an object removed from the
lab's object store. The twin: readable, the changed run file is held as
changed; the recovery: the object restored, the same hold again."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import test_end_to_end as e2e
from labkit.formats import evidence
from labkit.gates import report_check
from labkit.gates import next_step

UNREAD = "cannot be compared with"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


class ChangedRunUnreadable(e2e.CountCommands):
    """A closed run committed; its metrics.json changed in the tree."""

    def setUp(self) -> None:
        super().setUp()
        self.run_id = self.measure()
        self.lab.commit("run measured")
        metrics = self.area / "runs" / self.run_id / "metrics.json"
        metrics.write_text(
            metrics.read_text(encoding="utf-8").replace("}", ', "x": 1}'),
            encoding="utf-8",
        )
        self.rel = metrics.relative_to(self.lab.root).as_posix()
        self.kept = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.kept)

    def remove(self, spec: str) -> tuple[Path, Path]:
        sha = git(self.lab.root, "rev-parse", spec)
        obj = self.lab.root / ".git" / "objects" / sha[:2] / sha[2:]
        kept = self.kept / sha
        shutil.move(str(obj), str(kept))
        return obj, kept

    def test_the_twin_a_readable_change_is_held_as_changed(self):
        ((why, _),) = evidence.change_findings(self.area)
        self.assertIn("metrics.json (changed)", why)

    def test_an_unreadable_object_is_held_and_restored_held_as_changed(self):
        obj, kept = self.remove(f"HEAD:{self.rel}")
        ((why, fix),) = evidence.change_findings(self.area)
        self.assertIn(UNREAD, why)
        self.assertIn("unable to read", why)
        self.assertIn("git fsck", fix)
        shutil.move(str(kept), str(obj))
        ((why, _),) = evidence.change_findings(self.area)
        self.assertIn("metrics.json (changed)", why)

    def test_report_check_and_labkit_next_hold_it_without_a_traceback(self):
        self.remove(f"HEAD:{self.rel}")
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = report_check.main([str(self.area)])
            step = next_step.next_step(self.area, self.protocol)
        finally:
            os.chdir(old)
        self.assertEqual(rc, 1, out.getvalue())
        self.assertIn(UNREAD, out.getvalue())
        self.assertIn(UNREAD, step.where)


class CommittedChangeUnreadable(e2e.CountCommands):
    """A commit past the pre-commit rewrote a closed run's file; git cannot
    read the parent's tree of that run."""

    def test_commit_changes_holds_an_unreadable_parent(self):
        run_id = self.measure()
        self.lab.commit("run measured")
        since = git(self.lab.root, "rev-parse", "HEAD")
        metrics = self.area / "runs" / run_id / "metrics.json"
        metrics.write_text("{}", encoding="utf-8")
        self.lab.commit("the run's metrics rewritten past the pre-commit")
        self.assertEqual(len(evidence.commit_changes(self.area, since + "~1")), 1)
        rel = (self.area / "runs" / run_id).relative_to(self.lab.root).as_posix()
        tree = git(self.lab.root, "rev-parse", f"{since}:{rel}")
        (self.lab.root / ".git" / "objects" / tree[:2] / tree[2:]).unlink()
        # both commits read that tree: each is held, none passes
        lines = evidence.commit_changes(self.area, since + "~1")
        self.assertEqual(len(lines), 2, lines)
        for line in lines:
            self.assertIn(UNREAD, line)
            self.assertIn("git fsck", line)
