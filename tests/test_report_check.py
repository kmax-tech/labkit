"""report-check: the last gate at every repeat cost — frozen (high repeat cost
only), finalize clean and named, the answering run a full run, an analysis
audit of code, promises and that run as they are now, `02_analyze.py
--check` passing.

finalize runs before the analysis audit and cannot ask for it or for what
follows — the check and the note — so the end has its own gate, at every
repeat cost: a probe's number never passes as a reported one. Each station
is tested where it lives (audit_gaps.audit_coverage, recheck.holds,
finalize); what is owed when and that every station blocks on its own, on
an area without a repository: tests/test_report_check_areas.py. Here, in a
repository: `--if-reported` — the gate the stop hook and the pre-commit
run — holds exactly the protocols whose answer cites a run, on the index
or the tree, and a registered report is held to its blocks.
"""

from __future__ import annotations

import pytest

from labkit.formats.evidence import read_evidence
from labkit.formats import run_index
from labkit.formats.area_state import state_of
from labkit.formats import area_state
from labkit.gates import registered_report
from labkit.tools import report_command
from labkit.formats.runs import RunKind
from labkit.tools import protocol_fill

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from protocol_fixture import (
    source_entry,
    protocol_id_of,
    registration_of,
    C1_BLOCK,
    C1_PROSE,
    completed_run,
    head,
    scope_file,
    started_at,
    shown_sha,
)

from labkit.formats import (
    findings,
    handovers,
    promises,
    protocol_block,
    scope_sha,
)
from labkit.gates import report_check, report_hold
from labkit.gates import report_context
from labkit.checks import report_blocks
from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow


def _measured(protocol: Path) -> area_state.Measured:
    """What PROTOCOL's area measured of it, as the tree holds it."""
    text = protocol.read_text(encoding="utf-8")
    return area_state.state_of(protocol.parent).measured_of(
        protocol_block.head(text).id
    )


