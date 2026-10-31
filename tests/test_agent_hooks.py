"""Tests for claude-hook — the two Claude Code hooks (2026-10-05).

pre-run: a command that starts a run script in an area triggers preflight;
frozen + blockers blocks (exit 2), unfrozen + blockers only reports,
throwaway stages and non-run scripts pass untouched; at `repeat_cost = "low"`
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
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import report_blocks  # noqa: E402
from labkit.gates import agent_hooks  # noqa: E402
from labkit.tools import protocol_result
from labkit.formats import findings, promises, repo, scope_sha, shell  # noqa: E402
from protocol_fixture import (
    registration_of,
    run_record,
    DEFAULT_BLOCK,
    PID,
    head,
    head_commit,
    scope_file,
    script_sha_of,
    shown_sha,
)  # noqa: E402

BODY = """\
- **Terms of this protocol:** n/a — standard vocabulary
- **Question / hypothesis:** does it hold?
- **Inference criterion:** [criterion-1] p < .05
- **Quality check:** [quality-check-1] parse yield above 80%
- **Model I/O:** in: text · out: a label, parsed by parse()
- **Prompt (verbatim, per variant):**

  ```text
  prompt
  ```

- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels stay at chance
- **Exclusions / filters:** none
"""


def _protocol(frozen: bool, repeat_cost: str = "high") -> str:
    # every area here answers from a full run, so it carries the tables (0.19)
    return (
        "# Experiment protocol: x\n\n"
        + head(
            frozen=frozen, repeat_cost=repeat_cost, kind="fit", promises=DEFAULT_BLOCK
        )
        + "\n"
        + BODY
    )


RUN_SCRIPT = (
    "from labkit.run import runlog\n"
    'with runlog.run("t", {}, protocol="PROTOCOL-x.md") as r:\n'
    '    metrics = {"criterion_1_pass": True, "quality_check_1_pass": True, "quality_check_2_pass": True}\n'
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _repo(frozen: bool, script: str = RUN_SCRIPT, repeat_cost: str = "high") -> Path:
    root = Path(tempfile.mkdtemp())
    area = root / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "PROTOCOL-x.md").write_text(
        _protocol(frozen, repeat_cost), encoding="utf-8"
    )
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    (root / "notes" / "messung").mkdir(parents=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


@contextlib.contextmanager
def _dated(seconds_ago: int):
    """Commits made inside are dated SECONDS_AGO before now (committer and
    author): a fixture committed before the session began."""
    stamp = f"@{int(time.time()) - seconds_ago} +0000"
    with mock.patch.dict(
        os.environ, {"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp}
    ):
        yield


def _transcript(start: datetime | None = None) -> Path:
    """A transcript outside every repository whose first record is dated
    START (now): where Claude Code's session began."""
    when = (start or datetime.now(timezone.utc)).astimezone(timezone.utc)
    path = Path(tempfile.mkdtemp()) / "session.jsonl"
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"
    path.write_text(
        json.dumps({"type": "user", "timestamp": stamp}) + "\n", encoding="utf-8"
    )
    return path


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
            agent_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKED", err)
        self.assertIn("preflight", err)

    def test_a_session_started_below_the_area_finds_it(self):
        """Claude Code started in `<area>/scripts`: the walk to the area
        ended at the project directory, and the run read as unbound. The
        twin: a throwaway stage from there stays free."""
        root = _repo(True)
        scripts = root / "experiments/01-x/scripts"
        (scripts / "01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        os.environ["CLAUDE_PROJECT_DIR"] = str(scripts)
        try:
            rc, _, err = _run(
                agent_hooks.pre_run, _bash(scripts, "python 01_measure.py")
            )
            self.assertEqual(rc, 2, err)
            self.assertIn("BLOCKED", err)
            rc, out, err = _run(
                agent_hooks.pre_run, _bash(scripts, "python 01_measure.py --probe 3")
            )
            self.assertEqual((rc, out, err), (0, "", ""))
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)

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
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual(rc, 2, cmd)
            self.assertIn("BLOCKED", err, cmd)
        # the twin: a throwaway stage alone, before or after a cd, is free
        for cmd in (
            "cd experiments/01-x && python scripts/01_measure.py --probe 3",
            f"{full} --show 2 | head",
        ):
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
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
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)
        _, out, _ = _run(agent_hooks.pre_run, _bash(root, script))
        self.assertNotEqual(out, "")

    def test_unfrozen_with_blockers_only_reports(self):
        root = _repo(False)
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            agent_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pilot", ctx)

    def test_without_a_blocker_the_warnings_reach_the_context(self):
        """On exit 0 the hook gave the summary's one line — "0 blockers, N
        warning(s) — review the warnings above" with nothing above — and
        an agent froze on the false "0 blockers" with its audit's finding
        still open (SAB task 71, 2026-10-29). The warnings come with the
        summary, the open finding among them; a blocker's note is as before."""
        from test_preflight import CLEAN_PROTOCOL

        root = _repo(False)
        area = root / "experiments/01-x"
        (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL, encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "clean")
        findings.write(
            area,
            "preflight",
            "opus",
            "0123456789ab",
            promises.block_stamp(CLEAN_PROTOCOL),
            (0, 1, 0),
            [
                (
                    "WARNING",
                    "WARNING · scripts/01_measure.py:9 · the seed is not recorded",
                )
            ],
            registration=registration_of(area),
        )
        rc, out, err = _run(
            agent_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual((rc, err), (0, ""))
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        lines = ctx.splitlines()
        self.assertEqual(lines[0], "preflight 01-x --protocol PROTOCOL-x.md:")
        undecided = [ln for ln in lines if ln.startswith("  WARNING: undecided in ")]
        self.assertEqual(len(undecided), 1, ctx)
        self.assertIn("the seed is not recorded", undecided[0])
        self.assertIn("--decide", undecided[0])  # the way out comes with it
        summary = lines[-1]
        self.assertTrue(summary.startswith("preflight: 0 blockers, "), summary)
        self.assertEqual(
            len(lines), 2 + sum(ln.startswith("  WARNING") for ln in lines)
        )

    def test_low_skips_preflight_even_with_blockers(self):
        root = _repo(True, repeat_cost="low")
        (root / "experiments/01-x/scripts/01_measure.py").write_text(
            'from labkit.run import runlog\nwith runlog.run("t", {}) as r:\n    pass\n',
            encoding="utf-8",
        )
        rc, out, err = _run(
            agent_hooks.pre_run,
            _bash(root, "python experiments/01-x/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("repeat cost low", ctx)
        self.assertIn("registration written", ctx)
        self.assertNotIn("BLOCKED", err)

    def test_low_without_question_is_reported_not_blocked(self):
        root = _repo(False, repeat_cost="low")
        proto = root / "experiments/01-x/PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                "does it hold?", "<the question>"
            ),
            encoding="utf-8",
        )
        rc, out, err = _run(
            agent_hooks.pre_run,
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
                agent_hooks.pre_run,
                _bash(root, f"python experiments/01-x/scripts/01_measure.py {flag}"),
            )
            self.assertEqual((rc, out, err), (0, "", ""), flag)

    def test_every_stamped_no_run_stage_passes_and_the_runs_stay_gated(self):
        """The stamped producer documents `00_prepare.py --audit` as "no
        write", and the estimator's `--calibrate-null` as "No run, nothing
        written"; the hook knew only --show, --probe and --eval-only and
        blocked `--audit` on a frozen protocol with blockers (labkit-paper
        area 15, round 2, t15, D7). The twins: the producer's and the
        measurement's own runs stay blocked."""
        from labkit.tools import scaffold

        root = Path(tempfile.mkdtemp())
        with contextlib.redirect_stdout(io.StringIO()):
            scaffold.stamp_lab(root, "lab")
            scaffold.stamp_area(root, "fit", repeat_cost="high", kind="fit")
            scaffold.stamp_area(
                root, "judge", repeat_cost="high", model="haiku", kind="apply"
            )
            scaffold.stamp_area(root, "local", repeat_cost="high", kind="apply")
        _git(root, "init", "-q", ".")
        for proto in root.glob("experiments/*/PROTOCOL-*.md"):
            text = proto.read_text(encoding="utf-8")
            self.assertEqual(text.count("frozen = false"), 1, proto)
            proto.write_text(text.replace("frozen = false", "frozen = true"))
        python = "python experiments"
        for cmd in (
            f"{python}/01-fit/scripts/00_prepare.py",
            f"{python}/02-judge/scripts/00_prepare.py",
            f"{python}/03-local/scripts/01_measure.py",
        ):
            rc, _, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual(rc, 2, cmd)
            self.assertIn("BLOCKED", err)
        for cmd in (
            f"{python}/01-fit/scripts/00_prepare.py --audit",
            f"{python}/01-fit/scripts/00_prepare.py --show",
            f"{python}/02-judge/scripts/00_prepare.py --audit",
            f"{python}/03-local/scripts/01_measure.py --calibrate-null",
            f"{python}/03-local/scripts/01_measure.py --calibrate-null 50",
        ):
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)

    def test_script_without_run_passes_silently(self):
        root = _repo(True, script="print('analysis only')\n")
        rc, out, err = _run(
            agent_hooks.pre_run,
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
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)
        # the twin: running the same file is seen
        rc, out, _ = _run(agent_hooks.pre_run, _bash(root, "python lib/opens.py"))
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
                p for seg in shell.segments(cmd) for p in agent_hooks.executed_py(seg)
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
            agent_hooks.pre_run,
            _bash(
                root,
                "LABKIT_PREFLIGHT=skip python experiments/01-x/scripts/01_measure.py",
            ),
        )
        self.assertEqual(rc, 0)
        self.assertIn("skipped", out)

    def test_the_prompt_skeleton_is_a_run_start(self):
        """The prompt skeleton opens its run inside `lanes.Lanes.main`
        (`run/lanes.py`): its own text names no `runlog.run(`, and the hook
        let every LLM measurement pass without preflight (audit 2026-10-27,
        criterion-5). Its full run, a repeat and a run under another model get
        preflight — frozen with blockers is held, unfrozen only told; its
        throwaway stages and its analysis stay free; the compute skeleton
        keeps its gate."""
        from labkit.tools import scaffold

        root = Path(tempfile.mkdtemp()) / "lab"
        with contextlib.redirect_stdout(io.StringIO()):
            scaffold.stamp_lab(root, "lab")
            scaffold.stamp_area(root, "judge", model="haiku", kind="apply")
            scaffold.stamp_area(root, "count", "low", kind="compute")
        _git(root, "init", "-q", ".")
        measure = "python experiments/01-judge/scripts/01_measure.py"
        head = "preflight 01-judge --protocol PROTOCOL-judge.md"  # the script names it
        for cmd in (
            measure,
            f"{measure} --repeat-of 2026-01-01T00-00-00_0001",
            f"{measure} --model sonnet",
        ):
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual(rc, 0, cmd)
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            self.assertIn(f"{head}: blockers, protocol not frozen", ctx)
        for cmd in (
            f"{measure} --show 3",
            f"{measure} --probe 2",
            f"{measure} --eval-only",
            "python experiments/01-judge/scripts/02_analyze.py --check",
        ):
            rc, out, err = _run(agent_hooks.pre_run, _bash(root, cmd))
            self.assertEqual((rc, out, err), (0, "", ""), cmd)
        proto = root / "experiments/01-judge/PROTOCOL-judge.md"
        text = proto.read_text(encoding="utf-8")
        self.assertEqual(text.count("frozen = false"), 1)
        proto.write_text(text.replace("frozen = false", "frozen = true"))
        rc, out, err = _run(agent_hooks.pre_run, _bash(root, measure))
        self.assertEqual(rc, 2)
        self.assertIn(f"{head}: BLOCKED", err)
        rc, out, err = _run(
            agent_hooks.pre_run,
            _bash(root, "python experiments/02-count/scripts/01_measure.py"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(
            "preflight 02-count --protocol PROTOCOL-count.md: repeat cost low", ctx
        )

    def test_relative_to_cwd_inside_area(self):
        # unfrozen: the fixture's should-gaps stay warnings (graduation
        # gate), so this test sees only the path resolution
        root = _repo(False)
        ev = _bash(root / "experiments/01-x", "python scripts/01_measure.py")
        rc, out, err = _run(agent_hooks.pre_run, ev)
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
                "- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels "
                "stay at chance\n",
                "",
            ),
            encoding="utf-8",
        )
        rc, out, err = _run(
            agent_hooks.post_change,
            _bash(self.root, "cat > PROTOCOL-x.md <<EOF ... EOF"),
        )
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("PROTOCOL-x.md", ctx)
        self.assertIn("MISSING (must): Null condition / anchors", ctx)

    def test_a_session_started_in_a_subdirectory_checks_the_repo(self):
        """The project directory below the repo root has no `.git` of its
        own: git status was never read, and a protocol written by a heredoc
        went unchecked. The twin: nothing changed, nothing said."""
        sub = self.root / "experiments"
        os.environ["CLAUDE_PROJECT_DIR"] = str(sub)
        ev = _bash(sub, "cat > 01-x/PROTOCOL-x.md <<EOF ... EOF")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        self.assertEqual(_run(agent_hooks.post_change, ev), (0, "", ""))
        p = self.root / "experiments/01-x/PROTOCOL-x.md"
        p.write_text(
            _protocol(False).replace(
                "- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels "
                "stay at chance\n",
                "",
            ),
            encoding="utf-8",
        )
        rc, out, _ = _run(agent_hooks.post_change, ev)
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("experiments/01-x/PROTOCOL-x.md", ctx)
        self.assertIn("MISSING (must): Null condition / anchors", ctx)
        # the checker ran from the repo root on the relative path: no line
        # names the file absolutely (audit 2026-10-27, third, M4)
        self.assertNotIn(str(self.root.resolve()), ctx)
        self.assertNotIn(str(self.root), ctx)

    def test_same_content_is_reported_once_per_session(self):
        p = self.root / "experiments/01-x/PROTOCOL-x.md"
        p.write_text(_protocol(False) + "\nmore\n", encoding="utf-8")
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        rc, out1, _ = _run(agent_hooks.post_change, ev)
        rc, out2, _ = _run(agent_hooks.post_change, ev)
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
        rc, out, _ = _run(agent_hooks.post_change, ev)
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
        rc, out, _ = _run(agent_hooks.post_change, ev)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("größe.md", ctx)

    def test_wants_check_takes_any_notes_messung_pair(self):
        self.assertEqual(
            agent_hooks.wants_check(Path("/home/u/notes/lab/notes/messung/a.md")),
            "note",
        )
        self.assertIsNone(agent_hooks.wants_check(Path("/home/u/notes/x/messung/a.md")))

    def test_sessions_run_without_a_value_is_a_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = agent_hooks.sessions(["--run"])
        self.assertEqual(rc, 2)
        self.assertEqual(out.getvalue(), "")  # a refusal, not a finding
        self.assertIn("needs a RUN_ID", err.getvalue())

    def _marked_report(self, why: str = "audit failed") -> dict:
        run = "2026-10-25T20-57-42_9ae7"
        (self.root / "experiments/01-x/runs" / run).mkdir(parents=True)
        block = "\n".join(
            report_blocks.discussion_lines("experiments/01-x/PROTOCOL-x.md", run, why)
        )
        (self.root / "REPORT.md").write_text(f"# Report\n\n{block}\n", encoding="utf-8")
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        return ev

    def test_a_report_marking_a_run_gets_the_review_command_once_per_text(self):
        """Seventh haiku round: the mark was taken and the numbers stayed;
        the review that reads them is named where the report is written."""
        ev = self._marked_report()
        rc, out1, _ = _run(agent_hooks.post_change, ev)
        self.assertEqual(rc, 0)
        ctx = json.loads(out1)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("`labkit-audit experiments/01-x --report-review REPORT.md`", ctx)
        self.assertEqual(_run(agent_hooks.post_change, ev)[1], "")  # same text
        block = "\n".join(
            report_blocks.discussion_lines(
                "experiments/01-x/PROTOCOL-x.md", "2026-10-25T20-57-42_9ae7", "other"
            )
        )
        (self.root / "REPORT.md").write_text(f"# Report\n\n{block}\n", encoding="utf-8")
        self.assertIn("--report-review", _run(agent_hooks.post_change, ev)[1])

    def test_a_report_that_is_a_link_is_told_its_refusal_where_it_is_written(self):
        """post-change resolved every path, so a REPORT.md linking to a file
        under data/ was read where it points — a skipped directory — and
        got no word, while the stop and the commit refuse it. It hears the
        refusal and its way out now. The twin: the regular report above
        gets the review command."""
        ev = self._marked_report()
        report = self.root / "REPORT.md"
        (self.root / "data").mkdir()
        target = self.root / "data" / "report.md"
        report.rename(target)
        report.symlink_to(Path("data") / "report.md")
        rc, out, _ = _run(agent_hooks.post_change, ev)
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("REPORT.md: a symbolic link to data/report.md", ctx)
        self.assertIn("rm REPORT.md && cp data/report.md REPORT.md", ctx)
        self.assertNotIn("--report-review", ctx)
        # the way out followed in the same session: the copy has the bytes
        # the link read, and the cache, keyed on them, kept the review
        # command back (cold review 2026-10-27); another hint is told
        report.unlink()
        report.write_bytes(target.read_bytes())
        rc, out, _ = _run(agent_hooks.post_change, ev)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("--report-review", ctx)

    def test_a_report_citing_a_run_unmarked_gets_no_review_command(self):
        ev = self._marked_report()
        (self.root / "REPORT.md").write_text(
            "# Report\n\nrun 2026-10-25T20-57-42_9ae7 looked at\n", encoding="utf-8"
        )
        self.assertNotIn("--report-review", _run(agent_hooks.post_change, ev)[1])

    def test_nothing_changed_is_silent(self):
        ev = _bash(self.root, "ls")
        ev["session_id"] = "s-" + os.urandom(4).hex()
        self.assertEqual(_run(agent_hooks.post_change, ev), (0, "", ""))


