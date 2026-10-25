"""report-check at the low lane holds the registration to the commit of
the first measurement: the oldest full run bound to the protocol
(`answering_run.first_measurement`) and the commit its record names
(`runs.recorded_commit`). What stood before the number is what that commit
holds; the tree now says nothing about it, and runlog's start gate reads
the tree.

Why (labkit-paper area 09, fifth haiku round, 2026-10-22): none of the
three labkit agents had committed criterion and admissibility condition
before the first measurement, and every gate was green.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from protocol_fixture import PID, completed_run, head, scope_file

from labkit.formats import answering_run, protocol_history, runs
from labkit.formats.runs import RunKind
from labkit.gates import report_check

RUN = "2026-10-07T10-00-00_ab12"
REGISTRATION = "- **Question / hypothesis:** does it hold?\n"


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


class RegistrationAtTheFirstMeasurement(unittest.TestCase):
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

    def _commit(self, body: str) -> str:
        """The protocol with BODY committed; HEAD's short sha."""
        self.proto.write_text(
            head(repeat_cost="low", result=RUN) + body, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "protocol")
        return _git(self.root, "rev-parse", "--short", "HEAD")

    def _run(
        self, git: str, name: str = RUN, *, run_kind: RunKind = "measurement"
    ) -> Path:
        run = completed_run(
            self.area, name, metrics={"c1_pass": True}, run_kind=run_kind
        )
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["git"] = git
        cfg.write_text(json.dumps(data), encoding="utf-8")
        return run

    def test_the_twin_a_registration_committed_before_the_run_passes(self):
        sha = self._commit(REGISTRATION)
        self._run(
            sha + runs.DIRTY_MARK
        )  # the tree held more; the commit held the registration
        code, out = _report_check(self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_protocol_committed_after_the_first_measurement_blocks(self):
        before = self._commit("")  # a commit without the protocol's registration
        self.proto.unlink()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "no protocol yet")
        sha = _git(self.root, "rev-parse", "--short", "HEAD")
        self.assertNotEqual(sha, before)
        self._commit(REGISTRATION)  # written and committed after the run below started
        self._run(sha)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"PROTOCOL-x.md was not committed at the first measurement {RUN} ({sha})",
            out,
        )

    def test_a_field_written_after_the_first_measurement_blocks(self):
        sha = self._commit("")  # the question not yet written
        self._run(sha)
        self._commit(REGISTRATION)  # the tree (and HEAD) say it now
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"the registration as committed at the first measurement {RUN} ({sha}) "
            f"lacks Question / hypothesis",
            out,
        )

    def test_the_first_measurement_is_the_oldest_full_run_not_the_answering_one(self):
        sha = self._commit("")
        self._run(
            sha, name="2026-10-07T09-00-00_0000"
        )  # the first, without the question
        later = self._commit(REGISTRATION)
        self._run(later)  # the answering run, after the question was written
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn("first measurement 2026-10-07T09-00-00_0000", out)
        self.assertEqual(
            answering_run.first_measurement(self.area, PID),
            self.area / "runs" / "2026-10-07T09-00-00_0000",
        )

    def test_a_probe_and_a_repeat_are_not_the_first_measurement(self):
        sha = self._commit(REGISTRATION)
        self._run(sha, name="2026-10-07T09-00-00_0000", run_kind="probe")
        self.assertIsNone(answering_run.first_measurement(self.area, PID))
        self._run(sha)
        self.assertEqual(
            answering_run.first_measurement(self.area, PID), self.area / "runs" / RUN
        )

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
        old = _git(self.root, "rev-parse", "--short", "HEAD")
        self.assertNotEqual(old, sha)
        (lack,) = protocol_history.registration_in_commit(self.proto, old) or ["?"]
        self.assertIn("a head this labkit reads", lack)
        self.assertIn("0.21", lack)

    def test_a_run_outside_a_repository_recorded_no_commit(self):
        sha = self._commit(REGISTRATION)
        self._run(runs.NO_GIT)
        code, out = _report_check(self.area)
        self.assertEqual(code, 1, out)
        self.assertIn(f"the first measurement {RUN} recorded no commit ('no-git')", out)
        self.assertEqual(protocol_history.registration_in_commit(self.proto, sha), [])

    def test_recorded_commit_reads_the_mark_and_the_no_git_word(self):
        def cfg(git: str) -> runs.RunConfig:
            from protocol_fixture import run_record

            return runs.parse_run_config(run_record(git=git))

        self.assertEqual(runs.recorded_commit(cfg("abc1234")), "abc1234")
        self.assertEqual(runs.recorded_commit(cfg("abc1234+dirty")), "abc1234")
        self.assertIsNone(runs.recorded_commit(cfg("no-git")))
        self.assertIsNone(runs.recorded_commit(cfg("")))


class OutsideARepository(unittest.TestCase):
    def test_a_warning_not_a_blocker(self):
        """As the provenance station: the fixture areas of the other tests
        stand in temp dirs without git, and a lab repo is always one."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        scope_file(area)
        (area / "PROTOCOL-x.md").write_text(
            head(repeat_cost="low", result=RUN) + REGISTRATION, encoding="utf-8"
        )
        completed_run(area, RUN, metrics={"c1_pass": True})
        code, out = _report_check(area)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "WARNING: not a git repository — the registration cannot be held", out
        )


if __name__ == "__main__":
    unittest.main()
