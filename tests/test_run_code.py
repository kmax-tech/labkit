"""The code that produced a run's number is the code here now (finalize
station 3, `run_record_check.code_since_run`).

The case: the script counted `len(files) + 1`, the run kept 4.5, the
script was fixed to `len(files)`, and the old number is not adopted — the
run's code is compared with today's. Each way the code can differ
holds, each with the way back; an analysis fix and a pin raise do not.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import recheck  # noqa: E402
from labkit.checks.run_record_check import code_since_run  # noqa: E402
from labkit.formats import gate, repo, runs  # noqa: E402
from labkit.formats.commands import measure_anew  # noqa: E402
from labkit.formats.answer_reading import (  # noqa: E402
    ANSWER_READING_FILE,
    AnswerReading,
    write_answer_reading,
)
from labkit.formats.run_code import code_then  # noqa: E402
from labkit.gates import finalize  # noqa: E402
from protocol_fixture import (  # noqa: E402
    completed_run,
    head,
    run_record,
    script_sha_of,
)
from repo_fixture import git as _git

SCRIPT = "import features\nfrom lib import counting\n\nprint(counting.n(features.FILES) + 1)\n"


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
        """The blockers as the gate tells them: each sentence with its way out."""
        blockers, warnings = code_since_run(self.area, run)
        self.assertEqual(warnings, [])
        self.assertTrue(all(b.fix for b in blockers))
        return [b.line for b in blockers]

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
        # the fix comes first: measuring anew; restoring is for a change not meant
        self.assertLess(line.index("measure anew"), line.index("restore it as it ran"))
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
        self.assertIn("extra.py is in neither", line)
        self.assertIn("cannot be compared with what the run imported", line)
        (found,) = code_since_run(self.area, run)[0]
        self.assertEqual(found.rule, gate.TECHNICAL_RULE)

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
        """A patch an earlier labkit wrote is `git diff HEAD` as the user's
        git printed it, stripped: a last hunk ending in blank lines lost
        them, a colour setting coloured it, `diff.noprefix` dropped the a/ b/,
        a dirty binary file had no full index line. Only the helpers' part is
        applied, recounted, uncoloured, at its own prefix, so none of these
        holds correct code; the user's `apply.whitespace` is not asked. Each run's helper is dirty, committed afterwards as it
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
                # and the hunk's last context blank lines, which stripping cuts
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
        """A second script of the name runlog records, in scripts/llm/, is
        compared as itself, not with scripts/01_measure.py: the command names
        the path, so the printed `cp` overwrites no other script."""
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
        after the parent ran holds the derived run that answers, not only the
        parent. The chain is followed."""
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

    def derived_reading(self, parent: Path, module: str | None) -> Path:
        """A derived run of PARENT by 03_reevaluate.py, which imports the
        counting helper as its answer reading, declared as MODULE (None:
        nothing declared) — as runlog leaves it."""
        again = self.area / "scripts" / "03_reevaluate.py"
        again.write_text(
            "from lib import counting\n\nprint(counting.n([]))\n", encoding="utf-8"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "re-evaluation")
        derived = self.run_now(
            script=again, name="2026-10-27T11-00-00_cd34", derived_from=parent.name
        )
        if module is not None:
            write_answer_reading(derived, AnswerReading(module=module, labkit="9.9.9"))
        return derived

    def test_a_declared_answer_reading_compares_only_that_module(self) -> None:
        """The evaluation fixed after the parent ran: with the answer reading
        declared, the parent is compared in that module only and passes;
        without it the parent's whole script holds, as before, and the way
        out names the declaration."""
        parent = self.run_now()
        declared = self.derived_reading(parent, "lib/counting.py")
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        self.assertEqual(self.held(declared), [])
        (declared / ANSWER_READING_FILE).unlink()
        (line,) = self.held(declared)
        self.assertIn(f"changed since {parent.name} ran it", line)
        self.assertIn("answer_reading=MODULE", line)

    def test_a_change_to_the_answer_reading_or_what_it_imports_holds(self) -> None:
        """The declared module, a constant in it, and a module it imports
        are compared with the parent's tree; each change holds with the way
        out to measure anew."""
        letters = self.repo / "lib" / "letters.py"
        letters.write_text("LETTERS = 'AB'\n", encoding="utf-8")
        self.helper.write_text(
            "from lib import letters\n\nCAP = 2\n\n\ndef n(files):\n    return len(files)\n",
            encoding="utf-8",
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the reading imports letters")
        parent = self.run_now()
        declared = self.derived_reading(parent, "lib/counting.py")
        self.assertEqual(self.held(declared), [])
        for path, old, new in (
            (self.helper, "CAP = 2", "CAP = 3"),
            (letters, "'AB'", "'ABC'"),
        ):
            with self.subTest(changed=path.name):
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace(old, new), encoding="utf-8")
                # the derived run's own script imports it too: both hold
                lines = self.held(declared)
                (line,) = [ln for ln in lines if f"since {parent.name}" in ln]
                self.assertIn(f"{path.name} changed since {parent.name} ran", line)
                self.assertIn("measure anew", line)
                path.write_text(text, encoding="utf-8")

    def test_a_declaration_that_cannot_be_held_holds(self) -> None:
        """A declared module the declaring script does not import, one that is
        gone, and a declaration that does not read each hold; the last
        compares the parent whole as well."""
        unused = self.repo / "lib" / "unused.py"
        unused.write_text("X = 1\n", encoding="utf-8")
        parent = self.run_now()
        declared = self.derived_reading(parent, "lib/unused.py")
        (line,) = self.held(declared)
        self.assertIn("no longer imports it", line)
        write_answer_reading(
            declared, AnswerReading(module="lib/gone.py", labkit="9.9.9")
        )
        (line,) = self.held(declared)
        self.assertIn("lib/gone.py that", line)
        self.assertIn("cannot be read now", line)
        (declared / ANSWER_READING_FILE).write_text("{", encoding="utf-8")
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        unread, whole = self.held(declared)
        self.assertIn(ANSWER_READING_FILE, unread)
        self.assertIn(f"changed since {parent.name} ran it", whole)

    def test_a_declared_reading_without_a_repository_or_its_script_holds(self) -> None:
        """The comparison of a declared answer reading needs the area's
        repository and the declaring run's script. With the script gone the
        run's own code comparison tells it, once, with the restore in its
        way out — the comparison of the declared reading adds no second
        finding for the same cause. With the repository gone, the reading's
        comparison holds as not made. The twin, both in place: the
        declaration passes."""
        parent = self.run_now()
        declared = self.derived_reading(parent, "lib/counting.py")
        self.assertEqual(self.held(declared), [])
        again = self.area / "scripts" / "03_reevaluate.py"
        kept = again.read_text(encoding="utf-8")
        again.unlink()
        (script_gone,) = code_since_run(self.area, declared)[0]
        self.assertEqual(
            script_gone.text,
            f"{declared.name}: its script scripts/03_reevaluate.py is gone",
        )
        self.assertIn(measure_anew(self.area), script_gone.fix or "")
        self.assertIn("restore it from", script_gone.fix or "")
        self.assertEqual(script_gone.rule, gate.TECHNICAL_RULE)
        again.write_text(kept, encoding="utf-8")
        shutil.rmtree(self.repo / ".git")
        (reading_not_compared,) = [
            f
            for f in code_since_run(self.area, declared)[0]
            if f.text.startswith("the answer reading")
        ]
        self.assertEqual(
            reading_not_compared.text,
            f"the answer reading lib/counting.py that {declared.name} declared "
            f"cannot be compared with what {parent.name} ran: the area lies in "
            f"no git repository now",
        )
        self.assertEqual(reading_not_compared.fix, measure_anew(self.area))
        self.assertEqual(reading_not_compared.rule, gate.TECHNICAL_RULE)

    def test_a_gone_script_no_own_comparison_told_is_told_by_the_reading(self) -> None:
        """A derived run in the middle of a chain — it declares its reading
        over its parent, and a later run declares one over it — has no code
        comparison of its own: its script gone is told by the comparison of
        its declared reading, once. The twin, the script in place: nothing
        is held."""
        parent = self.run_now()
        middle = self.derived_reading(parent, "lib/counting.py")
        later_script = self.area / "scripts" / "04_reevaluate_again.py"
        later_script.write_text(
            "from lib import counting\n\nprint(counting.n([]) + 0)\n", encoding="utf-8"
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "a second re-evaluation")
        last = self.run_now(
            script=later_script,
            name="2026-10-27T12-00-00_ef56",
            derived_from=middle.name,
        )
        write_answer_reading(
            last, AnswerReading(module="lib/counting.py", labkit="9.9.9")
        )
        self.assertEqual(self.held(last), [])
        (self.area / "scripts" / "03_reevaluate.py").unlink()
        (script_gone,) = code_since_run(self.area, last)[0]
        self.assertEqual(
            script_gone.text,
            f"{middle.name}: its script scripts/03_reevaluate.py is gone",
        )
        self.assertEqual(script_gone.fix, measure_anew(self.area))

    def test_only_a_found_difference_names_its_run(self) -> None:
        """`GateFinding.changed_since` is the comparison's datum: the run
        whose code differs — the parent's for a derived run — and nothing
        where the code could not be compared."""
        parent = self.run_now(name="2026-10-27T10-00-00_ab12")
        again = self.area / "scripts" / "03_reevaluate.py"
        again.write_text("print('re-evaluate')\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "re-evaluation")
        derived = self.run_now(
            script=again, name="2026-10-27T11-00-00_cd34", derived_from=parent.name
        )
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        (changed,) = code_since_run(self.area, derived)[0]
        self.assertEqual(changed.changed_since, parent.name)
        # not compared: no script recorded, the script gone
        cfg = json.loads((parent / "config.json").read_text(encoding="utf-8"))
        (parent / "config.json").write_text(
            json.dumps({**cfg, "script_sha": "no-script"})
        )
        (unrecorded,) = code_since_run(self.area, parent)[0]
        self.assertIsNone(unrecorded.changed_since)
        (parent / "config.json").write_text(json.dumps(cfg))
        self.script.unlink()
        (gone,) = code_since_run(self.area, parent)[0]
        self.assertIsNone(gone.changed_since)

    def _record(self, run: Path, **fields: object) -> None:
        """Rewrite FIELDS of RUN's record, as a run of another state left it."""
        cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
        (run / "config.json").write_text(json.dumps({**cfg, **fields}))

    def test_the_comparisons_that_cannot_be_made_each_hold(self) -> None:
        """The boundary's branches where the code cannot be compared — each
        a blocker with its way out, none naming a changed run: a lineage
        that breaks, a script that does not read now, no commit recorded, a
        commit this clone lacks, a patch that does not apply to it."""
        broken = self.run_now(
            name="2026-10-27T13-00-00_aa00", derived_from="2026-10-27T09-00-00_gone"
        )
        (cut,) = code_since_run(self.area, broken)[0]
        self.assertIn("its runs cannot be followed", cut.line)
        self.assertIsNone(cut.changed_since)
        run = self.run_now()
        self._record(run, git_full=runs.NO_GIT)
        (line,) = self.held(run)
        # the cause that holds, and not the other: the area is in a repository
        self.assertIn(f"{run.name} recorded no commit, so the helpers", line)
        self.assertNotIn("no git repository", line)
        # a record that only lacks the commit leaves the comparison without
        # its basis; `git` NO_GIT is the run's word that it started outside
        # the history
        (found,) = code_since_run(self.area, run)[0]
        self.assertEqual(found.rule, gate.TECHNICAL_RULE)
        self._record(run, git=runs.NO_GIT, git_full="")
        (found,) = code_since_run(self.area, run)[0]
        self.assertEqual(found.rule, gate.cited_rule("LAB-010 Commit before the run"))
        self._record(run, git_full="f" * 40)
        (line,) = self.held(run)
        self.assertIn(
            f"started at commit {'f' * 12}, which this clone does not hold", line
        )
        foreign = (
            "diff --git a/lib/counting.py b/lib/counting.py\n"
            "--- a/lib/counting.py\n+++ b/lib/counting.py\n"
            "@@ -1,2 +1,2 @@\n-def nothing_like_this():\n+def other():\n     return 0\n"
        )
        unapplied = self.run_now(name="2026-10-27T12-00-00_ef56", patch=foreign)
        (line,) = self.held(unapplied)
        self.assertIn("cannot be read for", line)
        self.script.write_text("import features\nfrom lib import (\n", encoding="utf-8")
        lines = self.held(run)
        self.assertTrue(any("cannot be read now" in ln for ln in lines), lines)

    def test_the_tree_then_names_which_part_is_missing(self) -> None:
        """`run_code.code_then`: no repository to read from is not a run
        that recorded no commit; the twin, both present, reads the tree."""
        run = self.run_now()
        read = runs.read_run_dir
        self.assertIsNotNone(code_then(read(run), self.repo).tree)
        where = code_then(read(run), None).where
        self.assertIn("no repository to read the commit from", where)
        self.assertNotIn("recorded no commit", where)
        self._record(run, git=runs.NO_GIT, git_full="")
        self.assertEqual(
            code_then(read(run), self.repo).where, f"run {run.name} recorded no commit"
        )

    def test_an_area_outside_a_repository_is_the_cause_named(self) -> None:
        """The run recorded its commit and the area's repository is gone
        since: the sentence names that cause and not a missing commit; with
        both, both."""
        run = self.run_now()
        shutil.rmtree(self.repo / ".git")
        (found,) = code_since_run(self.area, run)[0]
        self.assertIn("the area lies in no git repository now, so the", found.text)
        self.assertNotIn("recorded no commit", found.text)
        self.assertEqual(found.rule, gate.TECHNICAL_RULE)
        self._record(run, git_full="")
        (found,) = code_since_run(self.area, run)[0]
        self.assertIn(
            f"{run.name} recorded no commit and the area lies in no git "
            f"repository now, so the",
            found.text,
        )

    def test_a_helper_in_another_repository_is_named_not_compared(self) -> None:
        """`lib/` as a link out of the repository or as a submodule cannot be
        compared: such a module is a warning, never a crash or a blocker
        without a way out; the area's own code is still compared."""
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
        # finalize's station tells each as a guaranteed warning, rule open
        told = gate.Findings(tell=None)
        finalize.check_run_code(told, self.area, run, None)
        self.assertEqual(
            [(f.grade, f.rule) for f in told.found],
            [(gate.WARNING, gate.TECHNICAL_RULE)] * 2,
        )
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

    # --- the recalculation's code step (`recheck.require_run_code`) ---------------

    def test_a_recalculation_with_the_runs_code_is_established(self) -> None:
        recheck.require_run_code(self.run_now(), self.area)  # raises nothing

    def test_a_recalculation_is_refused_once_the_code_changed_and_back_with_it(
        self,
    ) -> None:
        """Equal numbers from other code would read as a recalculation of
        the run: the script fixed after the run refuses; restored, it is
        the run's code again."""
        run = self.run_now()
        self.script.write_text(SCRIPT.replace(" + 1", ""), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            recheck.require_run_code(run, self.area)
        # a difference found is a refusal of its own, not a missing proof
        self.assertNotIsInstance(cm.exception, recheck.NotVerifiable)
        told = str(cm.exception)
        self.assertIn("the code that computed run 2026-10-27T10-00-00_ab12", told)
        self.assertIn("01_measure.py changed since", told)
        self.assertIn("no recalculation of that run", told)
        self.script.write_text(SCRIPT, encoding="utf-8")
        recheck.require_run_code(run, self.area)

    def test_code_that_cannot_be_compared_is_not_verifiable(self) -> None:
        """No script recorded: nothing shows a difference, and nothing
        shows the same code — the proof is missing, named with both ways
        out; the record back, the recalculation holds again."""
        run = self.run_now()
        recorded = (run / "config.json").read_text()
        cfg = json.loads(recorded)
        (run / "config.json").write_text(json.dumps({**cfg, "script_sha": "no-script"}))
        with self.assertRaises(recheck.NotVerifiable) as cm:
            recheck.require_run_code(run, self.area)
        told = str(cm.exception)
        self.assertIn("run 2026-10-27T10-00-00_ab12 is not verifiable", told)
        self.assertIn("recorded no script", told)
        self.assertIn("A missing proof, not a failed comparison", told)
        self.assertIn("Restore the code as the run ran it", told)
        self.assertIn("or measure anew", told)
        (run / "config.json").write_text(recorded)
        recheck.require_run_code(run, self.area)

    def test_a_module_in_another_repository_is_not_verifiable(self) -> None:
        """finalize warns of a module it cannot compare; a recalculation
        cannot claim the run's code over it."""
        outside = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}-shared"
        outside.mkdir()
        self.addCleanup(lambda: subprocess.run(["rm", "-r", str(outside)], check=True))
        for f in ("__init__.py", "counting.py"):
            (outside / f).write_bytes((self.repo / "lib" / f).read_bytes())
        _git(self.repo, "rm", "-rq", "lib")
        (self.repo / "lib").symlink_to(outside, target_is_directory=True)
        _git(self.repo, "add", "lib")
        _git(self.repo, "commit", "-qm", "lib is shared")
        with self.assertRaises(recheck.NotVerifiable) as cm:
            recheck.require_run_code(self.run_now(), self.area)
        self.assertIn("lies in another repository", str(cm.exception))


