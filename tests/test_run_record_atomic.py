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

from labkit.run import runlog


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

    def test_every_record_file_is_written_whole_or_not_at_all(self) -> None:
        """config, outputs, metrics and completion go through `runs.write_atomic`
        (CODE-013); until 0.94.0 only completion.json did, and a listing that
        read config.json mid-write saw a damaged run (audit 2026-10-15). No
        staging file stays behind."""
        written: list[str] = []
        real = runlog.write_atomic

        def spy(path: Path, text: str) -> None:
            written.append(path.name)
            real(path, text)

        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            out = area / "rows.jsonl"
            out.write_text("{}\n", encoding="utf-8")
            with (
                mock.patch.object(runlog, "write_atomic", spy),
                contextlib.redirect_stdout(io.StringIO()),
                runlog.run("t", {}, area) as r,
            ):
                r.output(out)
                r.metrics(n=1)
            self.assertEqual(
                set(written),
                {"config.json", "outputs.json", "metrics.json", "completion.json"},
            )
            staged = [p.name for p in (area / "runs").rglob(".*tmp*")]
            self.assertEqual(staged, [])

    def test_a_refusal_in_the_start_check_leaves_no_directory(self) -> None:
        """Every refusal of the start check comes before mkdir: an unbound
        full run (the freeze gate), a run index with foreign columns, a
        split leakage — none leaves a run directory behind."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            train = area / "train.jsonl"
            train.write_text('{"id": "a"}\n', encoding="utf-8")
            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                runlog.Run("t", {}, area, long=True)  # unbound full run
            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(RuntimeError, "split leakage"),
            ):
                runlog.Run("t", {}, area, data={"train": train, "test": train})
            (area / "runs.tsv").write_text("foreign\tcolumns\n", encoding="utf-8")
            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(RuntimeError, "runs.tsv columns"),
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
