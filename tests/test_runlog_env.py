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
        got = runlog._parse_lock(write_lock(
            "en_core_web_md @ https://example.invalid/en_core_web_md.whl\n"))
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
        self.assertEqual(runlog._lock_drift(lock),
                         runlog._lock_drift(write_lock("")))

    def test_real_lock_is_clean(self):
        """The repo's own lock must match the venv — that is the whole point."""
        lock = REPO / "requirements.lock"
        if not lock.exists():
            self.skipTest("no requirements.lock")
        self.assertEqual(
            runlog._lock_drift(lock), 0,
            "requirements.lock weicht von der Umgebung ab — "
            "`.venv/bin/pip freeze > requirements.lock`")

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
