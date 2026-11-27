"""A run's start file, `run-starts/<run_id>.json` (`run_starts`): written
whole and durably before the run's block executes, never over a file that
is there, read strictly or refused, left alone by `runlog reindex`, and
never made up for a run that has none. It says which run started with
which protocol, when and as what; which runs reached completion stays the
run index's (tests/test_runs_index.py). What holds a committed start file
against change: tests/test_evidence.py (`CommittedStartFile`,
`TheCommitCarriesTheStartFile`).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from labkit.formats import area_state, run_index, run_starts, runs
from labkit.formats.area_state import state_of
from labkit.formats.run_starts import RunStart, RunStartsError
from labkit.formats.runs import RunKind
from labkit.gates import hook_post_change
from labkit.run import runlog
from protocol_fixture import PID, head

NOON = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
RUN = "2026-11-18T13-00-00_ab12"
TEXT = (
    '{\n  "run_id": "2026-11-18T13-00-00_ab12",\n'
    f'  "protocol_id": "{PID}",\n'
    '  "started_utc": "2026-11-18T12:00:00+00:00",\n'
    '  "run_kind": "measurement"\n}\n'
)


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

    def start_files(self) -> list[str]:
        """The names of the area's start files, sorted."""
        return sorted(p.name for p in (self.area / "run-starts").glob("*.json"))

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
    def test_a_file_written_is_the_file_read(self):
        path = run_starts.write_start(
            self.area, RunStart(RUN, PID, NOON, "measurement")
        )
        self.assertEqual(path, self.area / "run-starts" / f"{RUN}.json")
        self.assertEqual(path.read_text(encoding="utf-8"), TEXT)
        self.assertEqual(
            run_starts.read_starts(self.area),
            {RUN: RunStart(RUN, PID, NOON, "measurement")},
        )
        # whole or not at all: no temporary file is left beside it
        self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])

    def test_no_file_reads_as_no_start(self):
        self.assertEqual(run_starts.read_starts(self.area), {})
        (self.area / "run-starts").mkdir()
        (self.area / "run-starts" / "notes.json").write_text("not a run's")
        self.assertEqual(run_starts.read_starts(self.area), {})

    def test_an_existing_start_file_is_never_overwritten(self):
        """The same run id started twice collides, loudly; the first file
        stands as written."""
        run_starts.write_start(self.area, RunStart(RUN, PID, NOON, "measurement"))
        with self.assertRaises(FileExistsError):
            run_starts.write_start(
                self.area, RunStart(RUN, "p-other", NOON + timedelta(1), "probe")
            )
        self.assertEqual(
            run_starts.start_path(self.area, RUN).read_text(encoding="utf-8"), TEXT
        )
        self.assertEqual(self.start_files(), [f"{RUN}.json"])

    def test_a_file_that_does_not_read_is_an_incomplete_start_not_a_refusal(self):
        """The parser refuses it, naming the file; the area's readers take
        it as that run's incomplete start — every value unknown, none
        defaulted — and the area's state is built all the same."""
        data = json.loads(TEXT)
        for name, text, said in (
            ("no JSON", "{not json", "not JSON"),
            (
                "a key missing",
                json.dumps({k: data[k] for k in list(data)[:3]}),
                "exactly the keys",
            ),
            ("a key too many", json.dumps({**data, "host": "x"}), "exactly the keys"),
            (
                "another run's id",
                json.dumps({**data, "run_id": "2026-11-18T13-00-01_cd34"}),
                "is not the run its name says",
            ),
            (
                "a local time",
                json.dumps({**data, "started_utc": "2026-11-18T13:00:01"}),
                "is no time in UTC",
            ),
            (
                "another zone",
                json.dumps({**data, "started_utc": "2026-11-18T13:00:01+01:00"}),
                "is no time in UTC",
            ),
            (
                "a kind that is none",
                json.dumps({**data, "run_kind": "pilot"}),
                "run_kind = 'pilot'",
            ),
        ):
            with self.subTest(name):
                path = run_starts.start_path(self.area, RUN)
                path.parent.mkdir(exist_ok=True)
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(RunStartsError) as cm:
                    run_starts.parse_start(text, str(path), RUN)
                self.assertIn(said, str(cm.exception))
                self.assertIn(path.name, str(cm.exception))
                (start,) = run_starts.read_starts(self.area).values()
                self.assertEqual(
                    (start.run_id, start.protocol_id, start.started, start.run_kind),
                    (RUN, None, None, None),
                )
                self.assertIn(said, start.unread)
                # never "no run started", and never a refusal of the area
                state = state_of(self.area)
                self.assertEqual(state.unassigned_starts, (RUN,))
                self.assertEqual(state.started_only, {})
                self.assertFalse(state.measured_of(PID).has_measured)

    def test_only_a_complete_start_is_written(self):
        with self.assertRaises(ValueError):
            run_starts.write_start(self.area, RunStart(RUN, PID, None, "measurement"))
        self.assertEqual(run_starts.read_starts(self.area), {})

    def test_which_paths_are_start_files(self):
        self.assertTrue(run_starts.is_start_file(f"run-starts/{RUN}.json"))
        for rel in (
            f"runs/{RUN}/config.json",
            "run-starts/notes.json",
            f"audits/{RUN}.json",
            f"runs/{RUN}.json",
            f"run-starts/{RUN}/x.json",
        ):
            with self.subTest(rel):
                self.assertFalse(run_starts.is_start_file(rel))


