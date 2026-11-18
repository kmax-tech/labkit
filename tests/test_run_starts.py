"""The start record of an area, `run-starts.tsv` (`run_starts`): written
durably before a measurement executes, read whole or refused, kept by
`runlog reindex`, and never made up for a run that has none. It answers
which run started with which protocol and when; which runs reached
completion stays the run index's (tests/test_runs_index.py).
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from labkit.formats import area_state, run_index, run_starts, runs
from labkit.formats.area_state import state_of
from labkit.gates import hook_post_change
from labkit.formats.run_starts import RunStart, RunStartsError
from labkit.formats.runs import RunKind
from labkit.run import runlog
from protocol_fixture import PID, head

NOON = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
RUN = "2026-11-18T13-00-00_ab12"


class _Area(unittest.TestCase):
    """An area with one protocol at low repeat cost, outside a repository."""

    def setUp(self) -> None:
        self.area = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.area)
        (self.area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", promises=None)
            + "\n- **Question / hypothesis:** how many?\n",
            encoding="utf-8",
        )
        self.file = self.area / run_starts.RUN_STARTS

    def measure(self, *, fail: bool = False, run_kind: RunKind = "measurement") -> str:
        """One run of RUN_KIND through `runlog.run`; with FAIL it breaks off
        inside the block. Its id."""
        ids: list[str] = []
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                with runlog.run("x", {}, self.area, run_kind=run_kind) as run:
                    ids.append(run.run_id)
                    if fail:
                        raise RuntimeError("broke off")
                    run.metrics(count=1)
            except RuntimeError:
                pass
        return ids[0]


class TheFile(_Area):
    def write(self, start: RunStart) -> None:
        with run_index.index_lock(self.area):
            run_starts.write_start(self.area, start)

    def test_a_row_written_is_the_row_read(self):
        self.write(RunStart(RUN, PID, NOON, "measurement"))
        self.write(
            RunStart(
                "2026-11-18T13-00-01_cd34",
                "",
                NOON + timedelta(seconds=1),
                "measurement",
            )
        )
        self.assertEqual(
            run_starts.read_starts(self.area),
            {
                RUN: RunStart(RUN, PID, NOON, "measurement"),
                "2026-11-18T13-00-01_cd34": RunStart(
                    "2026-11-18T13-00-01_cd34",
                    "",
                    NOON + timedelta(seconds=1),
                    "measurement",
                ),
            },
        )
        self.assertEqual(
            self.file.read_text(encoding="utf-8").splitlines()[:2],
            [
                "run_id\tprotocol_id\tstarted_utc\trun_kind",
                f"{RUN}\t{PID}\t2026-11-18T12:00:00+00:00\tmeasurement",
            ],
        )

    def test_no_file_reads_as_no_start_and_makes_no_lock_file(self):
        self.assertEqual(run_starts.read_starts(self.area), {})
        self.assertEqual([p.name for p in self.area.iterdir()], ["PROTOCOL-x.md"])

    def test_a_file_that_does_not_read_is_refused_naming_the_line(self):
        good = (
            "run_id\tprotocol_id\tstarted_utc\trun_kind\n"
            f"{RUN}\t{PID}\t2026-11-18T12:00:00+00:00\tmeasurement\n"
        )
        other = "2026-11-18T13-00-01_cd34\tp-1"
        for name, text, said in (
            ("other columns", "run_id\tprotocol_id\n", ":1: columns"),
            ("a short row", good + other + "\n", ":3: 2 of 4"),
            (
                "a row without its kind",
                good + other + "\t2026-11-18T13:00:01+00:00\n",
                ":3: 3 of 4",
            ),
            (
                "a kind that is none",
                good + other + "\t2026-11-18T13:00:01+00:00\tpilot\n",
                "run_kind = 'pilot'",
            ),
            (
                "a local time",
                good + other + "\t2026-11-18T13:00:01\tprobe\n",
                "is no time in UTC",
            ),
            (
                "another zone",
                good + other + "\t2026-11-18T13:00:01+01:00\tprobe\n",
                "is no time in UTC",
            ),
            ("a run twice", good + good.splitlines()[1] + "\n", "is listed twice"),
        ):
            with self.subTest(name):
                self.file.write_text(text, encoding="utf-8")
                with self.assertRaises(RunStartsError) as cm:
                    run_starts.read_starts(self.area)
                self.assertIn(said, str(cm.exception))
                self.assertIn(
                    "never delete the row of a run that started", str(cm.exception)
                )
                # the area state refuses with it: no reading as "no run started"
                with self.assertRaises(RunStartsError):
                    state_of(self.area)

    def test_a_run_starts_once(self):
        self.write(RunStart(RUN, PID, NOON, "measurement"))
        with self.assertRaises(RunStartsError) as cm:
            self.write(RunStart(RUN, PID, NOON, "measurement"))
        self.assertIn("already lists", str(cm.exception))


class WrittenAtTheStart(_Area):
    def test_a_measurement_has_its_row_before_its_block_runs(self):
        seen: list[dict[str, RunStart]] = []
        before = run_starts.utc_now()
        with contextlib.redirect_stdout(io.StringIO()):
            with runlog.run("x", {}, self.area, run_kind="measurement") as run:
                seen.append(run_starts.read_starts(self.area))
                run.metrics(count=1)
        (start,) = seen[0].values()
        self.assertEqual(
            (start.run_id, start.protocol_id, start.run_kind),
            (run.run_id, PID, "measurement"),
        )
        self.assertLessEqual(before, start.started)
        self.assertLessEqual(start.started, run_starts.utc_now())
        # the end adds nothing to it: completion is the index's
        self.assertEqual(run_starts.read_starts(self.area), seen[0])
        self.assertIn(run.run_id, run_index.indexed_bindings(self.area))

    def test_a_run_that_breaks_off_keeps_its_row_and_gets_no_index_row(self):
        run_id = self.measure(fail=True)
        self.assertEqual(list(run_starts.read_starts(self.area)), [run_id])
        self.assertEqual(run_index.indexed_bindings(self.area), {})

    def test_every_run_kind_gets_its_row_and_a_refused_start_none(self):
        """A run of any kind can produce numbers, so each start is listed
        with what it started as; a start refused before the run directory
        exists leaves no row."""
        prepared = self.measure(run_kind="preparation")
        measured = self.measure()
        starts = run_starts.read_starts(self.area)
        self.assertEqual(
            {r: s.run_kind for r, s in starts.items()},
            {prepared: "preparation", measured: "measurement"},
        )
        kept = self.file.read_text(encoding="utf-8")
        (self.area / "PROTOCOL-y.md").write_text(head(repeat_cost="low"))
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            runlog.run("x", {}, self.area, run_kind="measurement")  # two protocols
        self.assertEqual(self.file.read_text(encoding="utf-8"), kept)

    def test_a_row_that_cannot_be_synced_refuses_the_start_and_leaves_no_run(self):
        with (
            mock.patch.object(os, "fsync", side_effect=OSError("disk full")),
            self.assertRaises(SystemExit) as cm,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            runlog.run("x", {}, self.area, run_kind="measurement")
        said = str(cm.exception)
        self.assertIn("could not be recorded in", said)
        self.assertIn("disk full", said)
        self.assertIn("the run did not start", said)
        runs_dir = self.area / "runs"
        self.assertEqual(list(runs_dir.iterdir()) if runs_dir.is_dir() else [], [])

    def test_concurrent_starts_lose_no_row(self):
        ids: list[str] = []

        def start(n: int) -> None:
            with run_index.index_lock(self.area):
                run_id = f"2026-11-18T13-00-{n:02d}_ab12"
                run_starts.write_start(
                    self.area, RunStart(run_id, PID, NOON, "measurement")
                )
                ids.append(run_id)

        threads = [threading.Thread(target=start, args=(n,)) for n in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(run_starts.read_starts(self.area)), sorted(ids))
        self.assertEqual(len(ids), 12)


class ReindexKeepsIt(_Area):
    def test_reindex_keeps_every_row_and_invents_none(self):
        """A run whose directory is gone keeps its start row through a
        reindex, and a run from before the start record — its row removed
        here — gets none made up from its id or its config.json."""
        gone, old = self.measure(), self.measure()
        rows = self.file.read_text(encoding="utf-8").splitlines()
        self.file.write_text("\n".join(r for r in rows if old not in r) + "\n")
        kept = self.file.read_text(encoding="utf-8")
        shutil.rmtree(self.area / "runs" / gone)
        (self.area / "runs.tsv").unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runlog.reindex(self.area), 0)
        self.assertEqual(self.file.read_text(encoding="utf-8"), kept)
        self.assertEqual(list(run_starts.read_starts(self.area)), [gone])
        # the area state: the gone run is one only the start record names
        state = state_of(self.area)
        self.assertEqual(state.started_only, {gone: PID})
        self.assertEqual(state.measured_of(PID).started_only, (gone,))
        self.assertNotIn(old, state.measured_of(PID).started)


class ThePostChangeHookTellsThem(_Area):
    """`hook_post_change.index_problems`: a run the start record lists that
    started and never completed (its directory stands) and one whose
    record is gone (no directory) are told in words of their own; a run
    that completed is told nothing."""

    def problems(self) -> list[str]:
        return hook_post_change.index_problems(state_of(self.area))

    def test_the_twin_completed_runs_tell_nothing(self):
        self.measure()
        self.measure(run_kind="preparation")
        self.assertFalse(area_state.starts_name_open_runs(self.area))
        self.assertEqual(self.problems(), [])

    def test_an_abort_whose_directory_stands_is_a_run_that_never_completed(self):
        broke_off = self.measure(fail=True)
        self.assertTrue(area_state.starts_name_open_runs(self.area))
        # the run's recorded pid is this test's own: its process is gone in
        # the case under test
        with mock.patch.object(runs, "is_alive", return_value=False):
            (line,) = self.problems()
        self.assertIn(
            f"run {broke_off}: started as a measurement (run-starts.tsv) and never "
            f"completed — its directory stands",
            line,
        )
        self.assertNotIn("is gone", line)

    def test_a_run_whose_directory_is_gone_is_a_record_that_is_gone(self):
        for kind in ("measurement", "preparation"):
            with self.subTest(kind):
                gone = self.measure(fail=True, run_kind=kind)
                shutil.rmtree(self.area / "runs" / gone)
                self.assertTrue(area_state.starts_name_open_runs(self.area))
                line = next(ln for ln in self.problems() if gone in ln)
                self.assertIn(
                    f"run {gone}: its directory is gone — run-starts.tsv lists it "
                    f"as a {kind} that started, runs.tsv lists no completion",
                    line,
                )
                self.assertNotIn("never completed", line)

    def test_a_run_still_running_is_not_told_as_aborted(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with runlog.run("x", {}, self.area, run_kind="measurement"):
                with mock.patch.object(runs, "is_alive", return_value=True):
                    self.assertEqual(self.problems(), [])
                with mock.patch.object(runs, "is_alive", return_value=None):
                    (line,) = self.problems()
                self.assertIn("whether it still runs cannot be told", line)


if __name__ == "__main__":
    unittest.main()
