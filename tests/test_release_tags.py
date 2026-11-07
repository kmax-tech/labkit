"""Every release tag points at the commit that declares that version.

Why this exists: the version lives in pyproject.toml, the tag is set by a
second hand afterwards, and the two can disagree in both directions.

- Tag missing: every repo the scaffolder produces pins a release tag, and
  `pip install` breaks on a ref that does not exist. That half is caught
  where it hurts — `labkit_pin()` falls back to the commit and says so.
- Tag on the wrong commit: a tag that names a version the commit does not
  declare is a second truth with a name.

This test makes the tag a CHECKED POINTER instead: pyproject.toml is the
version, the commit is the identity, the tag is a label over the commit
that has to agree with it. There is deliberately no `__version__` in the
package — nothing reads one, and a literal that must be kept in step by hand
is the same problem one layer down.
"""

import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RELEASE_TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=20
    ).stdout.strip()  # stripped: `== "true"` never holds against the trailing newline


def _declared_version(ref: str) -> str | None:
    out = _git("show", f"{ref}:pyproject.toml")
    if not out:
        return None
    try:
        return tomllib.loads(out)["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError):
        return None


class TestReleaseTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (REPO / ".git").exists():
            raise unittest.SkipTest("not a git checkout")
        cls.tags = [t for t in _git("tag", "-l").split() if RELEASE_TAG.match(t)]
        if not cls.tags and _git("rev-parse", "--is-shallow-repository") == "true":
            # a cloud session's clone: depth-limited and without tags — there
            # is nothing to hold, and "no tags" is the clone's shape, not a
            # release gone wrong; `git fetch --tags` brings them
            raise unittest.SkipTest("a shallow clone without tags")

    def test_there_are_release_tags_to_check(self):
        """Guard against the check quietly passing on an empty list."""
        self.assertTrue(
            self.tags, "no vX.Y.Z tags found — is this a clone without tags?"
        )

    def test_every_tag_names_the_version_its_commit_declares(self):
        for tag in self.tags:
            with self.subTest(tag=tag):
                m = RELEASE_TAG.match(tag)
                assert m
                declared = _declared_version(tag)
                if declared is None:
                    self.skipTest(f"{tag} predates pyproject.toml")
                self.assertEqual(
                    declared,
                    m.group(1),
                    f"{tag} points at a commit declaring {declared}",
                )

    def test_the_package_keeps_no_second_version_literal(self):
        """No `__version__`: it would be a copy nobody reads, kept in step by a test.

        Deriving it instead — `importlib.metadata.version("labkit")` — is
        the obvious repair and the wrong one: metadata describes whatever
        distribution the interpreter finds first on sys.path, which need
        not be the code that was imported — a stale `labkit.egg-info/` in
        the working directory answers for it, so the answer depends on the
        working directory. A literal that is wrong can be read; a derivation
        that is wrong is believed. So the package states no version at all."""
        import labkit

        self.assertFalse(
            hasattr(labkit, "__version__"),
            "a version literal is back in labkit/__init__.py — "
            "pyproject.toml is the version, the commit is the "
            "identity",
        )

    def test_the_current_version_is_a_release_number(self):
        with (REPO / "pyproject.toml").open("rb") as f:
            self.assertRegex(tomllib.load(f)["project"]["version"], r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
