"""report-check at the low lane holds the registration to the commit of
the first measurement: the measurements git's history puts first
(`answering_run.first_measurements`) and the commit each record names
(`runs.recorded_commit`). What stood before the number is what that commit
holds; the tree now says nothing about it, and runlog's start gate reads
the tree. A run id is local time, so it orders only runs at one commit.

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): none of the
three labkit agents had committed criterion and admissibility condition
before the first measurement, and every gate was green. The order (A11,
audit 2026-10-27): a run started under `TZ=Etc/GMT+12` sorted before an
earlier one at a commit without the registration and became the first
measurement.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import PID, completed_run, head, scope_file

from labkit.formats import answering_run, protocol_history, runs
from labkit.formats.runs import RunKind
from labkit.gates import report_check

RUN = "2026-10-07T10-00-00_ab12"
REGISTRATION = "- **Question / hypothesis:** does it hold?\n"
BAR = (
    "- **Success / failure criterion:** [C1] accuracy >= 0.8\n"
    "- **Admissibility condition:** [A1] no empty answer\n"
    "- **Null condition / anchors:** [A2] shuffled labels near chance\n"
)
#: the local time zones a counter-test starts its second run under: twelve
#: hours behind UTC (its id sorts before a run started a moment earlier
#: here), one ahead (about this machine's), fourteen ahead (after)
ZONES = ("Etc/GMT+12", "Etc/GMT-1", "Etc/GMT-14")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _report_check(area: Path) -> tuple[int, str]:
    """The other stations stand in: station 1's registration is under test."""
    buf = io.StringIO()
    no_gaps = SimpleNamespace(missing_must=[], must_holes=[])
    with (
        mock.patch.object(report_check, "check_fields", return_value=no_gaps),
        mock.patch.object(report_check, "finalize_area", return_value=0),
        mock.patch.object(report_check, "analysis_audit_gap", return_value=None),
        mock.patch.object(report_check, "limit_gaps", return_value=[]),
        mock.patch.object(report_check, "check_analysis_script", return_value=None),
        contextlib.redirect_stdout(buf),
    ):
        code = report_check.report_check(area)
    return code, buf.getvalue()


@contextlib.contextmanager
def _local_time(zone: str) -> Iterator[None]:
    """The process's local time zone set to ZONE (`time.tzset`), restored after."""
    before = os.environ.get("TZ")
    os.environ["TZ"] = zone
    time.tzset()
    try:
        yield
    finally:
        if before is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = before
        time.tzset()


def _run_id(zone: str, suffix: str) -> str:
    """A run id as runlog draws it now (`runs.RUN_ID_TIME`, local time) under ZONE."""
    with _local_time(zone):
        return time.strftime(runs.RUN_ID_TIME) + "_" + suffix