class IfReported(unittest.TestCase):
    """`report-check --if-reported`: the gate at the stop and the commit.
    A number written back into
    "Recorded results" is held to the whole chain; a protocol whose
    answer is still open owes nothing — an exploration ends with no reported
    result, probes in `runs/` or not."""

    RUN = "2026-10-07T10-00-00_ab12"

    def _area(
        self,
        answer: str,
        *,
        declared: str | None = None,
        run_kind: RunKind = "measurement",
        audited: bool = True,
        git: bool = False,
        report: str | None = None,
        must_fields: bool = False,
    ) -> Path:
        """A low-lane area (no freeze owed, so the bare fixture head passes
        station 1) whose protocol says ANSWER and declares DECLARED as its
        result (the head's `[result] run`; None: an exploration); its one
        run a full run unless LONG says a probe; an analysis record of it
        when AUDITED. GIT: the
        root is a repository (before the record: the stamp's paths are
        repo-relative) and everything is committed at the end. REPORT: the
        head's registered report file (`report = "…"`). MUST_FIELDS: the four
        MUST fields the fixture's prose lacks are registered too, so the
        hook's protocol-check passes."""
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        if git:
            self._git(area.parent.parent, "init", "-q", ".")
            self._git(area.parent.parent, "config", "user.email", "t@t")
            self._git(area.parent.parent, "config", "user.name", "t")
        (area / "scripts" / "02_analyze.py").write_text(
            "print('ok')\n", encoding="utf-8"
        )
        scope_file(area)
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            head(repeat_cost="low", result=declared, promises=C1_BLOCK, report=report)
            + "- **Question / hypothesis:** does it hold?\n"
            + C1_PROSE
            + f"- **Recorded results:** {answer}\n"
            # a declared result owes its answer, which its block shows
            + "- **Conclusion:** criterion-1 holds on the one case.\n"
            + "".join(
                f"- **{label}:** n/a — test\n"
                for label in (
                    "Terms of this protocol",
                    "Data / scope",
                    "Exclusions / filters",
                    "Unit",
                )
                if must_fields
            ),
            encoding="utf-8",
        )
        if git:
            # the registration committed before the run, as the lane owes it
            self._git(area.parent.parent, "add", "-A")
            self._git(area.parent.parent, "commit", "-qm", "registration")
        run = completed_run(
            area, self.RUN, metrics={"criterion_1_pass": True}, run_kind=run_kind
        )
        if git:
            started_at(run, area.parent.parent)
        # at low repeat cost finalize holds the provenance: the source frozen in the run
        src = area / "data.jsonl"
        src.write_text('{"id": 1}\n', encoding="utf-8")
        cfg = run / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["data"] = {"cases": source_entry(src)}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        if audited:
            findings.write(
                area,
                "analysis",
                "opus",
                scope_sha.area_stamp(area)[0],
                promises.block_stamp(proto.read_text(encoding="utf-8")),
                (0, 0, 0),
                [],
                run_id=run.name,
                shown_sha=shown_sha(area, run),
                registration=registration_of(area),
                protocol_id=protocol_id_of(area),
            )
        if git:
            self._git(area.parent.parent, "add", "-A")
            self._git(area.parent.parent, "commit", "-qm", "init")
        return area

    @staticmethod
    def _git(cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)

    def _staged_gate(self, root: Path, *paths: Path) -> tuple[int, str]:
        """The pre-commit's form of the gate over PATHS in the repo ROOT."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.hold_reported(list(paths), root, staged=True).exit
        return code, buf.getvalue()

    def test_staged_reads_the_answer_as_the_index_holds_it(self):
        """The pre-commit's form: a reported answer in the index, the tree's
        reopened — the hook reads the index, the state the commit holds."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 0, out)  # the twin: tree is index, all holds
        self.assertIn("finalized, audited, checked", out)
        reported = proto.read_text(encoding="utf-8")
        proto.write_text(
            reported.replace(f'\n[result]\nrun = "{self.RUN}"\n', ""),
            encoding="utf-8",
        )  # reopened: the declaration gone, the tree differs from the index
        code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "the working tree differs from the index (experiments/01-x/PROTOCOL-x.md)",
            out,
        )
        # the twin's twin: the index open, the answer only in the tree —
        # the commit declares nothing, the gate is silent
        self._git(root, "add", "-A")
        proto.write_text(reported, encoding="utf-8")
        code, out = self._staged_gate(root, proto)
        self.assertEqual((code, out), (0, ""))

    def test_staged_names_the_index_as_the_state_held(self):
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        code, out = self._staged_gate(area.parent.parent, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertIn("read from the index; the head has adopted " + self.RUN, out)

    def test_staged_refuses_an_area_whose_tree_is_not_the_index(self):
        """A script modified and one untracked under a reported number: the
        stations would judge a state the commit does not hold."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        root = area.parent.parent
        (area / "scripts" / "02_analyze.py").write_text(
            "print('changed')\n", encoding="utf-8"
        )
        (area / "scripts" / "new.py").write_text("x = 1\n", encoding="utf-8")
        code, out = self._staged_gate(root, area / "PROTOCOL-x.md")
        self.assertEqual(code, 1, out)
        self.assertIn(
            "(experiments/01-x/scripts/02_analyze.py, experiments/01-x/scripts/new.py)",
            out,
        )
        self.assertNotIn("analysis audit", out)  # no station ran

    def test_the_commits_tree_vs_index_hold_is_nexts_step(self):
        """One mouth (docs/notes/2026-11-04-one-explainer-plan.md): an
        adoption committed with the run untracked is held as "the working
        tree differs from the index", and the hold is a finding `next`
        carries — the gate prints the one finding
        (`report_hold.staged_area_gap`) and `next --staged` names its step,
        the whole area staged; in the tree `next` says nothing of it, and
        once staged neither does."""
        from labkit.gates import next_step

        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        # the fixture's prose lacks four MUST fields, which `next` names
        # first, as the hook's protocol-check would: fill and commit them
        with proto.open("a", encoding="utf-8") as f:
            for label in (
                "Terms of this protocol",
                "Data / scope",
                "Exclusions / filters",
                "Unit",
            ):
                f.write(f"- **{label}:** n/a — test\n")
        self._git(root, "commit", "-qam", "fields")
        (area / "scripts" / "new.py").write_text("x = 1\n", encoding="utf-8")
        with contextlib.chdir(root):
            staged = next_step.next_step(area, proto, file_state=area_state.INDEX)
            tree = next_step.next_step(area, proto, file_state=area_state.TREE)
            code, out = self._staged_gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertEqual(
            staged.next.split(" stages")[0], "`git add -- experiments/01-x`"
        )
        self.assertIn(staged.where, out)  # the gate's hold is next's finding
        self.assertIn(staged.next, out)
        self.assertNotIn("git add", tree.next)  # the tree is not the commit
        self._git(root, "add", "-A")
        with contextlib.chdir(root):
            after = next_step.next_step(area, proto, file_state=area_state.INDEX)
        self.assertNotIn("git add", after.next)

    def test_a_commit_without_the_adopted_runs_record_is_held(self):
        """The record is the run's integrity evidence, so the commit that
        first cites an adopted run must carry `runs/<id>/` (pin route, "Check
        before building", docs/notes/2026-11-06-pin-route.md): left out of
        the index, the commit gate names its files; kept out by an ignore
        rule, it names the rule's way out. The twin, the record staged,
        passes. A fresh clone of a commit made past the hook fails loudly
        elsewhere (`report_blocks`: "cites run … no runs/<id>/ in the
        repo")."""
        from labkit.gates import claude_hooks

        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
            must_fields=True,
        )
        root = area.parent.parent
        # the run, its audit and the adoption staged, not yet committed: the
        # registration alone is in HEAD
        self._git(root, "reset", "-q", "--soft", "HEAD~1")
        run = f"experiments/01-x/runs/{self.RUN}"
        self._git(root, "rm", "-r", "-q", "--cached", run)

        def commit_gate() -> tuple[int, str]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.chdir(root):
                rc = claude_hooks.main(["pre-commit"])
            return rc, out.getvalue()

        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn("the working tree differs from the index", out)
        self.assertIn(f"{run}/config.json", out)
        (root / ".gitignore").write_text("runs/\n", encoding="utf-8")
        self._git(root, "add", ".gitignore")
        rc, out = commit_gate()
        self.assertEqual(rc, 1, out)
        self.assertIn(
            f"runs/{self.RUN}/config.json: git ignores it — evidence labkit wrote",
            out,
        )
        self._git(root, "rm", "-q", "--cached", ".gitignore")
        (root / ".gitignore").unlink()
        self._git(root, "add", run)
        rc, out = commit_gate()
        self.assertEqual(rc, 0, out)
        self.assertIn("finalized, audited, checked", out)

    def test_staged_finds_a_protocol_deleted_only_in_the_tree(self):
        """The script staged, the reported protocol deleted in the tree and
        not in the index: the commit keeps the protocol, so the gate holds
        it — the search for protocols reads the index, not the tree."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=True,
        )
        root = area.parent.parent
        script = area / "scripts" / "02_analyze.py"
        script.write_text("print('changed')\n", encoding="utf-8")
        self._git(root, "add", "-A")
        (area / "PROTOCOL-x.md").unlink()
        code, out = self._staged_gate(root, script)
        self.assertEqual(code, 1, out)
        self.assertIn("report-check", out)
        self.assertIn("the working tree differs from the index", out)

    def test_an_adoption_written_but_not_staged_is_named_as_such(self):
        """`--from-run` wrote the declaration into the tree, and the commit
        stages the report, not the protocol: the hold names the unstaged
        protocol and `git add`, never a bare "declares no result" an agent
        could read as a rejected review; staged, that line is gone (the twin).
        """
        area = self._area("criterion-1 met", git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        prose = text[text.index("- **Question") :]
        proto.write_text(
            head(repeat_cost="low", result=self.RUN, promises=C1_BLOCK) + prose,
            encoding="utf-8",
        )
        report = root / "REPORT.md"
        report.write_text(f"# Report\n\nRun ID: {self.RUN}\n", encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        code, out = self._staged_gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("adopts it in the working tree but not in the index", out)
        self.assertIn("`git add experiments/01-x/PROTOCOL-x.md`", out)
        self.assertNotIn("which has adopted no result", out)
        self._git(root, "add", "experiments/01-x/PROTOCOL-x.md")
        code, out = self._staged_gate(root, report)
        self.assertNotIn("not in the index", out)
        self.assertNotIn("which has adopted no result", out)

    def test_a_shared_helper_reopens_the_areas_that_import_it(self):
        """lib/scoring.py lies in no area; an area whose script imports it is
        touched by its change, and one that does not is not."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
            git=False,
        )
        root = area.parent.parent
        (root / "lib").mkdir()
        helper = root / "lib" / "scoring.py"
        helper.write_text("T = 1\n", encoding="utf-8")
        (area / "scripts" / "01_measure.py").write_text(
            "from lib import scoring\n", encoding="utf-8"
        )
        other = root / "experiments" / "02-y"
        (other / "scripts").mkdir(parents=True)
        (other / "PROTOCOL-y.md").write_text(head(), encoding="utf-8")
        (other / "scripts" / "01_measure.py").write_text("x = 1\n")
        self.assertEqual(
            report_check.affected_protocols([helper], root),
            [area.resolve() / "PROTOCOL-x.md"],
        )
        helper.unlink()  # a deleted helper is still one the area rests on
        self.assertEqual(
            report_check.affected_protocols([helper], root),
            [area.resolve() / "PROTOCOL-x.md"],
        )

    def test_the_cli_takes_staged(self):
        clean = report_check.HoldVerdict(0, {})
        with mock.patch.object(
            report_check, "hold_reported", return_value=clean
        ) as gate:
            report_command.main(["--if-reported", "--staged", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=True)
        with mock.patch.object(
            report_check, "hold_reported", return_value=clean
        ) as gate:
            report_command.main(["--if-reported", "a/PROTOCOL-x.md"])
        gate.assert_called_once_with([Path("a/PROTOCOL-x.md")], mock.ANY, staged=False)

    def _gate(self, area: Path, *paths: Path) -> tuple[int, str]:
        """The gate over PATHS — the protocol itself when none are named."""
        buf = io.StringIO()
        paths = paths or (area / "PROTOCOL-x.md",)
        with contextlib.redirect_stdout(buf):
            code = report_command.main(["--if-reported", *map(str, paths)])
        return code, buf.getvalue()

    def test_a_changed_script_reopens_the_areas_reported_number(self):
        """The protocol untouched, a script under it edited: the analysis
        audit saw other code, and both hooks hold the reported number."""
        area = self._area(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=self.RUN,
        )
        script = area / "scripts" / "02_analyze.py"
        code, out = self._gate(area, script)
        self.assertEqual(code, 0, out)  # the twin: unchanged, the gate holds
        script.write_text("print('changed')\n", encoding="utf-8")
        code, out = self._gate(area, script)
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)
        # a path under no area, and a path in another area, owe nothing here
        code, out = self._gate(area, area.parent.parent / "README.md")
        self.assertEqual((code, out), (0, ""))

    def test_an_open_answer_owes_nothing_even_over_a_probe(self):
        """The exploration: a probe in runs/, the answer still the stamp's."""
        code, out = self._gate(
            self._area("<number + run_id>", run_kind="probe", audited=False)
        )
        self.assertEqual((code, out), (0, ""))

    def test_an_answer_without_a_declaration_is_not_one(self):
        """Neither reported nor open: protocol-check warns, this gate is silent."""
        code, out = self._gate(self._area("AUC 0.91", audited=False))
        self.assertEqual((code, out), (0, ""))

    def test_a_declaration_that_does_not_read_is_held_and_blocks(self):
        """A typed `…_final` in [result]: no exploration to skip, a blocker
        naming the table — the commit must not carry it."""
        area = self._area("AUC 0.91")
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            proto.read_text(encoding="utf-8").replace(
                'preflight_audit = ""\n',
                'preflight_audit = ""\n\n[result]\nrun = "2026-10-01T09-00-00_final"\n',
            ),
            encoding="utf-8",
        )
        code, out = self._gate(area)
        self.assertEqual(code, 1, out)
        self.assertIn("a result that does not read", out)
        self.assertIn("no run id runlog writes", out)

    def test_a_reported_full_run_passes(self):
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
            )
        )
        self.assertEqual(code, 0, out)
        self.assertIn(f"its head has adopted {self.RUN}", out)
        self.assertIn("finalized, audited, checked", out)

    def test_a_reported_probe_is_refused(self):
        """The probe's number, written back."""
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
                run_kind="probe",
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("a probe (run_kind='probe'), not a measurement", out)

    def test_citing_a_run_that_does_not_exist_blocks(self):
        other = "2026-10-01T09-00-00_ffff"
        code, out = self._gate(
            self._area(f"criterion_1_pass = True (run {other})", declared=other)
        )
        self.assertEqual(code, 1, out)
        self.assertIn("finalize: ", out)
        self.assertIn("which cannot answer for", out)

    def test_a_reported_run_without_its_analysis_audit_blocks(self):
        code, out = self._gate(
            self._area(
                f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
                declared=self.RUN,
                audited=False,
            )
        )
        self.assertEqual(code, 1, out)
        self.assertIn("no analysis audit saw the area as it is now", out)


