"""labkit.repo — repo root, an area's protocols and git, answered once.

Before 2026-10-06 two private `_git` helpers turned every git failure into
"", which preflight read as "working tree clean". Now outside a repo is
None, a failure inside one is loud, and an exit code that IS the answer
goes through git_run.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import repo, runlog  # noqa: E402


def make_repo(commit: bool = True) -> Path:
    d = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    if commit:
        (d / "f.txt").write_text("x")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
            cwd=d,
            check=True,
        )
    return d


class Layout(unittest.TestCase):
    def test_area_protocols_is_the_sorted_list(self):
        area = Path(tempfile.mkdtemp())
        for n in ("PROTOCOL-s10-b.md", "PROTOCOL-s1-a.md", "notes.md"):
            (area / n).write_text("")
        self.assertEqual(
            [p.name for p in repo.area_protocols(area)],
            ["PROTOCOL-s1-a.md", "PROTOCOL-s10-b.md"],
        )

    def test_roots(self):
        plain = Path(tempfile.mkdtemp())
        self.assertIsNone(repo.git_root(plain))
        (plain / "tests").mkdir()
        area = plain / "experiments" / "01"
        area.mkdir(parents=True)
        self.assertEqual(
            repo.layout_root(area), plain.resolve()
        )  # stamped tree, no git
        self.assertEqual(
            repo.layout_root(Path(".")), repo.layout_root(Path.cwd())
        )  # "." climbs too
        r = make_repo()
        (r / "a").mkdir()
        self.assertEqual(repo.git_root(r / "a"), r.resolve())
        self.assertEqual(repo.layout_root(r / "a"), r.resolve())


class RepoWide(unittest.TestCase):
    """`repo_protocols` reads the repo outside SKIP_DIRS: a protocol copied
    under runs/<id>/ or shipped in .venv/ made a false "two protocols carry
    id" blocker in three of four scans (audit 2026-10-15); `lab_root` is the
    one rule for the scaffolder and the model backend."""

    def test_repo_protocols_skips_records_and_packages(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            live = root / "experiments" / "01-x" / "PROTOCOL-x.md"
            live.parent.mkdir(parents=True)
            live.write_text("")
            for copy in (
                root / "experiments" / "01-x" / "runs" / "r1" / "PROTOCOL-x.md",
                root / ".venv" / "lib" / "PROTOCOL-x.md",
                root / "data" / "PROTOCOL-x.md",
            ):
                copy.parent.mkdir(parents=True)
                copy.write_text("")
            self.assertEqual(repo.repo_protocols(root), [live])
            self.assertTrue(repo.PROTOCOL_NAME.match("PROTOCOL-s2-foo.md"))
            self.assertFalse(repo.PROTOCOL_NAME.match("PROTOCOL-x.md.bak"))

    def test_lab_root_is_the_nearest_models_toml(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "models.toml").write_text("")
            deep = root / "experiments" / "01-x" / "scripts"
            deep.mkdir(parents=True)
            self.assertEqual(repo.lab_root(deep), root.resolve())
            self.assertIsNone(repo.lab_root(Path(tempfile.mkdtemp())))


class ProtocolChoice(unittest.TestCase):
    """`the_protocol` never guesses; `choose_protocol` says the same and returns None."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp())

    def test_the_only_protocol_is_the_choice(self):
        only = self.area / "PROTOCOL-a.md"
        only.write_text("")
        self.assertEqual(repo.the_protocol(self.area, None), only)
        self.assertEqual(repo.choose_protocol(self.area, None, "t"), only)

    def test_none_or_several_refuse_and_say_why(self):
        with self.assertRaisesRegex(repo.ProtocolChoiceError, "no PROTOCOL-"):
            repo.the_protocol(self.area, None)
        (self.area / "PROTOCOL-a.md").write_text("")
        (self.area / "PROTOCOL-b.md").write_text("")
        with self.assertRaisesRegex(
            repo.ProtocolChoiceError, r"2 protocols (.|\n)*PROTOCOL-b"
        ):
            repo.the_protocol(self.area, None)
        with self.assertRaisesRegex(repo.ProtocolChoiceError, "no such protocol"):
            repo.the_protocol(self.area, self.area / "PROTOCOL-c.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertIsNone(repo.choose_protocol(self.area, None, "t"))
        self.assertIn("t: 2 protocols", out.getvalue())

    def test_a_named_protocol_wins(self):
        (self.area / "PROTOCOL-a.md").write_text("")
        named = self.area / "PROTOCOL-b.md"
        named.write_text("")
        self.assertEqual(repo.the_protocol(self.area, named), named)


class RequirementLines(unittest.TestCase):
    """One grammar for a pin: every spelling pip writes names its package."""

    def test_every_spelling_names_the_package(self):
        for line, name in (
            ("labkit @ git+https://github.com/x/labkit@v0.89.0", "labkit"),
            ("labkit @ git+file:///home/x/labkit@abc1234  # dev", "labkit"),
            ("-e git+https://github.com/x/labkit@abc1234#egg=labkit", "labkit"),
            ("-e /Users/x/projects/labkit", "labkit"),
            ("labkit==0.89.0", "labkit"),
            ("Lab_Kit==1.0", "lab-kit"),
            ("en_core_web_sm @ https://x.invalid/en_core_web_sm.whl", "en-core-web-sm"),
            ("# a comment", None),
            ("", None),
            ("pytest", None),
        ):
            with self.subTest(line):
                self.assertEqual(repo.requirement_name(line), name)

    def test_requirement_lines_filters_a_file(self):
        text = "pytest==8.0\nlabkit @ git+https://g/x/labkit@v1\n# labkit old\n"
        self.assertEqual(
            repo.requirement_lines(text, "labkit"),
            ["labkit @ git+https://g/x/labkit@v1"],
        )
        self.assertEqual(repo.requirement_lines(text, "numpy"), [])

    def test_the_vcs_grammar_reads_url_and_ref(self):
        m = repo.VCS_REQUIREMENT.match("labkit @ git+https://g/x/labkit@v0.1.0")
        assert m is not None
        self.assertEqual(
            (m["name"], m["url"], m["ref"]), ("labkit", "https://g/x/labkit", "v0.1.0")
        )
        unpinned = repo.VCS_REQUIREMENT.match("labkit @ git+https://g/x/labkit")
        assert unpinned is not None
        self.assertIsNone(
            unpinned["ref"]
        )  # a VCS line without a ref is read, not a pin


class Git(unittest.TestCase):
    def test_outside_a_repo_is_none(self):
        self.assertIsNone(repo.git(["status", "--porcelain"], Path(tempfile.mkdtemp())))

    def test_failure_inside_a_repo_is_loud(self):
        with self.assertRaises(repo.GitError) as cm:
            repo.git(["rev-parse", "--verify", "no-such-ref"], make_repo())
        self.assertIn("failed", str(cm.exception))

    def test_exit_code_as_answer(self):
        r = make_repo()
        self.assertEqual(
            repo.git_run(["ls-files", "--error-unmatch", "f.txt"], r).returncode, 0
        )
        self.assertNotEqual(
            repo.git_run(["ls-files", "--error-unmatch", "nope"], r).returncode, 0
        )

    def test_clean_and_dirty(self):
        r = make_repo()
        self.assertEqual(repo.git(["status", "--porcelain"], r), "")
        (r / "g.txt").write_text("y")
        self.assertIn("g.txt", repo.git(["status", "--porcelain"], r) or "")


class RunlogGitState(unittest.TestCase):
    def test_unborn_head_is_a_state_not_an_error(self):
        self.assertEqual(runlog._git_state(make_repo(commit=False)), "no-git")

    def test_committed_and_dirty(self):
        r = make_repo()
        clean = runlog._git_state(r)
        self.assertNotIn("+dirty", clean)
        (r / "g.txt").write_text("y")
        self.assertEqual(runlog._git_state(r), clean + "+dirty")

    def test_the_end_state_ignores_untracked_files_but_not_tracked_drift(self):
        r = make_repo()
        clean = runlog._git_state(r)
        (r / "g.txt").write_text("y")  # untracked: counts at start, not at the end
        self.assertEqual(runlog._git_state(r, untracked=False), clean)
        (r / "f.txt").write_text("changed")  # tracked drift counts at both
        self.assertEqual(runlog._git_state(r, untracked=False), clean + "+dirty")

    def test_a_run_in_a_clean_tree_is_indexed_clean_despite_its_own_products(self):
        import json

        r = make_repo()
        clean = runlog._git_state(r)
        old_argv = sys.argv[0]
        sys.argv[0] = str(r / "f.txt")
        try:
            with runlog.run("t", config={}, base_dir=r) as run:
                run.metrics(n=1)
        finally:
            sys.argv[0] = old_argv
        comp = json.loads((run.dir / "completion.json").read_text(encoding="utf-8"))
        self.assertEqual(comp["git"], clean)  # runs/<id>/ and runs.tsv are its own
        row = (r / "runs.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(row[1], clean)


if __name__ == "__main__":
    unittest.main()
