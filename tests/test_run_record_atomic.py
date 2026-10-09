"""A run directory exists only with its config.json (0.74.0): everything that
can fail on its own — git, the environment, the model alias — is read
before mkdir, and a failure while writing the record removes the directory.
Before, a failure in between left a directory without config.json that the
listings read as `legacy` ("written before labkit 0.21").

    .venv/bin/python -m pytest tests/test_run_record_atomic.py
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit import runlog


class NoHalfMadeRun(unittest.TestCase):
    def test_a_failure_before_the_record_leaves_no_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            with (
                mock.patch.object(
                    runlog, "_env_state", side_effect=RuntimeError("env")
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(RuntimeError),
            ):
                runlog.Run("t", {}, area)
            self.assertEqual(list((area / "runs").iterdir()), [])

    def test_a_failure_while_writing_the_record_removes_the_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            with (
                mock.patch.object(
                    runlog, "_snapshot_script", side_effect=OSError("disk")
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(OSError),
            ):
                runlog.Run("t", {}, area)
            self.assertEqual(list((area / "runs").iterdir()), [])

    def test_twin_a_run_starts_with_its_record(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                r = runlog.Run("t", {}, area)
            self.assertTrue((r.dir / "config.json").is_file())


if __name__ == "__main__":
    unittest.main()
