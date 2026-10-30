"""labkit.formats.repo — repo root, an area's protocols and git, answered once.

Before 2026-10-06 two private `_git` helpers turned every git failure into
"", which preflight read as "working tree clean". Now outside a repo is
None, a failure inside one is loud, and an exit code that IS the answer
goes through git_run.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import repo  # noqa: E402
from labkit.run import provenance, runlog  # noqa: E402


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

    def test_areas_of_names_each_touched_area_once_in_path_order(self):
        """The stop's reported numbers and the commit's undecided findings
        read the same answer: the nearest area above each path, each once,
        a path under no area contributing nothing."""
        root = Path(tempfile.mkdtemp())
        b, a = root / "experiments" / "02-b", root / "experiments" / "01-a"
        for area in (a, b):
            (area / "scripts").mkdir(parents=True)
            (area / f"PROTOCOL-{area.name[3:]}.md").write_text("")
        (root / "lib").mkdir()
        touched = repo.areas_of(
            [
                b / "scripts" / "01_measure.py",
                root / "lib" / "x.py",
                a / "PROTOCOL-a.md",
                b / "runs" / "r" / "metrics.json",
            ],
            stop=root,
        )
        self.assertEqual(touched, [b.resolve(), a.resolve()])
        self.assertEqual(repo.areas_of([root / "lib" / "x.py"], stop=root), [])

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

    def test_split_area_name(self):
        self.assertEqual(
            repo.split_area_name("01-docs-per-case"), ("01", "docs-per-case")
        )
        self.assertEqual(repo.split_area_name("100-foo"), ("100", "foo"))
        self.assertEqual(repo.split_area_name("explore"), (None, "explore"))

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
        err = io.StringIO()
        with contextlib.redirect_stderr(err):  # a refusal to run: stderr
            self.assertIsNone(repo.choose_protocol(self.area, None, "t"))
        self.assertIn("t: 2 protocols", err.getvalue())

    def test_a_named_protocol_wins(self):
        (self.area / "PROTOCOL-a.md").write_text("")
        named = self.area / "PROTOCOL-b.md"
        named.write_text("")
        self.assertEqual(repo.the_protocol(self.area, named), named)

    def test_a_bare_file_name_names_the_areas_protocol(self):
        # `preflight <AREA> [--protocol PROTOCOL-*.md]` and the pre-run hook's
        # label name it so; from the repo root the name was refused
        # (labkit-paper area 15, round 2, t71 and t21)
        (self.area / "PROTOCOL-a.md").write_text("")
        named = self.area / "PROTOCOL-b.md"
        named.write_text("")
        elsewhere = Path(tempfile.mkdtemp())
        with contextlib.chdir(elsewhere):
            self.assertEqual(repo.the_protocol(self.area, Path("PROTOCOL-b.md")), named)
            with self.assertRaisesRegex(
                repo.ProtocolChoiceError,
                re.escape(
                    f"no such protocol: PROTOCOL-c.md (not in {self.area.resolve()} either)"
                ),
            ):
                repo.the_protocol(self.area, Path("PROTOCOL-c.md"))
            # a path keeps being read from the working directory
            with self.assertRaisesRegex(repo.ProtocolChoiceError, "no such protocol"):
                repo.the_protocol(self.area, Path("sub") / "PROTOCOL-b.md")

    def test_a_name_there_as_given_is_read_as_given(self):
        # the twin: what the working directory holds under the name is taken,
        # as before — from inside the area that is the area's own file
        (self.area / "PROTOCOL-a.md").write_text("")
        (self.area / "PROTOCOL-b.md").write_text("")
        with contextlib.chdir(self.area):
            self.assertEqual(
                repo.the_protocol(self.area, Path("PROTOCOL-b.md")),
                Path("PROTOCOL-b.md"),
            )


class RequirementLines(unittest.TestCase):
    """One grammar for a pin: every spelling pip writes names its package."""

    def test_every_spelling_names_the_package(self):
        for line, name in (
            ("labkit @ git+https://github.com/x/labkit@v0.89.0", "labkit"),
            ("labkit @ git+file:///home/x/labkit@abc1234  # dev", "labkit"),
            ("-e git+https://github.com/x/labkit@abc1234#egg=labkit", "labkit"),
            (  # pip's freeze of an editable install in a git worktree
                "-e git+https://github.com/x/labkit@abc1234#egg=labkit&subdirectory=../../labkit-wt",
                "labkit",
            ),
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


class CommittedSince(unittest.TestCase):
    """`paths_committed_since`: what the commits after a base touched — the
    stop's second source beside git status (eighth haiku round, t3)."""

    def _commit(self, d: Path, msg: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
            cwd=d,
            check=True,
        )

    def test_added_deleted_and_both_sides_of_a_rename(self):
        d = make_repo()
        (d / "g.txt").write_text("y")
        self._commit(d, "g")
        base = repo.head_sha(d)
        (d / "f.txt").rename(d / "moved.txt")
        (d / "g.txt").unlink()
        (d / "new.txt").write_text("z")
        self._commit(d, "move, delete, add")
        self.assertEqual(
            sorted(p.name for p in repo.paths_committed_since(d, base)),
            ["f.txt", "g.txt", "moved.txt", "new.txt"],
        )
        self.assertEqual(repo.paths_committed_since(d, repo.head_sha(d)), [])
        self.assertEqual(repo.fork_point(d, base), base)

    def test_an_empty_base_is_every_path_head_holds(self):
        d = make_repo()
        self.assertEqual([p.name for p in repo.paths_committed_since(d, "")], ["f.txt"])

    def test_an_unborn_head_is_nothing_yet(self):
        d = make_repo(commit=False)
        self.assertEqual(repo.head_sha(d), "")
        self.assertEqual(repo.paths_committed_since(d, ""), [])

    def test_a_base_git_does_not_know_has_no_fork_point(self):
        self.assertIsNone(repo.fork_point(make_repo(), "0" * 40))


