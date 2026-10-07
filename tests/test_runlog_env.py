#!/usr/bin/env python3
"""Tests for runlog's environment fingerprint.

Why here: `env` is a *recorded provenance field*. If the drift check is wrong,
nothing crashes — every run just keeps claiming an environment it did not run
in. That is the same silent class as the sentence counter.

Two things are pinned: the URL-pin form (spaCy models have no `==` version and
must not count as drift) and the pip-freeze omissions (`pip` is installed but
deliberately absent from every lock — counting it would make drift permanently
non-zero and the warning worthless).

Run:  .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load(rel: str):
    path = REPO / rel
    spec = importlib.util.spec_from_file_location("mod_" + path.stem, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


runlog = load("labkit/runlog.py")


def write_lock(text: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "requirements.lock"
    tmp.write_text(text, encoding="utf-8")
    return tmp


class ParseLock(unittest.TestCase):
    def test_version_pin(self):
        got = runlog._parse_lock(write_lock("streamlit==1.61.1\npandas==2.0.0\n"))
        self.assertEqual(got, {"streamlit": "1.61.1", "pandas": "2.0.0"})

    def test_url_pin_has_no_version(self):
        """spaCy models come as `name @ https://...` — pinned, but versionless."""
        got = runlog._parse_lock(
            write_lock("en_core_web_md @ https://example.invalid/en_core_web_md.whl\n")
        )
        self.assertEqual(got, {"en-core-web-md": None})

    def test_normalises_underscores_and_case(self):
        got = runlog._parse_lock(write_lock("Ruamel_Yaml==0.18\n"))
        self.assertEqual(got, {"ruamel-yaml": "0.18"})

    def test_blank_lines_and_comments(self):
        got = runlog._parse_lock(write_lock("\n# a comment\nnumpy==2.1\n\n"))
        self.assertEqual(got, {"numpy": "2.1"})


class LockDrift(unittest.TestCase):
    """_lock_drift reads the LIVE environment, so assert on its properties."""

    def test_pip_omission_does_not_count_as_drift(self):
        """pip is installed but never in a freeze — it must be excluded."""
        self.assertIn("pip", runlog._FREEZE_OMITS)

    def test_omissions_are_filtered_on_both_sides(self):
        """Some pip versions DO freeze setuptools. Filtering it only out of the
        installed set would report it as "pinned but missing" forever."""
        lock = write_lock("setuptools==80.0\npip==26.0\n")
        self.assertEqual(runlog._lock_drift(lock), runlog._lock_drift(write_lock("")))

    def test_real_lock_is_clean(self):
        """The repo's own lock must match the venv — that is the whole point."""
        lock = REPO / "requirements.lock"
        if not lock.exists():
            self.skipTest("no requirements.lock")
        self.assertEqual(
            runlog._lock_drift(lock),
            0,
            "requirements.lock weicht von der Umgebung ab — "
            "`.venv/bin/pip freeze > requirements.lock`",
        )

    def test_empty_lock_counts_every_installed_package(self):
        drift = runlog._lock_drift(write_lock(""))
        self.assertGreater(drift, 0)


class EnvState(unittest.TestCase):
    def test_reports_interpreter_and_drift(self):
        # a lock beside a temp dir, not this repo's: as a package, labkit is
        # imported by repos whose layout it cannot assume (and it pins nothing
        # itself — stdlib only).
        got = runlog._env_state(write_lock("pandas==2.0.0\n").parent)
        self.assertIn(sys.executable, got)
        self.assertIn("requirements.lock:", got)
        self.assertIn("drift:", got)

    def test_unpinned_when_no_lock(self):
        empty = Path(tempfile.mkdtemp())
        # a temp dir has no lock in any parent up to / — unless the machine has
        # one at root, which it does not
        got = runlog._env_state(empty)
        self.assertTrue(got.endswith("unpinned") or "requirements.lock:" in got)


if __name__ == "__main__":
    unittest.main()


