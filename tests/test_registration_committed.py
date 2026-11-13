"""report-check at the low lane holds the registration to the commit of
the first measurement: the measurements git's history puts first
(`area_state.Measured.firsts`) and the commit each record names
(`runs.recorded_commit`). What stood before the number is what that commit
holds; the tree now says nothing about it, and runlog's start gate reads
the tree. A run id is local time, so it orders only runs at one commit:
a run started under `TZ=Etc/GMT+12` never sorts itself before an earlier
one at a commit without the registration.
"""

from __future__ import annotations

import pytest

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

from labkit.gates import registered_report
from labkit.gates import registration_hold
from labkit.tools import next_command, report_command
from labkit.formats import area_state, gate, protocol_history, runs
from labkit.formats import protocol_block
from labkit.formats.gate import BLOCKER, VIOLATED, Findings
from labkit.formats.runs import RunKind
from labkit.gates import finalize, report_check, report_hold
from labkit.gates import report_context

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

RUN = "2026-10-07T10-00-00_ab12"
REGISTRATION = "- **Question / hypothesis:** does it hold?\n"
BAR = (
    "- **Inference criterion:** [criterion-1] accuracy >= 0.8\n"
    "- **Quality check:** [quality-check-1] no empty answer\n"
    "- **Null condition / anchors:** [quality-check-2] shuffled labels near chance\n"
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
    no_gaps = SimpleNamespace(must_gaps=[], must_holes=[], repeated=[])
    with (
        mock.patch.object(report_check, "check_fields", return_value=no_gaps),
        mock.patch.object(report_check, "finalize_area", return_value=0),
        mock.patch.object(report_check, "analysis_audit_gap", return_value=None),
        mock.patch.object(report_check, "limit_gaps", return_value=[]),
        mock.patch.object(report_check, "check_analysis_script", return_value=None),
        contextlib.redirect_stdout(buf),
    ):
        code = report_check.protocol_verdict(area).exit
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
            self.area, name, metrics={"criterion_1_pass": True}, run_kind=run_kind
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
        return [rd.dir for rd in area_state.state_of(self.area).measured_of(PID).firsts]

    def _gaps(self) -> list[str]:
        """The registration station's findings, as report-check prints them."""
        ctx = report_context.checked(self.area, self.proto)
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

    def test_a_protocol_renamed_after_the_first_measurement_stood_before_it(self):
        """The id binds, not the path: a protocol renamed and moved since its
        first measurement is found in that commit by its id."""
        sha = self._commit(REGISTRATION)
        self._run(sha)
        _git(
            self.root,
            "mv",
            "experiments/01-x/PROTOCOL-x.md",
            "experiments/01-x/PROTOCOL-y.md",
        )
        _git(self.root, "commit", "-qm", "rename")
        self.proto = self.area / "PROTOCOL-y.md"
        self.assertEqual(self._gaps(), [])
        then = protocol_history.committed_at(
            self.proto,
            area_state.state_of(self.area).measured_of(PID).firsts[0],
            self.root,
        )
        self.assertIsNone(then.cause)
        self.assertIn("does it hold?", then.text or "")
        # what the run saw reads back too, where the comparisons read it
        rd = area_state.state_of(self.area).measured_of(PID).firsts[0]
        text, where = protocol_history.as_measured(self.proto, rd, self.root)
        self.assertIn("does it hold?", text or "", where)

    def test_the_twin_a_rename_finds_nothing_when_no_protocol_carried_the_id(self):
        before = self._commit("")
        self.proto.unlink()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "no protocol yet")
        sha = _git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(sha, before)
        self._commit(REGISTRATION)
        self._run(sha)
        self.assertIsNone(protocol_history.protocol_path_at(self.root, sha, PID))

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
        # the way on: exploratory, then a new
        # registration naming it, or a handover
        self.assertIn("that measurement is exploratory", out)
        self.assertIn("[replaces] protocol =", out)
        self.assertIn("hand over:", out)

    def test_a_kind_changed_after_the_first_measurement_blocks(self):
        """Registered and measured as a computation, then turned into a fit
        with its bar written: the bar did not stand before the number. The
        commit is judged by today's kind, not its own, and the change is
        named."""
        sha = self._commit(REGISTRATION, kind="compute")
        self._run(sha)
        self._commit(REGISTRATION + BAR, kind="fit")
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"the registration as committed at the first measurement {RUN} "
            f"({sha[:12]}) lacks [protocol] kind = 'fit' (it said 'compute' then), "
            f"Inference criterion, Quality check, Null "
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
                'standard = "0.28"', 'standard = "0.21"'
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
        # the record says the run started outside the history
        ctx = report_context.checked(self.area, self.proto)
        (gap,) = report_check.registration_gaps(ctx)
        self.assertEqual(gap.rule, report_check.LAB_010)
        # the line cites the rule the finding records, and no other
        self.assertIn("(LAB-010 Commit before the run). Next: ", gap.line)
        self.assertNotIn("LAB-003", gap.line)

    def test_a_record_that_names_no_commit_cites_no_rule(self):
        """A record without a commit that does not say `no-git`: the basis
        is unknown, a technical contract — the sentence names no rule."""
        self._commit(REGISTRATION)
        run = self._run(None)
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["git"] = "abc1234"
        cfg.write_text(json.dumps(data), encoding="utf-8")
        ctx = report_context.checked(self.area, self.proto)
        (gap,) = report_check.registration_gaps(ctx)
        self.assertEqual(gap.rule, gate.TECHNICAL_RULE)
        self.assertIn("recorded no commit ('abc1234')", gap.text)
        self.assertNotIn("LAB-", gap.text)

    def test_recorded_commit_is_the_full_sha_the_record_names(self):
        def cfg(git: str, git_full: str) -> runs.RunConfig:
            from protocol_fixture import run_record

            return runs.parse_run_config(run_record(git=git, git_full=git_full))

        full = "abc1234" + "0" * 33
        self.assertEqual(runs.recorded_commit(cfg("abc1234", full)), full)
        self.assertEqual(runs.recorded_commit(cfg("abc1234+dirty", full)), full)
        self.assertIsNone(runs.recorded_commit(cfg(runs.NO_GIT, "")))


