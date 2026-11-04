"""A comparison with the first measurement that cannot run blocks; it is
never read as "nothing changed".

finalize holds the protocol, as the answering run saw it and as it stands,
to what its first measurement registered, read back through git
(`protocol_history.as_measured`). When git could not read that text — a
commit's tree or a blob missing from the object store, a recorded patch
that does not apply — finalize passed over it and said "what the number is
about … are the ones the first measurement registered": a changed question
went through finalize, and labkit-next sent the agent to the audit before
adopting it (side finding 1 of
docs/notes/2026-11-03-finalize-hold-missing-once.md). Each failure here is
real: an object removed from the lab's repository, a patch that does not
apply. The twin: the same area readable is held for its changed question;
the recovery: the object restored, finalize holds as before."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import test_end_to_end as e2e

UNREAD = "cannot be compared with its first measurement"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


class UnreadFirstMeasurement(e2e.CorrectionCommands):
    """Run A measured (the fixture), then the question changed and
    committed: finalize owes the hold of the changed question."""

    def setUp(self) -> None:
        super().setUp()
        self.lab.fill(
            self.protocol,
            "--force",
            f"Question / hypothesis={e2e.CorrectedDescription.MEDIAN}",
        )
        self.lab.commit("the question changed after run A")
        self.kept = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.kept)

    def commit_of_a(self) -> str:
        cfg = json.loads(
            (self.area / "runs" / self.run_a / "config.json").read_text(
                encoding="utf-8"
            )
        )
        return cfg["git_full"]

    def remove_object(self, sha: str) -> Path:
        """Move the loose object SHA out of the store; where it was."""
        obj = self.lab.root / ".git" / "objects" / sha[:2] / sha[2:]
        self.assertTrue(obj.is_file(), obj)
        shutil.move(str(obj), str(self.kept / sha))
        return obj

    def finalized(self) -> str:
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        return out

    def assert_unread_blocks(self, out: str, why: str) -> None:
        """The hold names the source (the run), the reason and the way back."""
        (line,) = [ln for ln in out.splitlines() if UNREAD in ln and "BLOCKER" in ln]
        self.assertIn(self.run_a, line)
        self.assertIn(why, line)
        self.assertIn("git fetch", line)
        self.assertIn("register anew", line)
        self.assertNotIn("are the ones the first measurement registered", out)

    def test_the_twin_a_readable_first_measurement_holds_the_changed_question(self):
        out = self.finalized()
        self.assertIn(self.HELD, out)
        self.assertNotIn(UNREAD, out)

    def test_a_missing_tree_blocks_and_restored_holds_again(self):
        tree = git(self.lab.root, "rev-parse", f"{self.commit_of_a()}^{{tree}}")
        where = self.remove_object(tree)
        self.assert_unread_blocks(self.finalized(), "read-tree")
        shutil.move(str(self.kept / tree), str(where))
        out = self.finalized()
        self.assertIn(self.HELD, out)
        self.assertNotIn(UNREAD, out)

    def test_a_missing_blob_blocks_instead_of_raising(self):
        rel = self.protocol.relative_to(self.lab.root).as_posix()
        blob = git(self.lab.root, "rev-parse", f"{self.commit_of_a()}:{rel}")
        self.remove_object(blob)
        self.assert_unread_blocks(self.finalized(), "cat-file")

    def test_a_recorded_patch_that_does_not_apply_blocks(self):
        rel = self.protocol.relative_to(self.lab.root).as_posix()
        (self.area / "runs" / self.run_a / "uncommitted.patch").write_text(
            f"diff --git a/{rel} b/{rel}\n--- a/{rel}\n+++ b/{rel}\n"
            "@@ -1,1 +1,1 @@\n-a line that is not there\n+x\n",
            encoding="utf-8",
        )
        self.lab.commit("the patch run A recorded, as an older labkit wrote it")
        self.assert_unread_blocks(self.finalized(), "apply")
