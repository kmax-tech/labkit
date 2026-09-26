"""`labkit.__version__` must equal the version in pyproject.toml.

Why this is tested: the comment beside `__version__` says "keep in step with
pyproject.toml" and nothing enforced it. On 2026-09-26 the 0.19.0 bump went
into pyproject only, and the freshly installed package reported 0.18.0 — a
run's environment record would have named a version that never existed.
"""

import sys
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from labkit import __version__  # noqa: E402


class TestVersionInStep(unittest.TestCase):

    def test_package_version_matches_pyproject(self):
        with (REPO / "pyproject.toml").open("rb") as f:
            declared = tomllib.load(f)["project"]["version"]
        self.assertEqual(__version__, declared)

    def test_version_is_a_release_number(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
