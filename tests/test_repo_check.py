"""labkit-check: one command says whether a lab repo is on its pin and the pin is current (2026-10-12)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from labkit.gates import install_hooks
from labkit.tools import repo_check

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.org"]


def git(root: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *GIT_ID, "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout


def master_repo(version: str, tags: tuple[str, ...]) -> Path:
    """A labkit-like checkout: pyproject.toml with VERSION, one commit, TAGS on it."""
    root = Path(tempfile.mkdtemp())
    git(root, "init", "-q")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "labkit"\nversion = "{version}"\n'
    )
    git(root, "add", "pyproject.toml")
    git(root, "commit", "-q", "-m", "init")
    for t in tags:
        git(root, "tag", t)
    return root


def lab_repo(pin_line: str) -> Path:
    root = Path(tempfile.mkdtemp())
    git(root, "init", "-q")
    (root / "requirements.txt").write_text(f"# pinned\n{pin_line}\npytest\n")
    return root


class Pins(unittest.TestCase):
    def test_tag_commit_and_version_pins(self):
        root = Path(tempfile.mkdtemp())
        (root / "requirements.txt").write_text(
            "labkit @ git+file:///m/labkit@v0.83.0\n"
        )
        (root / "requirements.lock").write_text(
            "labkit @ git+https://github.com/x/labkit.git@0a3504e3\n"
        )
        pins = repo_check.read_pins(root)
        self.assertEqual(
            [p.file for p in pins], ["requirements.txt", "requirements.lock"]
        )
        self.assertEqual(pins[0].version, "0.83.0")
        self.assertEqual(pins[0].local_path, Path("/m/labkit"))
        self.assertIsNone(pins[1].version)
        self.assertIsNone(pins[1].local_path)
        (root / "requirements.txt").write_text("labkit==1.2.3\n")
        self.assertEqual(repo_check.read_pins(root)[0].version, "1.2.3")

    def test_no_pin_is_empty_but_an_unreadable_line_raises(self):
        root = Path(tempfile.mkdtemp())
        self.assertEqual(repo_check.read_pins(root), [])
        (root / "requirements.txt").write_text("numpy\n")
        self.assertEqual(repo_check.read_pins(root), [])
        (root / "requirements.txt").write_text("labkit @ file:///somewhere\n")
        with self.assertRaises(ValueError) as cm:
            repo_check.read_pins(root)
        self.assertIn("requirements.txt", str(cm.exception))

    def test_versions_compare_numerically(self):
        self.assertEqual(repo_check.version_tuple("0.10.2"), (0, 10, 2))
        self.assertGreater(
            repo_check.version_tuple("0.10.0"), repo_check.version_tuple("0.9.9")
        )
        with self.assertRaises(ValueError):
            repo_check.version_tuple("v0.1")


class Source(unittest.TestCase):
    def test_latest_tag_is_the_numerically_highest(self):
        master = master_repo("0.10.0", ("v0.1.0", "v0.10.0", "v0.2.0", "unrelated"))
        pin = repo_check.Pin("requirements.txt", f"git+file://{master}", "v0.2.0")
        self.assertEqual(repo_check.latest_tag(pin, master), "v0.10.0")

    def test_no_release_tag_is_none_and_a_missing_source_raises(self):
        master = master_repo("0.1.0", ())
        pin = repo_check.Pin("requirements.txt", f"git+file://{master}", "v0.1.0")
        self.assertIsNone(repo_check.latest_tag(pin, master))
        gone = repo_check.Pin(
            "requirements.txt", "git+file:///no/such/checkout", "v0.1.0"
        )
        with self.assertRaises(RuntimeError):
            repo_check.latest_tag(gone, master)

    def test_commit_pin_reads_its_version_from_a_local_source(self):
        master = master_repo("0.7.1", ("v0.7.1",))
        commit = git(master, "rev-parse", "HEAD").strip()
        pin = repo_check.Pin("requirements.txt", f"git+file://{master}", commit)
        self.assertEqual(repo_check.pinned_version(pin, master), "0.7.1")
        remote = repo_check.Pin(
            "requirements.txt", "git+https://github.com/x/labkit.git", commit
        )
        self.assertIsNone(repo_check.pinned_version(remote, master))


FROZEN_HEAD = """```toml
[protocol]
standard = "0.20"
id = "p-0123456789abcdef"
type = "exploratory"
cost = "seconds"
frozen = true
preflight_audit = ""
```
"""


class Refs(unittest.TestCase):
    def test_a_named_reference_passes_and_a_bare_id_is_a_problem(self):
        root = Path(tempfile.mkdtemp())
        (root / "notes").mkdir()
        (root / "notes" / "ok.md").write_text(
            "see LAB-004 Identifiers make the intent addressable.\n"
        )
        (root / "runs").mkdir()
        (root / "runs" / "old.md").write_text("LAB-004 alone, in a run record\n")
        self.assertEqual(repo_check.ref_problems(root), (1, 0, []))
        (root / "notes" / "bad.py").write_text("# LAB-004 without a name\n")
        n, _, problems = repo_check.ref_problems(root)
        self.assertEqual(n, 2)
        self.assertEqual(len(problems), 1)
        self.assertIn("notes/bad.py:1", problems[0])

    def test_frozen_and_older_areas_are_records_and_not_read(self):
        root = Path(tempfile.mkdtemp())
        frozen = root / "experiments" / "01-frozen"
        older = root / "experiments" / "02-older"
        live = root / "experiments" / "03-live"
        for d in (frozen, older, live):
            d.mkdir(parents=True)
        (frozen / "PROTOCOL-frozen.md").write_text(
            FROZEN_HEAD + "\ncites LAB-004 bare\n"
        )
        (frozen / "measure.py").write_text("# LAB-015 bare, in a frozen area\n")
        (older / "PROTOCOL-older.md").write_text(
            "Standard: 0.16\n\nProtocol id: x\n\nLAB-004 bare\n"
        )
        (live / "PROTOCOL-live.md").write_text(
            FROZEN_HEAD.replace("frozen = true", "frozen = false") + "\nLAB-004 bare\n"
        )
        self.assertEqual(repo_check.record_areas(root), [frozen, older])
        n, n_records, problems = repo_check.ref_problems(root)
        self.assertEqual((n, n_records, len(problems)), (1, 2, 1))
        self.assertIn("03-live", problems[0])


class Report(unittest.TestCase):
    """The twin: a repo on its pin with current hooks is all OK, exit 0."""

    def test_current_repo_is_ok(self):
        installed = install_hooks.labkit_version()
        master = master_repo(installed, (f"v{installed}",))
        repo = lab_repo(f"labkit @ git+file://{master}@v{installed}")
        install_hooks.install(repo)
        lines, code = repo_check.check_repo(repo)
        self.assertEqual(code, repo_check.OK, "\n".join(lines))
        self.assertEqual(len(lines), 5)
        self.assertTrue(
            all(ln.rstrip().endswith("OK") for ln in lines), "\n".join(lines)
        )

    def test_old_pin_and_old_hook_are_stale(self):
        installed = install_hooks.labkit_version()
        master = master_repo(installed, ("v0.1.0", f"v{installed}"))
        repo = lab_repo(f"labkit @ git+file://{master}@v0.1.0")
        lines, code = repo_check.check_repo(repo)
        self.assertEqual(code, repo_check.STALE)
        by_label = {ln.split()[0]: ln for ln in lines}
        self.assertIn("STALE", by_label["installed"])
        self.assertIn(f"v{installed}", by_label["latest"])
        self.assertIn("STALE", by_label["latest"])
        self.assertIn("STALE", by_label["hook"])

    def test_commit_pin_is_stale_and_no_pin_is_undecided(self):
        installed = install_hooks.labkit_version()
        master = master_repo(installed, (f"v{installed}",))
        commit = git(master, "rev-parse", "HEAD").strip()
        repo = lab_repo(f"labkit @ git+file://{master}@{commit}")
        install_hooks.install(repo)
        lines, code = repo_check.check_repo(repo)
        by_label = {ln.split()[0]: ln for ln in lines}
        self.assertIn("STALE", by_label["pin"])
        self.assertIn("OK", by_label["installed"])  # the commit's version is readable
        self.assertEqual(code, repo_check.STALE)
        bare = lab_repo("pytest")
        lines, code = repo_check.check_repo(bare)
        self.assertEqual(code, repo_check.UNDECIDED)
        self.assertIn("UNDECIDED", lines[0])

    def test_a_lock_on_the_tags_commit_is_the_same_pin(self):
        """`pip freeze` writes the commit the requirements tag points at; the
        probe's pin line was STALE on every stamp (2026-10-13). The twin: a
        lock on another commit stays two pins."""
        installed = install_hooks.labkit_version()
        master = master_repo(installed, (f"v{installed}",))
        commit = git(master, "rev-parse", "HEAD").strip()
        source = f"labkit @ git+file://{master}"
        repo = lab_repo(f"{source}@v{installed}")
        (repo / "requirements.lock").write_text(f"{source}@{commit}\n")
        line = repo_check.pin_line(repo_check.read_pins(repo), repo)
        self.assertEqual(line.state, repo_check.OK, str(line))
        self.assertIn(commit[:12], str(line))
        (master / "x").write_text("x")
        git(master, "add", "x")
        git(master, "commit", "-q", "-m", "after the tag")
        later = git(master, "rev-parse", "HEAD").strip()
        (repo / "requirements.lock").write_text(f"{source}@{later}\n")
        line = repo_check.pin_line(repo_check.read_pins(repo), repo)
        self.assertEqual(line.state, repo_check.STALE, str(line))

    def test_a_remote_tag_resolves_to_its_commit_annotated_or_not(self):
        master = master_repo("0.1.0", ("v0.1.0",))
        git(master, "tag", "-a", "v0.2.0", "-m", "annotated")
        commit = git(master, "rev-parse", "HEAD").strip()
        for tag in ("v0.1.0", "v0.2.0"):
            pin = repo_check.Pin("requirements.txt", f"git+{master}", tag)
            self.assertIsNone(pin.local_path)  # read with ls-remote
            self.assertEqual(repo_check.tag_commit(pin, master), commit)
        gone = repo_check.Pin("requirements.txt", f"git+{master}", "v9.9.9")
        with self.assertRaises(RuntimeError):
            repo_check.tag_commit(gone, master)

    def test_main_prints_and_exits(self):
        self.assertEqual(
            repo_check.main([str(Path(tempfile.mkdtemp()) / "nope")]),
            repo_check.UNDECIDED,
        )