class CommittedAtTheFirstMeasurement(_Repository):
    """`protocol_history.committed_at`: the one reading of the protocol a
    first measurement's commit holds, shared by the registration station and
    the registered report's binding — read, or one of three causes."""

    def _at(self, run: Path) -> protocol_history.CommittedAt:
        (rd,) = area_state.state_of(self.area).measured_of(PID).firsts
        self.assertEqual(rd.dir, run)
        return protocol_history.committed_at(self.proto, rd, self.root)

    def test_the_protocol_as_committed_is_read(self):
        commit = self._commit("- **Question / hypothesis:** q\n")
        self.proto.write_text("changed since\n", encoding="utf-8")
        at = self._at(self._run(commit))
        self.assertIsNone(at.cause)
        self.assertEqual(at.commit, commit)
        self.assertIn("**Question / hypothesis:** q", at.text or "")

    def test_no_commit_an_unknown_commit_and_an_uncommitted_protocol(self):
        self._commit("- **Question / hypothesis:** q\n")
        run = self._run(None)
        self.assertEqual(self._at(run).cause, protocol_history.NO_COMMIT)
        shutil.rmtree(run)
        run = self._run("0" * 40)
        at = self._at(run)
        self.assertEqual(at.cause, protocol_history.UNKNOWN_COMMIT)
        self.assertIsNone(at.text)
        shutil.rmtree(run)
        _git(self.root, "rm", "-q", "--cached", str(self.proto))
        _git(self.root, "commit", "-qm", "protocol untracked")
        commit = _git(self.root, "rev-parse", "HEAD")
        self.assertEqual(
            self._at(self._run(commit)).cause, protocol_history.NOT_COMMITTED
        )


def _block(null_band: float, sentence: str = "the null lane stays near chance") -> str:
    """A promise block whose [quality-check-2] carries NULL_BAND, as the repair case's did."""
    return (
        '[[promise]]\nid = "criterion-1"\nkey = "criterion_1_pass"\nsentence = "the criterion holds"\n'
        'scope = ["scripts/01_measure.py"]\n\n'
        '[[promise]]\nid = "quality-check-1"\nkey = "quality_check_1_pass"\nsentence = "the yield suffices"\n'
        'scope = ["scripts/01_measure.py"]\n\n'
        f'[[promise]]\nid = "quality-check-2"\nkey = "quality_check_2_pass"\nsentence = "{sentence}"\n'
        f'scope = ["scripts/01_measure.py"]\nconstants = {{ null_band = {null_band} }}\n'
    )


def _registration_changes(area: Path, proto: Path) -> list:
    """finalize's registration station on the answering run report-check
    chooses."""
    ctx = report_context.checked(area, proto)
    return registration_hold.registration_changes(
        ctx.area, ctx.protocol, ctx.head.id, ctx.run, ctx.area_state, ctx.evidence
    )


def _measured(protocol: Path, text: str) -> area_state.Measured:
    """What PROTOCOL's area measured of the protocol TEXT's head names."""
    return area_state.state_of(protocol.parent).measured_of(
        protocol_block.head(text).id
    )


