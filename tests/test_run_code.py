"""The code that produced a run's number is the code here now (finalize
station 3, `run_record_check.code_since_run`; audit 2026-10-27, A1).

Red-team scenario g1: the script counted `len(files) + 1`, the run kept
4.5, the script was fixed to `len(files)` and the old number adopted — no
gate compared the run's code with today's. Each way the code can differ
holds, each with the way back; an analysis fix and a pin raise do not.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks.run_record_check import code_since_run  # noqa: E402
from labkit.formats import runs  # noqa: E402
from labkit.gates import finalize  # noqa: E402
from protocol_fixture import (  # noqa: E402
    completed_run,
    head,
    run_record,
    script_sha_of,
)

SCRIPT = "import features\nfrom lib import counting\n\nprint(counting.n(features.FILES) + 1)\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class CodeSinceRun(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        self.area = self.repo / "experiments" / "01-x"
        self.script = self.area / "scripts" / "01_measure.py"
        self.sibling = self.area / "scripts" / "features.py"
        self.helper = self.repo / "lib" / "counting.py"
        self.analysis = self.area / "scripts" / "02_analyze.py"
        self.pin = self.repo / "requirements.txt"
        for path, text in (
            (self.script, SCRIPT),
            (self.sibling, "FILES = ['a', 'b']\n"),
            (self.helper, "def n(files):\n    return len(files)\n"),
            (self.repo / "lib" / "__init__.py", ""),
            (self.analysis, "print('analysis')\n"),
            (self.pin, "labkit @ git+https://example.invalid/labkit.git@v1.0.0\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the area")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_now(self, *, untracked: tuple[str, ...] = ()) -> Path:
        """A run of the script as runlog leaves its record of the code: the
        script's hash and its copy, the commit, the `git diff HEAD` when the
        tree differs, and copies of UNTRACKED siblings."""
        d = runs.run_path(self.area, "2026-10-27T10-00-00_ab12")
        d.mkdir(parents=True, exist_ok=True)
        runs.script_copy_path(d, ".py").write_bytes(self.script.read_bytes())
        patch = _git(self.repo, "diff", "HEAD")
        if patch:
            runs.patch_path(d).write_text(patch, encoding="utf-8")
        for rel in untracked:
            copy = runs.untracked_copy_path(d, rel)
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes((self.script.parent / rel).read_bytes())
        cfg = run_record(
            script_sha=script_sha_of(self.script),
            git_full=_git(self.repo, "rev-parse", "HEAD"),
            untracked_sources=list(untracked),
        )
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return d

    def held(self, run: Path) -> list[str]:
        return code_since_run(self.area, run)

    def test_unchanged_code_passes(self) -> None:
        self.assertEqual(self.held(self.run_now()), [])

    def test_a_script_fixed_after_the_run_holds_with_its_copy_named(self) -> None:
        run = self.run_now()
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        (line,) = self.held(run)
        self.assertIn(
            "01_measure.py changed since 2026-10-27T10-00-00_ab12 ran it", line
        )
        self.assertIn("script-source.py", line)
        self.script.write_bytes(runs.script_copy_path(run, ".py").read_bytes())
        self.assertEqual(self.held(run), [])  # the way back: restored as it ran

    def test_a_helper_or_a_sibling_changed_after_the_run_holds(self) -> None:
        for path, edit in (
            (self.helper, "def n(files):\n    return len(files) - 1\n"),
            (self.sibling, "FILES = ['a']\n"),
        ):
            with self.subTest(path=path.name):
                run = self.run_now()
                before = path.read_text(encoding="utf-8")
                path.write_text(edit, encoding="utf-8")
                _git(self.repo, "commit", "-qam", "change after the run")
                (line,) = self.held(run)
                self.assertIn(f"{path.name} changed since", line)
                self.assertIn("git checkout", line)
                path.write_text(before, encoding="utf-8")
                _git(self.repo, "commit", "-qam", "back")

    def test_an_analysis_fix_and_a_pin_raise_do_not_hold(self) -> None:
        run = self.run_now()
        self.analysis.write_text("print('fixed analysis')\n", encoding="utf-8")
        self.pin.write_text(self.pin.read_text().replace("v1.0.0", "v2.0.0"))
        _git(self.repo, "commit", "-qam", "analysis fix, pin raise")
        self.assertEqual(self.held(run), [])

    def test_a_run_from_a_dirty_tree_is_compared_with_that_tree(self) -> None:
        """The helper changed but not committed when the run started: the
        run's patch holds it. Committed afterwards as it ran, it passes;
        changed again, it holds."""
        self.helper.write_text("def n(files):\n    return 2 * len(files)\n")
        run = self.run_now()
        self.assertTrue(runs.patch_path(run).is_file())
        _git(self.repo, "commit", "-qam", "commit what ran")
        self.assertEqual(self.held(run), [])
        self.helper.write_text("def n(files):\n    return 3 * len(files)\n")
        (line,) = self.held(run)
        self.assertIn("counting.py changed since", line)
        self.assertIn("uncommitted.patch", line)

    def test_a_helper_untracked_at_the_run_is_not_recorded_and_holds(self) -> None:
        extra = self.repo / "lib" / "extra.py"
        extra.write_text("X = 1\n", encoding="utf-8")
        self.script.write_text("from lib import extra\n" + SCRIPT, encoding="utf-8")
        _git(self.repo, "add", str(self.script))
        _git(self.repo, "commit", "-qm", "the script imports an untracked helper")
        run = self.run_now()
        (line,) = self.held(run)
        self.assertIn("extra.py was not committed when", line)

    def test_an_untracked_sibling_is_compared_with_the_runs_copy(self) -> None:
        local = self.script.parent / "local.py"
        local.write_text("Y = 1\n", encoding="utf-8")
        self.script.write_text("import local\n" + SCRIPT, encoding="utf-8")
        _git(self.repo, "commit", "-qam", "imports a sibling not committed")
        run = self.run_now(untracked=("local.py",))
        self.assertEqual(self.held(run), [])
        local.write_text("Y = 2\n", encoding="utf-8")
        (line,) = self.held(run)
        self.assertIn("local.py changed since", line)
        self.assertIn("source-untracked", line)

    def test_a_run_without_a_script_or_with_its_script_gone_holds(self) -> None:
        run = self.run_now()
        cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
        (run / "config.json").write_text(json.dumps({**cfg, "script_sha": "no-script"}))
        (line,) = self.held(run)
        self.assertIn("recorded no script", line)
        (run / "config.json").write_text(json.dumps(cfg))
        self.script.unlink()
        (line,) = self.held(run)
        self.assertIn("01_measure.py is gone", line)


class FinalizeStation(unittest.TestCase):
    """finalize holds the number at station 3 for every kind — a
    computation registers no promise id, and the declared-scope half of the
    station said n/a for it."""

    def test_a_computation_whose_script_changed_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp) / "experiments" / "01-x"
            area.mkdir(parents=True)
            (area / "PROTOCOL-x.md").write_text(
                "# Experiment protocol: x\n\n" + head(repeat_cost="low", promises=None),
                encoding="utf-8",
            )
            completed_run(area, "2026-10-27T10-00-00_ab12", metrics={"mean": 3.5})

            def station() -> str:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    finalize.main([str(area)])
                out = buf.getvalue()
                return out[out.index("── the run's code") : out.index("── open fields")]

            self.assertIn("as 2026-10-27T10-00-00_ab12 ran them", station())
            script = area / "scripts" / "01_measure.py"
            script.write_text(script.read_text() + "# fixed after the run\n")
            self.assertIn("BLOCKER: ", station())
            self.assertIn("changed since 2026-10-27T10-00-00_ab12 ran it", station())


if __name__ == "__main__":
    unittest.main()