class FinalizeStation(unittest.TestCase):
    """finalize holds the number at station 4 for every kind — a
    computation registers no promise id, and its code is compared all the
    same."""

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


class ThePromptsOfADeclaredReading(unittest.TestCase):
    """`finalize.check_answer_reading`: a derived run that declares its
    answer reading is held to the prompts field its parent was measured
    under, so the protocol text each of the two runs saw must read back."""

    PARENT, DERIVED = "2026-10-27T10-00-00_ab12", "2026-10-27T11-00-00_cd34"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(
            head(repeat_cost="low", promises=None)
            + "- **Prompt (verbatim, per variant):** count the files\n",
            encoding="utf-8",
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the protocol")
        self.commit = _git(self.repo, "rev-parse", "HEAD")

    def run_recorded(self, name: str, *, git_full: str, parent: str | None) -> Path:
        """Run NAME as runlog leaves it: its record naming the commit
        GIT_FULL and the run it derives from, and the one answer file both
        runs register."""
        d = runs.run_path(self.area, name)
        d.mkdir(parents=True)
        cfg = run_record(git=git_full[:7], git_full=git_full, derived_from=parent)
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        answers = [{"path": "experiments/01-x/answers.jsonl", "sha256": "abc"}]
        (d / "outputs.json").write_text(json.dumps(answers), encoding="utf-8")
        return d

    def held(self, *, parent_commit: str) -> list[gate.GateFinding]:
        """The blockers of the station's part for a derived run that declares
        its answer reading, its parent recorded at PARENT_COMMIT."""
        self.run_recorded(self.PARENT, git_full=parent_commit, parent=None)
        derived = self.run_recorded(
            self.DERIVED, git_full=self.commit, parent=self.PARENT
        )
        write_answer_reading(
            derived, AnswerReading(module="lib/counting.py", labkit="9.9.9")
        )
        found = gate.Findings(tell=None)
        finalize.check_answer_reading(found, self.area, self.protocol, derived)
        return [f for f in found.found if f.grade == gate.BLOCKER]

    def test_a_parent_whose_protocol_text_cannot_be_read_back_holds(self) -> None:
        (f,) = self.held(parent_commit="")
        self.assertEqual(
            f.text,
            f"the prompts {self.DERIVED} re-reads with cannot be held to "
            f"{self.PARENT}'s: run {self.PARENT} recorded no commit",
        )
        self.assertEqual(f.rule, gate.TECHNICAL_RULE)
        self.assertIn("restore what the sentence names, or measure anew", f.fix or "")

    def test_the_twin_both_texts_read_back_with_one_prompt_passes(self) -> None:
        self.assertEqual(self.held(parent_commit=self.commit), [])


if __name__ == "__main__":
    unittest.main()