class _Repository(unittest.TestCase):
    """A repository with the area `experiments/01-x`, its protocol, and runs
    recorded at chosen commits."""

    def setUp(self) -> None:
        root = Path(tempfile.mkdtemp())
        _git(root, "init", "-q", ".")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
        self.area = root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.proto = self.area / "PROTOCOL-x.md"
        self.root = root

    def _commit(self, body: str, kind: str | None = None) -> str:
        """The protocol with BODY, of KIND (the fixture's default when None),
        committed; HEAD's full sha."""
        self.proto.write_text(
            head(repeat_cost="low", result=RUN, kind=kind) + body, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def _run(
        self,
        commit: str | None,
        name: str = RUN,
        *,
        dirty: bool = False,
        run_kind: RunKind = "measurement",
    ) -> Path:
        """A finished run NAME that started at COMMIT (a full sha; None: no
        repository), recorded as runlog records it: `git` the short form,
        `+dirty` with DIRTY, `git_full` the full sha."""
        run = completed_run(
            self.area, name, metrics={"c1_pass": True}, run_kind=run_kind
        )
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["git"] = (
            runs.NO_GIT
            if commit is None
            else commit[:7] + (runs.DIRTY_MARK if dirty else "")
        )
        data["git_full"] = commit or ""
        cfg.write_text(json.dumps(data), encoding="utf-8")
        return run

    def _first(self) -> list[Path]:
        return [
            rd.dir for rd in answering_run.first_measurements(self.area, PID, self.root)
        ]

    def _gaps(self) -> list[str]:
        """The registration station's findings, as report-check prints them."""
        ctx = report_check.checked(self.area, self.proto)
        return [f.line for f in report_check.registration_gaps(ctx)]


class RegistrationAtTheFirstMeasurement(_Repository):
    def test_the_twin_a_registration_committed_before_the_run_passes(self):
        sha = self._commit(REGISTRATION)
        self._run(
            sha, dirty=True
        )  # the tree held more; the commit held the registration
        code, out = _report_check(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_protocol_committed_after_the_first_measurement_blocks(self):
        before = self._commit("")  # a commit without the protocol's registration
        self.proto.unlink()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "no protocol yet")
        sha = _git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(sha, before)
        self._commit(REGISTRATION)  # written and committed after the run below started
        self._run(sha)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"PROTOCOL-x.md was not committed at the first measurement {RUN} "
            f"({sha[:12]})",
            out,
        )

    def test_a_field_written_after_the_first_measurement_blocks(self):
        sha = self._commit("")  # the question not yet written
        self._run(sha)
        self._commit(REGISTRATION)  # the tree (and HEAD) say it now
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"the registration as committed at the first measurement {RUN} "
            f"({sha[:12]}) lacks Question / hypothesis",
            out,
        )
        # the way on (TODO 12a, decided 2026-10-28): exploratory, then a new
        # registration naming it, or a handover
        self.assertIn("that measurement is exploratory", out)
        self.assertIn("[replaces] protocol =", out)
        self.assertIn("hand over:", out)

    def test_a_kind_changed_after_the_first_measurement_blocks(self):
        """Registered and measured as a computation, then turned into a fit
        with its bar written: the bar did not stand before the number. The
        commit is judged by today's kind, and the change is named (review
        2026-10-26: the check read the kind of the commit and was silent)."""
        sha = self._commit(REGISTRATION, kind="compute")
        self._run(sha)
        self._commit(REGISTRATION + BAR, kind="fit")
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"the registration as committed at the first measurement {RUN} "
            f"({sha[:12]}) lacks [protocol] kind = 'fit' (it said 'compute' then), "
            f"Success / failure criterion, Admissibility condition, Null "
            f"condition / anchors",
            out,
        )

    def test_the_twin_a_fit_registered_before_its_first_measurement_passes(self):
        sha = self._commit(REGISTRATION + BAR, kind="fit")
        self._run(sha)
        code, out = _report_check(self.area)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            protocol_history.registration_in_commit(self.proto, sha, "fit"), []
        )

    def test_the_first_measurement_is_the_oldest_full_run_not_the_answering_one(self):
        sha = self._commit("")
        early = self._run(sha, name="2026-10-07T09-00-00_0000")  # without the question
        later = self._commit(REGISTRATION)
        self._run(later)  # the answering run, after the question was written
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("first measurement 2026-10-07T09-00-00_0000", out)
        self.assertEqual(self._first(), [early])

    def test_a_probe_and_a_repeat_are_not_the_first_measurement(self):
        sha = self._commit(REGISTRATION)
        self._run(sha, name="2026-10-07T09-00-00_0000", run_kind="probe")
        self.assertEqual(self._first(), [])
        self._run(sha)
        self.assertEqual(self._first(), [self.area / "runs" / RUN])

    def test_a_committed_head_this_labkit_cannot_read_is_named(self):
        sha = self._commit(REGISTRATION.replace("", ""))
        self.proto.write_text(
            self.proto.read_text(encoding="utf-8").replace(
                'standard = "0.23"', 'standard = "0.21"'
            ),
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "an older standard")
        old = _git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(old, sha)
        (lack,) = protocol_history.registration_in_commit(self.proto, old) or ["?"]
        self.assertIn("a head this labkit reads", lack)
        self.assertIn("0.21", lack)

    def test_a_run_outside_a_repository_recorded_no_commit(self):
        sha = self._commit(REGISTRATION)
        self._run(None)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"the first measurement {RUN} recorded no commit ('no-git')", out)
        self.assertEqual(protocol_history.registration_in_commit(self.proto, sha), [])

    def test_recorded_commit_is_the_full_sha_the_record_names(self):
        def cfg(git: str, git_full: str) -> runs.RunConfig:
            from protocol_fixture import run_record

            return runs.parse_run_config(run_record(git=git, git_full=git_full))

        full = "abc1234" + "0" * 33
        self.assertEqual(runs.recorded_commit(cfg("abc1234", full)), full)
        self.assertEqual(runs.recorded_commit(cfg("abc1234+dirty", full)), full)
        self.assertIsNone(runs.recorded_commit(cfg(runs.NO_GIT, "")))


