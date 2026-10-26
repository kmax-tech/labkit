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
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import attempts, findings  # noqa: E402
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
        running = attempts.begin(area, "analysis", "opus", "s")
        (path := area / "audits" / "r.toml").write_text("x", encoding="utf-8")
        running.end("record", file=path.name)
        (a,) = attempts.read_journal(area)
        self.assertEqual((a.outcome, a.file), ("record", "r.toml"))
        self.assertEqual(attempts.area_gaps(area).blockers, [])
        path.unlink()
        (gap,) = attempts.area_gaps(area).blockers
        self.assertIn("ended as record in audits/r.toml, and the file is gone", gap)
        with self.assertRaisesRegex(attempts.AttemptError, "the file is gone"):
            attempts.begin(area, "analysis", "opus", "s")

    def test_a_running_attempt_refuses_a_second_and_an_ended_one_does_not(self):
        area = area_in_repo()
        first = attempts.begin(area, "analysis", "opus", "s")
        with self.assertRaisesRegex(attempts.AttemptError, "is running"):
            attempts.begin(area, "analysis", "opus", "s")
        first.end("none", error="no answer")
        attempts.begin(area, "analysis", "opus", "s").end("none", error="again")

    def test_a_committed_record_removed_refuses_the_next_attempt(self):
        area = area_in_repo()
        findings.write_failed(area, "analysis", "opus", "s", "b", 60, "e", "c",
                              cause="unavailable")  # fmt: skip
        git(area.parent.parent, "add", "-A")
        git(area.parent.parent, "commit", "-qm", "failed attempt")
        for f in (area / "audits").glob("*.toml"):
            f.unlink()  # `rm audits/*.toml`, as t18 ran it
        with self.assertRaisesRegex(attempts.AttemptError, "committed and gone"):
            attempts.begin(area, "analysis", "opus", "s")

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
                "r = attempts.begin(Path(sys.argv[1]), 'analysis', 'opus', 's');"
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
                attempts.begin(area, "analysis", "opus", "s")
        finally:
            os.kill(child.pid, signal.SIGKILL)
            child.wait()
        running = attempts.begin(area, "analysis", "opus", "s")
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
            "\ntry:\n r = attempts.begin(Path(sys.argv[1]), 'analysis', 'opus', 's')"
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
            attempts.begin(area, "analysis", "opus", "s")  # never ended
        running = attempts.begin(area, "analysis", "opus", "s")
        self.assertIn("started on elsewhere and has no end", running.notes[0])
        running.end("none", error="test")


class Hook(unittest.TestCase):
    def test_the_stop_and_the_commit_name_a_record_gone(self):
        from labkit.gates import claude_hooks

        area = area_in_repo()
        root = area.parent.parent
        failed = findings.write_failed(area, "analysis", "opus", "s", "b", 60, "e",
                                       "c", cause="unavailable")  # fmt: skip
        git(root, "add", "-A")
        git(root, "commit", "-qm", "failed attempt")
        self.assertEqual(claude_hooks.undecided_blockers(root, [failed]), [])
        failed.unlink()
        (line,) = claude_hooks.undecided_blockers(root, [failed])
        self.assertIn(f"audits/{failed.name} is committed and gone from the tree", line)
        # the commit: deleted on disk only, the index still carries it — fine;
        # removed from the index while it stays on disk — gone from the commit
        git(root, "checkout", "HEAD", "--", str(failed.relative_to(root)))
        self.assertEqual(
            claude_hooks.undecided_blockers(root, [failed], staged=True), []
        )
        git(root, "rm", "-q", "--cached", str(failed.relative_to(root)))
        self.assertTrue(failed.is_file())
        (line,) = claude_hooks.undecided_blockers(root, [failed], staged=True)
        self.assertIn("is committed and gone from the index", line)
        out = io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}),
        ):
            rc = claude_hooks.undecided([str(failed.relative_to(root))])
        self.assertEqual(rc, 1)
        self.assertIn("an audit record is gone", out.getvalue())


if __name__ == "__main__":
    unittest.main()
