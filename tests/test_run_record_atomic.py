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
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from labkit.formats import files, runs
from labkit.run import provenance, runlog
from labkit.tools import protocol_fill


_real_strftime = time.strftime


def one_second(fmt: str, *args: object) -> str:
    """`time.strftime` with the run id's time part held to one second: two
    starts that straddle a second boundary collide on nothing, and a test
    of the collision passes or fails with the clock (the hook refused a
    commit on that, 2026-10-23 and 2026-10-25)."""
    if fmt == runlog.RUN_ID_TIME:
        return "2026-10-23T16-30-03"
    return _real_strftime(fmt, *args)  # type: ignore[arg-type]


class NoHalfMadeRun(unittest.TestCase):
    def test_a_failure_before_the_record_leaves_no_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            with (
                mock.patch.object(
                    provenance, "env_state", side_effect=RuntimeError("env")
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
                    runlog, "snapshot_script", side_effect=OSError("disk")
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(OSError),
            ):
                runlog.Run("t", {}, area)
            self.assertEqual(list((area / "runs").iterdir()), [])

    def test_every_record_file_is_written_whole_or_not_at_all(self) -> None:
        """config, outputs, metrics and completion go through `files.write_atomic`
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

    def test_the_other_files_a_run_leaves_are_written_whole_too(self) -> None:
        """failure.json, a raw artefact and the script snapshot took the plain
        path while the architecture said every record file is atomic (audit
        2026-10-23, B2): now they go through `files.write_atomic` /
        `write_atomic_bytes` as well, and no staging file stays behind."""
        written: list[str] = []

        def spy_text(path: Path, text: str) -> None:
            written.append(path.name)
            files.write_atomic(path, text)

        def spy_bytes(path: Path, data: bytes) -> None:
            written.append(path.name)
            files.write_atomic_bytes(path, data)

        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            script = area / "measure.py"  # the snapshot copies sys.argv[0]
            script.write_text("print(1)\n", encoding="utf-8")
            with (
                mock.patch.object(sys, "argv", [str(script)]),
                mock.patch.object(runlog, "write_atomic", spy_text),
                mock.patch.object(runs, "write_atomic", spy_text),
                mock.patch.object(provenance, "write_atomic_bytes", spy_bytes),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(RuntimeError),
                runlog.run("t", {}, area) as r,
            ):
                r.save_raw("reply.txt", "raw")
                raise RuntimeError("the run fails")
            self.assertIn("reply.txt", written)
            self.assertIn("failure.json", written)
            self.assertTrue(
                any(name.startswith("script-source") for name in written), written
            )
            staged = [p.name for p in (area / "runs").rglob(".*tmp*")]
            self.assertEqual(staged, [])

    def test_a_taken_run_id_is_drawn_again(self) -> None:
        """Two starts in one second drew the same suffix and the second
        `mkdir` failed (test_repeats, 2026-10-21): a taken id is redrawn,
        and a free one is kept as drawn — the first draw, no needless redraw."""
        draws = iter(["aaaa0000", "aaaa0000", "bbbb0000"])  # the 2nd collides
        fake = lambda: SimpleNamespace(hex=next(draws))  # noqa: E731
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            with (
                mock.patch.object(runlog.uuid, "uuid4", fake),
                mock.patch.object(runlog.time, "strftime", one_second),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with runlog.run("t", {}, area) as first:
                    pass
                with runlog.run("t", {}, area) as second:
                    pass
            self.assertTrue(first.run_id.endswith("_aaaa"), first.run_id)
            self.assertTrue(second.run_id.endswith("_bbbb"), second.run_id)
            self.assertEqual(len(list((area / "runs").iterdir())), 2)

    def test_every_draw_taken_is_an_error_not_a_loop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "runs").mkdir()
            fake = lambda: SimpleNamespace(hex="cccc0000")  # noqa: E731
            with (
                mock.patch.object(runlog.uuid, "uuid4", fake),
                mock.patch.object(runlog.time, "strftime", one_second),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with runlog.run("t", {}, area):
                    pass
                with self.assertRaises(RuntimeError) as caught:
                    runlog.Run("t", {}, area)
            self.assertIn("every one taken", str(caught.exception))

    def test_a_filled_protocol_is_written_whole_or_not_at_all(self) -> None:
        """protocol-fill's own writes (a field, --prompts, --render, the
        report's result block) go through `files.write_atomic` like the
        write-back of the result (audit 2026-10-23, B2)."""
        written: list[str] = []
        real = files.write_atomic

        def spy(path: Path, text: str) -> None:
            written.append(path.name)
            real(path, text)

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text("- **Unit:** <what one row is>\n", encoding="utf-8")
            with (
                mock.patch.object(files, "write_atomic", spy),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(protocol_fill.main([str(p), "unit", "one row"]), 0)
            self.assertEqual(written, ["PROTOCOL-x.md"])
            self.assertIn("- **Unit:** one row", p.read_text(encoding="utf-8"))

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
                runlog.Run("t", {}, area, run_kind="measurement")  # unbound full run
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