def _block(null_band: float, sentence: str = "the null lane stays near chance") -> str:
    """A promise block whose [A2] carries NULL_BAND, as the repair case's did."""
    return (
        '[[promise]]\nid = "C1"\nkey = "c1_pass"\nsentence = "the criterion holds"\n'
        'scope = ["scripts/01_measure.py"]\n\n'
        '[[promise]]\nid = "A1"\nkey = "a1_pass"\nsentence = "the yield suffices"\n'
        'scope = ["scripts/01_measure.py"]\n\n'
        f'[[promise]]\nid = "A2"\nkey = "a2_pass"\nsentence = "{sentence}"\n'
        f'scope = ["scripts/01_measure.py"]\nconstants = {{ null_band = {null_band} }}\n'
    )


class RegistrationAsFirstMeasured(_Repository):
    """K3 (docs/notes/2026-10-27-new-registration-contracts.md): the
    answering run holds the registration its protocol's first measurement
    recorded. The repair case (2026-10-27): run 98dd failed [A2] at
    null_band 0.1, the band became 0.15 "to accommodate observed null
    score", and the next run passed."""

    # named before RUN: the answering run is still the newest by name
    FIRST = "2026-10-07T09-25-31_98dd"

    def _register(self, block: str) -> str:
        self.proto.write_text(
            head(repeat_cost="low", result=RUN, promises=block) + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def _changes(self) -> list[str]:
        ctx = report_check.checked(self.area, self.proto)
        return [f.line for f in report_check.registration_changes(ctx)]

    def test_a_bar_moved_after_the_first_measurement_is_held_with_its_way_back(self):
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        later = self._register(_block(0.15))
        self._run(later, RUN)
        (line,) = self._changes()
        self.assertIn(
            f"the registration changed after the first measurement {self.FIRST}", line
        )
        self.assertIn("[A2] null_band 0.1 → 0.15", line)
        self.assertIn(
            f"way out: restore the [[promise]] tables as {self.FIRST} registered", line
        )
        self.assertIn("[A2] null_band 0.1 back", line)
        self.assertIn(f"git show {first[:12]}:experiments/01-x/PROTOCOL-x.md", line)
        self.assertIn("register anew", line)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)

    def test_the_way_back_undoes_every_change_and_then_passes(self):
        """The start state of the repair case: [A3] added and the band raised
        after the first measurement. The way back names both, and taken, it
        releases the protocol — a restore that named only the band left
        [A3] and was held again."""
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        a3 = (
            '\n[[promise]]\nid = "A3"\nkey = "a3_pass"\nsentence = "no leak"\n'
            'scope = ["scripts/01_measure.py"]\n'
        )
        self._run(self._register(_block(0.15) + a3), RUN)
        (line,) = self._changes()
        self.assertIn("[A3] added; [A2] null_band 0.1 → 0.15", line)
        self.assertIn("([A3] out; [A2] null_band 0.1 back)", line)
        self.assertIn('[replaces] protocol = "', line)
        self._run(self._register(_block(0.1)), "2026-10-07T11-00-00_cd34")
        self.assertEqual(self._changes(), [])

    def test_the_twin_a_repair_under_the_same_registration_passes(self):
        """The code changed and measured again under unchanged promises: the
        declared scope's digest moves, the registration does not."""
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# repaired\n")
        _git(self.root, "commit", "-qam", "repair")
        self._run(_git(self.root, "rev-parse", "HEAD"), RUN)
        self.assertEqual(self._changes(), [])

    def test_one_measurement_has_nothing_to_compare(self):
        self._run(self._register(_block(0.1)), RUN)
        self.assertEqual(self._changes(), [])

    def test_a_changed_sentence_is_named_though_its_old_text_is_not_kept(self):
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        self._run(self._register(_block(0.1, "the null lane stays somewhere")), RUN)
        (line,) = self._changes()
        self.assertIn("a promise's sentence", line)
        self.assertIn("git show", line)

    def test_first_measurements_that_disagree_are_held_with_both_ways_out(self):
        """Two runs at one commit with different blocks (the tree differed):
        which registration stood cannot be told, and a run id does not
        settle it — no run answers a registered question. The ways out:
        register anew against each, or hand over (both walked in
        tests/test_replacement.py `ConflictingRegistrations`)."""
        sha = self._register(_block(0.1))
        early = self._run(sha, "2026-10-07T08-00-00_aaaa")
        self.proto.write_text(
            head(repeat_cost="low", result=RUN, promises=_block(0.15)) + REGISTRATION,
            encoding="utf-8",
        )  # not committed: the second run at the same commit saw another block
        later = self._run(sha, "2026-10-07T09-00-00_bbbb")
        self._run(sha, RUN)
        (finding,) = report_check.registration_changes(
            report_check.checked(self.area, self.proto)
        )
        self.assertEqual(finding.grade, report_check.BLOCKER)
        self.assertIn(
            "the first measurements recorded different registrations", finding.line
        )
        self.assertIn(early.name, finding.line)
        self.assertIn(later.name, finding.line)
        self.assertIn('[replaces] protocol = "', finding.line)
        self.assertIn("against each of these registrations", finding.line)
        self.assertIn("or hand over: `labkit-audit <area> --findings`", finding.line)
        self.assertIn("--handover", finding.line)
        self.assertIn("the report names the protocol, not its runs", finding.line)