if __name__ == "__main__":
    unittest.main()


class RegisteredReport(unittest.TestCase):
    """The registered report owes its result: a protocol
    whose head says `report = "REPORT.md"` holds that file, once it is
    delivered, to the result block of the declared run or the protocol's
    handover block — at the stop, the commit and the plain call. A number
    without a run id is inside the gate too, so deleting the run id after a
    refused citation passes nothing."""

    RUN = IfReported.RUN
    _git = staticmethod(IfReported._git)
    _fixture = IfReported._area  # the low-lane area, as ReportFiles reuses it
    P = "experiments/01-x/PROTOCOL-x.md"

    def _area(
        self,
        declared: str | None = None,
        *,
        report: str | None = "REPORT.md",
        git: bool = False,
    ) -> Path:
        return self._fixture(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            declared=declared,
            git=git,
            report=report,
        )

    def _gate(self, root: Path, *paths: Path, staged: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report_check.hold_reported(list(paths), root, staged=staged).exit
        return code, buf.getvalue()

    OWED = "carries neither"
    WAYS = ("--into", "--discuss", "--handover")
    UNREVIEWED = "PROTOCOL-x.md registers and has no clean report review"

    def _reviewed(self, area: Path, report: Path, claims: tuple = ()) -> None:
        """A report review of REPORT under the area's protocol in its state
        now, naming CLAIMS — what `--report-review` writes."""
        from labkit.formats import report_reviews
        from labkit.gates import report_review

        proto = area / "PROTOCOL-x.md"
        text = report.read_text(encoding="utf-8")
        pieces = report_review.review_pieces(
            area,
            report,
            text,
            proto,
            proto.read_text(encoding="utf-8"),
            report_review.discussed_under(report, text, proto),
            state_of(area),
            read_evidence(area, staged=False),
        )
        whole, parts = report_hold.review_fingerprint(pieces)
        rkey, pkey = report_review.review_keys(area, report, proto)
        report_reviews.write_report_review(
            area,
            model="m",
            report=rkey,
            protocol=pkey,
            whole=whole,
            parts=parts,
            claims=list(claims),
            again=False,
        )

    def test_a_registered_report_without_its_block_is_held_with_the_three_ways_out(
        self,
    ):
        """A delivered report with a number and no run id.
        Held when the report is among the paths (it lies in no area) and
        when the protocol is; the plain call's station holds it too."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        for path in (report, area / "PROTOCOL-x.md"):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 1, out)
                self.assertIn(
                    "/REPORT.md carries "
                    "neither a result block (the head has adopted no result) nor "
                    "the protocol's handover block — a registered report owes "
                    "the result or an explicit end without one; a number with "
                    "its run id removed, or a run id typed in, releases nothing",
                    out,
                )
                self.assertIn("PROTOCOL-x.md registers ", out)
                self.assertIn(
                    f" {self.RUN}` adopts the run (the newest kept one) and writes "
                    "its result block",
                    out,
                )
                self.assertIn(f"--discuss {self.RUN} --why", out)
                self.assertIn(
                    "writes the progress account of the run the gates hold it to — "
                    "the commit takes it, it releases nothing and the result or the "
                    "handover stays owed",
                    out,
                )
                self.assertIn("--handover --why", out)
                self.assertIn("ends the protocol without a result", out)
                self.assertIn(
                    "its head has adopted no result; its registered report is delivered",
                    out,
                )
        ctx = report_context.checked(area, area / "PROTOCOL-x.md")
        (gap,) = report_check.report_findings(ctx)
        self.assertEqual(gap.grade, "BLOCKER")
        self.assertIn(self.OWED, gap.text)
        self.assertEqual(gap.rule, OPEN_RULE)
        # blocks that do not read: what the report owes could not be looked for
        report.write_text("# Report\n\n" + report_blocks.CLOSE + "\n", encoding="utf-8")
        ctx = report_context.checked(area, area / "PROTOCOL-x.md")
        (gap,) = report_check.report_findings(ctx)
        self.assertIn("its blocks do not read", gap.text)
        self.assertEqual(gap.rule, TECHNICAL_RULE)

    def test_the_adoption_is_not_held_against_itself(self):
        """With the registered REPORT.md already in the tree (no block yet),
        the adoption's own check (PROPOSED) does not hold the report for the
        block only `--into` can write after it — else `--from-run` and
        `--into` would each refuse the other's step; the tree and the index
        hold it (the twin)."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        declared = (
            head(repeat_cost="low", result=self.RUN, promises=C1_BLOCK)
            + text[text.index("- **Question") :]
        )
        ctx = report_context.checked(
            area, proto, file_state=area_state.PROPOSED, text=declared
        )
        self.assertEqual(report_check.report_findings(ctx), [])
        ctx = report_context.checked(area, proto)
        (gap,) = report_check.report_findings(ctx)
        self.assertIn(self.OWED, gap.text)

    def test_the_twin_the_result_block_of_the_declared_run_passes(self):
        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        new, _ = protocol_fill.into_report(
            proto.read_text(encoding="utf-8"), area, "# Report\n\n", self.P
        )
        report.write_text(new, encoding="utf-8")
        # the block releases the result; the report's text still owes its
        # review — the prose may present another run
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertNotIn(self.OWED, out)
        self.assertIn(self.UNREVIEWED, out)
        self.assertIn("--report-review", out)
        self._reviewed(area, report)
        for path in (report, proto):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 0, out)
                self.assertNotIn(self.OWED, out)
        self.assertEqual(
            report_check.report_findings(report_context.checked(area, proto)), []
        )
        # a block showing another run than the head declares is no release;
        # with a result declared the way out is `--into` alone
        report.write_text(
            new.replace(self.RUN, "2026-10-07T11-00-00_cd34"), encoding="utf-8"
        )
        code, out = self._gate(root, proto)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f"neither the result block of run {self.RUN}, its adopted result", out
        )
        line = next(ln for ln in out.splitlines() if "registers " in ln)
        self.assertIn("Next: `protocol-fill ", line)
        self.assertIn("--into ", line)
        self.assertNotIn("--from-run", line.split("--discuss")[0])

    def test_the_registered_report_is_held_by_a_claim_and_reviewed_again_after_a_change(
        self,
    ):
        """A REPORT.md may call an older run's criterion "PASS", with or
        without a discussion block: the registered report owes a review of its
        final state; a claim holds it; a clean review releases that state only
        — a later edit owes another."""
        from labkit.formats.report_reviews import ReportClaim

        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        new, _ = protocol_fill.into_report(
            proto.read_text(encoding="utf-8"), area, "# Report\n\n", self.P
        )
        report.write_text(
            new + "\nAn older run passed criterion-1.\n", encoding="utf-8"
        )
        claim = ReportClaim(
            line=len(new.split("\n")) + 1, kind="result", why="an older run's verdict"
        )
        self._reviewed(area, report, (claim,))
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn("the report review holds this state (is the report", out)
        # the twin: the claim answered by the text, a clean review of that state
        report.write_text(new, encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertIn(self.UNREVIEWED, out)
        self._reviewed(area, report)
        self.assertEqual(self._gate(root, report)[0], 0)
        report.write_text(new + "\nAdded later.\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.UNREVIEWED, out)
        self.assertIn("changed since", out)

    def test_a_registered_report_a_commit_held_is_told_as_gone_not_as_unwritten(self):
        """The rule's sentence names a report never written. One a commit
        held is told as written and gone and claims no rule — removed in
        the tree, staged as removed, or removed by an earlier commit; the
        twin never written is the test below."""
        from labkit.formats.gate import OPEN_RULE

        area = self._area(git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        text = proto.read_text(encoding="utf-8")
        (root / "REPORT.md").write_text("# Report\n", encoding="utf-8")
        self._git(root, "add", "REPORT.md")
        self._git(root, "commit", "-q", "-m", "report")

        def gap(*, staged: bool = False):
            found = registered_report.missing_report(
                proto, text, root, measured=_measured(proto), staged=staged
            )
            assert found is not None
            return found

        (root / "REPORT.md").unlink()
        self._git(root, "rm", "-q", "--cached", "REPORT.md")
        for staged in (False, True):
            with self.subTest(staged=staged):
                found = gap(staged=staged)
                self.assertEqual(found.rule, OPEN_RULE)
                self.assertIn("which was written and is gone", found.text)
                self.assertNotIn("not written", found.text)
        self._git(root, "commit", "-q", "-m", "report removed")
        self.assertEqual(gap().rule, OPEN_RULE)

    def test_a_registered_report_never_written_is_an_incomplete_delivery(self):
        """The registered report owes its review, written or not: once the
        area measured, the stop holds a protocol whose registered report is
        missing — deleting the run does not lift it;
        the twins: before a measurement, and with the report written,
        nothing."""
        import shutil

        from labkit.gates import agent_hooks

        area = self._area(git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        # the bare fixture lacks MUST fields; filled, so that the step the
        # stop prints is the report's, not the registration's
        proto.write_text(
            proto.read_text(encoding="utf-8")
            + "- **Terms of this protocol:** none\n- **Data / scope:** all\n"
            "- **Exclusions / filters:** none\n- **Unit:** 1\n",
            encoding="utf-8",
        )
        text = proto.read_text(encoding="utf-8")
        gap = registered_report.missing_report(
            proto, text, root, measured=_measured(proto)
        )
        assert gap is not None
        self.assertIn("REPORT.md as its report, which is not written", gap.text)
        self.assertEqual(gap.rule, registered_report.LAB_104)
        self.assertIn("labkit-adopt", gap.fix or "")
        self.assertIn("--handover", gap.fix or "")
        # the stop holds on that finding and prints `labkit-next`'s step for
        # the state: the progress account into the registered report
        from labkit.gates import next_step

        with contextlib.chdir(root):
            (line,) = agent_hooks.missing_reports(root, [proto]).steps.values()
            step = next_step.next_step(area, proto)
        self.assertEqual(line, step.render("experiments/01-x"))
        self.assertIn("REPORT.md carries no account of it yet", line)
        # the twin: the report written, nothing missing
        (root / "REPORT.md").write_text("# Report\n", encoding="utf-8")
        self.assertIsNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        (root / "REPORT.md").unlink()
        # deleting the measured run does not lift it: the commit holds it,
        # and so does runs.tsv (`area_state.Measured`)
        from labkit.run import runlog

        runlog.reindex(area)
        shutil.rmtree(area / "runs")
        self.assertIsNotNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        (area / run_index.RUN_INDEX).unlink()
        self.assertIsNotNone(
            registered_report.missing_report(
                proto, text, root, measured=_measured(proto)
            )
        )
        # the twin: a run never committed, deleted with its index — no
        # measurement anywhere, nothing owed yet
        area = self._area(git=False)
        proto = area / "PROTOCOL-x.md"
        shutil.rmtree(area / "runs")
        self.assertIsNone(
            registered_report.missing_report(
                proto,
                proto.read_text(encoding="utf-8"),
                area.parent.parent,
                measured=_measured(proto),
            )
        )

    def test_the_twin_a_note_citing_a_run_owes_no_review(self):
        """A research note may describe an unreviewed run: only the report
        the head registers owes a review, not every file citing a run."""
        area = self._area(declared=self.RUN, git=True)
        root = area.parent.parent
        older = "2026-10-06T10-00-00_aa11"
        completed_run(area, older, metrics={"criterion_1_pass": True})
        note = root / "notes" / "pilot.md"
        note.parent.mkdir()
        note.write_text(
            f"The first run, {older}, gave 0.89 and was dropped.\n",
            encoding="utf-8",
        )
        code, out = self._gate(root, note)
        self.assertNotIn("report review", out)
        self.assertEqual(code, 0, out)

    def test_the_twin_the_handover_block_passes_and_a_typed_one_does_not(self):
        area = self._area(git=True)
        root = area.parent.parent
        proto = area / "PROTOCOL-x.md"
        report = root / "REPORT.md"
        report.write_text("# Report\n\nno result\n", encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = protocol_fill.main(
                [
                    str(proto),
                    "--handover",
                    "--why",
                    "the audit found what the data cannot answer",
                    "--tried",
                    "two runs",
                    "--into",
                    str(report),
                ]
            )
        self.assertEqual(rc, 0, buf.getvalue())
        code, out = self._gate(root, report)
        self.assertIn(self.UNREVIEWED, out)  # a handover owes its review too
        self._reviewed(area, report)
        for path in (report, proto):
            with self.subTest(path=path.name):
                code, out = self._gate(root, path)
                self.assertEqual(code, 0, out)
                self.assertNotIn(self.OWED, out)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        # a block typed by hand names no record that reads: held, saying so
        typed = "\n".join(
            [
                "# Report",
                "",
                handovers.OPEN,
                f'protocol = "{self.P}"',
                'record = "experiments/01-x/audits/handovers/handover-00.json"',
                "-->",
                "Unresolved: handed over.",
                handovers.CLOSE,
                "",
            ]
        )
        report.write_text(typed, encoding="utf-8")
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)
        self.assertIn("its handover block at line 3 names no record that reads", out)

    def _discussed(self, area: Path, run_id: str) -> Path:
        """REPORT.md at the root with the progress account of RUN_ID."""
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            protocol_fill.discuss_into(
                (area / "PROTOCOL-x.md").read_text(encoding="utf-8"),
                area,
                "# Report\n\nmeasured; the audit is still open\n",
                self.P,
                run_id,
                "measured, the analysis audit still open",
            ),
            encoding="utf-8",
        )
        return report

    def test_the_progress_account_passes_the_commit_and_the_stop(
        self,
    ):
        """While nothing is adopted, a discussion of the answering run is the
        progress account, an honest interim state: the commit and the stop
        take it without a model call. It releases nothing: nothing is
        adopted, and report-check of the protocol still owes the analysis
        audit."""
        area = self._fixture(
            f"criterion-1 met · recorded: kept number: n = 1 (run {self.RUN})",
            git=True,
            report="REPORT.md",
            audited=False,
        )
        root = area.parent.parent
        report = self._discussed(area, self.RUN)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self.assertNotIn("report review", out.lower().replace("report-check", ""))
        code, out = self._gate(root, report)
        self.assertEqual(code, 0, out)
        self.assertNotIn("carries the progress account of run", out)
        proto = area / "PROTOCOL-x.md"
        self.assertIsNone(protocol_block.declared_run(proto.read_text("utf-8")))
        ctx = report_context.checked(area, proto)
        gaps = report_check.chain_gaps(ctx, undeclared=True).found
        self.assertTrue(any("analysis" in g.text for g in gaps), gaps)

    def test_the_twin_a_discussion_of_another_run_is_no_progress_account(self):
        area = self._area(git=True)
        root = area.parent.parent
        other = completed_run(area, "2026-10-01T00-00-00_0000", metrics={"n": 1})
        started_at(other, root)
        report = self._discussed(area, other.name)
        self._git(root, "add", "-A")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)

    def test_a_typed_run_id_without_the_block_is_held(self):
        area = self._area()
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text(
            f"# Report\n\nmean = 0.69 (run {self.RUN})\n", encoding="utf-8"
        )
        code, out = self._gate(root, report)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)
        self.assertIn("a run id typed in, releases nothing", out)

    def test_a_protocol_without_report_and_a_second_file_hold_nothing(self):
        """The obligation is the registered file's alone: a protocol that
        registers none holds REPORT.md to nothing new, and a note beside a
        registered report owes nothing; a registered report not yet
        written owes nothing either — the obligation is on what is
        delivered."""
        area = self._area(report=None)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, report, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)
        self.assertNotIn("registers", out)
        area = self._area()
        root = area.parent.parent
        code, out = self._gate(root, area / "PROTOCOL-x.md")
        self.assertEqual(code, 0, out)  # REPORT.md not written yet
        note = root / "notes" / "x.md"
        note.parent.mkdir()
        note.write_text("# Notes\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, note)
        self.assertEqual(code, 0, out)
        self.assertNotIn("registers", out)

    def test_staged_reads_the_report_as_the_index_holds_it(self):
        """The commit holds the index: a REPORT.md only in the tree is not
        delivered by the commit; staged without its block it is held."""
        area = self._area(git=True)
        root = area.parent.parent
        report = root / "REPORT.md"
        report.write_text("# Report\n\nmean = 0.69 over 12 cases\n", encoding="utf-8")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 0, out)
        self._git(root, "add", "REPORT.md")
        code, out = self._gate(root, report, staged=True)
        self.assertEqual(code, 1, out)
        self.assertIn(self.OWED, out)


if __name__ == "__main__":
    unittest.main()
