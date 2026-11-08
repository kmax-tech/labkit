"""The area state's first field: what a protocol measured, and which
measurements were first (`area_state.Measured`) — one answer for the run's
start check, the registration comparison, the report gates and the handover,
read from the file state, from git where a commit holds a deleted run, and
from the local run index where only it knows a run.

The deleted first measurement: a commit holds it, so its registration is
read back and still binds (cases 1 and 2 of the plan, Phase 4 pilot); a
run only `runs.tsv` lists is lost, never an invented record (case 3). The
twin: a deleted run that was no measurement binds nothing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from protocol_fixture import PID, completed_run, head, run_record, scope_file

from labkit.formats import area_state, run_index, runs
from labkit.formats.area_state import INDEX, TREE, Measured, assemble, state_of
from labkit.gates import hook_post_change, report_check

RUN = "2026-10-07T10-00-00_ab12"
PROBE = "2026-10-07T09-00-00_0000"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


class _Repository(unittest.TestCase):
    """A repository with the area `experiments/01-x`, its protocol committed,
    and runs committed at HEAD."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _git(self.root, "init", "-q", ".")
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        self.proto = self.area / "PROTOCOL-x.md"
        self.proto.write_text(
            head(repeat_cost="low") + "\n- **Question / hypothesis:** how many?\n",
            encoding="utf-8",
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")

    def _run(self, name: str, run_kind: runs.RunKind = "measurement") -> Path:
        """A finished run NAME recorded at HEAD and committed."""
        run = completed_run(self.area, name, metrics={"n": 1}, run_kind=run_kind)
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        sha = _git(self.root, "rev-parse", "HEAD")
        data["git"], data["git_full"] = sha[:7], sha
        cfg.write_text(json.dumps(data), encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", f"run {name}")
        return run


class ADeletedFirstMeasurementStillBinds(_Repository):
    def test_the_deletion_committed_reads_the_record_from_the_last_commit(self):
        run = self._run(RUN)
        held = _git(self.root, "rev-parse", "HEAD")
        _git(self.root, "rm", "-rq", str(run))
        _git(self.root, "commit", "-qm", "deleted")
        m = state_of(self.area).measured_of(PID)
        self.assertTrue(m.has_measured)
        (first,) = m.firsts
        self.assertEqual((first.dir, first.from_commit), (run, held))
        assert first.config is not None
        self.assertEqual(first.config.protocol.id, PID)
        self.assertEqual([rd.dir.name for rd in m.deleted], [RUN])
        self.assertEqual(m.present, ())
        self.assertEqual(m.lost, ())
        # the registration station still holds the protocol to that run
        ctx = report_check.checked(self.area, self.proto)
        self.assertEqual(report_check.registration_gaps(ctx), [])
        # the handover names the way back, never "no run of it was measured"
        account = report_check.adoption_state(
            self.area, self.proto, self.proto.read_text(encoding="utf-8")
        )
        self.assertEqual((account.run, account.state), (RUN, "unusable"))
        self.assertIn(f"git checkout {held} -- runs/{RUN}", account.why[0])
        # the evidence hook tells the restore, not a loss
        (line,) = hook_post_change.index_problems(state_of(self.area))
        self.assertIn(f"run {RUN}: its directory is gone — `git checkout {held}", line)

    def test_deleted_in_the_tree_only_reads_from_head_and_the_index_holds_it(self):
        run = self._run(RUN)
        sha = _git(self.root, "rev-parse", "HEAD")
        shutil.rmtree(run)
        tree = state_of(self.area).measured_of(PID)
        (first,) = tree.firsts
        self.assertEqual(first.from_commit, sha)
        self.assertEqual(first.dir, run)
        # the index (what a commit now would carry) still holds the run
        index = state_of(self.area, file_state=INDEX).measured_of(PID)
        (first,) = index.firsts
        self.assertIsNone(first.from_commit)
        self.assertEqual(index.present, index.runs)

    def test_the_twin_a_deleted_probe_binds_nothing(self):
        run = self._run(PROBE, run_kind="probe")
        _git(self.root, "rm", "-rq", str(run))
        _git(self.root, "commit", "-qm", "deleted")
        m = state_of(self.area).measured_of(PID)
        self.assertFalse(m.has_measured)
        self.assertEqual(m.firsts, ())
        self.assertEqual([rd.dir.name for rd in m.deleted], [PROBE])
        account = report_check.adoption_state(
            self.area, self.proto, self.proto.read_text(encoding="utf-8")
        )
        self.assertEqual(account.state, "not-measured")

    def test_a_present_and_a_deleted_measurement_are_ordered_by_git(self):
        first = self._run("2026-10-07T08-00-00_0001")
        self._run(RUN)
        _git(self.root, "rm", "-rq", str(first))
        _git(self.root, "commit", "-qm", "deleted the first")
        m = state_of(self.area).measured_of(PID)
        self.assertEqual([rd.dir.name for rd in m.firsts], [first.name])
        self.assertEqual([rd.dir.name for rd in m.present], [RUN])


class AHistoryGitCannotRead(_Repository):
    def test_a_missing_object_is_told_not_read_as_no_deleted_run(self):
        run = self._run(RUN)
        _git(self.root, "rm", "-rq", str(run))
        _git(self.root, "commit", "-qm", "deleted")
        tree = _git(self.root, "rev-parse", "HEAD~1^{tree}")
        obj = self.root / ".git" / "objects" / tree[:2] / tree[2:]
        self.assertTrue(obj.is_file(), obj)
        obj.unlink()
        state = state_of(self.area)
        self.assertIn("cannot be listed", state.history_unread)
        self.assertIn("git fsck", state.history_unread)
        self.assertEqual(state.deleted, ())
        self.assertFalse(state.measured_of(PID).has_measured)
        (line,) = hook_post_change.index_problems(state)
        self.assertEqual(line, state.history_unread)


class OneStateBuildPerCheckRun(_Repository):
    """The state is built once per check run and handed down: report-check's
    context carries it to every station and to finalize, `labkit-next`
    builds it once for its steps and the chain (plan Phase 4, the first step
    of the build-out). Counted at `committed_runs`, which every build in a
    repository calls once."""

    def _builds(self, action) -> int:
        from unittest import mock

        real = area_state.committed_runs
        calls: list[int] = []

        def counting(*args, **kwargs):
            calls.append(1)
            return real(*args, **kwargs)

        with mock.patch.object(area_state, "committed_runs", counting):
            action()
        return len(calls)

    def test_report_checks_chain_builds_the_state_once(self):
        self._run(RUN)

        def chain() -> None:
            ctx = report_check.checked(self.area, self.proto)
            report_check.chain_gaps(ctx, undeclared=True, review=False)

        self.assertEqual(self._builds(chain), 1)

    def test_next_step_builds_the_state_once(self):
        from labkit.gates import next_step

        self._run(RUN)
        self.assertEqual(
            self._builds(lambda: next_step.next_step(self.area, self.proto)), 1
        )

    def test_the_report_path_builds_the_state_and_the_evidence_once(self):
        """`hold_reported` over a report discussing a run: the protocol's
        chain and the report's checks share one state build and one
        evidence read of the area (`report_hold.Sources.held_state`; the
        audit of 2026-11-08, F4 and F5)."""
        from unittest import mock

        from labkit.checks import report_blocks
        from labkit.formats import evidence

        self._run(RUN)
        report = self.root / "REPORT.md"
        report.write_text(
            report_blocks.with_discussion(
                "# Report\n",
                f"experiments/01-x/{self.proto.name}",
                RUN,
                "a probe of the setup, not the answer",
            ),
            encoding="utf-8",
        )
        lines: list[str] = []
        reads: list[int] = []
        real = evidence.read_evidence

        def counting(*args, **kwargs):
            reads.append(1)
            return real(*args, **kwargs)

        with mock.patch.object(evidence, "read_evidence", counting):
            builds = self._builds(
                lambda: report_check.hold_reported(
                    [report], self.root, staged=False, tell=lines.append
                )
            )
        self.assertEqual((builds, len(reads)), (1, 1), "\n".join(lines))

    def test_the_commits_gate_builds_the_state_once_per_protocol(self):
        """`hold_reported` at the commit (STAGED): the one protocol the paths
        touch, one build of its area's state."""
        self._run(RUN)
        lines: list[str] = []
        self.assertEqual(
            self._builds(
                lambda: report_check.hold_reported(
                    [self.proto], self.root, staged=True, tell=lines.append
                )
            ),
            1,
        )


class TheFileStateNamedIsTheOneRead(_Repository):
    """A gate reads the file state its caller names: the index at the
    commit, the tree at the stop and the console. The twin that bit before
    (the check note of 2026-11-08, point 7): a run deleted in the tree, the
    deletion not staged — the commit carries the run, so a discussion of
    it is no gap there; the tree's reading names the gap."""

    def test_a_run_deleted_only_in_the_tree_stands_in_the_index(self):
        from labkit.checks import report_blocks
        from labkit.gates import report_hold

        run = self._run(RUN)
        shutil.rmtree(run)
        report = self.root / "REPORT.md"
        found = [
            report_blocks.Discussion(
                f"experiments/01-x/{self.proto.name}", RUN, "why", 1, 3, ""
            )
        ]
        staged = report_hold.repo_sources(self.root, staged=True)
        self.assertEqual(report_hold.discussion_sources(report, found, staged), [])
        tree = report_hold.repo_sources(self.root, staged=False)
        (gap,) = report_hold.discussion_sources(report, found, tree)
        self.assertIn(f"has no runs/{RUN}/", gap.text)

    def test_the_runs_a_report_may_cite_follow_the_file_state(self):
        """`repo_sources(staged=True)` knows the runs the index holds: a run
        deleted only in the tree is cited rightly at the commit, and a gap
        at the stop."""
        from labkit.gates import report_hold

        run = self._run(RUN)
        shutil.rmtree(run)
        self.assertIn(RUN, report_hold.repo_sources(self.root, staged=True).known)
        self.assertNotIn(RUN, report_hold.repo_sources(self.root, staged=False).known)


class OneRuleForAReportsPlace(unittest.TestCase):
    """Where a report may stand is one rule (`repo.report_place_problem`):
    the head's `report` field, the gates' held places and the former
    registrations read it — the third audit's H6, where `SKIP_DIRS` was
    tested in two of five places."""

    def test_the_head_refuses_a_report_under_a_skipped_directory(self):
        from labkit.formats import protocol_block, repo

        self.assertIsNone(repo.report_place_problem(PurePosixPath("REPORT.md")))
        for value, words in [
            ("data/REPORT.md", "no gate holds a report"),
            ("runs/REPORT.md", "no gate holds a report"),
            ("PROTOCOL-x.md", "a protocol is no report"),
            ("REPORT.txt", "a Markdown file"),
        ]:
            with self.subTest(value=value):
                with self.assertRaises(protocol_block.BlockError) as cm:
                    protocol_block.report_field(value)
                self.assertIn(words, str(cm.exception))
        self.assertEqual(
            protocol_block.report_field("notes/REPORT.md"), "notes/REPORT.md"
        )

    def test_the_gate_holds_the_same_places(self):
        from labkit.gates import report_hold

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertTrue(report_hold.held_place(root, root / "REPORT.md"))
            self.assertFalse(report_hold.held_place(root, root / "data" / "REPORT.md"))
            self.assertFalse(report_hold.held_place(root, root / "PROTOCOL-x.md"))
            self.assertFalse(report_hold.held_place(root, root.parent / "REPORT.md"))


class ARunOnlyTheIndexKnows(unittest.TestCase):
    """Never committed and deleted: `runs.tsv` alone names it — measured,
    lost, never read back."""

    def test_lost_counts_as_measured_and_binds_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / run_index.RUN_INDEX).write_text(
                "\t".join(run_index.RUN_INDEX_COLS)
                + "\n"
                + "\t".join(
                    [RUN, "abc1234", "01_measure.py", "{}", "{}", "{}", "", PID]
                )
                + "\n",
                encoding="utf-8",
            )
            state = state_of(area)
            self.assertEqual(state.lost, {RUN: PID})
            m = state.measured_of(PID)
            self.assertTrue(m.has_measured)
            self.assertEqual((m.firsts, m.lost), ((), (RUN,)))
            self.assertFalse(state.measured_of("p-other").has_measured)
            (line,) = hook_post_change.index_problems(state_of(area))
            self.assertIn(f"run {RUN}: its directory is gone — runs.tsv lists it", line)

    def test_a_present_run_the_index_lists_is_not_lost(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(
                head(repeat_cost="low"), encoding="utf-8"
            )
            scope_file(area)
            completed_run(area, RUN, metrics={"n": 1})
            (area / run_index.RUN_INDEX).write_text(
                "\t".join(run_index.RUN_INDEX_COLS)
                + "\n"
                + "\t".join([RUN, "g", "01_measure.py", "{}", "{}", "{}", "", PID])
                + "\n",
                encoding="utf-8",
            )
            state = state_of(area)
            self.assertEqual(state.lost, {})
            self.assertEqual(
                [rd.dir.name for rd in state.measured_of(PID).present], [RUN]
            )


class AStateBuiltWithoutFiles(unittest.TestCase):
    """`assemble` is the one assembly: a test states records, not files."""

    def _record(self, name: str, run_kind: runs.RunKind = "measurement") -> runs.RunDir:
        cfg = runs.parse_run_config(
            run_record(protocol={"id": PID, "path": "P.md"}, run_kind=run_kind)
        )
        return runs.RunDir(Path("runs") / name, cfg, None)

    def test_the_field_over_given_records(self):
        state = assemble(
            Path("area"),
            None,
            TREE,
            [self._record(RUN), self._record(PROBE, run_kind="probe")],
            [
                runs.RunDir(
                    Path("runs") / "2026-10-06T10-00-00_dead",
                    None,
                    "unreadable",
                    "c" * 40,
                )
            ],
            {"2026-10-05T10-00-00_lost": PID},
        )
        m = state.measured_of(PID)
        self.assertIsInstance(m, Measured)
        self.assertTrue(m.has_measured)
        self.assertEqual([rd.dir.name for rd in m.firsts], [RUN])
        self.assertEqual(m.lost, ("2026-10-05T10-00-00_lost",))
        # the unreadable record counts for every protocol: it may be one
        other = state.measured_of("p-other")
        self.assertTrue(other.has_measured)
        self.assertEqual(other.firsts, ())
        self.assertEqual(
            [rd.dir.name for rd in other.deleted], ["2026-10-06T10-00-00_dead"]
        )

    def test_nothing_measured(self):
        state = assemble(
            Path("area"), None, TREE, [self._record(PROBE, run_kind="probe")], [], {}
        )
        self.assertFalse(state.measured_of(PID).has_measured)
        self.assertEqual(state.measured_of(PID).runs[0].dir.name, PROBE)


class ARecordGitHolds(unittest.TestCase):
    def test_a_record_read_from_text_carries_its_commit_or_its_error(self):
        d = Path("runs") / RUN
        rd = runs.run_dir_from_text(d, json.dumps(run_record()), from_commit="a" * 40)
        self.assertEqual((rd.dir, rd.from_commit, rd.error), (d, "a" * 40, None))
        assert rd.config is not None
        self.assertEqual(rd.config.run_kind, "measurement")
        bad = runs.run_dir_from_text(d, "{not json", from_commit="a" * 40)
        self.assertIsNone(bad.config)
        self.assertIn("unreadable run metadata", bad.error or "")
        self.assertIn(str(d / runs.CONFIG_FILE), bad.error or "")
        self.assertTrue(area_state.is_measurement(bad))


if __name__ == "__main__":
    unittest.main()


class RoundTwoFileStates(_Repository):
    """The audit of 2026-11-08, round 2: R1, R4, R5."""

    def test_the_commit_reaches_an_area_whose_protocol_is_deleted_only_in_the_tree(
        self,
    ):
        from labkit.formats.scope_sha import areas_touched

        self.proto.unlink()  # in the tree only; the index still holds it
        self.assertEqual(
            areas_touched([self.proto], self.root, staged=True), [self.area.resolve()]
        )
        self.assertEqual(areas_touched([self.proto], self.root, staged=False), [])

    def test_the_undecided_gate_asks_the_areas_in_its_file_state(self):
        from unittest import mock

        from labkit.gates import undecided

        seen: list[bool] = []

        def touched(paths, repo, *, staged):
            seen.append(staged)
            return []

        with mock.patch.object(undecided, "areas_touched", touched):
            undecided.undecided_state(self.root, [self.proto], staged=True)
            undecided.undecided_state(self.root, [self.proto], staged=False)
        self.assertEqual(seen, [True, False])

    def test_a_gone_run_git_holds_is_put_back_from_the_commit_that_held_it(self):
        from labkit.gates import finalize

        run = self._run(RUN)
        held = _git(self.root, "rev-parse", "HEAD")
        _git(self.root, "rm", "-rq", str(run))
        _git(self.root, "commit", "-qm", "deleted")
        way, _ = finalize.gone_run_way(self.area, RUN, state_of(self.area))
        self.assertIn(held[:7], way)
        self.assertNotIn("checkout HEAD", way)
        # the twin: a run no commit held has no restore to offer
        way, _ = finalize.gone_run_way(self.area, "never-held", state_of(self.area))
        self.assertIn("no commit holds it", way)
        self.assertNotIn("git checkout", way)

    def test_a_report_under_the_evidence_directory_is_refused_by_both_rules(self):
        from pathlib import PurePosixPath

        from labkit.formats import handovers, repo

        rel = PurePosixPath("experiments/01-x/audits/REPORT.md")
        self.assertIsNotNone(repo.report_place_problem(rel))
        with self.assertRaisesRegex(handovers.HandoverError, "audit evidence"):
            handovers.report_destination(self.root.resolve(), self.root / rel)
        # the twin: the area's own report stands
        self.assertIsNone(
            repo.report_place_problem(PurePosixPath("experiments/01-x/REPORT.md"))
        )