class WrittenAtTheStart(_Area):
    def test_a_run_has_its_start_file_before_its_block_runs(self):
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
        assert start.started is not None
        self.assertLessEqual(before, start.started)
        self.assertLessEqual(start.started, run_starts.utc_now())
        # the mark in the run's directory says a start file was written for it
        mark = self.area / "runs" / run.run_id / run_starts.START_MARK
        self.assertEqual(
            mark.read_text(encoding="utf-8"), f"run-starts/{run.run_id}.json\n"
        )
        # outside runs/, which holds the run's directory alone, and the
        # end adds nothing
        self.assertEqual(self.start_files(), [f"{run.run_id}.json"])
        self.assertEqual([p.name for p in (self.area / "runs").iterdir()], [run.run_id])
        self.assertEqual(run_starts.read_starts(self.area), seen[0])
        self.assertIn(run.run_id, run_index.indexed_bindings(self.area))

    def test_a_run_that_breaks_off_keeps_its_start_file_and_gets_no_index_row(self):
        run_id = self.measure(fail=True)
        self.assertEqual(list(run_starts.read_starts(self.area)), [run_id])
        self.assertEqual(run_index.indexed_bindings(self.area), {})

    def test_every_run_kind_gets_its_start_file_and_a_refused_start_none(self):
        """A run of any kind can produce numbers, so each start is recorded
        with what it started as; a start refused before the run directory
        exists leaves no start file."""
        prepared = self.measure(run_kind="preparation")
        measured = self.measure()
        starts = run_starts.read_starts(self.area)
        self.assertEqual(
            {r: s.run_kind for r, s in starts.items()},
            {prepared: "preparation", measured: "measurement"},
        )
        kept = self.start_files()
        (self.area / "PROTOCOL-y.md").write_text(head(repeat_cost="low"))
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            runlog.run("x", {}, self.area, run_kind="measurement")  # two protocols
        self.assertEqual(self.start_files(), kept)

    def test_a_start_file_that_cannot_be_synced_refuses_the_start_and_leaves_no_run(
        self,
    ):
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
        left = [
            p.name for d in ("runs", "run-starts") for p in (self.area / d).iterdir()
        ]
        self.assertEqual(left, [])  # no run directory, no start file, no temp

    def test_a_run_id_whose_start_file_stands_refuses_the_start(self):
        """A run directory deleted, its start file kept, and a new start
        drawing the same id: the start fails loudly, nothing is overwritten
        and no run directory is left."""
        gone = self.measure()
        shutil.rmtree(self.area / "runs" / gone)
        kept = run_starts.start_path(self.area, gone).read_text(encoding="utf-8")
        with (
            mock.patch.object(
                runlog,
                "_make_run_dir",
                side_effect=lambda base: (gone, self._made(base, gone)),
            ),
            self.assertRaises(SystemExit) as cm,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            runlog.run("x", {}, self.area, run_kind="measurement")
        said = str(cm.exception)
        self.assertIn(f"a run with the id {gone} started before", said)
        self.assertIn("never overwritten", said)
        self.assertFalse((self.area / "runs" / gone).exists())
        self.assertEqual(
            run_starts.start_path(self.area, gone).read_text(encoding="utf-8"), kept
        )

    @staticmethod
    def _made(base: Path, run_id: str) -> Path:
        d = runs.run_path(base, run_id)
        d.mkdir(parents=True)
        return d


class ReindexLeavesThem(_Area):
    def test_reindex_keeps_every_start_file_and_invents_none(self):
        """A run whose directory is gone keeps its start file through a
        reindex, and a run from before start files — its file removed here
        — gets none made up from its id or its config.json."""
        gone, old = self.measure(), self.measure()
        run_starts.start_path(self.area, old).unlink()
        shutil.rmtree(self.area / "runs" / gone)
        (self.area / "runs.tsv").unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runlog.reindex(self.area), 0)
        self.assertEqual(self.start_files(), [f"{gone}.json"])
        # the area state: the gone run is one only a start file names
        state = state_of(self.area)
        self.assertEqual(state.started_only, {gone: PID})
        self.assertEqual(state.measured_of(PID).started_only_measurements, (gone,))
        self.assertNotIn(old, state.measured_of(PID).started)


