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
from labkit.formats import repo, runs  # noqa: E402
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

    def run_now(
        self,
        *,
        untracked: tuple[str, ...] = (),
        script: Path | None = None,
        name: str = "2026-10-27T10-00-00_ab12",
        derived_from: str | None = None,
        patch: str | None = None,
    ) -> Path:
        """A run of SCRIPT (the area's 01_measure.py) as runlog leaves its
        record of the code: the script's hash, copy and command, the
        commit, the tree's patch when it differs (`repo.tree_patch`, or
        PATCH as an earlier labkit wrote it), and copies of UNTRACKED
        siblings."""
        script = script or self.script
        d = runs.run_path(self.area, name)
        d.mkdir(parents=True, exist_ok=True)
        runs.script_copy_path(d, ".py").write_bytes(script.read_bytes())
        patch = repo.tree_patch(self.repo) if patch is None else patch
        if patch:
            runs.patch_path(d).write_text(patch, encoding="utf-8")
        for rel in untracked:
            copy = runs.untracked_copy_path(d, rel)
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes((self.script.parent / rel).read_bytes())
        cfg = run_record(
            script=script.name,
            command=[str(script.relative_to(self.area))],
            script_sha=script_sha_of(script),
            git_full=_git(self.repo, "rev-parse", "HEAD"),
            untracked_sources=list(untracked),
            derived_from=derived_from,
        )
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return d

    def held(self, run: Path) -> list[str]:
        blockers, warnings = code_since_run(self.area, run)
        self.assertEqual(warnings, [])
        return blockers

    def run_printed(self, line: str) -> None:
        """Run the way out LINE prints (its backticked command), from the
        working directory, as a person pastes it into a shell."""
        command = line.split("`")[1]
        subprocess.run(command, shell=True, check=True, cwd=Path.cwd())

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
        self.run_printed(line)  # the way back: restored as it ran
        self.assertEqual(self.held(run), [])

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
                self.run_printed(line)  # the way back, as printed
                self.assertEqual(path.read_text(encoding="utf-8"), before)
                self.assertEqual(self.held(run), [])
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
        self.run_printed(line)  # restores the text that ran, never committed as such
        self.assertIn("2 * len", self.helper.read_text(encoding="utf-8"))
        self.assertEqual(self.held(run), [])

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

    def test_a_patch_an_earlier_labkit_wrote_still_reads(self) -> None:
        """Before `repo.tree_patch` the run kept `git diff HEAD` as the
        user's git printed it, stripped: a last hunk ending in blank lines
        lost them, a colour setting coloured it, `diff.noprefix` dropped
        the a/ b/, a dirty binary file had no full index line — and the
        whole patch was applied, so any of these held correct code (cold
        review 2026-10-27). Only the helpers' part is applied, recounted,
        uncoloured, at its own prefix; the user's `apply.whitespace` is
        not asked. Each run's helper is dirty, committed afterwards as it
        ran: no blocker; changed again: one."""
        figure = self.area / "output" / "fig.png"
        figure.parent.mkdir()
        figure.write_bytes(b"\x89PNG\x00one")
        self.helper.write_text(
            "def n(files):\n    x = 0\n    return len(files)\n\n\n\n"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "a figure, blank lines at the end")
        _git(self.repo, "config", "apply.whitespace", "error")
        for i, flags in enumerate(
            ([], ["-c", "color.diff=always"], ["-c", "diff.noprefix=true"]), start=2
        ):
            with self.subTest(flags=flags):
                # an added line with trailing blanks (apply.whitespace=error),
                # and the hunk's last context blank lines, which the stripping cut
                self.helper.write_text(
                    f"def n(files):\n    x = {i}  \n    return {i} * len(files)\n\n\n\n"
                )
                figure.write_bytes(b"\x89PNG\x00" + bytes([i]))
                old = subprocess.run(
                    ["git", *flags, "diff", "HEAD"],
                    cwd=self.area,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                run = self.run_now(patch=old)
                _git(self.repo, "commit", "-qam", "commit what ran")
                self.assertEqual(self.held(run), [])
                self.helper.write_text(f"def n(files):\n    return {i}0 * len(files)\n")
                (line,) = self.held(run)
                self.assertIn("counting.py changed since", line)
                _git(self.repo, "commit", "-qam", "changed again")

    def test_a_script_in_a_subfolder_is_the_one_its_command_names(self) -> None:
        """runlog records the script's name; a second script of that name
        in scripts/llm/ was compared with scripts/01_measure.py, and the
        printed `cp` overwrote the other one (cold review 2026-10-27). The
        command names the path."""
        other = self.area / "scripts" / "llm" / "01_measure.py"
        other.parent.mkdir()
        other.write_text("print('the llm lane')\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "a second lane")
        run = self.run_now(script=other)
        self.assertEqual(self.held(run), [])
        other.write_text("print('the llm lane, fixed')\n", encoding="utf-8")
        (line,) = self.held(run)
        self.assertIn("llm/01_measure.py changed since", line)

    def test_a_derived_run_is_held_to_its_parents_code(self) -> None:
        """A re-evaluation rests on its parent's rows: the row code fixed
        after the parent ran held the parent, not the derived run that
        answers (cold review 2026-10-27). The chain is followed."""
        parent = self.run_now(name="2026-10-27T10-00-00_ab12")
        again = self.area / "scripts" / "03_reevaluate.py"
        again.write_text("print('re-evaluate')\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "re-evaluation")
        derived = self.run_now(
            script=again, name="2026-10-27T11-00-00_cd34", derived_from=parent.name
        )
        self.assertEqual(self.held(derived), [])
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        (line,) = self.held(derived)
        self.assertIn(f"changed since {parent.name} ran it", line)

    def test_a_helper_in_another_repository_is_named_not_compared(self) -> None:
        """`lib/` as a link out of the repository crashed finalize, as a
        submodule it read as never committed — every finalize there held,
        with no way out (cold review 2026-10-27). Such a module is a
        warning; the area's own code is still compared."""
        outside = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}-shared"
        outside.mkdir()
        self.addCleanup(lambda: subprocess.run(["rm", "-r", str(outside)], check=True))
        for f in ("__init__.py", "counting.py"):
            (outside / f).write_bytes((self.repo / "lib" / f).read_bytes())
        _git(self.repo, "rm", "-rq", "lib")
        (self.repo / "lib").symlink_to(outside, target_is_directory=True)
        _git(self.repo, "add", "lib")
        _git(self.repo, "commit", "-qm", "lib is shared")
        run = self.run_now()
        blockers, warnings = code_since_run(self.area, run)
        self.assertEqual(blockers, [])
        self.assertEqual(len(warnings), 2, warnings)
        self.assertIn("lies in another repository", warnings[0])
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        self.assertEqual(len(code_since_run(self.area, run)[0]), 1)

    def test_a_helper_in_a_submodule_is_named_not_compared(self) -> None:
        shared = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}-sub"
        shared.mkdir()
        self.addCleanup(lambda: subprocess.run(["rm", "-r", str(shared)], check=True))
        _git(shared, "init", "-q")
        for f in ("__init__.py", "counting.py"):
            (shared / f).write_bytes((self.repo / "lib" / f).read_bytes())
        _git(shared, "add", "-A")
        _git(shared, "commit", "-qm", "shared lib")
        _git(self.repo, "rm", "-rq", "lib")
        _git(self.repo, "commit", "-qm", "lib moves out")
        _git(
            self.repo,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(shared),
            "lib",
        )
        _git(self.repo, "commit", "-qm", "lib as a submodule")
        run = self.run_now()
        blockers, warnings = code_since_run(self.area, run)
        self.assertEqual(blockers, [])
        self.assertEqual(len(warnings), 2, warnings)


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