class CommitOrder(unittest.TestCase):
    """`commit_known`, `is_ancestor`, `earliest_commits`: the order git's
    history gives the commits runs recorded — the first measurement is
    ordered by it, not by a run id's local time (A11, audit 2026-10-27)."""

    def _commit(self, d: Path, msg: str) -> str:
        (d / "f.txt").write_text(msg)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
            cwd=d,
            check=True,
        )
        return repo.head_sha(d)

    def _diverged(self) -> tuple[Path, str, str, str]:
        """A base and two branches from it: (repo, base, x, y)."""
        d = make_repo()
        base = repo.head_sha(d)
        x = self._commit(d, "left")
        subprocess.run(["git", "checkout", "-q", base], cwd=d, check=True)
        y = self._commit(d, "right")
        return d, base, x, y

    def test_a_linear_history_has_one_earliest(self):
        d = make_repo()
        a = repo.head_sha(d)
        b = self._commit(d, "b")
        c = self._commit(d, "c")
        self.assertTrue(repo.is_ancestor(d, a, c))
        self.assertFalse(repo.is_ancestor(d, c, a))
        self.assertTrue(repo.is_ancestor(d, b, b))
        self.assertEqual(repo.earliest_commits(d, [c, a, b, a]), [a])
        self.assertEqual(repo.earliest_commits(d, [c]), [c])
        self.assertEqual(repo.earliest_commits(d, []), [])

    def test_diverged_history_has_one_earliest_per_branch(self):
        d, base, x, y = self._diverged()
        self.assertFalse(repo.is_ancestor(d, x, y))
        self.assertFalse(repo.is_ancestor(d, y, x))
        self.assertEqual(repo.earliest_commits(d, [y, x]), [y, x])
        # the shared base precedes both
        self.assertEqual(repo.earliest_commits(d, [y, x, base]), [base])

    def test_an_amended_commit_and_its_replacement_are_not_ordered(self):
        d = make_repo()
        first = self._commit(d, "first")
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q"]
            + ["--amend", "-m", "amended"],
            cwd=d,
            check=True,
        )
        amended = repo.head_sha(d)
        self.assertEqual(repo.earliest_commits(d, [first, amended]), [first, amended])

    def test_a_file_url_names_its_path_also_after_git_plus(self):
        # three callers read file:// by hand (audit 2026-10-28, H8)
        self.assertEqual(repo.file_url_path("file:///src/labkit"), Path("/src/labkit"))
        self.assertEqual(
            repo.file_url_path("git+file:///src/labkit"), Path("/src/labkit")
        )
        self.assertIsNone(repo.file_url_path("git+https://github.com/x/labkit.git"))

    def test_a_ref_names_its_commit_or_none(self):
        # one "ref → commit" for the lab-pin check, a lock's ref and a pin's
        # tag (audit 2026-10-27, third, S8)
        d = make_repo()
        head = repo.head_sha(d)
        subprocess.run(["git", "tag", "v1.0.0"], cwd=d, check=True)
        self.assertEqual(repo.commit_of(d, "v1.0.0"), head)
        self.assertEqual(repo.commit_of(d, "HEAD"), head)
        self.assertIsNone(repo.commit_of(d, "v9.9.9"))  # not echoed back

    def test_only_a_full_sha_the_repository_holds_is_known(self):
        d = make_repo()
        head = repo.head_sha(d)
        self.assertTrue(repo.commit_known(d, head))
        self.assertFalse(repo.commit_known(d, "0" * 40))  # never fetched or pruned
        self.assertFalse(
            repo.commit_known(d, head[:7])
        )  # resolves to what it names now
        branch = repo.git(["branch", "--show-current"], d) or "?"
        self.assertFalse(repo.commit_known(d, branch))
        self.assertFalse(repo.commit_known(d, "HEAD"))
        tree = repo.git(["rev-parse", "HEAD^{tree}"], d) or "?"
        self.assertFalse(repo.commit_known(d, tree))  # an object, not a commit

    def test_a_failing_git_is_loud(self):
        with self.assertRaises(RuntimeError):
            repo.is_ancestor(make_repo(), "0" * 40, "HEAD")


