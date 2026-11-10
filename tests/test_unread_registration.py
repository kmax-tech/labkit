"""A comparison with the first measurement that cannot run blocks; it is
never read as "nothing changed".

finalize holds the protocol, as the answering run saw it and as it stands,
to what its first measurement registered, read back through git
(`protocol_history.as_measured`). When git cannot read that text — a
commit's tree or a blob missing from the object store, a recorded patch
that does not apply — finalize does not pass over it as if the first
measurement's registration stood, which would let a changed question
through. Each failure here is real: an object removed from the lab's repository, a patch that does not
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


class ChangedQuestion(e2e.CorrectionCommands):
    """Run A measured (the fixture), then the question changed and
    committed: finalize owes the hold of the changed question. A base
    without tests of its own."""

    def setUp(self) -> None:
        super().setUp()
        self.lab.fill(
            self.protocol,
            "--force",
            "Question / hypothesis=What is the median number of lines of a "
            "document of data/raw/docs?",
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


class UnreadFirstMeasurement(ChangedQuestion):
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


class UnreadCommitAtTheRegistrationStation(ChangedQuestion):
    """report-check's registration station reads the protocol as the first
    measurement's commit holds it (`protocol_history.committed_at`). A
    commit git cannot read is not told "was not committed", a cause that
    does not hold with a way out that does not apply: it names git's
    failure and the way back; the twin, a protocol the commit truly lacks,
    keeps its sentence."""

    def station(self) -> list[str]:
        from labkit.gates import report_check, report_context

        ctx = report_context.checked(self.area, self.protocol)
        return [f.line for f in report_check.registration_gaps(ctx)]

    def test_an_unreadable_commit_is_named_as_unreadable(self):
        tree = git(self.lab.root, "rev-parse", f"{self.commit_of_a()}^{{tree}}")
        where = self.remove_object(tree)
        (line,) = self.station()
        self.assertIn("cannot be read", line)
        self.assertIn(self.run_a, line)
        self.assertNotIn("was not committed", line)
        self.assertIn("git fsck", line)
        shutil.move(str(self.kept / tree), str(where))
        self.assertEqual(self.station(), [])


class ReleaseThatCannotBeChecked(e2e.CorrectionCommands):
    """A correction in place released for run A by its follow-up; then a
    file the run registered is gone, so the state A was audited in cannot
    be computed (`audit_binding.covering_analysis` raises AuditError).
    `resolved_corrections` does not read that as "no release", whose hold
    would tell to restore Data / scope as A registered it — the known-false
    value. Held as a release that cannot be checked, naming the file; the
    twin: the file there, finalize passes; the recovery: put back, passes."""

    def setUp(self) -> None:
        super().setUp()
        blocking = self.audited("BLOCKER", "Data / scope")
        self.describe(self.RIGHT)
        self.decide(blocking, 1, "fixed", "Data / scope now says 3 documents")
        rc, out, _ = self.follow_up(blocking, "resolved", "3 documents, as A read")
        self.assertEqual(rc, 0, out)
        rows = json.loads(
            (self.area / "runs" / self.run_a / "outputs.json").read_text(
                encoding="utf-8"
            )
        )
        (recorded,) = [Path(r["path"]) for r in rows]
        self.output = recorded if recorded.is_absolute() else self.lab.root / recorded
        self.kept = Path(tempfile.mkdtemp()) / self.output.name
        self.addCleanup(shutil.rmtree, self.kept.parent)

    def test_the_twin_the_release_checked_passes(self):
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn("corrected in place after the first measurement", out)

    def test_a_release_that_cannot_be_checked_holds_as_such_and_restored_passes(
        self,
    ):
        shutil.move(str(self.output), str(self.kept))
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        (line,) = [
            ln
            for ln in out.splitlines()
            if "cannot be checked" in ln and "BLOCKER" in ln
        ]
        self.assertIn(self.output.name, line)
        self.assertNotIn(self.HELD, out)  # no unreleased change is claimed
        self.assertNotIn("restore Data / scope", out)
        shutil.move(str(self.kept), str(self.output))
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