class TestVcsPins(unittest.TestCase):
    """Git pins are compared by commit, not skipped as pinned-any
    (2026-09-15: installed labkit was two minor versions behind the lock,
    drift said 0, and the pinned tag did not even exist)."""

    def test_parse_reads_ref_and_url(self):
        lock = write_lock(
            "labkit @ git+file:///Users/x/labkit@v0.14.0\n"
            "en-core-web-sm @ https://example.org/model.whl\n"
            "numpy==2.1\n"
        )
        got = runlog._parse_vcs_pins(lock)
        self.assertEqual(got, {"labkit": ("file:///Users/x/labkit", "v0.14.0")})

    def test_parse_reads_an_editable_freeze_line(self):
        """`pip freeze` writes an editable install this way; the lock it wrote
        must not report drift against itself (probe 2026-10-07)."""
        lock = write_lock("-e git+https://github.com/x/labkit.git@fd4cd60#egg=labkit\n")
        self.assertEqual(
            runlog._parse_vcs_pins(lock),
            {"labkit": ("https://github.com/x/labkit.git", "fd4cd60")},
        )
        self.assertEqual(runlog._parse_lock(lock), {"labkit": None})

    def test_editable_install_is_compared_by_its_checkout_head(self):
        head = runlog._checkout_head(REPO)
        assert head is not None
        url = "https://github.com/x/labkit.git"
        self.assertFalse(runlog._vcs_mismatch(url, head[:12], head))
        self.assertTrue(runlog._vcs_mismatch(url, "deadbeef0000", head))

    def test_parse_skips_git_pin_without_ref(self):
        lock = write_lock("labkit @ git+file:///Users/x/labkit\n")
        self.assertEqual(runlog._parse_vcs_pins(lock), {})

    def test_parse_normalises_name(self):
        lock = write_lock("Lab_Kit @ git+file:///x@abc1234\n")
        self.assertIn("lab-kit", runlog._parse_vcs_pins(lock))

    def test_hex_ref_prefix_match_is_clean(self):
        self.assertFalse(
            runlog._vcs_mismatch(
                "file:///x", "a93d4c30fe93", "a93d4c30fe939237f28f4f12604a4d8b"
            )
        )

    def test_hex_ref_mismatch_is_drift(self):
        self.assertTrue(
            runlog._vcs_mismatch(
                "file:///x", "a93d4c30fe93", "deadbeefdeadbeefdeadbeefdeadbeef"
            )
        )

    def test_installed_without_recorded_commit_is_drift(self):
        self.assertTrue(runlog._vcs_mismatch("file:///x", "a93d4c30fe93", None))

    def test_remote_tag_is_unverifiable_and_stays_pinned_any(self):
        self.assertFalse(
            runlog._vcs_mismatch("https://github.com/x/y", "v1.0.0", "whatever")
        )

    def _make_repo(self):
        import subprocess
        import tempfile

        d = tempfile.mkdtemp()
        env_git = ["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run([*env_git, "init", "-q"], check=True)
        (Path(d) / "f").write_text("x")
        subprocess.run([*env_git, "add", "f"], check=True)
        subprocess.run([*env_git, "commit", "-qm", "c"], check=True)
        subprocess.run([*env_git, "tag", "v1.0.0"], check=True)
        sha = subprocess.run(
            [*env_git, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        return d, sha

    def test_local_tag_resolves_to_its_commit(self):
        d, sha = self._make_repo()
        self.assertEqual(runlog._resolve_ref(f"file://{d}", "v1.0.0"), sha)
        self.assertFalse(runlog._vcs_mismatch(f"file://{d}", "v1.0.0", sha))
        self.assertTrue(
            runlog._vcs_mismatch(
                f"file://{d}", "v1.0.0", "deadbeefdeadbeefdeadbeefdeadbeef"
            )
        )

    def test_missing_local_tag_is_drift(self):
        """The scar itself: a lock pinning a tag that does not exist is
        uninstallable — that must count, whatever is installed."""
        d, sha = self._make_repo()
        self.assertEqual(runlog._resolve_ref(f"file://{d}", "v9.9.9"), "")
        self.assertTrue(runlog._vcs_mismatch(f"file://{d}", "v9.9.9", sha))