class HeadBefore(unittest.TestCase):
    """`head_before`: the commit HEAD's line stood on before a time, by
    commit dates — the stop's base when the kept one is gone."""

    T = 1_800_000_000  # the session's start, in whole seconds

    def _commit_at(self, d: Path, msg: str, epoch: int) -> str:
        (d / f"{msg}.txt").write_text(msg)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        stamp = f"@{epoch} +0000"
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
            cwd=d,
            check=True,
            env={**os.environ, "GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp},
        )
        return repo.head_sha(d)

    def _at(self, epoch: int) -> datetime:
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    def test_the_parent_of_the_oldest_commit_dated_since(self):
        d = make_repo(commit=False)
        root = self._commit_at(d, "old", self.T - 60)
        self._commit_at(d, "first", self.T)  # the same second counts
        head = self._commit_at(d, "second", self.T + 60)
        self.assertEqual(repo.head_before(d, self._at(self.T)), root)
        # a naive time is local time, the same instant
        naive = self._at(self.T).astimezone().replace(tzinfo=None)
        self.assertEqual(repo.head_before(d, naive), root)
        self.assertEqual(repo.head_before(d, self._at(self.T + 61)), head)

    def test_a_root_commit_dated_since_is_every_commit(self):
        d = make_repo(commit=False)
        self._commit_at(d, "first", self.T + 1)
        self.assertEqual(repo.head_before(d, self._at(self.T)), "")

    def test_an_unborn_head_is_none(self):
        self.assertIsNone(repo.head_before(make_repo(commit=False), self._at(self.T)))


