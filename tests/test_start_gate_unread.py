"""The run's start check reads the protocol as HEAD holds it; a HEAD git
cannot read is named as such, never as "not committed" nor as "registers
no report".

`repo.text_at` says None both for a file HEAD lacks and for git failing.
The start check (`start_check._committed_registration`) read that None as
"is not committed — commit the protocol" at low repeat cost, and as "HEAD
registers no report" for the report binding, on both lanes. Each case is
real: the blob of the protocol at HEAD removed from the lab's object store.
The twin: the protocol truly uncommitted keeps its sentence; the recovery:
the object restored, the run's start check passes."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import test_end_to_end as e2e
from labkit.run import start_check


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


class UnreadHeadAtTheStart(e2e.CountCommands):
    """The count, registered and committed at low repeat cost, no run yet."""

    def findings(self) -> list[str]:
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        return start_check._freeze_findings(self.area, bound)

    def remove_head_blob(self) -> tuple[Path, Path]:
        rel = self.protocol.relative_to(self.lab.root).as_posix()
        blob = git(self.lab.root, "rev-parse", f"HEAD:{rel}")
        obj = self.lab.root / ".git" / "objects" / blob[:2] / blob[2:]
        kept = Path(tempfile.mkdtemp()) / blob
        self.addCleanup(shutil.rmtree, kept.parent)
        shutil.move(str(obj), str(kept))
        return obj, kept

    def test_the_twin_a_readable_head_lets_the_run_start(self):
        self.assertEqual(self.findings(), [])

    def test_an_unreadable_head_is_named_and_restored_starts(self):
        obj, kept = self.remove_head_blob()
        (line,) = self.findings()
        self.assertIn("cannot be read at HEAD", line)
        self.assertNotIn("is not committed", line)
        self.assertIn("git fsck", line)
        shutil.move(str(kept), str(obj))
        self.assertEqual(self.findings(), [])

    def test_the_twin_an_uncommitted_protocol_keeps_its_sentence(self):
        rel = self.protocol.relative_to(self.lab.root).as_posix()
        self.lab.git("rm", "-q", "--cached", rel)
        self.lab.git("commit", "-qm", "the protocol out of the index")
        (line,) = self.findings()
        self.assertIn("is not committed", line)


class UnreadHeadForTheReportBinding(e2e.CountCommands):
    """At high repeat cost only the report binding reads HEAD here: an
    unreadable HEAD read as "registers no report" let a protocol that
    registers none pass, though what HEAD registers could not be told."""

    def test_an_unreadable_head_holds_the_binding_too(self):
        area, protocol = self.lab.exp("hi", repeat_cost="high", kind="compute")
        self.lab.commit("a high-cost protocol, registered")
        bound = start_check.protocol_binding(area, protocol.name)
        self.assertEqual(start_check._committed_registration(area, bound), [])
        rel = protocol.relative_to(self.lab.root).as_posix()
        blob = git(self.lab.root, "rev-parse", f"HEAD:{rel}")
        (self.lab.root / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
        (line,) = start_check._committed_registration(area, bound)
        self.assertIn("cannot be read at HEAD", line)


class NoCommitYet(e2e.CountCommands):
    def test_a_branch_without_a_commit_is_not_committed_not_unreadable(self):
        """HEAD that does not resolve holds nothing: the protocol is not
        committed, which `text_at`'s None and the start check say."""
        from labkit.formats import repo

        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty)
        subprocess.run(["git", "init", "-q", str(empty)], check=True)
        (empty / "PROTOCOL-x.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(repo.unreadable_at(empty, empty / "PROTOCOL-x.md", "HEAD"), "")