class RegistrationAsFirstMeasured(_Repository):
    """K3 (docs/notes/2026-10-27-new-registration-contracts.md): the
    answering run holds the registration its protocol's first measurement
    recorded. The repair case: run 98dd fails [quality-check-2] at
    null_band 0.1, the band becomes 0.15 "to accommodate observed null
    score", and the next run passes — held."""

    # named before RUN: the answering run is still the newest by name
    FIRST = "2026-10-07T09-25-31_98dd"

    def _register(self, block: str, result: str = RUN) -> str:
        """Commit the protocol with BLOCK as its promises, adopting RESULT —
        the run the checks then hold (`answering_run.bound_answering_run`)."""
        self.proto.write_text(
            head(repeat_cost="low", result=result, promises=block) + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def _changes(self) -> list[str]:
        return [f.line for f in _registration_changes(self.area, self.proto)]

    def test_a_bar_moved_after_the_first_measurement_is_held_with_its_way_back(self):
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        later = self._register(_block(0.15))
        self._run(later, RUN)
        (line,) = self._changes()
        self.assertIn(
            f"the registration changed after the first measurement {self.FIRST}", line
        )
        self.assertIn("[quality-check-2] null_band 0.1 → 0.15", line)
        self.assertIn(
            f"Next: restore the [[promise]] tables as {self.FIRST} registered", line
        )
        self.assertIn("[quality-check-2] null_band 0.1 back", line)
        self.assertIn(f"git show {first[:12]}:experiments/01-x/PROTOCOL-x.md", line)
        self.assertIn("register anew", line)

    def test_the_way_back_undoes_every_change_and_then_passes(self):
        """The start state of the repair case: [quality-check-3] added and the band raised
        after the first measurement. The way back names both, and taken, it
        releases the protocol — a restore of the band alone would leave
        [quality-check-3] and be held again."""
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        a3 = (
            '\n[[promise]]\nid = "quality-check-3"\nkey = "quality_check_3_pass"\nsentence = "no leak"\n'
            'scope = ["scripts/01_measure.py"]\n'
        )
        self._run(self._register(_block(0.15) + a3), RUN)
        (line,) = self._changes()
        self.assertIn(
            "[quality-check-2] null_band 0.1 → 0.15; [quality-check-3] added", line
        )
        self.assertIn(
            "([quality-check-2] null_band 0.1 back; [quality-check-3] out)", line
        )
        self.assertIn('[replaces] protocol = "', line)
        repaired = "2026-10-07T11-00-00_cd34"
        self._run(self._register(_block(0.1), result=repaired), repaired)
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

    def test_a_changed_sentence_is_named_from_the_texts_both_runs_saw(self):
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        self._run(self._register(_block(0.1, "the null lane stays somewhere")), RUN)
        (line,) = self._changes()
        self.assertIn(
            '[quality-check-2] sentence "the null lane stays near chance" → '
            '"the null lane stays somewhere"',
            line,
        )
        self.assertIn(
            '[quality-check-2] sentence "the null lane stays near chance" back', line
        )
        self.assertIn("git show", line)

    def test_a_sentence_and_a_bar_changed_together_are_both_named(self):
        """The margin and the sentence changed in one edit: the hold names
        both, so a restore of the constant alone is not held a second time for
        the sentence."""
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        self._run(self._register(_block(0.15, "within the calibrated band")), RUN)
        (line,) = self._changes()
        self.assertIn(
            '[quality-check-2] sentence "the null lane stays near chance" → '
            '"within the calibrated band"; [quality-check-2] null_band 0.1 → 0.15',
            line,
        )
        self.assertIn(
            '([quality-check-2] sentence "the null lane stays near chance" back; '
            "[quality-check-2] null_band 0.1 back)",
            line,
        )
        # restored as told, nothing is left to hold
        repaired = "2026-10-07T11-00-00_cd34"
        self._run(self._register(_block(0.1), result=repaired), repaired)
        self.assertEqual(self._changes(), [])

    def test_unread_sentences_are_said_with_what_the_records_hold(self):
        """A first measurement whose commit this clone does not hold: the
        constants come from the run records, and the hold says why the
        sentences are not named."""
        first = self._register(_block(0.1))
        # the first run saw a sentence its commit does not hold, and kept no patch
        self.proto.write_text(
            head(repeat_cost="low", result=RUN, promises=_block(0.1, "uncommitted"))
            + REGISTRATION,
            encoding="utf-8",
        )
        self._run(first, self.FIRST, dirty=True)
        self._run(self._register(_block(0.15)), RUN)
        lines = self._changes()
        (line,) = [ln for ln in lines if "null_band" in ln]
        self.assertIn("[quality-check-2] null_band 0.1 → 0.15", line)
        self.assertIn("the sentences unread (its first measurement", line)
        self.assertIn("cannot be read back", line)
        # what the number is about could not be compared either: held on its
        # own, never read as unchanged (tests/test_unread_registration.py)
        self.assertTrue(
            any("cannot be compared with its first measurement" in ln for ln in lines),
            lines,
        )

    def test_finalize_holds_it_after_the_run_not_first_at_the_adoption(self):
        first = self._register(_block(0.1))
        self._run(first, self.FIRST)
        self._run(self._register(_block(0.15)), RUN)
        collected = Findings(tell=None)
        self.assertEqual(finalize.finalize_area(self.area, self.proto, collected), 1)
        self.assertTrue(
            any(
                "the registration changed after the first measurement" in line
                for line in collected.blocked
            ),
            collected.blocked,
        )

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
        found = _registration_changes(self.area, self.proto)
        (finding,) = [f for f in found if "different registrations" in f.line]
        # the later run's text is not its commit's: what the number is about
        # cannot be compared with it, held on its own
        self.assertTrue(
            any(
                "cannot be compared with its first measurement" in f.line for f in found
            ),
            [f.line for f in found],
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


#: a computation's scope as a protocol registers it: all roads
ALL_ROADS = (
    "- **Question / hypothesis:** the deforested share within 5.5 km of the roads\n"
    "- **Data / scope:** roads.geojson and deforestedArea.geojson\n"
    "- **Exclusions / filters:** areas outside the buffer\n"
    "- **Unit:** a fraction of the buffer's area\n"
)
REFERENCE = 'value = 0.62\ntolerance = 0.01\nrelation = "within"\n'


class ScopeAsFirstMeasured(_Repository):
    """What a number is about holds from its first measurement on, at every
    kind (docs/notes/2026-10-31-scope-frozen.md). The case: all roads give
    0.4749 against a stated 0.62; the roads are then filtered to BR highways
    in the script and in Data / scope and Exclusions / filters, and the next
    run gives 0.6259 — a computation has no promise block, so the fields
    themselves are held."""

    FIRST = "2026-10-07T09-25-31_98dd"

    def _register(
        self,
        fields: str,
        reference: str = REFERENCE,
        result: str = RUN,
        kept: tuple[str, str] = ("percentage_deforestation", "1"),
    ) -> str:
        self.proto.write_text(
            head(
                repeat_cost="low",
                kind="compute",
                promises=None,
                reference=reference,
                result=result,
                kept=kept,
            )
            + fields,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def _changes(self) -> list[str]:
        return [f.line for f in _registration_changes(self.area, self.proto)]

    def test_the_scope_rewritten_after_a_missed_measurement_is_held_with_its_way_back(
        self,
    ):
        self._run(self._register(ALL_ROADS), self.FIRST)
        narrowed = ALL_ROADS.replace(
            "roads.geojson and", "roads.geojson (BR highways only) and"
        ).replace(
            "areas outside the buffer",
            "roads other than BR highways; areas outside the buffer",
        )
        later = self._register(narrowed)
        self._run(later, RUN)
        (line,) = self._changes()
        self.assertIn(
            f"what the number is about changed after the first measurement {self.FIRST}",
            line,
        )
        self.assertIn(
            'Data / scope "roads.geojson and deforestedArea.geojson" → "roads.geojson (BR highways only)',
            line,
        )
        self.assertIn("Exclusions / filters", line)
        self.assertIn(
            f"Next: restore Data / scope, Exclusions / filters as {self.FIRST} registered them",
            line,
        )
        self.assertIn("register anew", line)

    def test_a_reference_moved_after_the_first_measurement_is_held(self):
        self._run(self._register(ALL_ROADS), self.FIRST)
        self._run(
            self._register(ALL_ROADS, reference=REFERENCE.replace("0.62", "0.48")), RUN
        )
        (line,) = self._changes()
        self.assertIn("[reference]", line)
        self.assertIn("value = 0.62", line)
        self.assertIn("value = 0.48", line)

    def test_the_kept_key_named_anew_after_the_first_measurement_is_held(self):
        self._run(self._register(ALL_ROADS), self.FIRST)
        self._run(self._register(ALL_ROADS, kept=("roads_total", "1")), RUN)
        (line,) = self._changes()
        self.assertIn("[kept]", line)
        self.assertIn('key = "percentage_deforestation"', line)
        self.assertIn('key = "roads_total"', line)

    def test_a_first_measurement_whose_reference_did_not_read_yet_still_holds_the_fields(
        self,
    ):
        """The first runs started on a commit whose [reference] does not
        parse, the table repaired, the fields rewritten later: the fields are
        compared whatever the head held then, and the comparison is a hold
        of its own."""
        broken = (
            'value = 0.62\ntolerance = 0.01\nrelation = "within"\nunit = "fraction"\n'
        )
        self._run(self._register(ALL_ROADS, reference=broken), self.FIRST)
        narrowed = ALL_ROADS.replace(
            "roads.geojson and", "roads.geojson (BR highways only) and"
        )
        self._run(self._register(narrowed), RUN)
        fields, comparison = self._changes()
        self.assertIn("Data / scope", fields)
        self.assertNotIn("[reference]", fields)
        self.assertIn("[reference]", comparison)
        self.assertIn("does not read", comparison)

    def test_a_reference_moved_together_with_a_field_is_two_holds(self):
        """Each cause under the rule that names it, each a blocker with its
        own way back; finalize holds on both."""
        self._run(self._register(ALL_ROADS), self.FIRST)
        narrowed = ALL_ROADS.replace(
            "roads.geojson and", "roads.geojson (BR highways only) and"
        )
        self._run(
            self._register(narrowed, reference=REFERENCE.replace("0.62", "0.48")), RUN
        )
        fields, comparison = _registration_changes(self.area, self.proto)
        self.assertEqual(
            [(f.grade, f.rule, f.outcome) for f in (fields, comparison)],
            [
                (BLOCKER, registration_hold.LAB_003, VIOLATED),
                (BLOCKER, registration_hold.LAB_035, VIOLATED),
            ],
        )
        self.assertIn(
            f"Next: restore Data / scope as {self.FIRST} registered them", fields.line
        )
        self.assertNotIn("[reference]", fields.line)
        self.assertIn(
            f"Next: restore [reference] as {self.FIRST} registered them",
            comparison.line,
        )
        self.assertIn("value = 0.48", comparison.line)

    def test_the_twin_a_script_repaired_under_the_same_scope_passes(self):
        """The code changed and measured again under unchanged fields: what
        the run computes is the analysis audit's question, not this hold's."""
        self._run(self._register(ALL_ROADS), self.FIRST)
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# repaired\n")
        _git(self.root, "commit", "-qam", "repair")
        self._run(_git(self.root, "rev-parse", "HEAD"), RUN)
        self.assertEqual(self._changes(), [])

    def test_the_twin_generated_counts_and_reflowed_lines_are_no_change(self):
        """`protocol-fill --data-counts` writes its part into Data / scope after
        the prepare run, and an editor may reflow a value: neither changes
        what the number is about."""
        self._run(self._register(ALL_ROADS), self.FIRST)
        counted = ALL_ROADS.replace(
            "roads.geojson and deforestedArea.geojson\n",
            "roads.geojson and\n  deforestedArea.geojson · counts (prepare run "
            "2026-10-07T09-00-00_aaaa): read roads.geojson 27662 lines; 27662 items prepared\n",
        )
        self._run(self._register(counted), RUN)
        self.assertEqual(self._changes(), [])

    def test_the_twin_one_measurement_has_nothing_to_compare(self):
        self._run(self._register(ALL_ROADS), RUN)
        self.assertEqual(self._changes(), [])

    def _rewrite(self, old: str, new: str) -> None:
        """The protocol in the tree with OLD replaced by NEW — no run after."""
        text = self.proto.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.proto.write_text(text.replace(old, new), encoding="utf-8")

    def test_a_field_rewritten_after_the_last_measurement_is_held_before_any_run(
        self,
    ):
        """The Unit rewritten after the one measurement, then an audit of
        that run on the new text — no run saw the change. The protocol as it
        stands is held to the first measurement too."""
        self._run(self._register(ALL_ROADS), RUN)
        self._rewrite("a fraction of the buffer's area", "a share of the buffer")
        (line,) = self._changes()
        self.assertIn(
            f"what the number is about changed after the first measurement {RUN}: "
            'Unit "a fraction of the buffer\'s area" → "a share of the buffer" '
            "(as the protocol stands now; no run measured under it yet)",
            line,
        )
        self.assertIn(f"Next: restore Unit as {RUN} registered them", line)
        self.assertIn("the runs measured under them stay", line)
        self.assertIn("register anew", line)

    def test_the_twin_the_field_restored_passes(self):
        self._run(self._register(ALL_ROADS), RUN)
        self._rewrite("a fraction of the buffer's area", "a share of the buffer")
        self._rewrite("a share of the buffer", "a fraction of the buffer's area")
        self.assertEqual(self._changes(), [])

    def test_the_twin_a_conclusion_rewritten_after_the_run_passes(self):
        """What the Summary says after the run is not what the number is about."""
        self._run(
            self._register(
                ALL_ROADS + "- **Conclusion:** about a third is deforested\n"
            ),
            RUN,
        )
        self._rewrite("about a third is deforested", "0.47 of the buffer is deforested")
        self.assertEqual(self._changes(), [])

    def test_the_twin_a_reflowed_field_in_the_tree_passes(self):
        self._run(self._register(ALL_ROADS), RUN)
        self._rewrite(
            "a fraction of the buffer's area", "a fraction of\n  the buffer's area"
        )
        self.assertEqual(self._changes(), [])

    def test_a_change_measured_then_restored_in_the_tree_stays_held_by_the_run(self):
        """The run snapshot is still compared: a run measured under the change
        answers no registered question, whatever the tree says now."""
        self._run(self._register(ALL_ROADS), self.FIRST)
        self._run(self._register(ALL_ROADS.replace("5.5 km", "2.75 km")), RUN)
        self._rewrite("2.75 km", "5.5 km")
        (line,) = self._changes()
        self.assertIn(f"(as the answering run {RUN} saw the protocol)", line)

    def test_finalize_holds_it(self):
        self._run(self._register(ALL_ROADS), self.FIRST)
        self._run(self._register(ALL_ROADS.replace("5.5 km", "2.75 km")), RUN)
        collected = Findings(tell=None)
        self.assertEqual(finalize.finalize_area(self.area, self.proto, collected), 1)
        self.assertTrue(
            any(
                "what the number is about changed after the first measurement" in line
                for line in collected.blocked
            ),
            collected.blocked,
        )


class FirstMeasurementInGitOrder(_Repository):
    """Git's history orders the measurements, a run id only those at one
    commit."""

    def test_a_run_started_under_another_tz_does_not_become_the_first(self):
        """R0 measured at a commit without the registration (the tree held
        it), the registration committed, and R1 started under each zone.
        Under Etc/GMT+12 R1's id sorts before R0's; R0 stays the first
        measurement, though R1's commit holds the registration."""
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
        the run on the branch without the registration is held — though it
        sorts later."""
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

    def test_git_evidence_gone_or_unreadable_cites_no_rule(self):
        """A commit the repository does not hold, and one it cannot read:
        the check lacks its basis, a technical contract — neither sentence
        names a rule of the standard."""
        sha = self._commit(REGISTRATION)
        self._run("0123456789abcdef" * 2 + "01234567")
        ctx = report_context.checked(self.area, self.proto)
        (unknown,) = report_check.registration_gaps(ctx)
        self.assertIn("does not hold", unknown.text)
        unreadable = protocol_history.CommittedAt(
            run=RUN,
            commit=sha,
            text=None,
            cause=protocol_history.UNREADABLE_COMMIT,
            detail="fatal: bad object",
        )
        with mock.patch.object(report_check, "committed_at", return_value=unreadable):
            (unread,) = report_check.registration_gaps(ctx)
        self.assertIn("cannot be read: fatal: bad object", unread.text)
        for gap in (unknown, unread):
            self.assertEqual(gap.rule, gate.TECHNICAL_RULE)
            self.assertNotIn("LAB-", gap.text)

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
        run = completed_run(area, RUN, metrics={"criterion_1_pass": True})
        code, out = _report_check(area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "WARNING: not a git repository — the registration cannot be held", out
        )
        self.assertEqual(
            [rd.dir for rd in area_state.state_of(area).measured_of(PID).firsts], [run]
        )


if __name__ == "__main__":
    unittest.main()


class ReportRegisteredBeforeTheFirstMeasurement(_Repository):
    """The report a protocol registered before its first measurement is
    bound to what that measurement's commit holds
    (`registered_report.report_binding_gap`): dropped or moved since, held; the
    same on both lanes. Both selections reach the
    protocol: by its area where the head no longer names the report, and by
    the former report path where only that file changes
    (`registered_report.formerly_registering`). Each with its correct twin."""

    REPEAT_COST = "low"

    def _register(
        self,
        report: str | None,
        *,
        result: str | None = None,
        repeat_cost: str | None = None,
    ) -> str:
        """The protocol registering REPORT, committed; HEAD's full sha."""
        repeat_cost = repeat_cost or self.REPEAT_COST
        self.proto.write_text(
            head(
                repeat_cost=repeat_cost,
                frozen=repeat_cost == "high",
                result=result,
                report=report,
            )
            + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "HEAD")

    def _head_now(self, report: str | None, repeat_cost: str | None = None) -> str:
        """The protocol's text with its head registering REPORT now (tree)."""
        repeat_cost = repeat_cost or self.REPEAT_COST
        text = (
            head(repeat_cost=repeat_cost, frozen=repeat_cost == "high", report=report)
            + REGISTRATION
        )
        self.proto.write_text(text, encoding="utf-8")
        return text

    def _gap(self, text: str) -> str | None:
        gap = registered_report.report_binding_gap(
            self.proto, text, measured=_measured(self.proto, text)
        )
        return None if gap is None else gap.text + " | " + (gap.fix or "")

    def test_the_twin_unchanged_passes(self):
        self._run(self._register("REPORT.md"))
        self.assertIsNone(self._gap(self._head_now("REPORT.md")))
        self.assertIsNone(self._gap(self._head_now("./REPORT.md")))

    def test_a_report_dropped_after_the_first_measurement_is_held(self):
        self._run(self._register("REPORT.md"))
        gap = self._gap(self._head_now(None))
        assert gap is not None
        self.assertIn(
            f"registered REPORT.md as its report before its first measurement {RUN}",
            gap,
        )
        self.assertIn("now registers none", gap)
        self.assertIn('restore `report = "REPORT.md"`', gap)
        self.assertIn("--handover", gap)
        # restored: nothing
        self.assertIsNone(self._gap(self._head_now("REPORT.md")))

    def test_a_report_moved_after_the_first_measurement_passes(self):
        """The duty hangs on the protocol's id, not on the report's path:
        another file takes it over."""
        self._run(self._register("REPORT.md"))
        self.assertIsNone(self._gap(self._head_now("docs/OTHER.md")))

    def test_a_report_entered_after_the_first_measurement_may_go_again(self):
        """What binds for good is the promise given before the result was
        known. A later entry is held while the head names it; committed or
        not, taking it out again ends that, by the hook or past it."""
        self._run(self._register(None))
        self.assertIsNone(self._gap(self._head_now("REPORT.md")))
        self.assertIsNone(self._gap(self._head_now(None)))
        for report, said in (("REPORT.md", "entered late"), (None, "removed")):
            self._head_now(report)
            _git(self.root, "add", "-A")
            _git(self.root, "commit", "-qm", said, "--no-verify")
            self.assertIsNone(self._gap(self.proto.read_text(encoding="utf-8")))

    def test_the_twin_a_report_removed_before_the_first_measurement_binds_nothing(
        self,
    ):
        self._register("REPORT.md")
        self._run(self._register(None))
        self.assertIsNone(self._gap(self.proto.read_text(encoding="utf-8")))

    def test_the_twin_a_report_committed_before_any_measurement_binds_nothing(self):
        self._register("REPORT.md")
        self.assertIsNone(self._gap(self._head_now(None)))

    def test_switching_to_high_does_not_remove_the_binding(self):
        self._run(self._register("REPORT.md", repeat_cost="low"))
        self.assertIsNotNone(self._gap(self._head_now(None, repeat_cost="high")))

    def test_a_first_measurement_whose_registration_does_not_read_is_no_no_duty(
        self,
    ):
        """Its commit is not in the repository: what it registered cannot
        be read, and a head without a report is then a check not
        executable — with its two ways out told apart."""
        self._register("REPORT.md")
        self._run("0" * 40)  # a commit this clone does not hold
        # a head that registers a report drops no duty, whatever stood then
        self.assertIsNone(self._gap(self._head_now("REPORT.md")))
        text = self._head_now(None)
        gap = registered_report.report_binding_gap(
            self.proto, text, measured=_measured(self.proto, text)
        )
        assert gap is not None
        self.assertEqual(
            (gap.rule, gap.outcome), (gate.TECHNICAL_RULE, gate.NOT_EXECUTABLE)
        )
        self.assertIn("what it registered at its first measurement", gap.text)
        self.assertIn("does not hold", gap.text)
        self.assertIn("without filling in what is not known", gap.fix or "")
        self.assertIn("that tells nothing of what was owed before", gap.fix or "")

    def test_one_first_measurement_with_a_report_is_enough_for_the_duty(self):
        first = self._register("REPORT.md")
        self._run(first)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the run")  # kept across the checkouts
        # a second first measurement on diverged history, registering none
        main = _git(self.root, "rev-parse", "--abbrev-ref", "HEAD")
        _git(self.root, "checkout", "-q", "--orphan", "side")
        side = self._register(None)
        _git(self.root, "checkout", "-q", "-f", main)
        self._run(side, name="2026-10-07T10-00-01_cd34")
        # one of them registered a report: the duty stands, at any path
        self.assertIsNone(self._gap(self._head_now("REPORT.md")))
        gap = self._gap(self._head_now(None))
        assert gap is not None
        self.assertIn(f"before its first measurement {RUN}", gap)

    def _finding(self, proto: Path) -> gate.GateFinding | None:
        text = proto.read_text(encoding="utf-8")
        return registered_report.report_binding_gap(
            proto, text, measured=_measured(proto, text)
        )

    def test_a_measurement_only_the_run_index_lists_leaves_the_duty_untold(self):
        """Deleted without a commit: the index says it was measured, and no
        record is left to name the commit it stood under."""
        import shutil

        from labkit.run import runlog

        self._run(self._register(None))
        runlog.reindex(self.area)
        shutil.rmtree(self.area / "runs")
        gap = self._finding(self.proto)
        assert gap is not None
        self.assertEqual(
            (gap.rule, gap.outcome), (gate.TECHNICAL_RULE, gate.NOT_EXECUTABLE)
        )
        self.assertIn(f"a measurement of it is lost ({RUN}", gap.text)

    def test_a_first_measurement_off_heads_history_is_read_at_its_own_commit(self):
        """The run started on a line HEAD does not contain; its commit is in
        the repository, and what it registered there is what binds."""
        self._register(None)
        main = _git(self.root, "rev-parse", "--abbrev-ref", "HEAD")
        _git(self.root, "checkout", "-q", "--orphan", "side")
        side = self._register("REPORT.md")
        _git(self.root, "checkout", "-q", "-f", main)
        self._run(side)
        gap = self._finding(self.proto)
        assert gap is not None
        self.assertEqual(gap.rule, gate.OPEN_RULE)
        self.assertIn(f"before its first measurement {RUN}", gap.text)

    def test_the_gate_reaches_a_protocol_whose_head_no_longer_names_the_report(self):
        """Selection by the area: the commit that drops the report touches
        the protocol, an exploration, whose head names no report now."""
        self._run(self._register("REPORT.md"))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the run")
        self._head_now(None)
        _git(self.root, "add", str(self.proto))
        code, out = self._if_reported([self.proto])
        self.assertEqual(code, 1, out)
        self.assertIn("now registers none", out)
        # the twin: the head unchanged, the same commit passes this hold
        self._head_now("REPORT.md")
        _git(self.root, "add", str(self.proto))
        code, out = self._if_reported([self.proto])
        self.assertNotIn("now registers", out)

    def test_the_hook_entry_prints_next_steps_step_after_a_hold(self):
        """`report-check --if-reported --staged` (the pre-commit) holds and
        then prints `labkit-next --staged`'s step for the area, byte for byte;
        its findings keep their own lines."""
        from labkit.gates.next_step import next_step
        from labkit.formats.area_state import INDEX

        self._run(self._register("REPORT.md"))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the run")
        self._head_now(None)
        _git(self.root, "add", str(self.proto))
        rel = self.proto.relative_to(self.root).as_posix()
        out = io.StringIO()
        with contextlib.chdir(self.root), contextlib.redirect_stdout(out):
            code = report_command.main(["--if-reported", "--staged", rel])
            step = next_step(self.area, self.proto, file_state=INDEX).render(
                self.area.relative_to(self.root).as_posix()
            )
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("now registers none", out.getvalue())
        self.assertIn(step, out.getvalue())

    def test_the_gate_reaches_the_protocol_through_its_former_report(self):
        """Selection by the former path: the head moved the report in an
        earlier state, and only the old file changes now."""
        self._run(self._register("REPORT.md"))
        self._head_now("docs/OTHER.md")
        report = self.root / "REPORT.md"
        report.write_text("# Report\n\n0.93\n", encoding="utf-8")
        _git(self.root, "add", "-A")
        code, out = self._if_reported([report])
        # the protocol is reached through its former report; the move
        # itself is no finding
        self.assertIn(
            self.proto.resolve(),
            registered_report.formerly_registering(
                [report], self.root, report_hold.repo_sources(self.root, staged=True)
            ),
        )
        self.assertNotIn("now registers", out)
        # the twin: a report no first measurement registered reaches nothing
        note = self.root / "NOTE.md"
        note.write_text("# Note\n", encoding="utf-8")
        _git(self.root, "add", "-A")
        code, out = self._if_reported([note])
        self.assertNotIn("now registers", out)

    def test_the_stop_reaches_an_unwritten_report_through_the_former_one(self):
        """The stop finds registered reports not written by the gate's own
        reader (`report_check.reached_by`): a change to the report the first
        measurement registered reaches the protocol, whose head now
        registers another, unwritten one. The twin: an unrelated note
        reaches nothing."""
        from labkit.gates import agent_hooks

        self._run(self._register("REPORT.md"))
        self._head_now("docs/OTHER.md")
        report = self.root / "REPORT.md"
        report.write_text("# Report\n\n0.93\n", encoding="utf-8")
        with contextlib.chdir(self.root):
            (line,) = agent_hooks.missing_reports(self.root, [report]).steps.values()
            self.assertIn("labkit-next:", line)
            note = self.root / "NOTE.md"
            note.write_text("# Note\n", encoding="utf-8")
            self.assertEqual(agent_hooks.missing_reports(self.root, [note]).steps, {})

    def test_an_index_that_does_not_read_is_no_missing_report(self):
        """A run index that does not read is told apart from a report not
        written: whether a measurement owes the report cannot be told, so it
        holds under its own heading, never as an unwritten report."""
        from labkit.gates import agent_hooks

        self._register("docs/OTHER.md")
        (self.area / "runs.tsv").write_text("not a header\n", encoding="utf-8")
        with contextlib.chdir(self.root):
            missing = agent_hooks.missing_reports(self.root, [self.proto])
        self.assertEqual(missing.steps, {})
        (line,) = missing.unreadable
        self.assertIn("runs.tsv", line)

    def test_the_first_measurement_starts_only_with_its_report_committed(self):
        from labkit.run import start_check

        self._register(None)
        self._head_now("REPORT.md")  # registered in the tree, not committed
        bound = start_check.protocol_binding(self.area, "PROTOCOL-x.md")
        problems = start_check._freeze_findings(
            self.area, bound, area_state.state_of(self.area)
        )
        self.assertTrue(any("HEAD registers none" in p for p in problems), problems)
        _, way = start_check.measurement_refusal(self.area, self.proto)
        self.assertIn("commit", way.casefold())
        self.assertNotIn("Freeze first", way)
        # committed: the run may start
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "report registered")
        bound = start_check.protocol_binding(self.area, "PROTOCOL-x.md")
        with mock.patch.object(start_check, "_audit_line_findings", return_value=[]):
            self.assertEqual(
                start_check._freeze_findings(
                    self.area, bound, area_state.state_of(self.area)
                ),
                [],
            )

    def test_the_setter_moves_the_report_after_the_first_measurement(self):
        from labkit.tools import protocol_edit, protocol_fill

        self._run(self._register("REPORT.md"))
        before = self.proto.read_text(encoding="utf-8")
        proposed = protocol_edit.fill_many(before, [("report", "OTHER.md")], force=True)
        self.assertIsNone(
            registered_report.report_binding_gap(
                self.proto, proposed, measured=_measured(self.proto, proposed)
            )
        )
        # the setter moves the report after the measurement; replacing a
        # value still asks for --force, as before one
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main([str(self.proto), "report=OTHER.md"])
        self.assertEqual(code, 2, out.getvalue())
        self.assertIn("--force", out.getvalue())
        self.assertEqual(self.proto.read_text(encoding="utf-8"), before)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                protocol_fill.main([str(self.proto), "report=OTHER.md", "--force"]), 0
            )
        self.assertIsNone(self._gap(self.proto.read_text(encoding="utf-8")))

    def test_a_renamed_protocol_keeps_the_report_it_registered(self):
        """The id binds: renaming the protocol and dropping its report in
        one commit does not remove the report its first measurement stood
        under."""
        self._run(self._register("REPORT.md"))
        renamed = self.area / "PROTOCOL-y.md"
        _git(self.root, "mv", str(self.proto), str(renamed))
        self.proto = renamed
        text = self._head_now(None)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "renamed, report dropped")
        gap = self._gap(text)
        assert gap is not None
        self.assertIn("registered REPORT.md as its report", gap)
        self.assertIn("its head now registers none", gap)

    def test_the_setter_enters_a_report_after_the_first_measurement(self):
        from labkit.tools import protocol_edit, protocol_fill

        self._run(self._register(None))
        before = self.proto.read_text(encoding="utf-8")
        proposed = protocol_edit.fill_many(before, [("report", "REPORT.md")])
        self.assertIsNone(
            registered_report.report_binding_gap(
                self.proto, proposed, measured=_measured(self.proto, proposed)
            )
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main([str(self.proto), "report=REPORT.md"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertNotEqual(self.proto.read_text(encoding="utf-8"), before)

    def test_handover_and_new_protocol_allow_a_new_report(self):
        from labkit.formats import handovers
        from labkit.tools import protocol_fill

        self._run(self._register("REPORT.md"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main(
                [
                    str(self.proto),
                    "--handover",
                    "--why",
                    "the report moves to a new protocol",
                    "--tried",
                    "measured the original question",
                    "--into",
                    str(self.root / "REPORT.md"),
                ]
            )
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(
            handovers.protocol_handed_over(
                self.area, self.proto, area_state.state_of(self.area)
            )
        )
        self.assertIsNone(self._gap(self.proto.read_text(encoding="utf-8")))
        new_area = self.area.parent / "02-new"
        new_area.mkdir()
        successor = new_area / "PROTOCOL-new.md"
        text = (
            head(id="p-1111111111111111", repeat_cost=self.REPEAT_COST, report="NEW.md")
            + REGISTRATION
        )
        successor.write_text(text, encoding="utf-8")
        self.assertIsNone(
            registered_report.report_binding_gap(
                successor, text, measured=_measured(successor, text)
            )
        )
        self.assertTrue(
            handovers.protocol_handed_over(
                self.area, self.proto, area_state.state_of(self.area)
            )
        )

    def test_a_handover_block_still_ends_a_protocol_renamed_since(self):
        """The block shows the path at the handover; its record names the
        id, and by it the registered report finds the block of a protocol
        renamed since — only the report review stays owed."""
        from labkit.tools import protocol_fill

        self._run(self._register("REPORT.md"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main(
                [
                    str(self.proto),
                    "--handover",
                    "--why",
                    "the data cannot be had",
                    "--tried",
                    "asked for it",
                    "--into",
                    str(self.root / "REPORT.md"),
                ]
            )
        self.assertEqual(code, 0, out.getvalue())
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "handed over", "--no-verify")
        _git(self.root, "mv", str(self.proto), str(self.area / "PROTOCOL-y.md"))
        _git(self.root, "commit", "-qm", "renamed", "--no-verify")
        code, said = _report_check(self.area)
        self.assertEqual(code, 1, said)
        self.assertIn("has no clean report review of this state", said)
        self.assertNotIn("ends the protocol without a result", said)

    def test_a_handover_ends_the_duty_and_an_edit_after_it_ends_the_handover(self):
        from labkit.formats import handovers
        from labkit.tools import protocol_fill

        self._run(self._register("REPORT.md"))
        self._head_now("OTHER.md")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = protocol_fill.main(
                [
                    str(self.proto),
                    "--handover",
                    "--why",
                    "register another report in a new area",
                    "--tried",
                    "measured the registered question",
                    "--into",
                    str(self.root / "OTHER.md"),
                ]
            )
        self.assertEqual(code, 0, out.getvalue())
        _git(self.root, "add", "-A")
        # Isolate binding: the separate report review remains an obligation.
        with mock.patch.object(report_check, "report_owed", return_value=None):
            code, out = self._if_reported([self.proto])
        self.assertEqual(code, 0, out)
        # an edit after the handover ends the handover, not the freedom to
        # move the report: the binding holds nothing, the handover no longer
        # covers the protocol
        self._head_now("THIRD.md")
        _git(self.root, "add", str(self.proto))
        with mock.patch.object(report_check, "report_owed", return_value=None):
            code, out = self._if_reported([self.proto])
        self.assertNotIn("now registers", out)
        self.assertFalse(
            handovers.protocol_handed_over(
                self.area, self.proto, area_state.state_of(self.area)
            )
        )

    def test_unreadable_history_is_named_by_the_registration_station_alone(self):
        self._register("REPORT.md")
        self._run("0" * 40)
        with mock.patch.object(report_check, "freeze_gaps", return_value=[]):
            ctx = report_context.checked(self.area, self.proto)
            # finalize names the commit too, for its own comparison
            gaps = [
                g
                for g in report_check.chain_gaps(ctx).found
                if not g.text.startswith(report_check.FINALIZE)
            ]
        unread = [
            g for g in gaps if "cannot be read" in g.text or "does not hold" in g.text
        ]
        # the registration station names the commit where the lane owes it;
        # the report binding does not: a head that registers a report drops
        # no duty, whatever that commit held
        named = 1 if self.REPEAT_COST == "low" else 0
        self.assertEqual(len(unread), named, [g.text for g in gaps])

    def _if_reported(self, paths: list[Path]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = report_check.hold_reported(paths, self.root, staged=True).exit
        return code, out.getvalue()


class ReportOwedByADeletedProtocol(_Repository):
    """A protocol that measured under a registered report and is deleted,
    a new one with another id and no report in its place: the area still
    holds the first protocol's run, and its report was neither delivered
    nor ended by a handover."""

    def test_deleting_the_protocol_does_not_remove_the_report_it_owes(self):
        self.proto.write_text(
            head(repeat_cost="low", report="REPORT.md") + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        self._run(_git(self.root, "rev-parse", "HEAD"))
        _git(self.root, "rm", "-q", str(self.proto))
        self.proto = self.area / "PROTOCOL-y.md"
        self.proto.write_text(
            head(id="p-1111111111111111", repeat_cost="low", report=None)
            + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "another protocol in its place")
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"no protocol of the area carries the id {PID}", out)
        self.assertIn(RUN, out)
        self.assertIn("registered REPORT.md as its report", out)

    def _measured_then_deleted(self, report: str | None) -> Path:
        """The protocol registering REPORT, committed and measured, then
        deleted in the tree and the index (not committed); its old path."""
        self.proto.write_text(
            head(repeat_cost="low", report=report) + REGISTRATION, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        self._run(_git(self.root, "rev-parse", "HEAD"))
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the run")
        _git(self.root, "rm", "-q", str(self.proto))
        return self.proto

    def _hold(self, paths: list[Path], *, staged: bool) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = report_check.hold_reported(paths, self.root, staged=staged).exit
        return code, out.getvalue()

    def test_the_commit_and_the_stop_hold_the_deletion_of_a_protocol_that_owes(self):
        """No protocol is left to run a chain for: the hold reaches the
        area through the deleted path, in the index and in the tree."""
        gone = self._measured_then_deleted("REPORT.md")
        for staged in (True, False):
            with self.subTest(staged=staged):
                code, out = self._hold([gone], staged=staged)
                self.assertEqual(code, 1, out)
                self.assertIn(f"no protocol of the area carries the id {PID}", out)
                self.assertIn("registered REPORT.md as its report", out)

    def test_report_check_on_an_area_without_a_protocol_names_the_duty(self):
        self._measured_then_deleted("REPORT.md")
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"no protocol of the area carries the id {PID}", out)

    def test_next_names_the_same_restore_as_the_gate_after_the_protocol_is_deleted(
        self,
    ):
        """The next step restores the protocol that still owes a report,
        in the tree and the index, rather than registering a new question."""
        self._measured_then_deleted("REPORT.md")
        for staged in (False, True):
            with self.subTest(staged=staged), contextlib.chdir(self.root):
                state = area_state.state_of(
                    self.area, file_state=area_state.file_state_of(staged=staged)
                )
                (gap,) = report_check.orphaned_duty_gaps(state)
                out = io.StringIO()
                args = [str(self.area), *(["--staged"] if staged else [])]
                with contextlib.redirect_stdout(out):
                    code = next_command.main(args)
                self.assertEqual(code, 0, out.getvalue())
                self.assertIn(f"where: {gap.text}", out.getvalue())
                self.assertIn(f"next:  {gap.fix}", out.getvalue())
                self.assertNotIn("labkit-init exp", out.getvalue())

    def test_next_registers_when_the_deleted_protocol_owed_no_report(self):
        """A measured protocol without a report duty need not be restored."""
        self._measured_then_deleted(None)
        for staged in (False, True):
            with self.subTest(staged=staged), contextlib.chdir(self.root):
                out = io.StringIO()
                args = [str(self.area), *(["--staged"] if staged else [])]
                with contextlib.redirect_stdout(out):
                    code = next_command.main(args)
                self.assertEqual(code, 0, out.getvalue())
                self.assertIn("holds no protocol", out.getvalue())
                self.assertIn("labkit-init exp", out.getvalue())
                self.assertNotIn("restore the protocol", out.getvalue())

    def test_the_twin_deleting_a_protocol_that_owes_no_report_passes_the_holds(self):
        gone = self._measured_then_deleted(None)
        for staged in (True, False):
            with self.subTest(staged=staged):
                code, out = self._hold([gone], staged=staged)
                self.assertEqual(code, 0, out)
        # the area form still says what it always said of an area without one
        code, out = _report_check(self.area)
        self.assertEqual(code, 2, out)

    def test_the_twin_a_renamed_protocol_is_no_orphan(self):
        self.proto.write_text(
            head(repeat_cost="low", report="REPORT.md") + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        self._run(_git(self.root, "rev-parse", "HEAD"))
        renamed = self.area / "PROTOCOL-y.md"
        _git(self.root, "mv", str(self.proto), str(renamed))
        for staged in (True, False):
            with self.subTest(staged=staged):
                _, out = self._hold([self.proto, renamed], staged=staged)
                self.assertNotIn("no protocol of the area carries", out)

    def _unreadable_run_beside(self, report: str | None) -> None:
        """The protocol registering REPORT, a readable measurement at that
        commit, and an older run of the area whose record does not read."""
        self.proto.write_text(
            head(repeat_cost="low", report=report) + REGISTRATION, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        self._run(_git(self.root, "rev-parse", "HEAD"))
        broken = self.area / "runs" / "2026-10-01T10-00-00_bad0"
        broken.mkdir(parents=True)
        (broken / "config.json").write_text("{not json", encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the runs", "--no-verify")

    def test_an_unreadable_run_may_have_been_the_first_measurement(self):
        """Its binding and its commit are unknowable; beside a readable
        measurement that registered no report, "no duty" is not told — at
        report-check, at the stop and at the commit."""
        self._unreadable_run_beside(None)
        for staged in (True, False):
            with self.subTest(staged=staged):
                code, out = self._hold([self.proto], staged=staged)
                self.assertEqual(code, 1, out)
                self.assertIn("check not executable", out)
                self.assertIn("2026-10-01T10-00-00_bad0 does not read", out)
                self.assertIn("written anew from memory settles nothing", out)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("2026-10-01T10-00-00_bad0 does not read", out)

    def test_the_twin_a_report_the_head_names_or_a_first_measurement_promised(self):
        """Either settles this decision, whatever else does not read: the
        readable first measurement registered the report, and the head
        still names one."""
        self._unreadable_run_beside("REPORT.md")
        text = self.proto.read_text(encoding="utf-8")
        measured = _measured(self.proto, text)
        self.assertIsNone(
            registered_report.report_binding_gap(self.proto, text, measured=measured)
        )
        duty = registered_report.report_duty(measured, self.root)
        assert duty is not None
        self.assertEqual((duty.report, duty.unread), ("REPORT.md", None))

    def test_the_twin_a_deleted_protocol_that_owed_no_report_is_passed_over(self):
        self.proto.write_text(
            head(repeat_cost="low", report=None) + REGISTRATION, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        self._run(_git(self.root, "rev-parse", "HEAD"))
        _git(self.root, "rm", "-q", str(self.proto))
        self.proto = self.area / "PROTOCOL-y.md"
        self.proto.write_text(
            head(id="p-1111111111111111", repeat_cost="low", report=None)
            + REGISTRATION,
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "another protocol in its place")
        code, out = _report_check(self.area)
        self.assertNotIn("no protocol of the area carries", out)


class HighReportRegisteredBeforeTheFirstMeasurement(
    ReportRegisteredBeforeTheFirstMeasurement
):
    """The same report-binding contract at high repeat cost."""

    REPEAT_COST = "high"