class GitHomes(unittest.TestCase):
    """The git questions asked in one place (audit 2026-10-27, D): HEAD, a
    dirty tree, a path in the git directory, the files a state holds."""

    def _commit(self, d: Path) -> None:
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
            cwd=d,
            check=True,
        )

    def test_head_sha_short_and_outside_a_repository(self):
        d = make_repo()
        full, short = repo.head_sha(d), repo.head_sha(d, short=True)
        self.assertEqual(len(full), 40)
        self.assertTrue(full.startswith(short) and 4 <= len(short) < 40)
        self.assertEqual(repo.head_sha(Path(tempfile.mkdtemp())), "")

    def test_tree_dirty_counts_untracked_files_unless_told_not_to(self):
        d = make_repo()
        self.assertFalse(repo.tree_dirty(d))
        (d / "new.txt").write_text("y")
        self.assertTrue(repo.tree_dirty(d))
        self.assertFalse(repo.tree_dirty(d, untracked=False))
        (d / "f.txt").write_text("changed")
        self.assertTrue(repo.tree_dirty(d, untracked=False))
        self.assertFalse(repo.tree_dirty(Path(tempfile.mkdtemp())))

    def test_git_dir_path_is_the_worktrees_own_or_the_common_one(self):
        d = make_repo()
        self.assertEqual(repo.git_dir_path(d, "x"), d / ".git" / "x")
        wt = Path(tempfile.mkdtemp()) / "wt"
        subprocess.run(
            ["git", "worktree", "add", "-q", "--detach", str(wt)], cwd=d, check=True
        )
        own = repo.git_dir_path(wt, "x")
        self.assertIsNotNone(own)
        assert own is not None
        self.assertEqual(
            own.parent.parent.resolve(), (d / ".git" / "worktrees").resolve()
        )
        common = repo.git_dir_path(wt, "x", common=True)
        assert common is not None
        self.assertEqual(common.resolve(), (d / ".git" / "x").resolve())
        self.assertIsNone(repo.git_dir_path(Path(tempfile.mkdtemp()), "x"))

    def test_files_at_the_index_and_a_revision_under_a_folder(self):
        d = make_repo()
        (d / "audits" / "sub").mkdir(parents=True)
        (d / "audits" / "r.toml").write_text("a")
        (d / "audits" / "sub" / "s.toml").write_text("b")
        (d / "other.toml").write_text("c")
        self.assertEqual(repo.files_at(d, d / "audits"), set())  # nothing staged yet
        self.assertEqual(repo.files_at(d, d / "audits", "HEAD"), set())
        subprocess.run(["git", "add", "audits"], cwd=d, check=True)
        self.assertEqual(repo.files_at(d, d / "audits"), {"r.toml", "sub/s.toml"})
        self.assertEqual(repo.files_at(d, d / "audits", "HEAD"), set())
        self._commit(d)
        self.assertEqual(
            repo.files_at(d, d / "audits", "HEAD"), {"r.toml", "sub/s.toml"}
        )

    def test_text_at_reads_a_paths_own_entry_and_indexed_links_names_links(self):
        """A link in the tree is not followed to another entry, and a link
        git holds reads as the target it writes; `indexed_links` lists the
        links with their targets (A10: a report linked into data/)."""
        d = make_repo()
        (d / "data").mkdir()
        (d / "data" / "R.md").write_text("behind the link\n")
        (d / "R.md").write_text("own entry\n")
        (d / "L.md").symlink_to(Path("data") / "R.md")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        self.assertEqual(repo.text_at(d, d / "L.md"), "data/R.md")
        self.assertEqual(repo.indexed_links(d), {d.resolve() / "L.md": "data/R.md"})
        (d / "R.md").unlink()
        (d / "R.md").symlink_to(Path("data") / "R.md")  # the tree only
        self.assertEqual(repo.text_at(d, d / "R.md"), "own entry\n")
        self.assertEqual(repo.own_path(d / "R.md"), d.resolve() / "R.md")
        self.assertEqual(repo.indexed_links(make_repo()), {})

    def test_under_root_holds_a_link_where_it_lies(self):
        d = make_repo()
        elsewhere = Path(tempfile.mkdtemp())
        (elsewhere / "x.md").write_text("x")
        (d / "in.md").symlink_to(elsewhere / "x.md")
        (elsewhere / "back.md").symlink_to(d / "f.txt")
        self.assertTrue(repo.under_root(d, d / "in.md"))
        self.assertFalse(repo.under_root(d, elsewhere / "back.md"))
        self.assertTrue(repo.under_root(d, d / "f.txt"))

    def test_files_at_says_none_for_no_state_and_raises_for_a_failure(self):
        unborn = make_repo(commit=False)
        (unborn / "audits").mkdir()
        self.assertIsNone(repo.files_at(unborn, unborn / "audits", "HEAD"))
        self.assertEqual(
            repo.files_at(unborn, unborn / "audits"), set()
        )  # the index exists
        bare = Path(tempfile.mkdtemp())
        (bare / ".git").mkdir()  # a `.git` git does not take for a repository
        (bare / "audits").mkdir()
        self.assertIsNone(repo.files_at(bare, bare / "audits"))
        d = make_repo()
        self.assertIsNone(repo.files_at(d, d / "audits", "no-such-rev"))


