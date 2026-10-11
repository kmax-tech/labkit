"""Tests for claude-hook — the two Claude Code hooks (2026-10-05).

pre-run: a command that starts a run script in an area triggers preflight;
frozen + blockers blocks (exit 2), unfrozen + blockers only reports,
throwaway stages and non-run scripts pass untouched; at `cost = "seconds"`
preflight does not run and the hook only reports whether the criterion
is written (LAB-015 Preflight-Audit vor dem Einfrieren).
post-change: changed protocols and messung notes are checked whatever
tool wrote them (git status, not the tool name), once per content.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import claude_hooks, promises  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head  # noqa: E402

BODY = """\
- **Terms of this protocol:** n/a — standard vocabulary
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] p < .05
- **Admissibility condition:** [A1] parse yield above 80%
- **Model I/O:** in: text · out: a label, parsed by parse()
- **Prompt (verbatim, per variant):**

  ```text
  prompt
  ```

- **Null condition / anchors (in the same run):** [A2] shuffled labels stay at chance
- **Exclusions / filters:** none
"""


def _protocol(frozen: bool, cost: str = "minutes") -> str:
    # every area here answers from a full run, so it carries the tables (0.19)
    return (
        "# Experiment protocol: x\n\n"
        + head(frozen=frozen, cost=cost, promises=DEFAULT_BLOCK)
        + "\n"
        + BODY
    )


RUN_SCRIPT = (
    "from labkit import runlog\n"
    'with runlog.run("t", {}, protocol="PROTOCOL-x.md") as r:\n'
    '    metrics = {"c1_pass": True, "a1_pass": True, "a2_pass": True}\n'
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _repo(frozen: bool, script: str = RUN_SCRIPT, cost: str = "minutes") -> Path:
    root = Path(tempfile.mkdtemp())
    area = root / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "PROTOCOL-x.md").write_text(_protocol(frozen, cost), encoding="utf-8")
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    (root / "notes" / "messung").mkdir(parents=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _run(fn, event: dict) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(event)
    return rc, out.getvalue(), err.getvalue()


def _bash(root: Path, command: str) -> dict:
    return {
        "session_id": "s1",
        "cwd": str(root),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class PreRun(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_frozen_with_blockers_blocks(self):
        root = _repo(True)  # frozen, but no tests/ -> only a warning;
        # a missing intent id in the script is the blocker:
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKED", err)
        self.assertIn("preflight", err)

    def test_unfrozen_with_blockers_only_reports(self):
        root = _repo(False)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pilot", ctx)

    def test_seconds_skips_preflight_even_with_blockers(self):
        root = _repo(True, cost="seconds")
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("cost seconds", ctx)
        self.assertIn("registration written", ctx)
        self.assertNotIn("BLOCKED", err)

    def test_seconds_without_criterion_is_reported_not_blocked(self):
        root = _repo(False, cost="seconds")
        proto = root / "experiments/01-x/PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "[C1] p < .05", "<the criterion>"
            ),
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("placeholder", ctx)
        self.assertIn("runlog refuses", ctx)

    def test_throwaway_stage_passes_silently(self):
        root = _repo(True)
        for flag in ("--probe 3", "--show 2", "--eval-only"):
            rc, out, err = _run(
                claude_hooks.pre_run,
                _bash(root, f"python experiments/01-x/scripts/01_measure.py {flag}"),
            )
            self.assertEqual((rc, out, err), (0, "", ""), flag)

    def test_script_without_run_passes_silently(self):
        root = _repo(True, script="print('analysis only')\n")
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_a_script_merely_named_is_silent(self):
        # uniagent 2026-10-10: 85 of 272 hook lines in one session said a lib
        # module "opens a run" because a command READ it — sed, cat, a path
        # inside a heredoc. Only a run of the file is a run.
        root = _repo(True)
        (root / "lib").mkdir(exist_ok=True)
        (root / "lib" / "opens.py").write_text(RUN_SCRIPT, encoding="utf-8")
        for cmd in (
            "sed -n 1,5p lib/opens.py",
            "cat lib/opens.py | head",
            "grep -n runlog lib/opens.py experiments/01-x/scripts/01_measure.py",
            ".venv/bin/python - <<'EOF'\nfrom pathlib import Path\n"
            'p = Path("lib/opens.py")\nprint(p.read_text())\nEOF',
            "ls -l lib/opens.py",
        ):
            rc, out, err = _run(claude_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)
        # the twin: running the same file is seen
        rc, out, _ = _run(claude_hooks.pre_run, _bash(root, "python lib/opens.py"))
        self.assertEqual(rc, 0)
        self.assertIn("opens a run, but no PROTOCOL", out)

    def test_executed_py_names_runs_not_mentions(self):
        runs = {
            "python x.py": ["x.py"],
            "python3.12 -u x.py --n 3": ["x.py"],
            ".venv/bin/python scripts/01_measure.py": ["scripts/01_measure.py"],
            "./x.py": ["./x.py"],
            "cd a && python x.py; python y.py": ["x.py", "y.py"],
            "runlog start -- .venv/bin/python x.py": ["x.py"],
            "nohup x.py &": ["x.py"],
            "LABKIT_UNFROZEN=1 python x.py": ["x.py"],
        }
        for cmd, want in runs.items():
            self.assertEqual(claude_hooks.executed_py(cmd), want, cmd)
        for cmd in (
            "sed -n 1,5p x.py",
            "cat x.py",
            "ls -l x.py",
            "git add x.py",
            'p = Path("x.py")',
            "python -c 'import x'",
            "pytest tests/test_x.py -q",
        ):
            self.assertEqual(claude_hooks.executed_py(cmd), [], cmd)

    def test_skip_token_is_reported_not_blocked(self):
        root = _repo(True)
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(
                root,
                "LABKIT_PREFLIGHT=skip python experiments/01-x/scripts/01_measure.py",
            ),
        )
        self.assertEqual(rc, 0)
        self.assertIn("skipped", out)

    def test_relative_to_cwd_inside_area(self):
        # unfrozen: the fixture's should-gaps stay warnings (graduation
        # gate), so this test sees only the path resolution
        root = _repo(False)
        ev = _bash(root / "experiments/01-x", "python scripts/01_measure.py")
        rc, out, err = _run(claude_hooks.pre_run, ev)
        self.assertEqual(rc, 0, err)
        self.assertIn(
            "preflight 01-x", json.loads(out)["hookSpecificOutput"]["additionalContext"]
        )


class PostChange(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = _repo(False)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)

    def tearDown(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_protocol_written_by_heredoc_is_checked(self):
        p = self.root / "experiments/01-x/PROTOCOL-x.md"
        p.write_text(
            _protocol(False).replace(
                "- **Null condition / anchors (in the same run):** [A2] shuffled labels "
                "stay at chance\n",
                "",
            ),
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.post_change,
            _bash(self.root, "cat > PROTOCOL-x.md <<EOF ... EOF"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PROTOCOL-x.md", ctx)
        self.assertIn("MISSING (must): Null condition / anchors", ctx)

    def test_same_content_is_reported_once_per_session(self):
        p = self.root / "experiments/01-x/PROTOCOL-x.md"
        p.write_text(_protocol(False) + "\nmore\n", encoding="utf-8")
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        rc, out1, _ = _run(claude_hooks.post_change, ev)
        rc, out2, _ = _run(claude_hooks.post_change, ev)
        self.assertIn("PROTOCOL-x.md", out1)
        self.assertEqual(out2, "")

    def test_messung_note_is_checked_but_index_is_not(self):
        note = self.root / "notes/messung/2026-10-05-x.md"
        note.write_text("# x\n\nno kind line\n", encoding="utf-8")
        (self.root / "notes/messung/00-index.md").write_text(
            "# index\n", encoding="utf-8"
        )
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        rc, out, _ = _run(claude_hooks.post_change, ev)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("2026-10-05-x.md", ctx)
        self.assertNotIn("00-index.md", ctx)

    def test_nothing_changed_is_silent(self):
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        self.assertEqual(_run(claude_hooks.post_change, ev), (0, "", ""))


if __name__ == "__main__":
    unittest.main()


class Stop(unittest.TestCase):
    """`claude-hook stop`: a number written back in this session goes through
    finalize before the agent ends its turn (2026-10-07)."""

    RUN = "2026-10-07T10-00-00_ab12"

    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        from protocol_fixture import PID

        self.root = _repo(False)
        self.area = self.root / "experiments" / "01-x"
        d = self.area / "runs" / self.RUN
        d.mkdir(parents=True)
        block = promises.parse_block((self.area / "PROTOCOL-x.md").read_text())
        assert block is not None
        (d / "config.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                    "promises": promises.snapshot(block, self.area),
                }
            )
        )
        (d / "metrics.json").write_text(
            json.dumps({"c1_pass": True, "a1_pass": True, "a2_pass": True})
        )
        (d / "completion.json").write_text(json.dumps({"schema_version": 2}))

    def _answer(self, run_id: str) -> None:
        p = self.area / "PROTOCOL-x.md"
        p.write_text(
            p.read_text() + f"- **Answer to the question:** p = .01 ({run_id})\n"
        )

    def _stop(self, active: bool = False) -> tuple[int, str, str]:
        return _run(
            claude_hooks.stop,
            {"session_id": "s1", "cwd": str(self.root), "stop_hook_active": active},
        )

    def test_a_blocker_sends_the_agent_back(self):
        self._answer("2026-10-01T09-00-00_ffff")
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("but the run that answers is", err)

    def test_a_correct_answer_lets_it_stop(self):
        """Twin of the case above: the answer cites the run that answers."""
        self._answer(self.RUN)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_sent_back_once_already_no_loop(self):
        self._answer("2026-10-01T09-00-00_ffff")
        rc, _, _ = self._stop(active=True)
        self.assertEqual(rc, 0)

    def test_nothing_written_back_is_silent(self):
        rc, out, err = self._stop()
        self.assertEqual((rc, out, err), (0, "", ""))
