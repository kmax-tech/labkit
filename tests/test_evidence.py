"""evidence — committed evidence stays as written: a record changes in its
decision lines alone, other audit files never, a closed run never; the
tree and the index are held to HEAD, the session's commits to their
parents, and HEAD's reflog keeps the closed runs a reset left behind.

Why: the lab notebook's rule — a record is never erased or written over,
a correction is added beside it (docs/notes/2026-10-27-standard-way-out.md);
ninth haiku round t5 rewrote audit records field by field, and nothing
held a committed run's files. Each blocker has its twin: a decision
through `--decide`, a run still open, a journal appended to, an amend of
code alone, an ignored file labkit did not write.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import evidence, findings  # noqa: E402
from labkit.gates import audit, agent_hooks  # noqa: E402
from protocol_fixture import head, registration_of  # noqa: E402
from test_agent_hooks import _dated, _git, _run, _transcript  # noqa: E402

WARNING = ("WARNING", "WARNING · scripts/01_measure.py:9 · the seed is not recorded")
CLOSED = "2026-10-28T10-00-00_ab12"
OPEN = "2026-10-28T11-00-00_cd34"


def _record(area: Path) -> Path:
    return findings.write(
        area,
        "preflight",
        "opus",
        "0123456789ab",
        "b10c0000000a",
        (0, 1, 0),
        [WARNING],
        registration=registration_of(area),
    )


def _run_dir(area: Path, run_id: str, *, closed: bool) -> Path:
    d = area / "runs" / run_id
    d.mkdir(parents=True)
    (d / "config.json").write_text('{"run_id": "x"}\n', encoding="utf-8")
    (d / "metrics.json").write_text('{"acc": 0.8}\n', encoding="utf-8")
    if closed:
        (d / "completion.json").write_text('{"finished": "t"}\n', encoding="utf-8")
    return d


class Rules(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp()).resolve() / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")

    def test_a_decision_leaves_the_record_as_written_besides_its_lines(self):
        path = _record(self.area)
        before = path.read_text(encoding="utf-8")
        findings.write_decision(path, 1, "limitation", "noted", "stands")
        after = path.read_text(encoding="utf-8")
        self.assertNotEqual(before, after)
        self.assertFalse(evidence.record_changed(before, after))
        self.assertEqual(
            findings.without_decisions(before), findings.without_decisions(after)
        )

    def test_a_finding_rewritten_by_hand_is_a_change(self):
        path = _record(self.area)
        before = path.read_text(encoding="utf-8")
        after = before.replace("the seed is not recorded", "all is well")
        self.assertTrue(evidence.record_changed(before, after))

    def test_a_record_without_decision_lines_is_compared_whole(self):
        self.assertIsNone(findings.without_decisions("[[finding]]\ntext = 'x'\n"))
        self.assertTrue(evidence.record_changed("[[finding]]\n", "[[finding]]\n#\n"))

    def test_a_run_is_closed_by_its_completion_or_its_failure(self):
        files = [
            f"runs/{CLOSED}/completion.json",
            f"runs/{OPEN}/metrics.json",
            "runs/2026-10-28T12-00-00_ef56/failure.json",
            "audits/x.toml",
        ]
        self.assertEqual(
            evidence.closed_runs(files), {CLOSED, "2026-10-28T12-00-00_ef56"}
        )
        self.assertIsNone(evidence.run_of("runs/not-a-run/metrics.json"))

    def test_the_journal_an_open_run_and_a_new_file_break_nothing(self):
        entries = [
            ("M", "audits/attempts.jsonl"),
            ("M", f"runs/{OPEN}/metrics.json"),
            ("A", "audits/answers/a.txt"),
        ]
        audits, runs = evidence.broken(
            entries, set(), lambda rel: (None, None), lambda rel: False, deletions=True
        )
        self.assertEqual((audits, runs), ([], {}))


class Committed(unittest.TestCase):
    """The tree and the index against HEAD: `changes`, `ignored`."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")
        self.record = _record(self.area)
        (self.area / "audits" / "answers").mkdir()
        self.answer = self.area / "audits" / "answers" / "a1.txt"
        self.answer.write_text("FINDING ...\n", encoding="utf-8")
        self.closed = _run_dir(self.area, CLOSED, closed=True)
        self.open = _run_dir(self.area, OPEN, closed=False)
        _git(self.root, "init", "-q", ".")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "evidence")

    def test_a_decision_through_decide_is_no_change_in_tree_or_index(self):
        findings.write_decision(self.record, 1, "limitation", "noted", "stands")
        self.assertEqual(evidence.changes(self.area), [])
        _git(self.root, "add", "-A")
        self.assertEqual(evidence.changes(self.area, staged=True), [])

    def test_a_record_edited_beyond_its_decisions_names_its_restore(self):
        text = self.record.read_text(encoding="utf-8")
        self.record.write_text(text.replace("seed", "SEED"), encoding="utf-8")
        (line,) = evidence.changes(self.area)
        rel = f"experiments/01-x/audits/{self.record.name}"
        self.assertIn("changed beyond its findings' decision lines", line)
        self.assertIn(f"`git checkout HEAD -- {rel}`", line)
        self.assertIn("— way out: ", line)
        _git(self.root, "checkout", "HEAD", "--", rel)
        self.assertEqual(evidence.changes(self.area), [])

    def test_a_kept_answer_changed_is_named(self):
        self.answer.write_text("FINDING rewritten\n", encoding="utf-8")
        (line,) = evidence.changes(self.area)
        self.assertIn("audits/answers/a1.txt: changed in the tree since HEAD", line)

    def test_a_closed_runs_files_changed_or_gone_are_one_line(self):
        (self.closed / "metrics.json").write_text('{"acc": 0.9}\n', encoding="utf-8")
        (self.closed / "config.json").unlink()
        (line,) = evidence.changes(self.area)
        self.assertIn(f"runs/{CLOSED}: the closed run's", line)
        self.assertIn("metrics.json (changed)", line)
        self.assertIn("config.json (deleted)", line)
        self.assertIn(f"`git checkout HEAD -- experiments/01-x/runs/{CLOSED}`", line)

    def test_an_open_run_is_still_runlogs_to_write(self):
        (self.open / "metrics.json").write_text('{"acc": 0.9}\n', encoding="utf-8")
        (self.open / "completion.json").write_text("{}\n", encoding="utf-8")
        self.assertEqual(evidence.changes(self.area), [])

    def test_the_index_is_what_the_commit_carries(self):
        _git(
            self.root,
            "rm",
            "-q",
            "--cached",
            f"experiments/01-x/runs/{CLOSED}/metrics.json",
        )
        self.assertEqual(evidence.changes(self.area), [])  # the tree still holds it
        (line,) = evidence.changes(self.area, staged=True)
        self.assertIn("metrics.json (deleted) in the index since HEAD", line)

    def test_evidence_git_ignores_is_named_and_litter_is_not(self):
        (self.root / ".gitignore").write_text("answers/\n.DS_Store\n", encoding="utf-8")
        (self.area / "audits" / "answers" / "a2.txt").write_text(
            "x\n", encoding="utf-8"
        )
        (self.area / "audits" / ".DS_Store").write_text("x", encoding="utf-8")
        (line,) = evidence.ignored(self.area)
        self.assertIn("audits/answers/a2.txt: git ignores it", line)
        self.assertIn(
            "`git check-ignore -v experiments/01-x/audits/answers/a2.txt`", line
        )

    def test_the_commit_gate_holds_a_changed_record_and_a_handover_does_not_pass_it(
        self,
    ):
        text = self.record.read_text(encoding="utf-8")
        self.record.write_text(text.replace("seed", "SEED"), encoding="utf-8")
        _git(self.root, "add", "-A")
        with mock.patch.object(
            agent_hooks.handovers,
            "acknowledgement",
            return_value=agent_hooks.handovers.Acknowledgement(True, {}),
        ):
            state = agent_hooks.undecided_state(self.root, [self.record], staged=True)
        (line,) = state.blockers
        self.assertTrue(line.startswith("experiments/01-x: audits/"))
        self.assertIn("in the index since HEAD", line)

    def test_the_recovery_entry_shows_the_change_and_its_restore(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(audit.main([str(self.area), "--findings"]), 0)
        self.assertNotIn("evidence changed", out.getvalue())
        self.answer.write_text("FINDING rewritten\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(audit.main([str(self.area), "--findings"]), 2)
        self.assertIn(
            "evidence changed: audits/answers/a1.txt: changed", out.getvalue()
        )
        self.assertIn("git checkout HEAD --", out.getvalue())


class Session(unittest.TestCase):
    """The stop: the session's commits against their parents, HEAD's reflog."""

    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")
        (self.area / "scripts" / "01_measure.py").write_text("x = 1\n")
        self.record = _record(self.area)
        _git(self.root, "init", "-q", ".")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        with _dated(3600):  # the repo predates the session
            _git(self.root, "commit", "-qm", "init")
        self.transcript = _transcript()
        self.event = {
            "session_id": "s1",
            "cwd": str(self.root),
            "stop_hook_active": False,
            "transcript_path": str(self.transcript),
        }
        agent_hooks.keep_stop_base(self.root, self.event)  # the first Bash command

    def _stop(self) -> tuple[int, str]:
        rc, _, err = _run(agent_hooks.stop, self.event)
        return rc, err

    def _commit(self, message: str, *args: str) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", message, *args)

    def test_a_commit_past_the_pre_commit_that_rewrote_a_record_holds(self):
        parent = _head(self.root)
        text = self.record.read_text(encoding="utf-8")
        self.record.write_text(text.replace("seed", "SEED"), encoding="utf-8")
        self._commit("rewrite")  # no hook in this repo: as --no-verify
        rc, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("changed beyond its findings' decision lines by commit", err)
        rel = f"experiments/01-x/audits/{self.record.name}"
        self.assertIn(f"`git checkout {parent[:12]} -- {rel}`", err)
        # the restore is the repair, committed or not — and the commit that
        # carries it passes the pre-commit's rule though it changes HEAD's record
        _git(self.root, "checkout", parent[:12], "--", rel)
        rc, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertEqual(evidence.changes(self.area, staged=True), [])
        self._commit("restore")
        rc, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_a_decision_committed_in_the_session_passes(self):
        findings.write_decision(self.record, 1, "limitation", "noted", "stands")
        self._commit("decide")
        rc, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_a_reset_that_left_a_closed_run_behind_holds(self):
        _run_dir(self.area, CLOSED, closed=True)
        self._commit("run")
        held = _head(self.root)
        _git(self.root, "reset", "-q", "--hard", "HEAD~1")
        rc, err = self._stop()
        self.assertEqual(rc, 2)
        folder = f"experiments/01-x/runs/{CLOSED}"
        self.assertIn(f"{folder}: the closed run's 3 file(s) gone", err)
        self.assertIn("a reset, an amend or a rebase", err)
        self.assertIn(f"`git checkout {held[:12]} -- {folder}`", err)
        _git(self.root, "checkout", held[:12], "--", folder)
        rc, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_an_amend_of_code_alone_keeps_the_run_and_passes(self):
        _run_dir(self.area, CLOSED, closed=True)
        self._commit("run")
        (self.area / "scripts" / "01_measure.py").write_text("x = 2\n")
        self._commit("run", "--amend")
        rc, err = self._stop()
        self.assertEqual(rc, 0, err)


class Told(unittest.TestCase):
    """The post-change hook says right after the tool what the stop and the
    commit will hold of an area's evidence; it holds nothing itself."""

    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")
        self.record = _record(self.area)
        self.closed = _run_dir(self.area, CLOSED, closed=True)
        _git(self.root, "init", "-q", ".")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "evidence")
        self.event = {
            "session_id": "s-" + os.urandom(4).hex(),
            "cwd": str(self.root),
            "tool_name": "Bash",
            "tool_input": {"command": "rm …"},
        }

    def _told(self) -> str:
        rc, out, _ = _run(agent_hooks.post_change, self.event)
        self.assertEqual(rc, 0)  # it tells, never holds
        if not out:
            return ""
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_a_deleted_record_is_told_once_with_its_restore(self):
        self.record.unlink()
        ctx = self._told()
        self.assertIn("evidence of experiments/01-x is gone or changed", ctx)
        self.assertIn(f"audits/{self.record.name} is committed and gone", ctx)
        self.assertIn("git checkout HEAD --", ctx)
        self.assertEqual(self._told(), "")  # the same state, told already

    def test_a_closed_runs_file_changed_is_told(self):
        (self.closed / "metrics.json").write_text('{"acc": 0.99}\n', encoding="utf-8")
        ctx = self._told()
        self.assertIn(f"runs/{CLOSED}: the closed run's metrics.json (changed)", ctx)

    def test_a_decision_and_a_new_run_are_silent(self):
        findings.write_decision(self.record, 1, "limitation", "noted", "stands")
        _run_dir(self.area, OPEN, closed=False)
        self.assertEqual(self._told(), "")

    def test_a_restore_forgets_the_state_so_the_next_loss_is_told_again(self):
        self.record.unlink()
        self.assertNotEqual(self._told(), "")
        _git(
            self.root,
            "checkout",
            "HEAD",
            "--",
            f"experiments/01-x/audits/{self.record.name}",
        )
        self.assertEqual(self._told(), "")
        self.record.unlink()
        self.assertNotEqual(self._told(), "")


def _head(root: Path) -> str:
    return agent_hooks.head_sha(root)


if __name__ == "__main__":
    unittest.main()
