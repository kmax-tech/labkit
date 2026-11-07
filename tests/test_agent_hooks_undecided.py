"""The stop hook and the pre-commit hold an area the session touched to its
audit records: a BLOCKER nobody decided sends the agent back, and refuses
the commit (`claude-hook undecided`).

report-check refuses a number whose BLOCKERs stand open, but a gate the
agent has to call is no gate; the stop and the commit are the two it cannot
choose. Twins: a decided BLOCKER, an open
WARNING, an area the session did not touch — all silent.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.gates import agent_hooks, claude_hooks  # noqa: E402
from labkit.gates import undecided
from labkit.formats import findings, repo  # noqa: E402
from protocol_fixture import registration_of, head  # noqa: E402
from test_agent_hooks import _dated, _git, _run, _transcript  # noqa: E402

BLOCKER = (
    "BLOCKER",
    "BLOCKER · scripts/01_measure.py:3 · statement · the target leaks",
)
WARNING = (
    "WARNING",
    "WARNING · scripts/01_measure.py:9 · statement · the seed is not recorded",
)


class Undecided(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        self.other = self.root / "experiments" / "02-y"
        for area in (self.area, self.other):
            (area / "scripts").mkdir(parents=True)
            (area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")
            (area / "scripts" / "01_measure.py").write_text("x = 1\n")
        _git(self.root, "init", "-q", ".")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        with _dated(3600):  # the repo predates the session
            _git(self.root, "commit", "-qm", "init")

    def _record(self, area: Path, rows) -> Path:
        return findings.write(
            area,
            "preflight",
            "opus",
            "0123456789ab",
            "b10c0000000a",
            (
                sum(g == "BLOCKER" for g, _ in rows),
                sum(g == "WARNING" for g, _ in rows),
                0,
            ),
            rows,
            registration=registration_of(area),
        )

    def _touch(self, area: Path) -> Path:
        p = area / "scripts" / "01_measure.py"
        p.write_text("x = 2\n", encoding="utf-8")
        return p

    def _stop(self, active: bool = False) -> tuple[int, str, str]:
        # a session as Claude Code starts one: its transcript dates it
        if not hasattr(self, "transcript"):
            self.transcript = _transcript()
        return _run(
            agent_hooks.stop,
            {
                "session_id": "s1",
                "cwd": str(self.root),
                "stop_hook_active": active,
                "transcript_path": str(self.transcript),
            },
        )

    def test_an_open_blocker_in_a_touched_area_sends_the_agent_back(self):
        path = self._record(self.area, [BLOCKER])  # audits/ is itself a change
        with contextlib.chdir(self.root):  # the hook runs in the project dir
            rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKER(s) nobody decided", err)
        self.assertIn(
            f"experiments/01-x: {path.name}: BLOCKER · scripts/01_measure.py:3", err
        )
        self.assertIn("the stop holds", err)
        self.assertIn("labkit-next: experiments/01-x", err)  # the step is `next`'s

    def test_the_undecided_row_of_next_names_the_command_never_an_edit(self):
        """`next`'s row for the hold: the way to decide is the command, not
        an edit of the record; an outdated record stays and is decided, not
        removed; the twin: nothing open, no row."""
        from labkit.gates import next_step

        protocol = self.area / "PROTOCOL-x.md"
        with contextlib.chdir(self.root):
            self.assertIsNone(
                next_step._undecided_step(self.area, protocol, staged=False)
            )
            path = self._record(self.area, [BLOCKER])
            step = next_step._undecided_step(self.area, protocol, staged=False)
        assert step is not None
        self.assertIn(f"{path.name}: BLOCKER", step.where)
        self.assertIn("`labkit-audit experiments/01-x --findings`", step.next)
        self.assertIn("never by rewriting or deleting the record", step.next)
        self.assertIn(
            "one a later change made outdated stays and is decided", step.next
        )
        self.assertIn("--handover", step.next)
        self.assertIn("cannot be reported", step.held)

    def test_the_stop_and_the_commit_print_next_steps_step_for_the_hold(self):
        """The stop and the commit hold on the undecided BLOCKER and print
        `labkit-next`'s step for it, byte for byte, each from the state it
        judges (the tree, the index) — no sentence of their own names a way;
        the way's text has one home (`next_step.Step.render`)."""
        from labkit.gates.next_step import next_step
        from labkit.gates.report_context import INDEX

        path = self._record(self.area, [BLOCKER])
        protocol = self.area / "PROTOCOL-x.md"
        with contextlib.chdir(self.root):
            rc, _, err = self._stop()
            self.assertEqual(rc, 2)
            step = next_step(self.area, protocol).render("experiments/01-x")
            self.assertIn(step, err)
            self.assertIn(f"experiments/01-x: {path.name}: BLOCKER", err)  # the hold
            _git(self.root, "add", "-A")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_hooks.main(["pre-commit"])
            self.assertEqual(rc, 1)
            staged = next_step(self.area, protocol, state=INDEX).render(
                "experiments/01-x"
            )
            self.assertIn(staged, out.getvalue())
            self.assertIn(f"experiments/01-x: {path.name}: BLOCKER", out.getvalue())
        for text in (err, out.getvalue()):
            self.assertNotIn("decide each BLOCKER", text)  # no text of its own

    def test_the_committed_record_blocks_once_the_area_is_touched_again(self):
        self._record(self.area, [BLOCKER])
        with _dated(3600):  # committed before the session
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", "audit")
        rc, _, _ = self._stop()
        self.assertEqual(rc, 0)  # nothing of this area changed in the session
        self._touch(self.area)
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("the target leaks", err)

    def test_a_deleted_or_moved_script_touches_its_area(self):
        """A removal reopens the area as an edit does: the stop read only
        what is still there."""
        self._record(self.area, [BLOCKER])
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "audit")
        (self.area / "scripts" / "01_measure.py").unlink()
        rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        _git(self.root, "checkout", "--", ".")
        _git(self.root, "mv", "experiments/01-x/scripts/01_measure.py", "moved.py")
        rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("the target leaks", err)

    def test_a_decided_blocker_and_an_open_warning_let_it_stop(self):
        path = self._record(self.area, [BLOCKER, WARNING])
        text = path.read_text(encoding="utf-8")
        first, rest = text.split("[[finding]]", 1)
        blocker_tbl, warning_tbl = rest.split("[[finding]]")
        decided = blocker_tbl.replace(
            'status = "open"', 'status = "limitation"'
        ).replace('reason = ""', 'reason = "the leak is the measured quantity"')
        path.write_text(first + "[[finding]]" + decided + "[[finding]]" + warning_tbl)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_an_untouched_area_does_not_block(self):
        self._record(self.other, [BLOCKER])
        with _dated(3600):  # committed before the session
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", "audit elsewhere")
        self._touch(self.area)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_sent_back_once_already_may_stop(self):
        """Without a hold of this session on record, a second stop lets go
        as before."""
        self._record(self.area, [BLOCKER])
        rc, _, _ = self._stop(active=True)
        self.assertEqual(rc, 0)

    def test_the_same_checked_state_holds_once_per_turn_a_changed_one_again(self):
        """The guarantee is "the same checked state holds once per turn",
        not "no loop" — a tree changed since the hold (content, a file added
        or gone, HEAD) is a new state and holds again; the unchanged one lets
        go."""
        self._record(self.area, [BLOCKER])
        with contextlib.chdir(self.root):
            self.assertEqual(self._stop()[0], 2)  # the hold, its state kept
            rc, _, err = self._stop(active=True)
            self.assertEqual(rc, 0, err)
            self.assertIn("on this very state", err)
            self._touch(self.area)  # the agent did something: a new state
            rc, _, err = self._stop(active=True)
            self.assertEqual(rc, 2, err)
            self.assertIn("the state changed since", err)
            self.assertEqual(self._stop(active=True)[0], 0)  # unchanged again
            (self.area / "scripts" / "01_measure.py").unlink()  # a file gone
            self.assertEqual(self._stop(active=True)[0], 2)

    def test_a_run_index_that_does_not_read_is_told_and_keeps_the_loop_guard(self):
        """report-check raising on a damaged runs.tsv is a finding of the
        stop, told once per turn — never exit 2 on every turn, past
        `stop_hook_active`."""
        from unittest import mock

        from labkit.gates import report_check
        from labkit.run.runlog import RunIndexError

        self._touch(self.area)
        damaged = RunIndexError("runs.tsv:2: 1 of 8 tab-separated columns")
        with mock.patch.object(report_check, "hold_reported", side_effect=damaged):
            rc, _, err = self._stop()
            self.assertEqual(rc, 2)
            self.assertIn("runs.tsv:2: 1 of 8 tab-separated columns", err)
            self.assertEqual(self._stop(active=True)[0], 0)

    def test_an_unreadable_record_is_loud(self):
        (self.area / findings.DIR).mkdir()
        (self.area / findings.DIR / "2026-10-20T14-03-preflight.toml").write_text(
            "no = [toml\n"
        )
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("not TOML", err)

    def test_the_pre_commit_command_holds_the_staged_paths(self):
        """`claude-hook pre-commit` reads the index itself: the record staged
        holds; an untouched area or a file outside every area staged alone
        passes; an argument is refused."""
        path = self._record(self.area, [BLOCKER])
        _git(self.root, "add", "-A")  # the commit carries the record
        with contextlib.chdir(self.root):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_hooks.main(["pre-commit"])
            self.assertEqual(rc, 1)
            self.assertIn(path.name, out.getvalue())
            _git(self.root, "reset", "-q")
            _git(self.root, "add", str(self._touch(self.other)))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(claude_hooks.main(["pre-commit"]), 0)
                _git(self.root, "reset", "-q")
                (self.root / "README.md").write_text("# r\n", encoding="utf-8")
                _git(self.root, "add", "README.md")
                self.assertEqual(claude_hooks.main(["pre-commit"]), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(claude_hooks.main(["pre-commit", "README.md"]), 2)

    def test_the_pre_commit_entry_runs_every_gate_on_the_index_and_prints_next_once(
        self,
    ):
        """One entry, the gates of three commands (the protocol's fields,
        report-check, the undecided state), each telling its findings, and
        `next`'s step per protocol once; the twin, a clean index, passes
        in silence."""
        from labkit.checks import protocol_report

        path = self._record(self.area, [BLOCKER])
        protocol = self.area / "PROTOCOL-x.md"
        protocol.write_text(
            head(frozen=True), encoding="utf-8"
        )  # frozen: should → MUST
        _git(self.root, "add", "-A")
        with contextlib.chdir(self.root):
            fields = io.StringIO()
            with contextlib.redirect_stdout(fields):
                held = protocol_report.check_files(
                    [Path("experiments/01-x/PROTOCOL-x.md")],
                    protocol_report.template_lines(protocol_report.find_template(None)),
                    staged=True,
                )
            self.assertTrue(held)
            held_lines = undecided.undecided_blockers(
                self.root, [self.area / "PROTOCOL-x.md"], staged=True
            )
            self.assertTrue(held_lines)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_hooks.main(["pre-commit"])
        self.assertEqual(rc, 1)
        text = out.getvalue()
        self.assertIn(fields.getvalue(), text)  # the fields gate's own lines
        for line in held_lines:
            self.assertIn(line, text)  # the undecided gate's own lines
        self.assertIn(f"experiments/01-x: {path.name}: BLOCKER", text)
        self.assertEqual(text.count("labkit-next: experiments/01-x"), 1)
        self.assertIn("MUST field", text)  # next's step names the fields first
        _git(self.root, "reset", "-q")
        _git(self.root, "add", str(self._touch(self.other)))
        with contextlib.chdir(self.root):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_hooks.main(["pre-commit"])
        self.assertEqual((rc, out.getvalue()), (0, ""))

    def test_the_commit_reads_the_decisions_the_index_holds(self):
        """The pre-commit reads the decisions from the index, as the
        journal: a BLOCKER decided in the tree and never staged holds the
        commit, which carries it open. The twins: the decision staged
        passes, and a staged decision reopened only in the tree does not
        hold the commit, which carries the decision."""
        path = self._record(self.area, [BLOCKER])
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "audit")
        open_text = path.read_text(encoding="utf-8")
        findings.write_decision(path, 1, "limitation", "measured in area 02", "stands")
        script = self._touch(self.area)
        _git(self.root, "add", str(script))

        def commit_gate() -> tuple[int, str]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.chdir(self.root):
                rc = claude_hooks.main(["pre-commit"])
            return rc, out.getvalue()

        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn(f"experiments/01-x: {path.name}: BLOCKER", out)
        self.assertEqual(self._stop()[0], 0)  # the tree is decided
        _git(self.root, "add", str(path))
        self.assertEqual(commit_gate(), (0, ""))
        path.write_text(open_text, encoding="utf-8")  # reopened, not staged
        self.assertEqual(commit_gate(), (0, ""))
        self.assertEqual(self._stop()[0], 2)

    def test_a_record_left_out_of_the_commit_holds_it(self):
        """A record in the tree the index lacks holds the commit, naming the
        `git add`, so a fresh audit record never staged does not let a commit
        of the area's script pass its open BLOCKER; the twin, the record
        staged and decided, passes."""
        path = self._record(self.area, [BLOCKER])
        script = self._touch(self.area)
        _git(self.root, "add", str(script))

        def commit_gate() -> tuple[int, str]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.chdir(self.root):
                rc = claude_hooks.main(["pre-commit"])
            return rc, out.getvalue()

        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn("in the tree, not in the index", out)
        self.assertIn(f"git add experiments/01-x/audits/{path.name}", out)
        self.assertIn("a record a later change made outdated is staged too", out)
        findings.write_decision(path, 1, "limitation", "measured in area 02", "stands")
        _git(self.root, "add", str(path))
        self.assertEqual(commit_gate(), (0, ""))

    def test_a_record_the_index_cannot_read_is_named_as_the_index_holds_it(self):
        self._record(self.area, [BLOCKER])
        bad = self.area / findings.DIR / "2026-10-20T14-03-preflight.toml"
        bad.write_text("no = [toml\n", encoding="utf-8")
        _git(self.root, "add", "-A")
        bad.unlink()  # the tree lost it, the commit carries it
        lines = undecided.undecided_blockers(
            self.root, [self.area / "scripts" / "01_measure.py"], staged=True
        )
        self.assertTrue(
            any("not TOML" in ln and "as git's index holds it" in ln for ln in lines),
            lines,
        )

    def test_without_a_stop_base_only_the_sessions_commits_are_held(self):
        """The stop base gone: the commits dated since the transcript began
        stand in — never every protocol of the repo, or an old area's open
        BLOCKER would hold every stop. The twin: a session commit in that
        area holds."""
        with _dated(3600):  # the repo before the session
            self._record(self.other, [BLOCKER])
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", "an old audit")
        event = {
            "session_id": "s1",
            "cwd": str(self.root),
            "transcript_path": str(_transcript()),
            "stop_hook_active": False,
        }
        self._touch(self.area)
        _git(self.root, "commit", "-qam", "the session's work", "--no-verify")
        rc, _, err = _run(agent_hooks.stop, event)
        self.assertEqual(rc, 0, err)
        self.assertIn("the session has no stop base", err)
        self.assertNotIn("the target leaks", err)
        self._touch(self.other)
        _git(self.root, "commit", "-qam", "into the old area", "--no-verify")
        rc, _, err = _run(agent_hooks.stop, event)
        self.assertEqual(rc, 2, err)
        self.assertIn("experiments/02-y", err)
        self.assertIn("the target leaks", err)

    def test_a_session_started_in_a_subdirectory_is_held_too(self):
        """The project directory below the repo root has no `.git` of its
        own: the stop still holds, and the pre-commit — git runs it at the
        root, the session's CLAUDE_PROJECT_DIR inherited — reads the staged
        paths against the root and finds the area. The twins: an area the
        session did not touch stays silent from there."""
        path = self._record(self.area, [BLOCKER])
        sub = self.root / "experiments"
        os.environ["CLAUDE_PROJECT_DIR"] = str(sub)
        event = {
            "session_id": "s1",
            "cwd": str(sub),
            "stop_hook_active": False,
            "transcript_path": str(_transcript()),
        }
        try:
            rc, _, err = _run(agent_hooks.stop, event)
            self.assertEqual(rc, 2, err)
            self.assertIn(f"experiments/01-x: {path.name}", err)
            _git(self.root, "add", "-A")
            with contextlib.chdir(self.root):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = claude_hooks.main(["pre-commit"])
                self.assertEqual(rc, 1)
                self.assertIn(path.name, out.getvalue())
            with _dated(3600):  # the audit committed before the session
                _git(self.root, "add", "-A")
                _git(self.root, "commit", "-qm", "audit")
            self._touch(self.other)
            rc, _, err = _run(agent_hooks.stop, event)
            self.assertEqual(rc, 0, err)
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_outside_every_repository_the_stop_says_so_and_holds_once(self):
        """No repository: the stop cannot tell what changed. It holds once
        per turn and says why."""
        d = Path(tempfile.mkdtemp()).resolve()
        if repo.git_root(d) is not None:
            self.skipTest(f"the temp directory {d} lies inside a git repository")
        rc, _, err = _run(
            agent_hooks.stop,
            {"session_id": "s1", "cwd": str(d), "stop_hook_active": False},
        )
        self.assertEqual(rc, 2)
        self.assertIn("lies in no git repository", err)
        rc, _, err = _run(
            agent_hooks.stop,
            {"session_id": "s1", "cwd": str(d), "stop_hook_active": True},
        )
        self.assertEqual(rc, 0)
        self.assertIn("lies in no git repository", err)

    def test_the_stamped_pre_commit_runs_it(self):
        from labkit.gates import install_hooks

        self.assertIn("claude-hook pre-commit", install_hooks.pre_commit())


if __name__ == "__main__":
    unittest.main()