class FirstMeasurementInGitOrder(_Repository):
    """Git's history orders the measurements, a run id only those at one
    commit (A11, audit 2026-10-27)."""

    def test_a_run_started_under_another_tz_does_not_become_the_first(self):
        """The fault: R0 measured at a commit without the registration (the
        tree held it), the registration was committed, and R1 started under
        each zone. Under Etc/GMT+12 R1's id sorts before R0's, and R1 —
        whose commit holds the registration — was the first measurement."""
        before = self._commit("")
        r0 = self._run(before, _run_id("Etc/GMT-1", "0000"), dirty=True)
        after = self._commit(REGISTRATION)
        for zone in ZONES:
            with self.subTest(zone=zone):
                r1 = self._run(after, _run_id(zone, "ffff"))
                try:
                    code, out = _report_check(self.area)
                    self.assertEqual(code, 1, out)
                    self.assertIn(
                        f"the registration as committed at the first measurement "
                        f"{r0.name} ({before[:12]}) lacks Question / hypothesis",
                        out,
                    )
                    self.assertEqual(self._first(), [r0])
                finally:
                    shutil.rmtree(r1)

    def test_the_twin_registered_before_the_first_passes_under_every_tz(self):
        sha = self._commit(REGISTRATION)
        r0 = self._run(sha, _run_id("Etc/GMT-1", "0000"))
        later = self._commit(REGISTRATION + "- **Unit:** one answer\n")
        for zone in ZONES:
            with self.subTest(zone=zone):
                r1 = self._run(later, _run_id(zone, "ffff"))
                try:
                    self.assertEqual(self._gaps(), [])
                    self.assertEqual(self._first(), [r0])
                finally:
                    shutil.rmtree(r1)

    def test_runs_at_one_commit_share_a_verdict_and_the_earliest_name_stands(self):
        sha = self._commit("")
        self._run(sha, "2026-10-07T09-00-00_0000")
        self._run(
            sha, "2026-10-07T09-00-00_ffff"
        )  # the same second: the suffix is chance
        early = self._run(sha, "2026-10-07T08-00-00_aaaa")
        self.assertEqual(self._first(), [early])
        (gap,) = self._gaps()
        self.assertIn(f"the first measurement {early.name} ({sha[:12]}) lacks", gap)

    def test_diverged_history_holds_the_first_of_each_branch(self):
        """A side branch without the registration: neither commit is an
        ancestor of the other, so git cannot say which run came first, and
        the run on the unregistered branch is held — though it sorts later."""
        base = self._commit("")
        left = self._commit(REGISTRATION)
        _git(self.root, "checkout", "-q", base)
        right = self._commit("- **Unit:** one answer\n")
        on_left = self._run(left, "2026-10-07T09-00-00_0000")
        on_right = self._run(right, "2026-10-07T10-00-00_0000")
        self.assertEqual(self._first(), [on_left, on_right])
        (gap,) = self._gaps()
        self.assertIn(
            f"the registration as committed at the first measurement {on_right.name} "
            f"({right[:12]}; one of 2 that git's history does not order) lacks "
            f"Question / hypothesis",
            gap,
        )

    def test_the_twin_an_amended_registration_commit_passes(self):
        """`git commit --amend` after a run: the run's commit and its
        replacement are not ordered, both are first, both hold the
        registration — no blocker."""
        sha = self._commit(REGISTRATION)
        r1 = self._run(sha, "2026-10-07T09-00-00_0000")
        _git(self.root, "commit", "-q", "--amend", "-m", "amended")
        amended = _git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(amended, sha)
        r2 = self._run(amended, "2026-10-07T10-00-00_0000")
        self.assertEqual(self._first(), [r1, r2])
        self.assertEqual(self._gaps(), [])

    def test_a_commit_the_repository_does_not_hold_is_held(self):
        """Its place cannot be read, so nothing shows another measurement
        came before it — though it sorts after the placed one."""
        sha = self._commit(REGISTRATION)
        placed = self._run(sha, "2026-10-07T09-00-00_0000")
        gone = "0123456789abcdef" * 2 + "01234567"
        lost = self._run(gone, "2026-10-07T10-00-00_0000")
        self.assertEqual(self._first(), [placed, lost])
        (gap,) = self._gaps()
        self.assertIn(
            f"the first measurement {lost.name} ({gone}; one of 2 that git's "
            f"history does not order) recorded a commit this repository does "
            f"not hold",
            gap,
        )

    def test_a_run_without_a_commit_is_held_beside_the_placed_one(self):
        sha = self._commit(REGISTRATION)
        placed = self._run(sha, "2026-10-07T09-00-00_0000")
        unplaced = self._run(None, "2026-10-07T10-00-00_0000")
        self.assertEqual(self._first(), [placed, unplaced])
        (gap,) = self._gaps()
        self.assertIn(
            f"the first measurement {unplaced.name} recorded no commit ('no-git'; "
            f"one of 2 that git's history does not order)",
            gap,
        )


class OutsideARepository(unittest.TestCase):
    def test_a_warning_not_a_blocker(self):
        """As the provenance station: the fixture areas of the other tests
        stand in temp dirs without git, and a lab repo is always one. No
        commit can be placed, so every measurement is first."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", result=RUN) + REGISTRATION, encoding="utf-8"
        )
        run = completed_run(area, RUN, metrics={"c1_pass": True})
        code, out = _report_check(area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "WARNING: not a git repository — the registration cannot be held", out
        )
        self.assertEqual(
            [rd.dir for rd in answering_run.first_measurements(area, PID, None)], [run]
        )


if __name__ == "__main__":
    unittest.main()
