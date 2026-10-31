"""attempts — the journal of an area's audit attempts: a record that went
missing is noticed, a running attempt is told by the lock it holds, a start
is checked and written under one lock.

Why (sixth haiku round, t3; eighth, t18): agents ran `rm audits/*.toml`
before a new attempt, and nothing noticed that a record was gone.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import attempts  # noqa: E402
from labkit.formats import failed_attempts
from labkit.formats.attempts import Attempt  # noqa: E402

A = Attempt("a1", "analysis", "opus", "s", "2026-10-26T09:16:02", "here")
START = json.dumps(
    {"event": "started", "id": "a1", "mode": "analysis", "model": "opus",
     "scope_sha": "s", "started": "t", "host": "h"}
)  # fmt: skip
START2 = START.replace('"a1"', '"a2"')
END_R = json.dumps(
    {"event": "ended", "id": "a1", "outcome": "record", "file": "r.toml"}
)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def area_in_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    area = root / "experiments" / "01-x"
    (area / "audits").mkdir(parents=True)
    (area / "PROTOCOL-x.md").write_text("# P\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "area")
    return area


class Journal(unittest.TestCase):
    def test_parse_follows_each_attempt_through_its_events(self):
        lines = [
            {"event": "started", "id": "a1", "mode": "analysis", "model": "opus",
             "scope_sha": "s", "started": "t", "host": "h"},
            {"event": "started", "id": "a2", "mode": "analysis", "model": "opus",
             "scope_sha": "s", "started": "t", "host": "h"},
            {"event": "ended", "id": "a1", "outcome": "failed", "file": "x-failed.toml"},
            {"event": "interrupted", "id": "a2", "found_by": "a3"},
        ]  # fmt: skip
        text = "\n".join(json.dumps(r) for r in lines) + "\n"
        a1, a2 = attempts.parse_journal(text, "j")
        self.assertEqual((a1.outcome, a1.file), ("failed", "x-failed.toml"))
        self.assertTrue(a2.interrupted)
        self.assertEqual(a2.outcome, "")

    def test_a_line_that_does_not_read_is_named(self):
        start = json.dumps(
            {"event": "started", "id": "a1", "mode": "m", "model": "o",
             "scope_sha": "s", "started": "t", "host": "h"}
        )  # fmt: skip
        for text, said in (
            ("{nope\n", "j:1: not JSON"),
            ('{"event": "begun", "id": "a1"}\n', "j:1: an event is one of"),
            ('{"event": "ended", "id": "a9", "outcome": "none"}\n', "never started"),
            (f"{start}\n{start}\n", "j:2: attempt a1 started twice"),
            (
                f'{start}\n{{"event": "ended", "id": "a1", "outcome": "record"}}\n',
                "outcome record names its file",
            ),
            ('{"event": "started", "id": "a1"}\n', "a start holds mode"),
        ):
            with self.assertRaisesRegex(attempts.AttemptError, said):
                attempts.parse_journal(text, "j")


class Gaps(unittest.TestCase):
    """`gaps` is pure: journal, files and HEAD in, sentences out."""

    def _gaps(self, attempts_, present=(), at_head=(), now="", head=None, alive=None):
        return attempts.gaps(
            list(attempts_), set(present), set(at_head), now, head, alive or {}
        )

    def test_the_twin_a_journal_and_its_files_agree(self):
        ended = Attempt(**{**A.__dict__, "outcome": "record", "file": "r.toml"})
        head = START + "\n" + END_R + "\n"
        found = self._gaps([ended], present={"r.toml", "attempts.jsonl"},
                           at_head={"r.toml"}, now=head + START2 + "\n",
                           head=head)  # fmt: skip
        self.assertEqual((found.blockers, found.notes), ([], []))

    def test_a_record_heads_journal_names_and_head_lacks_blocks(self):
        """`git rm --cached` and a commit: the file stays on disk, the
        delivered state lost it while its journal still names it."""
        head = START + "\n" + END_R + "\n"
        (gap,) = self._gaps([], present={"r.toml"}, now=head, head=head).blockers
        self.assertIn("HEAD's journal names it while HEAD lacks the file", gap)

    def test_heads_lost_file_names_the_restore_that_works_there(self):
        """It said "restore and commit it" whether or not anything could
        (pilot of labkit-paper area 15, t60): on disk it is staged, else
        it is lost — never a restore that cannot work."""
        head = START + "\n" + END_R + "\n"
        (gap,) = self._gaps([], present={"r.toml"}, now=head, head=head).blockers
        self.assertIn(
            "bring it back and commit it — stage it (`git add audits/r.toml`)", gap
        )
        copy = Path("/copy/r.toml")
        (gap,) = attempts.gaps(
            [], set(), set(), head, head, {}, kept={"r.toml": copy}
        ).blockers
        self.assertIn(
            "bring it back and commit it — restore it as the audit wrote", gap
        )
        self.assertIn(f"cp {copy} audits/r.toml", gap)
        (gap,) = self._gaps([], now=head, head=head).blockers
        self.assertIn(attempts.LOST_WAY, gap)
        self.assertNotIn("git add", gap)
        self.assertNotIn("commit it", gap)

    def test_a_file_an_ended_attempt_names_that_is_gone_blocks(self):
        ended = Attempt(**{**A.__dict__, "outcome": "failed", "file": "f-failed.toml"})
        (gap,) = self._gaps([ended]).blockers
        self.assertIn("attempt a1 (analysis, opus) ended as failed in", gap)
        self.assertIn("audits/f-failed.toml, and the file is gone", gap)

    def test_a_committed_record_gone_from_the_tree_blocks(self):
        (gap,) = self._gaps([], at_head={"old.toml", "attempts.jsonl"}).blockers
        self.assertIn("audits/old.toml is committed and gone from the tree", gap)

    def test_a_journal_cut_against_head_blocks(self):
        (gap,) = self._gaps([], now=START2 + "\n", head=START + "\n").blockers
        self.assertIn("no longer starts with the lines HEAD holds", gap)

    def test_running_interrupted_and_undecidable_are_named_not_held(self):
        b = Attempt(**{**A.__dict__, "id": "a2"})
        c = Attempt(**{**A.__dict__, "id": "a3", "host": "elsewhere"})
        found = self._gaps([A, b, c], alive={"a1": True, "a2": False, "a3": None})
        self.assertEqual(found.blockers, [])
        self.assertEqual(len(found.notes), 3)
        self.assertIn("attempt a1 (analysis) is running", found.notes[0])
        self.assertIn("ended without a record — interrupted", found.notes[1])
        self.assertIn("started on elsewhere and has no end", found.notes[2])


class Begin(unittest.TestCase):
    def test_begin_end_and_the_area_as_it_is_now(self):
        area = area_in_repo()
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        (path := area / "audits" / "r.toml").write_text("x", encoding="utf-8")
        running.end("record", file=path.name)
        (a,) = attempts.read_journal(area)
        self.assertEqual((a.outcome, a.file), ("record", "r.toml"))
        self.assertEqual(attempts.area_gaps(area).blockers, [])
        path.unlink()
        (gap,) = attempts.area_gaps(area).blockers
        self.assertIn("ended as record in audits/r.toml, and the file is gone", gap)
        with self.assertRaisesRegex(attempts.AttemptError, "the file is gone"):
            attempts.begin(
                area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
            )

    def test_a_running_attempt_refuses_a_second_and_an_ended_one_does_not(self):
        area = area_in_repo()
        first = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        with self.assertRaisesRegex(
            attempts.AttemptError,
            "is running. Next: wait for it to end, then run this",
        ):
            attempts.begin(
                area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
            )
        first.end("none", error="no answer")
        attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        ).end("none", error="again")

    def test_a_committed_record_removed_refuses_the_next_attempt(self):
        area = area_in_repo()
        failed_attempts.write_failed(area, "analysis", "opus", "s", "b", 60, "e", "c",
                              cause="unavailable")  # fmt: skip
        git(area.parent.parent, "add", "-A")
        git(area.parent.parent, "commit", "-qm", "failed attempt")
        for f in (area / "audits").glob("*.toml"):
            f.unlink()  # `rm audits/*.toml`, as t18 ran it
        with self.assertRaisesRegex(attempts.AttemptError, "committed and gone"):
            attempts.begin(
                area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
            )

    def test_a_killed_attempt_is_marked_interrupted_by_the_next(self):
        """A real process holds the attempt's lock; while it lives a second
        attempt is refused, after `kill -9` the next one marks it
        interrupted and names it."""
        area = area_in_repo()
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys, time; from pathlib import Path;"
                "from labkit.formats import attempts;"
                "r = attempts.begin(Path(sys.argv[1]), 'analysis', 'opus', 's', block_sha='b', protocol='PROTOCOL-x.md');"
                "print('begun', flush=True); time.sleep(60)",
                str(area),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout is not None
            self.assertEqual(child.stdout.readline().strip(), "begun")
            with self.assertRaisesRegex(attempts.AttemptError, "is running"):
                attempts.begin(
                    area,
                    "analysis",
                    "opus",
                    "s",
                    block_sha="b",
                    protocol="PROTOCOL-x.md",
                )
        finally:
            os.kill(child.pid, signal.SIGKILL)
            child.wait()
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        self.assertEqual(len(running.notes), 1)
        self.assertIn("ended without a record — interrupted", running.notes[0])
        running.end("none", error="test")
        first, _ = attempts.read_journal(area)
        self.assertTrue(first.interrupted)

    def test_two_starts_at_once_begin_one(self):
        """The check and the start under one lock: of two processes started
        together, one begins and one is refused."""
        area = area_in_repo()
        code = (
            "import sys, time; from pathlib import Path;"
            "from labkit.formats import attempts;"
            "\ntry:\n r = attempts.begin(Path(sys.argv[1]), 'analysis', 'opus', 's', block_sha='b', protocol='PROTOCOL-x.md')"
            "\n print('begun', flush=True); time.sleep(5)"
            "\nexcept attempts.AttemptError:\n print('refused', flush=True)"
        )
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", code, str(area)],
                stdout=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        said = sorted(p.stdout.readline().strip() for p in procs if p.stdout)
        for p in procs:
            p.kill()
            p.wait()
        self.assertEqual(said, ["begun", "refused"])

    def test_another_hosts_attempt_is_named_and_does_not_block(self):
        area = area_in_repo()
        with mock.patch.object(attempts.socket, "gethostname", lambda: "elsewhere"):
            attempts.begin(
                area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
            )  # never ended
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        self.assertIn("started on elsewhere and has no end", running.notes[0])
        running.end("none", error="test")


class JournalCopy(unittest.TestCase):
    """The journal's copy in the git directory, one per branch: a journal
    deleted in the tree before any commit is noticed, and a branch switch,
    a merge or an older journal is no false block (2026-10-28; first
    SAB-like draw and ninth haiku round t5 deleted `audits/` whole)."""

    def attempt(self, area: Path, record: str = "r.toml") -> str:
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        (area / "audits" / record).write_text("x", encoding="utf-8")
        running.end("record", file=record)
        return running.id

    def test_audits_deleted_whole_before_a_commit_is_named(self):
        area = area_in_repo()
        aid = self.attempt(area)
        self.assertEqual(attempts.area_gaps(area).blockers, [])
        shutil.rmtree(area / "audits")  # rm -rf audits/, as the draws did
        lost = "\n".join(attempts.area_gaps(area).blockers)
        self.assertIn(f"lost 2 line(s) of attempt(s) {aid}", lost)
        self.assertIn("ended naming audits/r.toml, and the file is gone", lost)
        # the restore the message gives brings the lines back
        subprocess.run(
            lost.split("`")[1], shell=True, cwd=area, check=True, capture_output=True
        )
        self.assertNotIn("lost 2 line(s)", "\n".join(attempts.area_gaps(area).blockers))

    def test_a_branch_with_a_shorter_journal_meets_its_own_copy(self):
        area = area_in_repo()
        root = area.parent.parent
        git(root, "checkout", "-q", "-b", "feature")
        self.attempt(area)
        git(root, "add", "-A")
        git(root, "commit", "-qm", "an attempt on feature")
        git(root, "checkout", "-q", "-")  # back: no journal on this branch
        self.assertEqual(attempts.area_gaps(area).blockers, [])

    def test_lines_older_than_the_copy_and_a_merge_order_pass(self):
        area = area_in_repo()
        journal = attempts.journal_path(area)
        journal.write_text(START + "\n" + END_R + "\n", encoding="utf-8")
        (area / "audits" / "r.toml").write_text("x", encoding="utf-8")
        self.attempt(area, "r2.toml")  # the copy holds only this attempt
        lines = journal.read_text(encoding="utf-8").splitlines()
        journal.write_text("\n".join([*lines[2:], *lines[:2]]) + "\n", encoding="utf-8")
        self.assertEqual(attempts.area_gaps(area).blockers, [])

    def test_a_broken_copy_line_is_a_problem_not_a_traceback(self):
        # copy_gaps raised a bare ValueError the stop did not catch (audit
        # 2026-10-28, B1)
        area = area_in_repo()
        self.attempt(area)
        copy = attempts.journal_copy(area)
        assert copy is not None
        copy.write_text(
            copy.read_text(encoding="utf-8") + "not json\n", encoding="utf-8"
        )
        attempts.journal_path(area).unlink()
        (problem,) = [
            p for p in attempts.area_integrity(area).problems if str(copy) in p
        ]
        self.assertIn(f"{copy}:3: not JSON", problem)  # the copy's own line

    def test_a_detached_head_keeps_no_copy(self):
        area = area_in_repo()
        git(area.parent.parent, "checkout", "-q", "--detach")
        self.assertIsNone(attempts.journal_copy(area))
        self.attempt(area)
        self.assertEqual(attempts.area_gaps(area).blockers, [])


class EvidenceCopy(unittest.TestCase):
    """The files an attempt ends with are copied as written beside the
    journal's copy: in the fourth SAB-like draw an agent deleted a record
    it had never staged, the commit passed, and the restores offered
    (`git checkout`, `git add`) could not bring it back."""

    def attempt(self, area: Path) -> tuple[str, Path]:
        """An attempt that kept its answer and ended with a record written as
        labkit-audit writes one; (its id, the record)."""
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        running.keep_answer("the answer as the model gave it")
        record = failed_attempts.write_failed(area, "analysis", "opus", "s", "b", 60, "e",
                                       "c", cause="unavailable")  # fmt: skip
        running.end("failed", file=record.name)
        return running.id, record

    @staticmethod
    def restore(line: str) -> str:
        """The command the restore names, run where it says: in the area."""
        return line.split("restore it as the audit wrote it (`")[1].split("`")[0]

    def test_the_end_keeps_the_record_and_the_answer(self):
        area = area_in_repo()
        aid, record = self.attempt(area)
        kept = attempts.kept_files(area)
        self.assertEqual(sorted(kept), sorted([f"answers/{aid}.txt", record.name]))
        self.assertEqual(kept[record.name].read_bytes(), record.read_bytes())

    def test_a_record_deleted_before_it_was_staged_holds_the_commit(self):
        from labkit.gates import agent_hooks

        area = area_in_repo()
        root = area.parent.parent
        _, record = self.attempt(area)
        written = record.read_bytes()
        record.unlink()  # the journal was never staged
        notes = area / "notes.md"
        notes.write_text("a later change\n", encoding="utf-8")
        git(root, "add", str(notes.relative_to(root)))
        line = "\n".join(agent_hooks.undecided_blockers(root, [notes], staged=True))
        self.assertIn(
            f"audits/{record.name}, and the file is in neither the tree nor the index",
            line,
        )
        subprocess.run(self.restore(line), shell=True, cwd=area, check=True)
        self.assertEqual(record.read_bytes(), written)
        # the twin: the evidence staged with the change, the commit passes
        git(root, "add", str((area / "audits").relative_to(root)))
        self.assertEqual(agent_hooks.undecided_blockers(root, [notes], staged=True), [])

    def test_an_area_deleted_whole_holds_the_commit_and_the_stop(self):
        """`rm -rf <area>` took the protocol with the records, so no area
        walk found the area and the commit's evidence hold passed with
        three BLOCKERs open (SAB PubMedQA, 2026-10-29). The journal copy on
        the branch still names the area (`attempts.copied_areas`): the
        commit and the stop hold its lost record and cut journal. Twins: a
        change in another area brings it in no more than before, and the
        area restored from HEAD passes."""
        from labkit.gates import agent_hooks

        area = area_in_repo()
        root = area.parent.parent
        _, record = self.attempt(area)
        other = root / "experiments" / "02-y"
        other.mkdir()
        (other / "PROTOCOL-y.md").write_text("# P\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "audited")
        self.assertEqual(attempts.copied_areas(root), [area.resolve()])
        shutil.rmtree(area)
        (other / "notes.md").write_text("a change elsewhere\n", encoding="utf-8")
        git(root, "add", "-A")
        staged = [
            root / p
            for p in subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--no-renames"],
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout.split()
        ]  # fmt: skip
        self.assertIn(area / "audits" / record.name, staged)
        for held in (
            agent_hooks.undecided_blockers(root, staged, staged=True),
            agent_hooks.undecided_blockers(root, staged),
        ):
            line = "\n".join(held)
            self.assertIn(
                f"experiments/01-x: audits/{record.name} is committed and gone", line
            )
            self.assertIn(
                "audits/attempts.jsonl no longer starts with the lines HEAD holds", line
            )
        # the twin: a change elsewhere alone names the copied area nowhere
        self.assertEqual(
            agent_hooks.undecided_blockers(root, [other / "notes.md"], staged=True), []
        )
        git(root, "checkout", "HEAD", "--", "experiments/01-x")
        self.assertEqual(agent_hooks.undecided_blockers(root, staged, staged=True), [])

    def test_copied_areas_are_none_on_a_detached_head(self):
        area = area_in_repo()
        root = area.parent.parent
        self.assertEqual(attempts.copied_areas(root), [])  # no copy yet
        self.attempt(area)
        self.assertEqual(attempts.copied_areas(root), [area.resolve()])
        git(root, "checkout", "-q", "--detach")
        self.assertEqual(attempts.copied_areas(root), [])

    def test_the_next_audit_names_the_restore_that_works(self):
        area = area_in_repo()
        _, record = self.attempt(area)
        record.unlink()
        (gap,) = attempts.area_gaps(area).blockers
        self.assertNotIn("git checkout", gap)  # never committed: no checkout
        subprocess.run(self.restore(gap), shell=True, cwd=area, check=True)
        self.assertEqual(attempts.area_gaps(area).blockers, [])

    def test_a_decided_record_differs_from_its_copy_and_passes(self):
        area = area_in_repo()
        _, record = self.attempt(area)
        record.write_text(record.read_text(encoding="utf-8") + "# decided\n")
        self.assertEqual(attempts.area_gaps(area).blockers, [])

    def test_without_a_copy_the_loss_is_said_not_a_restore(self):
        area = area_in_repo()
        git(area.parent.parent, "checkout", "-q", "--detach")
        _, record = self.attempt(area)
        self.assertEqual(attempts.kept_files(area), {})
        record.unlink()
        (gap,) = attempts.area_gaps(area).blockers
        self.assertIn("no commit and no copy keeps it: it is lost", gap)
        self.assertIn("handover", gap)


class Hook(unittest.TestCase):
    def test_the_stop_and_the_commit_name_a_record_gone_and_release_its_repair(self):
        from labkit.gates import agent_hooks

        area = area_in_repo()
        root = area.parent.parent
        running = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        failed = failed_attempts.write_failed(area, "analysis", "opus", "s", "b", 60, "e",
                                       "c", cause="unavailable")  # fmt: skip
        running.end("failed", file=failed.name)  # as labkit-audit journals it
        git(root, "add", "-A")
        git(root, "commit", "-qm", "failed attempt")
        self.assertEqual(agent_hooks.undecided_blockers(root, [failed]), [])
        failed.unlink()
        line = "\n".join(agent_hooks.undecided_blockers(root, [failed]))
        self.assertIn(f"audits/{failed.name} is committed and gone from the tree", line)
        # the commit: deleted on disk only, the index still carries it — fine;
        # removed from the index while it stays on disk — gone from the commit
        git(root, "checkout", "HEAD", "--", str(failed.relative_to(root)))
        self.assertEqual(
            agent_hooks.undecided_blockers(root, [failed], staged=True), []
        )
        git(root, "rm", "-q", "--cached", str(failed.relative_to(root)))
        self.assertTrue(failed.is_file())
        line = "\n".join(agent_hooks.undecided_blockers(root, [failed], staged=True))
        self.assertIn("is committed and gone from the index", line)
        out = io.StringIO()
        # the pre-commit's paths are read at the repo git runs it in
        with contextlib.redirect_stdout(out), contextlib.chdir(root):
            rc = agent_hooks.undecided([str(failed.relative_to(root))])
        self.assertEqual(rc, 1)
        self.assertIn("evidence is gone, changed or does not read", out.getvalue())
        # the deletion committed past the pre-commit: HEAD's journal names a
        # record HEAD lacks — the stop holds it; the repair staged releases
        # the repair commit, and after it the stop is clean again
        git(root, "commit", "-qm", "drop the record", "--no-verify")
        self.assertTrue(failed.is_file())
        line = "\n".join(agent_hooks.undecided_blockers(root, [failed]))
        self.assertIn("HEAD's journal names it while HEAD lacks the file", line)
        git(root, "add", str(failed.relative_to(root)))
        self.assertEqual(
            agent_hooks.undecided_blockers(root, [failed], staged=True), []
        )
        git(root, "commit", "-qm", "restore the record")
        self.assertEqual(agent_hooks.undecided_blockers(root, [failed]), [])


class OneBlock(unittest.TestCase):
    """`attempt`: a call that starts and ends in one block — the reviews —
    always leaves an end in the journal."""

    def test_the_block_ends_it_with_its_record(self):
        area = area_in_repo()
        with attempts.attempt(area, "review", "opus", "s") as running:
            (path := area / "audits" / "r-review.toml").write_text(
                "x", encoding="utf-8"
            )
            running.end("record", file=attempts.under_audits(area, path))
        (a,) = attempts.read_journal(area)
        self.assertEqual((a.mode, a.outcome, a.file), ("review", "record", path.name))

    def test_a_block_that_raises_ends_it_none_with_the_words(self):
        area = area_in_repo()
        with self.assertRaisesRegex(RuntimeError, "the CLI died"):
            with attempts.attempt(area, "review", "opus", "s"):
                raise RuntimeError("the CLI died")
        (a,) = attempts.read_journal(area)
        self.assertEqual((a.outcome, a.error), ("none", "RuntimeError: the CLI died"))

    def test_a_block_that_returns_unended_ends_it_none(self):
        area = area_in_repo()
        with attempts.attempt(area, "report-review", "opus", "f"):
            pass
        (a,) = attempts.read_journal(area)
        self.assertEqual(
            (a.outcome, a.error), ("none", "the command ended before the record")
        )

    def test_a_refused_start_makes_no_attempt(self):
        area = area_in_repo()
        first = attempts.begin(
            area, "analysis", "opus", "s", block_sha="b", protocol="PROTOCOL-x.md"
        )
        with self.assertRaisesRegex(attempts.AttemptError, "is running"):
            with attempts.attempt(area, "review", "opus", "s"):
                self.fail("the block must not run")
        first.end("none", error="done")
        self.assertEqual([a.mode for a in attempts.read_journal(area)], ["analysis"])

    def test_under_audits_names_a_file_in_a_subfolder(self):
        area = area_in_repo()
        sub = area / "audits" / "report-reviews" / "m-review.toml"
        self.assertEqual(
            attempts.under_audits(area, sub), "report-reviews/m-review.toml"
        )
        with self.assertRaises(ValueError):
            attempts.under_audits(area, area / "PROTOCOL-x.md")


if __name__ == "__main__":
    unittest.main()