if __name__ == "__main__":
    unittest.main()


class Stop(unittest.TestCase):
    """`claude-hook stop`: a number written back in this session goes through
    report-check before the agent ends its turn (finalize until 0.99.0; the
    whole release check since — third haiku round: t3 and t5 reported a
    probe's number and no agent ever called report-check). The area is at
    low, where the hook's rule is the same and no freeze is owed."""

    RUN = "2026-10-07T10-00-00_ab12"

    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        with _dated(3600):  # the fixture predates the session
            self.root = _repo(False, repeat_cost="low")
            self.area = self.root / "experiments" / "01-x"
            (self.area / "scripts" / "02_analyze.py").write_text(
                "print('ok')\n", encoding="utf-8"
            )
            # at low repeat cost finalize holds the provenance: the source tracked in git
            (self.root / "data").mkdir()
            (self.root / "data" / "cases.jsonl").write_text(
                '{"id": 1}\n', encoding="utf-8"
            )
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", "analyze and data")
        self.transcript = _transcript()
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
                        "schema_version": 4,
                        "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                        "promises": promises.snapshot(block, self.area),
                        "run_kind": run_kind,
                        "script_sha": script_sha_of(scope_file(self.area)),
                        **head_commit(self.root),
                        "data": {
                            "cases": {"path": "data/cases.jsonl", "sha": "x", "rows": 1}
                        },
                    }
                )
            )
        )
        (d / "metrics.json").write_text(
            json.dumps(
                {
                    "criterion_1_pass": True,
                    "quality_check_1_pass": True,
                    "quality_check_2_pass": True,
                }
            )
        )
        (d / "completion.json").write_text(
            json.dumps({"schema_version": 4, "run_kind": "measurement"})
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
                shown_sha=shown_sha(self.area, self.area / "runs" / self.RUN),
                registration=registration_of(self.area),
            )

    def _answer(self, run_id: str) -> None:
        """Declare RUN_ID in the head and write the Answer, as --from-run does."""
        p = self.area / "PROTOCOL-x.md"
        # the line --from-run renders for the fixture's metrics (every promise
        # true, no limit); written as text, since some tests declare a run
        # that does not exist
        p.write_text(
            protocol_result.fill_result_run(p.read_text(), run_id)
            + f"- **Recorded results:** criterion-1 met; quality-check-1 met; quality-check-2 met · recorded: (run {run_id})\n"
        )

    def _stop(self, active: bool = False) -> tuple[int, str, str]:
        return _run(
            agent_hooks.stop,
            {
                "session_id": "s1",
                "cwd": str(self.root),
                "transcript_path": str(self.transcript),
                "stop_hook_active": active,
            },
        )

    def _command(self, command: str = "ls") -> tuple[int, str, str]:
        """A Bash command of the session: pre-run keeps the stop base."""
        event = _bash(self.root, command)
        event["transcript_path"] = str(self.transcript)
        return _run(agent_hooks.pre_run, event)

    def test_a_blocker_sends_the_agent_back(self):
        self._answer("2026-10-01T09-00-00_ffff")
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("report-check reports blockers", err)
        self.assertIn("which cannot answer for", err)

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
        self._command()  # the session's first command keeps the base
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

    def _base(self) -> str:
        path = agent_hooks.stop_base_file(self.root, "s1")
        assert path is not None
        return path.read_text(encoding="utf-8").strip()

    def test_a_commit_past_the_pre_commit_is_held_at_every_stop(self):
        """Eighth haiku round (t3): `git commit --no-verify` left the tree
        clean, and the stop, reading git status only, held nothing. The
        session's commits since its stop base are held; a stop sent back
        once in the turn may end, the base stays, the next turn's stop
        holds again."""
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))  # keeps the base
        base = self._base()
        self._answer("2026-10-01T09-00-00_ffff")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the answer", "--no-verify")
        rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("committed in this session", err)
        self.assertIn("which cannot answer for", err)
        rc, _, err = self._stop(active=True)
        self.assertEqual(rc, 0)
        self.assertIn("which cannot answer for", err)  # said, not dropped
        self.assertIn("sent back once in this turn", err)
        self.assertEqual(self._base(), base)
        rc, _, _ = self._stop()  # the next turn
        self.assertEqual(rc, 2)

    def test_a_bad_commit_beside_an_uncommitted_fix_keeps_the_base(self):
        """The stop reads the tree: a commit past the pre-commit with the
        wrong run declared, and the fix uncommitted, passed — and the base
        moved past the bad commit, so dropping the fix was never held. The
        base stays until a stop on a clean tree passes; the twin: the fix
        committed, the tree clean, the base moves."""
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))
        base = self._base()
        protocol = "experiments/01-x/PROTOCOL-x.md"
        self._answer("2026-10-01T09-00-00_ffff")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the wrong answer", "--no-verify")
        _git(self.root, "checkout", "HEAD~1", "--", protocol)
        _git(self.root, "reset", "-q", "--", protocol)
        self._answer(self.RUN)  # the fix, in the tree only
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._base(), base)
        _git(self.root, "checkout", "--", protocol)  # the fix dropped
        rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("which cannot answer for", err)
        self.assertEqual(self._base(), base)
        _git(self.root, "checkout", "HEAD~1", "--", protocol)
        _git(self.root, "reset", "-q", "--", protocol)
        self._answer(self.RUN)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the fix")
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._base(), repo.head_sha(self.root))

    def test_the_twin_a_correct_commit_stops_and_moves_the_base(self):
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))
        self._answer(self.RUN)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the answer")
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._base(), repo.head_sha(self.root))

    def test_a_commit_before_the_session_opens_nothing(self):
        self._answer("2026-10-01T09-00-00_ffff")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "an older answer")
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))  # the session begins
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))  # kept once, not moved
        self.assertEqual(self._base(), repo.head_sha(self.root))
        rc, out, err = self._stop()
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_a_base_that_left_the_history_is_said(self):
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))
        path = agent_hooks.stop_base_file(self.root, "s1")
        assert path is not None
        path.write_text("0" * 40 + "\n", encoding="utf-8")
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertIn("is no ancestor of HEAD and shares no commit with it", err)

    def test_a_base_removed_after_a_commit_holds_the_commits_since_the_transcript(
        self,
    ):
        """`rm -rf .git/labkit-stop-base` after a commit past the pre-commit:
        the stop checked no commit and said nothing, and the next command
        kept a new base past the bad commit. Without a base the stop says so
        and holds the commits dated since the transcript began; pre-run
        keeps no base past them. The twin: the fix committed, a clean stop
        keeps HEAD, and the next stop is silent."""
        self._command()
        path = agent_hooks.stop_base_file(self.root, "s1")
        assert path is not None
        self._answer("2026-10-01T09-00-00_ffff")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the wrong answer", "--no-verify")
        self._command("rm -rf .git/labkit-stop-base")
        path.unlink()
        rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        self.assertIn("the session has no stop base", err)
        self.assertIn("dated since the transcript began", err)
        self.assertIn("which cannot answer for", err)
        self._command()  # the next command keeps no base past the commit
        self.assertFalse(path.exists())
        self.assertEqual(self._stop()[0], 2)
        protocol = "experiments/01-x/PROTOCOL-x.md"
        _git(self.root, "checkout", "HEAD~1", "--", protocol)
        _git(self.root, "reset", "-q", "--", protocol)
        self._answer(self.RUN)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the fix")
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)
        self.assertIn("the session has no stop base", err)  # said, and clean
        self.assertEqual(self._base(), repo.head_sha(self.root))
        self.assertEqual(self._stop(), (0, "", ""))

    def test_a_session_without_a_command_or_a_commit_is_silent(self):
        """No Bash command, so no base kept, and nothing committed since the
        transcript began: nothing was missed, nothing is said."""
        self.assertEqual(self._stop(), (0, "", ""))

    def test_without_a_transcript_the_missing_base_holds_and_keeps_none(self):
        """No base and no transcript start: the session's commits cannot be
        read. The stop said so, passed, and kept HEAD as its base — past the
        commits it had just not checked (cold review 2026-10-27). A check
        that cannot run is not clean: it holds, once per turn, keeps no
        base, and names the way out — the files checked by hand, then a
        Bash command keeps a base. The twin: a clean stop with its commits
        read keeps HEAD (the stops above)."""
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "a commit the stop cannot date")
        path = agent_hooks.stop_base_file(self.root, "s1")
        assert path is not None
        event = {"session_id": "s1", "cwd": str(self.root), "stop_hook_active": False}
        rc, _, err = _run(agent_hooks.stop, event)
        self.assertEqual(rc, 2, err)
        self.assertIn("no stop base and no transcript start", err)
        self.assertIn("report-check --if-reported", err)
        self.assertFalse(path.exists())
        rc, _, _ = _run(agent_hooks.stop, {**event, "stop_hook_active": True})
        self.assertEqual(rc, 0)  # once per turn
        _run(agent_hooks.pre_run, {**_bash(self.root, "ls"), "session_id": "s1"})
        self.assertTrue(path.exists())  # the way out: a Bash command keeps a base
        self.assertEqual(_run(agent_hooks.stop, event)[0], 0)

    def test_the_stop_holds_when_its_checks_outrun_its_budget(self):
        """A stop Claude Code cancels at its timeout holds nothing: the
        checks end at the stop's own budget and hold, once per turn. The
        twin is every stop above, inside the budget."""
        (self.area / "scripts" / "02_analyze.py").write_text(
            "import time\ntime.sleep(30)\n", encoding="utf-8"
        )
        self._answer(self.RUN)
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))
        base = self._base()
        began = time.monotonic()
        with mock.patch.object(agent_hooks, "STOP_BUDGET_S", 1.0):
            rc, _, err = self._stop()
            self.assertLess(time.monotonic() - began, 20)  # the child was killed
            self.assertEqual(rc, 2, err)
            self.assertIn("the checks did not end within 1 s", err)
            rc, _, err = self._stop(active=True)
        self.assertEqual(rc, 0)
        self.assertIn("did not end within", err)
        self.assertEqual(self._base(), base)

    def test_over_budget_no_process_the_checks_started_is_left(self):
        """The budget killed only the check's direct child: a process that
        child started ran on, reparented (cold review 2026-10-27). Every
        process below the hook ends."""
        pidfile = self.root / "grandchild.pid"
        (self.area / "scripts" / "02_analyze.py").write_text(
            "import pathlib, subprocess\n"
            "p = subprocess.Popen(['sleep', '41'])\n"
            f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\n"
            "p.wait()\n",
            encoding="utf-8",
        )
        self._answer(self.RUN)
        _run(agent_hooks.pre_run, _bash(self.root, "ls"))
        # 10 s, not 3: under a load of 25 the budget ran out before the
        # script had started its child, and no pid file was left to read
        # (2026-10-28); `sleep 41` still outlives any budget by far
        with mock.patch.object(agent_hooks, "STOP_BUDGET_S", 10.0):
            rc, _, err = self._stop()
        self.assertEqual(rc, 2, err)
        self.assertTrue(pidfile.is_file(), f"the check never started its child: {err}")
        pid = int(pidfile.read_text())

        def alive() -> bool:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            return True

        deadline = time.monotonic() + 5
        while alive() and time.monotonic() < deadline:
            time.sleep(0.1)
        if alive():
            os.kill(pid, signal.SIGKILL)
            self.fail(f"sleep {pid} outlived the stop's budget")

    def test_the_budget_ends_before_claude_code_cancels_the_stop(self):
        from labkit.gates import install_hooks

        _, hook = install_hooks.CLAUDE_HOOKS["Stop"]
        self.assertEqual(hook["timeout"], install_hooks.STOP_TIMEOUT_S)
        self.assertLessEqual(
            agent_hooks.STOP_BUDGET_S + 20, install_hooks.STOP_TIMEOUT_S
        )

    def test_a_session_id_that_is_no_file_name_keeps_no_base(self):
        self.assertIsNone(agent_hooks.stop_base_file(self.root, "../x"))
