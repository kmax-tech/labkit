"""Tests for claude-hook — the two Claude Code hooks (2026-10-05).

pre-run: a command that starts a run script in an area triggers preflight;
frozen + blockers blocks (exit 2), unfrozen + blockers only reports,
throwaway stages and non-run scripts pass untouched; at `cost = "seconds"`
preflight does not run and the hook only reports whether the criterion
is written (LAB-015 Preflight audit before freezing).
post-change: changed protocols and messung notes are checked whatever
tool wrote them (git status, not the tool name), once per content.
"""

from __future__ import annotations

from labkit.formats.runs import RunKind

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

from labkit.gates import claude_hooks  # noqa: E402
from labkit.tools import protocol_fill  # noqa: E402
from labkit.checks import result_render  # noqa: E402
from labkit.checks import audit_binding  # noqa: E402
from labkit.formats import findings, promises, scope_sha, shell  # noqa: E402
from protocol_fixture import run_record, DEFAULT_BLOCK, PID, head, head_commit  # noqa: E402

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
        + head(frozen=frozen, cost=cost, kind="fit", promises=DEFAULT_BLOCK)
        + "\n"
        + BODY
    )


RUN_SCRIPT = (
    "from labkit.run import runlog\n"
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
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            claude_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKED", err)
        self.assertIn("preflight", err)

    def test_a_cd_or_a_compound_line_does_not_pass_the_gate(self):
        """`cd AREA && python scripts/01_measure.py` resolved the script
        against the event's cwd and found nothing; one `--probe` anywhere in
        a line freed every command in it (audit 2026-10-15)."""
        root = _repo(True)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        full = "python experiments/01-x/scripts/01_measure.py"
        for cmd in (
            "cd experiments/01-x && python scripts/01_measure.py",
            "cd experiments/01-x; python scripts/01_measure.py",
            f"{full} && {full} --probe",
            f"{full} --probe 3\n{full}",
            f"{full} --show 2 | head; {full}",
        ):
            rc, out, err = _run(claude_hooks.pre_run, _bash(root, cmd))
            self.assertEqual(rc, 2, cmd)
            self.assertIn("BLOCKED", err, cmd)
        # the twin: a throwaway stage alone, before or after a cd, is free
        for cmd in (
            "cd experiments/01-x && python scripts/01_measure.py --probe 3",
            f"{full} --show 2 | head",
        ):
            rc, out, err = _run(claude_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)

    def test_command_segments(self):
        self.assertEqual(
            shell.segments("cd a && python x.py; python y.py | head\nz.py"),
            [["cd", "a"], ["python", "x.py"], ["python", "y.py"], ["head"], ["z.py"]],
        )

    def test_a_script_inside_a_heredoc_or_a_quote_is_no_run(self):
        """The hook read a heredoc's body and a quoted `;` as shell: writing a
        file that mentions the measure script, or a `-c` string, was gated
        as running it. The twin: the same script run is held."""
        root = _repo(False)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        script = "python experiments/01-x/scripts/01_measure.py"
        for cmd in (
            f"cat > notes.md <<'EOF'\n{script}\nEOF",
            f"python -c 'print(1); {script}'",
        ):
            rc, out, err = _run(claude_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)
        _, out, _ = _run(claude_hooks.pre_run, _bash(root, script))
        self.assertNotEqual(out, "")

    def test_unfrozen_with_blockers_only_reports(self):
        root = _repo(False)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
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
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
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

    def test_seconds_without_question_is_reported_not_blocked(self):
        root = _repo(False, cost="seconds")
        proto = root / "experiments/01-x/PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "does it hold?", "<the question>"
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

        def executed(cmd: str) -> list[str]:
            return [
                p for seg in shell.segments(cmd) for p in claude_hooks.executed_py(seg)
            ]

        for cmd, want in runs.items():
            self.assertEqual(executed(cmd), want, cmd)
        for cmd in (
            "sed -n 1,5p x.py",
            "cat x.py",
            "ls -l x.py",
            "git add x.py",
            """echo 'p = Path("x.py")'""",
            "python -c 'import x'",
            "pytest tests/test_x.py -q",
        ):
            self.assertEqual(executed(cmd), [], cmd)

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

    def test_a_note_with_an_umlaut_in_its_name_is_checked(self):
        """`git status --porcelain` quotes such a name with octal escapes;
        the path then was no file and the note was never checked (audit
        2026-10-15)."""
        note = self.root / "notes/messung/2026-10-05-größe.md"
        note.write_text("# x\n\nno kind line\n", encoding="utf-8")
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        rc, out, _ = _run(claude_hooks.post_change, ev)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("größe.md", ctx)

    def test_wants_check_takes_any_notes_messung_pair(self):
        self.assertEqual(
            claude_hooks.wants_check(Path("/home/u/notes/lab/notes/messung/a.md")),
            "note",
        )
        self.assertIsNone(
            claude_hooks.wants_check(Path("/home/u/notes/x/messung/a.md"))
        )

    def test_sessions_run_without_a_value_is_a_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = claude_hooks.sessions(["--run"])
        self.assertEqual(rc, 2)
        self.assertEqual(out.getvalue(), "")  # a refusal, not a finding
        self.assertIn("needs a RUN_ID", err.getvalue())

    def test_nothing_changed_is_silent(self):
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        self.assertEqual(_run(claude_hooks.post_change, ev), (0, "", ""))


if __name__ == "__main__":
    unittest.main()


class Stop(unittest.TestCase):
    """`claude-hook stop`: a number written back in this session goes through
    report-check before the agent ends its turn (finalize until 0.99.0; the
    whole release check since — third haiku round: t3 and t5 reported a
    probe's number and no agent ever called report-check). The area is at
    seconds, where the hook's rule is the same and no freeze is owed."""

    RUN = "2026-10-07T10-00-00_ab12"

    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = _repo(False, cost="seconds")
        self.area = self.root / "experiments" / "01-x"
        (self.area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        # at seconds finalize holds the provenance: the source tracked in git
        (self.root / "data").mkdir()
        (self.root / "data" / "cases.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "analyze and data")
        self._run_dir(run_kind="measurement")

    def _run_dir(self, run_kind: RunKind) -> None:
        """The area's one completed run, a full run or a probe, with a decided
        analysis record of it (what report-check owes beyond the run itself)."""
        d = self.area / "runs" / self.RUN
        d.mkdir(parents=True, exist_ok=True)
        text = (self.area / "PROTOCOL-x.md").read_text()
        block = promises.parse_block(text)
        assert block is not None
        (d / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 3,
                        "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                        "promises": promises.snapshot(block, self.area),
                        "run_kind": run_kind,
                        "git": head_commit(self.root),
                        "data": {
                            "cases": {"path": "data/cases.jsonl", "sha": "x", "rows": 1}
                        },
                    }
                )
            )
        )
        (d / "metrics.json").write_text(
            json.dumps({"c1_pass": True, "a1_pass": True, "a2_pass": True})
        )
        (d / "completion.json").write_text(
            json.dumps({"schema_version": 3, "run_kind": "measurement"})
        )
        if not (self.area / "audits").is_dir():
            findings.write(
                self.area,
                "analysis",
                "opus",
                scope_sha.area_stamp(self.area)[0],
                promises.block_stamp(text),
                (0, 0, 0),
                [],
                run_id=self.RUN,
                shown_sha=audit_binding.run_shown(
                    self.area, self.area / "runs" / self.RUN, ""
                ).sha,
            )

    def _answer(self, run_id: str) -> None:
        """Declare RUN_ID in the head and write the Answer, as --from-run does."""
        p = self.area / "PROTOCOL-x.md"
        p.write_text(
            protocol_fill.fill_result_run(p.read_text(), run_id)
            + "- **Recorded results:** "
            + result_render.recorded_results_line(
                {"c1_pass": True, "a1_pass": True, "a2_pass": True}, run_id
            )
            + "\n"
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
        self.assertIn("report-check reports blockers", err)
        self.assertIn("but the run that answers is", err)

    def test_a_correct_answer_lets_it_stop(self):
        """Twin of the case above: the head declares the run that answers, a
        full run with its analysis record, and the check passes."""
        self._answer(self.RUN)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_a_script_changed_under_a_reported_number_is_sent_back(self):
        """The answer committed, then a script edited: the protocol is not
        among the changed files, and the stop hook let it pass (audit
        2026-10-19)."""
        self._answer(self.RUN)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the answer")
        rc, out, err = self._stop()
        self.assertEqual((rc, out, err), (0, "", ""))  # nothing changed
        (self.area / "scripts" / "02_analyze.py").write_text(
            "print('changed')\n", encoding="utf-8"
        )
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("no analysis audit saw the area as it is now", err)

    def test_a_probes_number_written_back_is_sent_back(self):
        """Third haiku round (t3, t5): measured with run_kind='probe', reported."""
        self._run_dir(run_kind="probe")
        self._answer(self.RUN)
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("a probe (run_kind='probe'), not a measurement", err)

    def test_an_exploration_over_a_probe_may_end(self):
        """The twin that must stay: the protocol changed, a probe in runs/,
        the answer still open — no reported result, nothing owed."""
        self._run_dir(run_kind="probe")
        p = self.area / "PROTOCOL-x.md"
        p.write_text(p.read_text() + "- **Deviations after freeze:** none\n")
        rc, out, err = self._stop()
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_sent_back_once_already_no_loop(self):
        self._answer("2026-10-01T09-00-00_ffff")
        rc, _, _ = self._stop(active=True)
        self.assertEqual(rc, 0)

    def test_nothing_written_back_is_silent(self):
        rc, out, err = self._stop()
        self.assertEqual((rc, out, err), (0, "", ""))
