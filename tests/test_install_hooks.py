"""labkit-hooks: the hooks come with the pinned labkit (2026-10-07)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from labkit import install_hooks


def git_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


class Install(unittest.TestCase):
    def test_install_then_check_is_clean_and_idempotent(self):
        repo = git_repo()
        self.assertTrue(install_hooks.check(repo))           # nothing installed yet
        install_hooks.install(repo)
        self.assertEqual(install_hooks.check(repo), [])
        again = install_hooks.install(repo)
        self.assertEqual(again, ["git core.hooksPath = .githooks"])   # nothing rewritten
        hook = repo / ".githooks" / "pre-commit"
        self.assertTrue(hook.stat().st_mode & 0o100)
        self.assertIn("finalize --if-reported", hook.read_text())

    def test_foreign_hooks_and_keys_are_kept(self):
        repo = git_repo()
        (repo / ".claude").mkdir()
        foreign = {"model": "x", "hooks": {"PreToolUse": [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "my-linter"}]}]}}
        (repo / ".claude" / "settings.json").write_text(json.dumps(foreign))
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        self.assertEqual(s["model"], "x")
        commands = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertIn("my-linter", commands)
        self.assertTrue(any("claude-hook\" pre-run" in c for c in commands))
        self.assertTrue(any("claude-hook\" stop" in h["command"]
                            for e in s["hooks"]["Stop"] for h in e["hooks"]))

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
        subprocess.run(["git", "config", "--unset", "core.hooksPath"], cwd=repo, check=True)
        self.assertTrue(any("never runs" in g for g in install_hooks.check(repo)))

    def test_an_old_claude_hook_entry_is_replaced_not_doubled(self):
        repo = git_repo()
        (repo / ".claude").mkdir()
        old = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": '".venv/bin/claude-hook" pre-run'}]}]}}
        (repo / ".claude" / "settings.json").write_text(json.dumps(old))
        install_hooks.install(repo)
        s = json.loads((repo / ".claude" / "settings.json").read_text())
        self.assertEqual(len(s["hooks"]["PreToolUse"]), 1)


if __name__ == "__main__":
    unittest.main()
