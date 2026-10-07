"""Tests for claude-hook — the two Claude Code hooks (2026-10-05).

pre-run: a command that starts a run script in an area triggers preflight;
frozen + blockers blocks (exit 2), unfrozen + blockers only reports,
throwaway stages and non-run scripts pass untouched; at `cost = "seconds"`
preflight does not run and the hook only reports whether the criterion
is written (§2.A12).
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

from labkit import claude_hooks  # noqa: E402
from protocol_fixture import head  # noqa: E402

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
    return "# Experiment protocol: x\n\n" + head(frozen=frozen, cost=cost) + "\n" + BODY


RUN_SCRIPT = ('from labkit import runlog\n'
              'with runlog.run("t", {}, protocol="PROTOCOL-x.md") as r:\n'
              '    metrics = {"c1_pass": True, "a1_pass": True, "a2_pass": True}\n')


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
    return {"session_id": "s1", "cwd": str(root), "tool_name": "Bash",
            "tool_input": {"command": command}}


class PreRun(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_frozen_with_blockers_blocks(self):
        root = _repo(True)      # frozen, but no tests/ -> only a warning;
        # a missing intent id in the script is the blocker:
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8")
        rc, out, err = _run(claude_hooks.pre_run,
                            _bash(root, "python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKED", err)
        self.assertIn("preflight", err)

    def test_unfrozen_with_blockers_only_reports(self):
        root = _repo(False)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8")
        rc, out, err = _run(claude_hooks.pre_run,
                            _bash(root, "python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pilot", ctx)

    def test_seconds_skips_preflight_even_with_blockers(self):
        root = _repo(True, cost="seconds")
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8")
        rc, out, err = _run(claude_hooks.pre_run,
                            _bash(root, "python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("cost seconds", ctx)
        self.assertIn("registration written", ctx)
        self.assertNotIn("BLOCKED", err)

    def test_seconds_without_criterion_is_reported_not_blocked(self):
        root = _repo(False, cost="seconds")
        proto = root / "experiments/01-x/PROTOCOL-x.md"
        proto.write_text(proto.read_text(encoding="utf-8")
                         .replace("[C1] p < .05", "<the criterion>"), encoding="utf-8")
        rc, out, err = _run(claude_hooks.pre_run,
                            _bash(root, "python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("placeholder", ctx)
        self.assertIn("runlog refuses", ctx)

    def test_throwaway_stage_passes_silently(self):
        root = _repo(True)
        for flag in ("--probe 3", "--show 2", "--eval-only"):
            rc, out, err = _run(claude_hooks.pre_run, _bash(
                root, f"python experiments/01-x/scripts/01_measure.py {flag}"))
            self.assertEqual((rc, out, err), (0, "", ""), flag)

    def test_script_without_run_passes_silently(self):
        root = _repo(True, script="print('analysis only')\n")
        rc, out, err = _run(claude_hooks.pre_run,
                            _bash(root, "python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_skip_token_is_reported_not_blocked(self):
        root = _repo(True)
        rc, out, err = _run(claude_hooks.pre_run, _bash(
            root, "LABKIT_PREFLIGHT=skip python experiments/01-x/scripts/01_measure.py"))
        self.assertEqual(rc, 0)
        self.assertIn("skipped", out)

    def test_relative_to_cwd_inside_area(self):
        # unfrozen: the fixture's should-gaps stay warnings (graduation
        # gate), so this test sees only the path resolution
        root = _repo(False)
        ev = _bash(root / "experiments/01-x", "python scripts/01_measure.py")
        rc, out, err = _run(claude_hooks.pre_run, ev)
        self.assertEqual(rc, 0, err)
        self.assertIn("preflight 01-x", json.loads(out)["hookSpecificOutput"]["additionalContext"])


class PostChange(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = _repo(False)
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)

    def tearDown(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_protocol_written_by_heredoc_is_checked(self):
        p = self.root / "experiments/01-x/PROTOCOL-x.md"
        p.write_text(_protocol(False).replace(
            "- **Null condition / anchors (in the same run):** [A2] shuffled labels "
            "stay at chance\n", ""), encoding="utf-8")
        rc, out, err = _run(claude_hooks.post_change,
                            _bash(self.root, "cat > PROTOCOL-x.md <<EOF ... EOF"))
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
        (self.root / "notes/messung/00-index.md").write_text("# index\n", encoding="utf-8")
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
