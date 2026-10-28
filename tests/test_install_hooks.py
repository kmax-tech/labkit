"""labkit-hooks: the hooks come with the pinned labkit (2026-10-07)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from labkit.gates import install_hooks


def git_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


class Install(unittest.TestCase):
    def test_install_then_check_is_clean_and_idempotent(self):
        repo = git_repo()
        self.assertTrue(install_hooks.check(repo))  # nothing installed yet
        install_hooks.install(repo)
        self.assertEqual(install_hooks.check(repo), [])
        again = install_hooks.install(repo)
        self.assertEqual(again, ["git core.hooksPath = .githooks"])  # nothing rewritten
        hook = repo / ".githooks" / "pre-commit"
        self.assertTrue(hook.stat().st_mode & 0o100)
        self.assertIn("report-check --if-reported", hook.read_text())
        merge_hook = repo / ".githooks" / "pre-merge-commit"
        self.assertTrue(merge_hook.stat().st_mode & 0o100)
        self.assertIn(".githooks/pre-commit && exit 0", merge_hook.read_text())
        self.assertIn("labkit-init numbers --staged", hook.read_text())
        merge_hook.unlink()
        self.assertEqual(
            install_hooks.check(repo), [".githooks/pre-merge-commit is missing"]
        )

    def test_foreign_hooks_and_keys_are_kept(self):
        repo = git_repo()
        (repo / ".claude").mkdir()
        foreign = {
            "model": "x",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Edit",
                        "hooks": [{"type": "command", "command": "my-linter"}],
                    }
                ]
            },
        }
        (repo / ".claude" / "settings.json").write_text(json.dumps(foreign))
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        self.assertEqual(s["model"], "x")
        commands = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertIn("my-linter", commands)
        self.assertTrue(any('claude-hook" pre-run' in c for c in commands))
        self.assertTrue(
            any(
                'claude-hook" stop' in h["command"]
                for e in s["hooks"]["Stop"]
                for h in e["hooks"]
            )
        )

    def test_a_foreign_hook_sharing_an_entry_with_ours_is_kept(self):
        repo = git_repo()
        (repo / ".claude").mkdir()
        old = {"type": "command", "command": ".venv/bin/claude-hook pre-run"}
        mine = {"type": "command", "command": "my-linter"}
        shared = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [old, mine]}]}}
        (repo / ".claude" / "settings.json").write_text(json.dumps(shared))
        self.assertEqual(
            install_hooks.stale_entries(shared),
            ["PreToolUse: .venv/bin/claude-hook pre-run"],
        )  # the foreign command is not named stale
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        entries = s["hooks"]["PreToolUse"]
        self.assertIn({"matcher": "Bash", "hooks": [mine]}, entries)
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertNotIn(old["command"], commands)

    def test_an_older_hook_is_reported_and_replaced(self):
        repo = git_repo()
        install_hooks.install(repo)
        hook = repo / ".githooks" / "pre-commit"
        hook.write_text("#!/bin/sh\n# installed by labkit-hooks 0.40.0 — reinstall\n")
        gaps = install_hooks.check(repo)
        self.assertTrue(any("is from labkit 0.40.0" in g for g in gaps), gaps)
        install_hooks.install(repo)
        self.assertEqual(install_hooks.check(repo), [])

    def test_unset_hooks_path_is_reported(self):
        repo = git_repo()
        install_hooks.install(repo)
        subprocess.run(
            ["git", "config", "--unset", "core.hooksPath"], cwd=repo, check=True
        )
        self.assertTrue(any("never runs" in g for g in install_hooks.check(repo)))

    def test_a_foreign_command_with_a_labkit_name_inside_is_not_ours(self):
        """`./bin/my-protocol-checker` matched `protocol-check` as a substring
        and was erased by an install (audit 2026-10-15)."""
        ours = lambda cmd: install_hooks._ours({"command": cmd})  # noqa: E731
        self.assertFalse(ours("./bin/my-protocol-checker"))
        self.assertFalse(ours("echo claude-hooks-are-great"))
        self.assertTrue(
            ours('"${CLAUDE_PROJECT_DIR:-.}/.venv/bin/protocol-check" "$f"')
        )
        self.assertTrue(ours("notes-check notes/"))
        self.assertTrue(ours("x; claude-hook stop"))

    def test_a_leftover_protocol_check_hook_is_named_and_replaced(self):
        # uniagent 2026-10-10: a jq one-liner from an earlier labkit ran
        # protocol-check on every PROTOCOL write beside post-change — every
        # report twice, and `check` said the settings were fine
        repo = git_repo()
        (repo / ".claude").mkdir()
        jq = (
            "f=$(jq -r '.tool_input.file_path // empty'); case \"${f##*/}\" in "
            'PROTOCOL-*.md) "${CLAUDE_PROJECT_DIR:-.}/.venv/bin/protocol-check" "$f";; esac'
        )
        old = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [{"type": "command", "command": jq}],
                    }
                ],
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": "notes-check notes/"}]}
                ],
            }
        }
        (repo / ".claude" / "settings.json").write_text(json.dumps(old))
        report = install_hooks.check(repo)
        self.assertTrue(
            any(
                "a hook from an earlier labkit — PostToolUse: f=$(jq" in r
                for r in report
            ),
            report,
        )
        self.assertTrue(any("UserPromptSubmit: notes-check" in r for r in report))
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        commands = [
            h["command"] for es in s["hooks"].values() for e in es for h in e["hooks"]
        ]
        self.assertFalse(any("jq" in c or "notes-check notes/" in c for c in commands))
        self.assertNotIn("UserPromptSubmit", s["hooks"])
        self.assertEqual(install_hooks.stale_entries(s), [])

    def test_an_old_claude_hook_entry_is_replaced_not_doubled(self):
        repo = git_repo()
        (repo / ".claude").mkdir()
        old = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": '".venv/bin/claude-hook" pre-run',
                            }
                        ],
                    }
                ]
            }
        }
        (repo / ".claude" / "settings.json").write_text(json.dumps(old))
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        self.assertEqual(len(s["hooks"]["PreToolUse"]), 1)


class RepoOwnSteps(unittest.TestCase):
    """A repo's own pre-commit steps survive an install (uniagent, 2026-10-07:
    a replay test of its runs lived in the hook and would have been erased)."""

    def test_a_foreign_hook_is_kept_beside_not_erased(self):
        repo = git_repo()
        hook = repo / ".githooks" / "pre-commit"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\npytest tests/test_replay_runs.py\n")
        done = install_hooks.install(repo)
        kept = repo / ".githooks" / "pre-commit.before-labkit"
        self.assertIn("test_replay_runs", kept.read_text())
        self.assertTrue(any("pre-commit.local" in d for d in done), done)

    def test_a_second_foreign_hook_refuses_instead_of_overwriting(self):
        repo = git_repo()
        hook = repo / ".githooks" / "pre-commit"
        hook.parent.mkdir()
        hook.write_text("#!/bin/sh\necho one\n")
        install_hooks.install(repo)
        hook.write_text("#!/bin/sh\necho two\n")
        with self.assertRaises(SystemExit):
            install_hooks.install(repo)

    def test_the_pre_commit_hands_report_check_every_staged_path(self):
        """Not only the staged protocols: a script staged under a reported
        number reopens it (audit 2026-10-19). A shim records the call."""
        repo = git_repo()
        install_hooks.install(repo)
        gate_shims(repo)
        (repo / "scripts").mkdir()
        (repo / "scripts" / "02_analyze.py").write_text("print('x')\n")
        subprocess.run(["git", "-C", str(repo), "add", "scripts"], check=True)
        r = commit(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(
            (repo / "report-check.argv").read_text().split(),
            ["--if-reported", "--staged", "scripts/02_analyze.py"],
        )

    def test_a_staged_deletion_reaches_both_gates(self):
        """Deleting the measure script under a reported number reopens it as
        an edit does; until now --diff-filter=ACMR dropped it."""
        repo = git_repo()
        (repo / "scripts").mkdir()
        (repo / "scripts" / "01_measure.py").write_text("print('x')\n")
        subprocess.run(["git", "-C", str(repo), "add", "scripts"], check=True)
        self.assertEqual(commit(repo).returncode, 0)  # no hook yet
        install_hooks.install(repo)
        gate_shims(repo)
        subprocess.run(
            ["git", "-C", str(repo), "rm", "-q", "scripts/01_measure.py"], check=True
        )
        r = commit(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for tool in ("report-check", "claude-hook"):
            self.assertIn(
                "scripts/01_measure.py", (repo / f"{tool}.argv").read_text(), tool
            )

    def test_a_missing_gate_tool_refuses_the_commit_by_name(self):
        repo = git_repo()
        install_hooks.install(repo)
        gate_shims(repo)
        (repo / ".venv" / "bin" / "claude-hook").unlink()
        (repo / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
        r = commit(repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(".venv/bin/claude-hook missing", r.stdout + r.stderr)

    def test_the_local_hook_runs_and_its_failure_blocks_the_commit(self):
        repo = git_repo()
        install_hooks.install(repo)
        gate_shims(repo)
        local = repo / ".githooks" / "pre-commit.local"
        local.write_text("#!/bin/sh\necho local-ran\nexit 1\n")
        local.chmod(0o755)
        (repo / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
        r = commit(repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("local-ran", r.stdout + r.stderr)
        local.write_text("#!/bin/sh\nexit 0\n")
        r = commit(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class AreaNumbers(unittest.TestCase):
    """Two branches each stamped their next area as 12 (labkit-paper,
    2026-10-27). git completes a merge without conflicts on its own and
    runs pre-merge-commit for it, never pre-commit."""

    def setUp(self):
        self.repo = git_repo()
        install_hooks.install(self.repo)
        gate_shims(self.repo)
        numbers_shim(self.repo)
        self.add_area("11-base")
        self.assertEqual(commit(self.repo).returncode, 0)
        self.main = run_git(self.repo, "branch", "--show-current").stdout.strip()

    def add_area(self, name: str) -> None:
        area = self.repo / "experiments" / name
        area.mkdir(parents=True)
        (area / "README.md").write_text(f"# {name}\n")
        run_git(self.repo, "add", "experiments")

    def diverge(self, on_side: str, on_main: str) -> None:
        run_git(self.repo, "checkout", "-qb", "side")
        self.add_area(on_side)
        self.assertEqual(commit(self.repo).returncode, 0)
        run_git(self.repo, "checkout", "-q", self.main)
        self.add_area(on_main)
        self.assertEqual(commit(self.repo).returncode, 0)

    def test_a_merge_that_brings_one_number_twice_is_refused(self):
        self.diverge("12-on-side", "12-on-main")
        r = run_git(self.repo, "merge", "--no-edit", "side", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(
            "number 12 is carried by 2 areas in the index: "
            "experiments/12-on-main, experiments/12-on-side",
            r.stdout + r.stderr,
        )
        self.assertIn("pre-commit: two areas carry one number", r.stdout + r.stderr)
        self.assertIn(
            "pre-merge-commit: the commit's checks above hold this merge",
            r.stdout + r.stderr,
        )
        # the merge is not committed, and its commit by hand meets pre-commit
        self.assertEqual(
            run_git(self.repo, "rev-list", "--count", "HEAD").stdout.strip(), "2"
        )
        r = commit(self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pre-commit: two areas carry one number", r.stdout + r.stderr)

    def test_a_merge_of_distinct_numbers_passes(self):
        self.diverge("12-on-side", "13-on-main")
        r = run_git(self.repo, "merge", "--no-edit", "side", check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class MergeChecks(unittest.TestCase):
    """A merge without a text conflict meets the commit's checks: a number
    reported on one branch and its analysis changed on the other merged
    cleanly and nothing held it (probed 2026-10-28 on the count
    walkthrough). report-check is a stand-in here; the walkthrough probe
    ran the real one."""

    def setUp(self):
        self.repo = git_repo()
        install_hooks.install(self.repo)
        gate_shims(self.repo)
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "02_analyze.py").write_text("print('x')\n")
        run_git(self.repo, "add", "scripts")
        self.assertEqual(commit(self.repo).returncode, 0)
        self.main = run_git(self.repo, "branch", "--show-current").stdout.strip()
        run_git(self.repo, "checkout", "-qb", "side")
        (self.repo / "scripts" / "02_analyze.py").write_text("print('y')\n")
        run_git(self.repo, "add", "scripts")
        self.assertEqual(commit(self.repo).returncode, 0)
        run_git(self.repo, "checkout", "-q", self.main)
        (self.repo / "REPORT.md").write_text("# Report\n")
        run_git(self.repo, "add", "REPORT.md")
        self.assertEqual(commit(self.repo).returncode, 0)

    def test_a_clean_merge_report_check_holds_stays_uncommitted(self):
        holding = self.repo / ".venv" / "bin" / "report-check"
        holding.write_text(
            '#!/bin/sh\necho "$@" > report-check.argv\n'
            'echo "report-check: 1 blocker(s)"\nexit 1\n'
        )
        r = run_git(self.repo, "merge", "--no-edit", "side", check=False)
        self.assertNotEqual(r.returncode, 0)
        out = r.stdout + r.stderr
        self.assertIn("pre-commit: report-check reports blockers", out)
        self.assertIn(
            "pre-merge-commit: the commit's checks above hold this merge", out
        )
        self.assertIn("git merge --abort", out)
        # the merged path, as the merge stages it against the first parent
        self.assertEqual(
            (self.repo / "report-check.argv").read_text().split(),
            ["--if-reported", "--staged", "scripts/02_analyze.py"],
        )
        self.assertEqual(
            run_git(self.repo, "rev-list", "--count", "HEAD").stdout.strip(), "2"
        )
        self.assertTrue((self.repo / ".git" / "MERGE_HEAD").is_file())

    def test_a_clean_merge_the_checks_pass_is_committed(self):
        r = run_git(self.repo, "merge", "--no-edit", "side", check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(
            run_git(self.repo, "rev-list", "--count", "HEAD").stdout.strip(), "4"
        )
        self.assertIn(
            "scripts/02_analyze.py", (self.repo / "report-check.argv").read_text()
        )


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def numbers_shim(repo: Path) -> None:
    """`.venv/bin/labkit-init` running this labkit's scaffold, as the
    installed command would."""
    shim = repo / ".venv" / "bin" / "labkit-init"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -m labkit.tools.scaffold "$@"\n'
    )
    shim.chmod(0o755)


def gate_shims(repo: Path) -> None:
    """`.venv/bin/report-check` and `claude-hook` stand-ins that record their
    arguments in `<tool>.argv` and pass."""
    shim = repo / ".venv" / "bin"
    shim.mkdir(parents=True)
    for tool in ("report-check", "claude-hook"):
        (shim / tool).write_text(f'#!/bin/sh\necho "$@" > {tool}.argv\nexit 0\n')
        (shim / tool).chmod(0o755)


def commit(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        + ["commit", "-q", "-m", "x"],
        capture_output=True,
        text=True,
        cwd=repo,
    )


if __name__ == "__main__":
    unittest.main()