class AStartFileTheRecordNamesAndNobodyFinds(_Area):
    """A run's directory contains the mark that a start file was written. Where
    none is found, that is told as evidence lost — at the hook, and in the
    state every station reads — and not as a start that is merely unknown;
    a marked run with its start file, and a run without a mark, are told
    nothing."""

    def test_a_marked_run_without_its_start_file_is_a_loss_told(self):
        run = self.measure()
        run_starts.start_path(self.area, run).unlink()
        state = state_of(self.area)
        self.assertEqual(state.missing_starts, (run,))
        self.assertEqual(state.measured_of(PID).missing_starts, (run,))
        self.assertEqual(state.measured_of("p-other").missing_starts, ())
        # the run reads and is PID's: nothing here is unassigned
        self.assertEqual(state.measured_of(PID).unassigned_missing_starts, ())
        (line,) = hook_post_change.index_problems(state)
        self.assertIn(f"run {run}: a start file was written for it", line)
        self.assertIn("evidence of its start is lost", line)

    def test_the_twins_a_start_file_that_stands_and_a_run_without_a_mark(self):
        marked, unmarked = self.measure(), self.measure()
        run_starts.start_path(self.area, unmarked).unlink()
        (self.area / "runs" / unmarked / run_starts.START_MARK).unlink()
        state = state_of(self.area)
        self.assertEqual(state.missing_starts, ())
        self.assertIn(marked, state.starts)
        self.assertEqual(hook_post_change.index_problems(state), [])


class ThePostChangeHookTellsThem(_Area):
    """`hook_post_change.index_problems`: a run with a start file that
    started and never completed (its directory stands) and one whose record
    is gone (no directory) are told in words of their own; a run that
    completed is told nothing."""

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
            f"run {broke_off}: started as a measurement (its start file stands) and "
            f"never completed — its directory stands",
            line,
        )
        self.assertNotIn("is gone", line)

    def test_a_run_whose_record_does_not_read_is_not_told_as_never_completed(self):
        """Its start file stands and its record does not read: whether it
        completed is unknown — here it did —, so it is a source that does
        not read, never a run that broke off."""
        done = self.measure()
        record = self.area / "runs" / done / "config.json"
        record.write_text("{", encoding="utf-8")
        state = state_of(self.area)
        self.assertEqual(hook_post_change.unfinished_starts(state), [])
        (line,) = hook_post_change.unread_sources(state)
        self.assertTrue(
            line.startswith(
                f"run {done}: its record does not read — whether it completed is "
                f"unknown, so it is not told as broken off"
            ),
            line,
        )
        self.assertIn(f"{record}: unreadable run metadata", line)
        self.assertNotIn("never completed", line)

    def test_a_run_whose_directory_is_gone_is_a_record_that_is_gone(self):
        """A probe or a preparation too: it binds no registration, and it
        stays visible here."""
        for kind in ("measurement", "preparation"):
            with self.subTest(kind):
                gone = self.measure(fail=True, run_kind=kind)
                shutil.rmtree(self.area / "runs" / gone)
                self.assertTrue(area_state.starts_name_open_runs(self.area))
                line = next(ln for ln in self.problems() if gone in ln)
                self.assertIn(
                    f"run {gone}: its directory is gone — its start file lists it "
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