class AuditCommand(unittest.TestCase):
    """`repo.audit_command`: the one builder of a printed audit step — paths
    as the working directory reaches them, quoted, `--protocol` where the
    area holds several (audit 2026-10-27, D)."""

    def test_quoted_from_here_and_the_protocol_where_several(self):
        root = Path(tempfile.mkdtemp()) / "my lab"
        area = root / "experiments" / "01-x"
        area.mkdir(parents=True)
        (area / "PROTOCOL-a.md").write_text("# a\n")
        one = repo.audit_command(
            area,
            "--review",
            "--record",
            "r 1.toml",
            protocol=area / "PROTOCOL-a.md",
            base=root,
        )
        self.assertEqual(
            one, "labkit-audit experiments/01-x --review --record 'r 1.toml'"
        )
        (area / "PROTOCOL-b.md").write_text("# b\n")
        two = repo.audit_command(
            area, "--mode", "analysis", protocol=area / "PROTOCOL-b.md", base=root
        )
        self.assertEqual(
            two,
            "labkit-audit experiments/01-x --mode analysis "
            "--protocol experiments/01-x/PROTOCOL-b.md",
        )
        self.assertEqual(
            repo.audit_command(area, base=root.parent),
            "labkit-audit 'my lab/experiments/01-x'",
        )
        # runs as printed: the words read back to the area and the protocol from there
        words = shlex.split(two)
        self.assertTrue((root / words[1]).is_dir() and (root / words[-1]).is_file())


class RunlogGitState(unittest.TestCase):
    def test_unborn_head_is_a_state_not_an_error(self):
        self.assertEqual(provenance.git_state(make_repo(commit=False)), "no-git")

    def test_committed_and_dirty(self):
        r = make_repo()
        clean = provenance.git_state(r)
        self.assertNotIn("+dirty", clean)
        (r / "g.txt").write_text("y")
        self.assertEqual(provenance.git_state(r), clean + "+dirty")

    def test_the_end_state_ignores_untracked_files_but_not_tracked_drift(self):
        r = make_repo()
        clean = provenance.git_state(r)
        (r / "g.txt").write_text("y")  # untracked: counts at start, not at the end
        self.assertEqual(provenance.git_state(r, untracked=False), clean)
        (r / "f.txt").write_text("changed")  # tracked drift counts at both
        self.assertEqual(provenance.git_state(r, untracked=False), clean + "+dirty")

    def test_a_run_in_a_clean_tree_is_indexed_clean_despite_its_own_products(self):
        import json

        r = make_repo()
        clean = provenance.git_state(r)
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


class Shown(unittest.TestCase):
    def test_below_the_base_relative_else_absolute(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d).resolve() / "repo"
            (base / "lib").mkdir(parents=True)
            self.assertEqual(repo.shown(base / "lib" / "a.py", base), "lib/a.py")
            outside = Path(d).resolve() / "elsewhere.py"
            self.assertEqual(repo.shown(outside, base), outside.as_posix())

    def test_a_path_below_the_base_only_through_a_link_is_still_below(self):
        """One side resolved, the other not, found nothing below (macOS
        /var is /private/var)."""
        with tempfile.TemporaryDirectory() as d:
            real = Path(d).resolve() / "real"
            (real / "lib").mkdir(parents=True)
            link = Path(d).resolve() / "link"
            link.symlink_to(real)
            self.assertEqual(repo.shown(link / "lib" / "a.py", real), "lib/a.py")
            self.assertEqual(repo.shown(real / "lib" / "a.py", link), "lib/a.py")


class AdoptCommand(unittest.TestCase):
    """The adopt line names the protocol as the working directory reaches
    it: a bare file name failed from the repo root (count probe, 2026-10-20)."""

    def test_the_protocol_is_named_from_the_working_directory(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            proto = root / "experiments" / "01-x" / "PROTOCOL-x.md"
            proto.parent.mkdir(parents=True)
            old = Path.cwd()
            try:
                os.chdir(root)
                at_root = repo.adopt_command(proto, "R1")
                os.chdir(proto.parent)
                in_area = repo.adopt_command(proto)
                os.chdir(root.parent)
                above = repo.adopt_command(proto)
            finally:
                os.chdir(old)
        self.assertEqual(at_root, "labkit-adopt experiments/01-x R1")
        self.assertEqual(in_area, "labkit-adopt . <run_id>")
        self.assertEqual(above, f"labkit-adopt {root.name}/experiments/01-x <run_id>")


if __name__ == "__main__":
    unittest.main()
