"""The code a run imported, per git repository (`code_repos`, stagekit
plan step 2b): a framework installed editable from its own checkout, a
topic module nobody committed, a module imported only during the run —
each lands in `code.json` with commit, patch and copies; a measurement
refuses untracked code it cannot copy, and passes on code it can.

A module of a test repository is imported through `sys.path`, as an
editable install puts its checkout there; each test removes its modules
and path entries again.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from protocol_fixture import head

from labkit.formats.runs import CODE_FILE
from labkit.run import code_repos, runlog


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def checkout(root: Path, files: dict[str, str]) -> Path:
    """A git repository at ROOT with FILES committed."""
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


class CodeRecord(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.lab = checkout(self.tmp / "lab", {"exp/.keep": ""})
        self.area = self.lab / "exp"
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def module(self, directory: Path, text: str = "VALUE = 1\n") -> tuple[str, Path]:
        """A new module in DIRECTORY, importable by its returned name."""
        name = f"m_{uuid.uuid4().hex[:12]}"
        path = directory / f"{name}.py"
        path.write_text(text, encoding="utf-8")
        return name, path

    def load(self, directory: Path, name: str) -> None:
        """Import NAME from DIRECTORY as an editable install would offer it."""
        sys.path.insert(0, str(directory))
        self.addCleanup(sys.path.remove, str(directory))
        self.addCleanup(sys.modules.pop, name, None)
        importlib.import_module(name)

    def record(self, run_dir: Path) -> dict:
        return json.loads((run_dir / CODE_FILE).read_text(encoding="utf-8"))

    def entry(self, run_dir: Path, root: Path) -> dict:
        found = [e for e in self.record(run_dir)["repos"] if e["root"] == str(root)]
        self.assertEqual(len(found), 1, f"{root} once in {self.record(run_dir)}")
        return found[0]

    def test_a_local_change_in_another_checkout_is_in_the_record(self) -> None:
        """The plan's first probe: an uncommitted change in an editable
        framework appears in the run record, with the commit it sits on."""
        fw = self.tmp / "framework"
        name, path = self.module(self.tmp)
        checkout(fw, {path.name: path.read_text()})
        path.unlink()
        (fw / path.name).write_text("VALUE = 2  # edited, not committed\n")
        self.load(fw, name)
        with runlog.run("e", {}, self.area) as run:
            pass
        entry = self.entry(run.dir, fw)
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=fw, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual((entry["commit"], entry["dirty"]), (commit, True))
        patch = (run.dir / entry["patch"]).read_text()
        self.assertIn("+VALUE = 2  # edited, not committed", patch)
        self.assertEqual(entry["read_at"], "start")

    def test_a_clean_checkout_is_named_without_a_patch(self) -> None:
        fw = self.tmp / "framework"
        name, path = self.module(self.tmp)
        checkout(fw, {path.name: path.read_text()})
        self.load(fw, name)
        with runlog.run("e", {}, self.area) as run:
            pass
        entry = self.entry(run.dir, fw)
        self.assertEqual((entry["dirty"], entry["patch"]), (False, None))
        self.assertEqual(entry["untracked"], {})

    def test_an_untracked_topic_module_is_copied_into_the_record(self) -> None:
        """The plan's second probe: a module nobody committed, in the lab
        repo holding the topic, is copied as it was imported."""
        topic = self.lab / "topic"
        topic.mkdir()
        name, path = self.module(topic, "LABELS = ['ad hominem']\n")
        self.load(topic, name)
        with runlog.run("e", {}, self.area) as run:
            pass
        entry = self.entry(run.dir, self.lab)
        rel = f"topic/{path.name}"
        self.assertEqual(entry["untracked"], {rel: "start"})
        copy = run.dir / entry["copies"] / rel
        self.assertEqual(copy.read_text(), "LABELS = ['ad hominem']\n")

    def test_a_module_imported_during_the_run_is_recorded_at_the_end(self) -> None:
        topic = self.tmp / "topic"
        name, path = self.module(self.tmp)
        checkout(topic, {path.name: path.read_text()})
        started: list[dict] = []
        with runlog.run("e", {}, self.area) as run:
            started += self.record(run.dir)["repos"]
            self.load(topic, name)
        self.assertNotIn(str(topic), [e["root"] for e in started])
        self.assertEqual(self.entry(run.dir, topic)["read_at"], "end")

    def test_code_outside_any_checkout_is_listed_with_its_digest(self) -> None:
        loose = self.tmp / "loose"
        loose.mkdir()
        name, path = self.module(loose)
        self.load(loose, name)
        found = code_repos.read_code(tuple(sys.modules.values()))
        self.assertIn(str(path), dict(found.outside_git))

    def test_installed_and_ignored_code_is_not_a_repository_s_code(self) -> None:
        """The stdlib and this venv's site-packages lie under an install
        prefix; a module git ignores is a build product, not source."""
        build = self.lab / "build"
        build.mkdir()
        (self.lab / ".gitignore").write_text("build/\n")
        name, _ = self.module(build)
        self.load(build, name)
        found = code_repos.read_code(tuple(sys.modules.values()))
        files = [str(r.root / u) for r in found.repos for u in r.untracked]
        self.assertFalse([f for f in files if "/build/" in f], files)
        listed = [str(r.root) for r in found.repos] + [p for p, _ in found.outside_git]
        self.assertFalse([p for p in listed if "site-packages" in p], listed)
        self.assertFalse([p for p in listed if p.startswith(sys.base_prefix)], listed)


class Measurement(unittest.TestCase):
    """A measurement refuses untracked code it cannot copy; the twin with
    code it can copy starts."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lab = checkout(Path(tmp.name).resolve() / "lab", {"exp/.keep": ""})
        self.area = self.lab / "exp"
        (self.area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", promises=None)
            + "\n- **Question / hypothesis:** how many?\n",
            encoding="utf-8",
        )
        git(self.lab, "add", "-A")
        git(self.lab, "commit", "-q", "-m", "register")
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def load_untracked(self, text: str) -> Path:
        name = f"m_{uuid.uuid4().hex[:12]}"
        path = self.lab / f"{name}.py"
        path.write_text(text, encoding="utf-8")
        sys.path.insert(0, str(self.lab))
        self.addCleanup(sys.path.remove, str(self.lab))
        self.addCleanup(sys.modules.pop, name, None)
        importlib.import_module(name)
        return path

    def test_untracked_code_above_the_cap_refuses_the_start(self) -> None:
        big = self.load_untracked("TABLE = 1\n#" + "x" * code_repos.COPY_CAP + "\n")
        with self.assertRaises(SystemExit) as cm:
            runlog.run("e", {}, self.area, run_kind="measurement")
        self.assertIn(str(big), str(cm.exception))
        self.assertIn("commit these files", str(cm.exception))
        self.assertFalse((self.area / "runs").exists())

    def test_untracked_code_it_can_copy_starts_the_measurement(self) -> None:
        small = self.load_untracked("TABLE = 1\n")
        with runlog.run("e", {}, self.area, run_kind="measurement") as run:
            pass
        record = json.loads((run.dir / CODE_FILE).read_text())
        [entry] = [e for e in record["repos"] if e["root"] == str(self.lab)]
        self.assertIn(small.name, entry["untracked"])
        self.assertEqual(entry["not_copied"], [])


if __name__ == "__main__":
    unittest.main()
