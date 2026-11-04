"""A repair after the analysis audit, followed the way an agent follows
labkit: the edit, `labkit-audit --decide N fixed`, `labkit-next`, the
action it names, the gate. On the count task in a staged lab repo
(`usability stage`), the audit records written by
`docs/examples/standin-audit.py` — every other step is a command a person
runs.

Why (probe 2026-11-02, docs/notes/2026-11-02-registered-field-repair.md):
an audit finding on the registered Unit field, decided `fixed`, was
answered with "measure again", and finalize refused the rewrite after the
new measurement; `labkit-next` named a new audit instead, and an audit of
the first run on the rewritten text released it. A Conclusion rewritten
after the audit was told to measure and audit again, which it never owed.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples"
VENV = Path(sys.prefix)
AREA = "experiments/01-docs-per-case"
P = f"{AREA}/PROTOCOL-docs-per-case.md"
UNIT = "one document = one visible regular file directly in a case's directory"
TERMS = "n/a — no coinage"
CONCLUSION = (
    "The twelve cases hold 3.5 documents each, which shows the inputs are complete."
)
WHO = {"NAME": "repair-paths", "EMAIL": "repair-paths@labkit.invalid"}
ENV = {
    **os.environ,
    **{
        f"GIT_{role}_{k}": v for role in ("AUTHOR", "COMMITTER") for k, v in WHO.items()
    },
}
#: Data / scope corrected in place: the same files, the count named
SCOPE_CORRECTED = (
    "data/raw/cases.jsonl (12 cases, one per line) and data/raw/inputs/<case_id>/"
)
#: why the tests withdraw an adoption
WITHDRAWN = "the adopted mean dropped cases with more than 5 documents"
#: what the scope hold says about a field rewritten after the last run
HELD_NOW = "(as the protocol stands now; no run measured under it yet)"


def sh(cwd: Path, *args: str) -> tuple[int, str]:
    """ARGS run in CWD (`.venv/bin/<tool>` for labkit's own); exit code and
    stdout with stderr."""
    p = subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, timeout=300, env=ENV
    )
    return p.returncode, p.stdout + p.stderr


@unittest.skipUnless(
    (VENV / "bin" / "usability").is_file() and shutil.which("git"),
    "needs the suite's venv with labkit's commands, and git",
)
class RepairPaths(unittest.TestCase):
    """Each test starts from one lab: registered, measured once, committed."""

    base: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = Path(tempfile.mkdtemp()) / "lab"
        steps = [
            [
                str(VENV / "bin" / "usability"),
                "stage",
                str(cls.base),
                "--task",
                "count",
                "--venv",
                str(VENV),
            ],
        ]
        for step in steps:
            rc, out = sh(cls.base.parent, *step)
            assert rc == 0, out
        lab = cls.base
        for step in (
            [".venv/bin/python", str(EXAMPLES / "count-fill.py")],
            [
                ".venv/bin/protocol-fill",
                P,
                "type=exploratory",
                "kept.key=mean_docs_per_case",
                "kept.unit=documents",
                f"Terms of this protocol={TERMS}",
                "Question / hypothesis=What is the mean number of input documents per case?",
                "Data / scope=data/raw/cases.jsonl (12 cases) and data/raw/inputs/<case_id>/",
                "Exclusions / filters=hidden files and nested directories are not counted",
                f"Unit={UNIT}",
            ],
            ["git", "add", AREA],
            ["git", "commit", "-q", "-m", "register", "--", AREA],
            [".venv/bin/python", f"{AREA}/scripts/01_measure.py"],
            [".venv/bin/protocol-fill", P, f"Conclusion={CONCLUSION}"],
            ["git", "add", AREA],
            ["git", "commit", "-q", "-m", "run 1", "--", AREA],
        ):
            rc, out = sh(lab, *step)
            assert rc == 0, (step, out)

    def setUp(self) -> None:
        self.lab = Path(tempfile.mkdtemp()) / "lab"
        shutil.copytree(self.base, self.lab, symlinks=True)

    def run_(self, *args: str, ok: bool | None = True) -> str:
        """ARGS in the lab; OK True holds exit 0, False a non-zero exit, None nothing."""
        rc, out = sh(self.lab, *args)
        if ok is True:
            self.assertEqual(rc, 0, out)
        elif ok is False:
            self.assertNotEqual(rc, 0, out)
        return out

    def audit(self, *warning: str) -> str:
        """A stand-in analysis record on the newest run (one WARNING at
        WARNING's place, with WARNING's text), committed; its file name."""
        self.run_(
            ".venv/bin/python", str(EXAMPLES / "standin-audit.py"), AREA, *warning
        )
        self.commit("audit record")
        return sorted((self.lab / AREA / "audits").glob("*-analysis*.toml"))[-1].name

    def commit(self, message: str) -> None:
        self.run_("git", "add", AREA)
        self.run_("git", "commit", "-q", "--allow-empty", "-m", message, "--", AREA)

    def fill(self, field: str) -> None:
        self.run_(".venv/bin/protocol-fill", P, "--force", field)

    def decide(self, record: str, status: str, why: str) -> str:
        return self.run_(
            ".venv/bin/labkit-audit",
            AREA,
            "--decide",
            "1",
            status,
            "--why",
            why,
            "--record",
            f"{AREA}/audits/{record}",
        )

    def adopt(self, ok: bool) -> str:
        run = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        return self.run_(".venv/bin/protocol-fill", P, "--from-run", run, ok=ok)

    def runs(self) -> int:
        return len(list((self.lab / AREA / "runs").iterdir()))

    def rewritten(self, label: str, place: str, rewritten: str) -> tuple[str, str]:
        """The registered field LABEL rewritten on an audit WARNING at PLACE
        and decided `fixed`; the record of the WARNING and the decision's
        output. labkit-next names the hold at once, and a fresh audit of
        the first run on the rewritten text — no verdict on the correction
        — does not release it."""
        record = self.audit(place, f"the {label} field is too vague · rewrite it")
        self.fill(f"{label}={rewritten}")
        said = self.decide(record, "fixed", f"rewrote {label} as the audit asked")
        self.assertNotIn("measure again", said)
        self.commit(f"{label} rewritten; finding 1 decided")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(
            "what the number is about changed after the first measurement", nxt
        )
        self.assertIn(HELD_NOW, nxt)
        self.audit()
        refused = self.adopt(ok=False)
        self.assertIn(HELD_NOW, refused)
        self.assertEqual(self.runs(), 1)
        return record, said

    def test_a_unit_named_as_its_place_takes_the_correction_route(self):
        """The decision's line names the correction: no new measurement, the
        follow-up audit's `resolved` alone releases it — a fresh audit does
        not (the `resolved` path: test_end_to_end.CorrectedDescription). The
        way back: the field as registered, the finding decided anew."""
        record, said = self.rewritten(
            "Unit", "Unit", UNIT + ", hidden files not counted"
        )
        self.assertIn("a correction of Unit in place", said)
        self.assertIn(
            "only a follow-up analysis audit's `resolved` on this finding, judged "
            "on the run that answers and exactly this text",
            said,
        )
        self.assertIn("names the step this repair owes now", said)
        self.fill(f"Unit={UNIT}")
        self.decide(
            record,
            "limitation",
            "the Unit stands as registered; the vagueness is the limit",
        )
        self.commit("Unit restored; finding 1 decided anew")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertNotIn("what the number is about changed", nxt)
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))
        self.assertEqual(self.runs(), 1)

    def test_a_field_not_named_by_its_label_is_held(self):
        """`:Terms` is not the label "Terms of this protocol": no correction
        is bound to it; the line says a changed registration is held and
        points to labkit-next, which names the hold and its ways back."""
        _, said = self.rewritten(
            "Terms of this protocol", "Terms", "case: one line of cases.jsonl"
        )
        self.assertIn("any other repair", said)
        self.assertIn("a new measurement carries it rather than repairs it", said)
        self.assertIn("names the step this repair owes now", said)

    def test_the_twin_a_conclusion_rewritten_owes_no_measurement_and_no_audit(self):
        record = self.audit(
            "Summary", "the Conclusion claims completeness nothing measured"
        )
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        said = self.decide(record, "fixed", "dropped the completeness claim")
        self.assertIn(
            "a Summary field rewritten after the audit owes no new measurement "
            "by itself",
            said,
        )
        self.assertIn("names the step this repair owes now", said)
        self.assertNotIn("measure again", said)
        self.commit("Conclusion rewritten; finding 1 decided")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("adopts it", nxt)
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))
        self.assertEqual(self.runs(), 1)
        self.assertEqual(
            len(list((self.lab / AREA / "audits").glob("*-analysis*.toml"))), 1
        )

    def test_the_twin_a_code_repair_is_measured_again_and_audited(self):
        """Where "measure again" is right: the measuring code changed."""
        record = self.audit("scripts/01_measure.py", "rows() counts nested files")
        script = self.lab / AREA / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "# repaired\n", encoding="utf-8"
        )
        said = self.decide(record, "fixed", "rows() reads the directory itself")
        self.assertIn("a change of code, inputs or configuration is confirmed", said)
        self.assertNotIn("measure again", said)  # labkit-next names it
        self.commit("rows() repaired; finding 1 decided")
        self.assertIn("01_measure.py", self.run_(".venv/bin/labkit-next", AREA))
        self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        self.commit("run 2")
        self.audit()
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))
        self.assertEqual(self.runs(), 2)


if __name__ == "__main__":
    unittest.main()


#: the answers the stand-in model gives (`tests/answer_audit.py`)
CLEAN_ANALYSIS = (
    f"verdict: 0 blockers, 0 warnings, 0 notes\nscope:\n{AREA}/scripts/01_measure.py"
)
CLEAN_REPORT_REVIEW = "verdict: 0 claim(s)"
OVERCLAIM = (
    "The twelve cases hold 3.5 documents each, which shows the inputs are complete."
)


def review_answer(verdict: str) -> str:
    """The decision reviewer's answer: VERDICT on decision #1."""
    return (
        f"DECISION #1 · {verdict} · the Conclusion as it stands claims only the mean\n"
        f"verdict: {int(verdict == 'upheld')} upheld, {int(verdict == 'rejected')} "
        f"rejected, {int(verdict == 'insufficient')} insufficient"
    )


@unittest.skipUnless(
    (VENV / "bin" / "usability").is_file() and shutil.which("git"),
    "needs the suite's venv with labkit's commands, and git",
)
class RegisteredReportRepairs(RepairPaths):
    """The same lab with `report = "REPORT.md"` registered before the first
    measurement and its progress account committed — the repair paths that
    end at the report (probe 2026-11-02,
    docs/notes/2026-11-02-repair-path-probe.md): a report deleted after the
    adoption, a handover that owes the report review, a BLOCKER on the
    Conclusion decided `fixed`. The model is given its answer
    (`tests/answer_audit.py`); every other step is a command."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = Path(tempfile.mkdtemp()) / "lab"
        rc, out = sh(
            cls.base.parent,
            str(VENV / "bin" / "usability"),
            "stage",
            str(cls.base),
            "--task",
            "count",
            "--venv",
            str(VENV),
        )
        assert rc == 0, out
        lab = cls.base
        steps: list[list[str]] = [
            [".venv/bin/python", str(EXAMPLES / "count-fill.py")],
            [
                ".venv/bin/protocol-fill",
                P,
                "type=exploratory",
                "kept.key=mean_docs_per_case",
                "kept.unit=documents",
                f"Terms of this protocol={TERMS}",
                "Question / hypothesis=What is the mean number of input documents per case?",
                "Data / scope=data/raw/cases.jsonl (12 cases) and data/raw/inputs/<case_id>/",
                "Exclusions / filters=hidden files and nested directories are not counted",
                f"Unit={UNIT}",
                "report=REPORT.md",
            ],
            ["git", "add", AREA, "tests"],
            ["git", "commit", "-q", "-m", "register", "--", AREA, "tests"],
            [".venv/bin/python", f"{AREA}/scripts/01_measure.py"],
        ]
        for step in steps:
            rc, out = sh(lab, *step)
            assert rc == 0, (step, out)
        (lab / "REPORT.md").write_text("# Report\n\nThe mean per case.\n", "utf-8")
        run = sorted(p.name for p in (lab / AREA / "runs").iterdir())[-1]
        for step in (
            [
                ".venv/bin/protocol-fill",
                P,
                "--discuss",
                run,
                "--why",
                "measured; the audit and the adoption are open",
                "--into",
                "REPORT.md",
            ],
            ["git", "add", AREA, "REPORT.md"],
            ["git", "commit", "-q", "-m", "run 1", "--", AREA, "REPORT.md"],
        ):
            rc, out = sh(lab, *step)
            assert rc == 0, (step, out)

    def commit(self, message: str, ok: bool | None = True) -> str:  # type: ignore[override]
        self.run_("git", "add", AREA, "REPORT.md")
        return self.run_(
            "git", "commit", "-q", "-m", message, "--", AREA, "REPORT.md", ok=ok
        )

    def answered(self, answer: str, *args: str, ok: bool | None = None) -> str:
        """`labkit-audit AREA ARGS`, the model answering ANSWER."""
        given = self.lab.parent / "answer.txt"
        given.write_text(answer, encoding="utf-8")
        return self.run_(
            ".venv/bin/python",
            str(ROOT / "tests" / "answer_audit.py"),
            str(given),
            "--",
            AREA,
            *args,
            ok=ok,
        )

    def adopted(self) -> None:
        """The run audited clean, adopted, its report reviewed and committed."""
        self.answered(CLEAN_ANALYSIS, "--mode", "analysis", ok=True)
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        run = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        self.run_(".venv/bin/labkit-adopt", AREA, run)
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.commit("adopted")

    # -- not the tests of the base class: this lab registers a report
    test_a_unit_named_as_its_place_takes_the_correction_route = None  # type: ignore[assignment]
    test_a_field_not_named_by_its_label_is_held = None  # type: ignore[assignment]
    test_the_twin_a_conclusion_rewritten_owes_no_measurement_and_no_audit = None  # type: ignore[assignment]
    test_the_twin_a_code_repair_is_measured_again_and_audited = None  # type: ignore[assignment]

    def test_a_registered_report_deleted_after_the_adoption_is_held(self):
        """`git rm REPORT.md`, committed alone, passed the commit,
        report-check and labkit-next ("the number may be reported"); only
        the stop named a missing report, and only for an area the session
        touched. The twin: the report restored passes."""
        self.adopted()
        self.run_("git", "rm", "-q", "REPORT.md")
        refused = self.run_(
            "git", "commit", "-q", "-m", "drop", "--", "REPORT.md", ok=False
        )
        self.assertIn(
            "registers REPORT.md as its report, which is not written", refused
        )
        self.assertIn(
            "registers REPORT.md as its report, which is not written",
            self.run_(".venv/bin/report-check", AREA, ok=False),
        )
        self.assertIn("which is not written", self.run_(".venv/bin/labkit-next", AREA))
        stop = self.run_(
            ".venv/bin/python",
            "-c",
            "from pathlib import Path; from labkit.gates import agent_hooks; "
            "r = Path('.').resolve(); print(agent_hooks.missing_reports(r, [r / 'REPORT.md']))",
        )
        self.assertIn("which is not written", stop)
        self.run_("git", "checkout", "HEAD", "--", "REPORT.md")
        self.run_(".venv/bin/report-check", AREA)

    def test_a_registered_report_deleted_before_the_adoption_is_held_at_the_commit(
        self,
    ):
        """The progress account committed, then the file removed: a commit
        that removes it is a commit without the registered report."""
        self.run_("git", "rm", "-q", "REPORT.md")
        refused = self.run_(
            "git", "commit", "-q", "-m", "drop", "--", "REPORT.md", ok=False
        )
        self.assertIn(
            "registers REPORT.md as its report, which is not written", refused
        )

    def test_a_handover_with_its_report_review_stays_a_handover(self):
        """The handover's record bound every file under audits/, and the
        report review it owes writes there: the review voided the handover,
        a new handover voided the review. The twin: an analysis audit after
        the handover still voids it — new evidence is not acknowledged."""
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--handover",
            "--why",
            "the report must live elsewhere; a successor registers it",
            "--tried",
            "measured once",
            "--into",
            "REPORT.md",
        )
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("--report-review", nxt)
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        self.commit("handed over, the report reviewed")
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        self.assertIn("nothing", self.run_(".venv/bin/labkit-next", AREA))
        self.answered(CLEAN_ANALYSIS, "--mode", "analysis")
        self.assertNotIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))

    def session_starts(self) -> None:
        """The session's transcript, its first record dated now: the stop
        dates the session's commits by it."""
        when = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        (self.lab.parent / "transcript.jsonl").write_text(
            json.dumps({"type": "user", "timestamp": when}) + "\n", encoding="utf-8"
        )

    def stop(self) -> tuple[int, str]:
        """`claude-hook stop` in the lab over what git sees as changed and
        what the session committed (`session_starts`): exit code and what
        it said."""
        transcript = self.lab.parent / "transcript.jsonl"
        return sh(
            self.lab,
            ".venv/bin/python",
            "-c",
            "import os, sys; from labkit.gates import agent_hooks; "
            f"os.environ['CLAUDE_PROJECT_DIR'] = {str(self.lab)!r}; "
            "sys.exit(agent_hooks.stop({'cwd': "
            f"{str(self.lab)!r}, 'session_id': 'repair-paths', 'transcript_path': "
            f"{str(transcript)!r}}}))",
        )

    def test_a_handover_after_an_analysis_audit_stays_through_its_review(self):
        """The journal `audits/attempts.jsonl` already held the analysis
        audit's lines when the handover was written; the report review it
        owes appended its own, and the handover was void: bound by the
        file's blob id, checked by a digest of another kind (probe
        2026-11-03, docs/notes/2026-11-03-handover-journal-binding.md). Its
        open BLOCKER then held the stop and the commit, and `labkit-next`
        offered the adoption. Now `labkit-next`, the stop and the commit
        agree: handed over, before and after the commit. The twin: a new
        analysis audit after it voids it in all three."""
        self.session_starts()
        self.answered(
            "BLOCKER · scripts/01_measure.py:130 · evaluate_rows() drops cases · the "
            "mean is over 11 cases · LAB-050 Analysis audit before reporting · remove "
            f"the filter, measure again\nverdict: 1 blockers, 0 warnings, 0 notes\n"
            f"scope:\n{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        journal = self.lab / AREA / "audits" / "attempts.jsonl"
        self.assertTrue(journal.read_text(encoding="utf-8").strip())
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--handover",
            "--why",
            "the filter cannot be repaired in this protocol; a successor measures",
            "--tried",
            "measured once",
            "--into",
            "REPORT.md",
        )
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        rc, out = self.stop()
        self.assertEqual(rc, 0, out)
        self.commit("handed over after an audit, the report reviewed")
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        rc, out = self.stop()
        self.assertEqual(rc, 0, out)
        # new audit activity is new evidence: the handover no longer holds
        self.answered(CLEAN_ANALYSIS, "--mode", "analysis")
        self.assertNotIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        rc, out = self.stop()
        self.assertNotEqual(rc, 0, out)
        self.commit("an analysis audit after the handover", ok=False)

    def handed_over_and_reviewed(self) -> None:
        """The handover written, its report reviewed clean, committed."""
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--handover",
            "--why",
            "the report must live elsewhere; a successor registers it",
            "--tried",
            "measured once",
            "--into",
            "REPORT.md",
        )
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.commit("handed over, the report reviewed")
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))

    def test_after_the_handover_a_changed_input_of_the_review_owes_it_again(self):
        """Only what the review writes is left out of the handover: the
        report it read, edited, owes a new review; the review record gone
        is lost evidence the journal names, restored it counts again. The
        handover stands through both — its block and the evidence it binds
        are unchanged. (A record edited before its first commit passes: no
        check reads a record's content against its kept copy — the limit
        docs/notes/2026-11-02-review-record-forgery.md describes.)"""
        self.handed_over_and_reviewed()
        report = self.lab / "REPORT.md"
        report.write_text(
            report.read_text(encoding="utf-8") + "\nThe mean is final.\n", "utf-8"
        )
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("is handed over", nxt)
        self.assertIn("--report-review", nxt)
        self.assertIn("--report-review", self.commit("prose", ok=False))
        self.run_("git", "checkout", "HEAD", "--", "REPORT.md")  # the refusal staged it
        self.assertNotIn("--report-review", self.run_(".venv/bin/labkit-next", AREA))
        (review,) = (self.lab / AREA / "audits" / "report-reviews").glob("*.toml")
        written = review.read_bytes()
        review.unlink()  # an output gone is lost evidence the journal names
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("audit evidence is gone", nxt)
        self.assertIn(
            review.name,
            self.run_(".venv/bin/labkit-audit", AREA, "--findings", ok=None),
        )
        review.write_bytes(written)
        self.assertNotIn("--report-review", self.run_(".venv/bin/labkit-next", AREA))

    def test_after_the_handover_other_evidence_or_the_protocol_voids_it(self):
        """The handover still binds everything else: an answer file of
        another attempt, and the protocol."""
        self.handed_over_and_reviewed()
        lab = self.lab
        stray = lab / AREA / "audits" / "answers" / "2026-11-02T10-00-analysis-ab12.txt"
        stray.write_text("verdict: 0 blockers\n", encoding="utf-8")
        self.assertNotIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        stray.unlink()
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))
        self.fill(f"Terms of this protocol={TERMS}; mean: the arithmetic mean")
        self.assertNotIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))

    def conclusion_blocker(self) -> tuple[str, str]:
        """An overclaiming Conclusion flagged as a BLOCKER at its field,
        rewritten and decided `fixed`; the record and the decision's line."""
        self.fill(f"Conclusion={OVERCLAIM}")
        self.commit("the Conclusion")
        self.answered(
            "BLOCKER · PROTOCOL-docs-per-case.md:Conclusion · the Conclusion claims "
            "completeness nothing measured · the claim outruns the number · LAB-050 "
            "Analysis audit before reporting · drop the claim\n"
            "verdict: 1 blockers, 0 warnings, 0 notes\nscope:\n"
            f"{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        record = sorted((self.lab / AREA / "audits").glob("*-analysis*.toml"))[-1].name
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        said = self.decide(record, "fixed", "dropped the completeness claim")
        self.commit("the Conclusion rewritten; finding 1 decided")
        return record, said

    def test_a_conclusion_blocker_fixed_is_released_by_the_decision_review(self):
        """The follow-up audit the decision named was never shown the
        finding (the Conclusion is not in the audited state), a FIX verdict
        on it was refused, and nothing else released it. The decision
        review judges the claim as it stands and binds it."""
        record, said = self.conclusion_blocker()
        self.assertIn("the decision review judges the Conclusion as it stands", said)
        self.assertNotIn("waits for the follow-up audit", said)
        self.assertIn("--review", self.run_(".venv/bin/labkit-next", AREA))
        self.adopt(ok=False)
        self.answered(review_answer("upheld"), "--review", "--record", record, ok=True)
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))
        self.assertEqual(self.runs(), 1)

    def test_the_twin_a_rejected_review_holds(self):
        record, _ = self.conclusion_blocker()
        self.answered(
            review_answer("rejected"), "--review", "--record", record, ok=False
        )
        self.adopt(ok=False)

    def test_the_twin_a_claim_changed_after_the_review_holds(self):
        record, _ = self.conclusion_blocker()
        self.answered(review_answer("upheld"), "--review", "--record", record, ok=True)
        self.fill(f"Conclusion={OVERCLAIM}")
        self.adopt(ok=False)

    def test_the_twin_a_decision_changed_after_the_review_holds(self):
        """The upheld review binds the decision as it stood: decided again
        with another reason, the BLOCKER is held until a review of that."""
        record, _ = self.conclusion_blocker()
        self.answered(review_answer("upheld"), "--review", "--record", record, ok=True)
        self.decide(record, "fixed", "the Conclusion now states the mean alone")
        self.adopt(ok=False)
        self.answered(review_answer("upheld"), "--review", "--record", record, ok=True)
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))

    def test_the_twin_a_review_of_another_claim_does_not_carry_over(self):
        """Upheld for one Conclusion, rewritten, then put back: the review
        of the first text counts again only for exactly that text."""
        record, _ = self.conclusion_blocker()
        self.answered(review_answer("upheld"), "--review", "--record", record, ok=True)
        self.fill("Conclusion=The twelve cases hold 3.5 documents each.")
        self.adopt(ok=False)
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))

    # -- a committed record edited in the tree is held where the commit holds
    # it (docs/notes/2026-11-02-review-record-forgery.md, "committed first")

    def held_in_the_tree(self, record: str, *, adoption: bool = True) -> None:
        """RECORD (a path under the area's `audits/`), committed and edited
        in the tree beyond its decision lines: report-check, the stop's
        `--if-reported` on the report, labkit-next, the adoption (where
        ADOPTION, a run not yet adopted) and the commit name it with the
        restore from HEAD; the restore they name clears that line."""
        rel = f"{AREA}/audits/{record}"
        restore = f"git checkout HEAD -- {rel}"
        changed = f"audits/{record}: changed"
        checked = self.run_(".venv/bin/report-check", AREA, ok=False)
        self.assertIn(changed, checked)
        self.assertIn(restore, checked)
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(f"where: {changed}", nxt)
        self.assertIn(f"next:  restore it (`{restore}`", nxt)
        self.assertNotIn("may be reported", nxt)
        self.assertNotIn("is handed over", nxt)
        self.assertIn(
            changed,
            self.run_(".venv/bin/report-check", "--if-reported", "REPORT.md", ok=False),
        )
        if adoption:
            self.assertIn(changed, self.adopt(ok=False))
        self.assertIn(changed, self.commit("the edit", ok=False))
        self.run_(*restore.split())  # the index too: the refused commit staged it
        self.assertNotIn(changed, self.run_(".venv/bin/report-check", AREA, ok=None))
        self.assertNotIn(changed, self.run_(".venv/bin/labkit-next", AREA))

    def edit(self, record: str, *pairs: tuple[str, str]) -> None:
        """RECORD (under the area's `audits/`) with each (old, new) of PAIRS
        replaced once."""
        path = self.lab / AREA / "audits" / record
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            self.assertIn(old, text)
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")

    def test_a_committed_record_unchanged_or_decided_again_passes(self):
        """The twin of every hold below: the committed record as written,
        and its decision lines changed by `--decide`, name no change."""
        record, _ = self.conclusion_blocker()
        for _ in range(2):
            self.assertNotIn(
                f"audits/{record}: changed",
                self.run_(".venv/bin/report-check", AREA, ok=None)
                + self.run_(".venv/bin/labkit-next", AREA),
            )
            self.decide(
                record, "false-positive", "the Conclusion claims the mean alone"
            )

    def test_a_committed_decision_review_turned_upheld_is_held_in_the_tree(self):
        """`rejected` → `upheld` in three lines released the decision it
        judged in every tree check; only the commit refused it."""
        record, _ = self.conclusion_blocker()
        self.answered(
            review_answer("rejected"), "--review", "--record", record, ok=False
        )
        (review,) = (self.lab / AREA / "audits").glob("*-review.toml")
        self.commit("the decision review")
        self.edit(
            review.name,
            ('verdict = "rejected"', 'verdict = "upheld"'),
            ("upheld = 0", "upheld = 1"),
            ("rejected = 1", "rejected = 0"),
        )
        self.held_in_the_tree(review.name)

    def test_a_committed_analysis_blocker_removed_is_held_in_the_tree(self):
        """The BLOCKER's table deleted and `blockers = 1` → `0`: no review
        was owed any more, and the adoption passed."""
        record, _ = self.conclusion_blocker()
        path = self.lab / AREA / "audits" / record
        text = path.read_text(encoding="utf-8")
        path.write_text(text[: text.index("[[finding]]")], encoding="utf-8")
        self.edit(record, ("blockers = 1", "blockers = 0"))
        self.held_in_the_tree(record)

    def test_a_committed_report_review_with_its_claim_removed_is_held_in_the_tree(
        self,
    ):
        """A report review naming a claim, committed past the hook, then
        `claims = 1` → `0` and its table deleted: the report counted as
        reviewed clean."""
        self.adopted()
        report = self.lab / "REPORT.md"
        report.write_text(
            report.read_text(encoding="utf-8") + "\nThe inputs are complete.\n", "utf-8"
        )
        self.answered(
            "CLAIM #1 · line 3 · result · completeness is not measured\n"
            "verdict: 1 claim(s)",
            "--report-review",
            "REPORT.md",
            ok=False,
        )
        self.run_("git", "add", AREA, "REPORT.md")
        self.run_(
            "git",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "claimed",
            "--",
            AREA,
            "REPORT.md",
        )
        # the minute's second review is `…-review-2.toml`: found by its claim
        (claimed,) = [
            p
            for p in (self.lab / AREA / "audits" / "report-reviews").glob("*.toml")
            if "[[claim]]" in p.read_text(encoding="utf-8")
        ]
        text = claimed.read_text(encoding="utf-8")
        claimed.write_text(text[: text.index("[[claim]]")], encoding="utf-8")
        self.edit(f"report-reviews/{claimed.name}", ("claims = 1", "claims = 0"))
        self.held_in_the_tree(f"report-reviews/{claimed.name}", adoption=False)

    def test_a_committed_report_review_of_a_handover_with_its_claim_removed_is_held(
        self,
    ):
        """After a handover its report is released by the report review
        alone, and labkit-next and the stop's report-check on an
        exploration never reached report-check's first station: a claim
        removed from a committed review read "handed over … nothing"."""
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--handover",
            "--why",
            "the report must live elsewhere; a successor registers it",
            "--tried",
            "measured once",
            "--into",
            "REPORT.md",
        )
        self.answered(
            "CLAIM #1 · line 3 · result · the mean is no result here\n"
            "verdict: 1 claim(s)",
            "--report-review",
            "REPORT.md",
            ok=False,
        )
        self.run_("git", "add", AREA, "REPORT.md")
        self.run_(
            "git",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "claimed",
            "--",
            AREA,
            "REPORT.md",
        )
        (review,) = (self.lab / AREA / "audits" / "report-reviews").glob("*.toml")
        text = review.read_text(encoding="utf-8")
        review.write_text(text[: text.index("[[claim]]")], encoding="utf-8")
        self.edit(f"report-reviews/{review.name}", ("claims = 1", "claims = 0"))
        self.held_in_the_tree(f"report-reviews/{review.name}", adoption=False)
        self.assertIn("is handed over", self.run_(".venv/bin/labkit-next", AREA))

    def test_a_code_blocker_decided_fixed_with_nothing_changed_is_not_sent_to_a_followup(
        self,
    ):
        """Nothing the record binds changed: no follow-up will be shown it,
        so the line names the repair still owed, not the follow-up."""
        self.answered(
            "BLOCKER · scripts/01_measure.py:130 · evaluate_rows() drops cases · the "
            "mean is over 11 cases · LAB-050 Analysis audit before reporting · remove "
            "the filter\nverdict: 1 blockers, 0 warnings, 0 notes\nscope:\n"
            f"{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        record = sorted((self.lab / AREA / "audits").glob("*-analysis*.toml"))[-1].name
        said = self.decide(record, "fixed", "fixed")
        self.assertNotIn("waits for the follow-up audit", said)
        self.assertIn("not repaired", said)

    def scope_corrected(self, decided: bool) -> str:
        """An audit BLOCKER placed at Data / scope, the field corrected in
        place and — DECIDED — the finding decided `fixed` and committed (an
        undecided BLOCKER holds the commit); the record's name."""
        self.answered(
            "BLOCKER · PROTOCOL-docs-per-case.md:Data / scope · Data / scope names "
            "no file count · the reader cannot tell what was read · LAB-050 "
            "Analysis audit before reporting · name the count\nverdict: 1 "
            f"blockers, 0 warnings, 0 notes\nscope:\n{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        record = sorted((self.lab / AREA / "audits").glob("*-analysis*.toml"))[-1].name
        self.fill(f"Data / scope={SCOPE_CORRECTED}")
        if decided:
            self.decide(record, "fixed", "Data / scope now names the twelve lines")
            self.commit("Data / scope corrected; finding 1 decided")
        return record

    def test_a_decided_correction_names_its_follow_up_first(self):
        """`labkit-next` offered three ways at a decided correction, the
        way back first, and no follow-up command (probe 2026-11-02, smaller
        points). The step is the follow-up the decision named; taken, the
        unchanged run is adopted, nothing measured again."""
        record = self.scope_corrected(decided=True)
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(
            f"next:  the follow-up analysis audit on the run as it stands "
            f"(`labkit-audit {AREA} --mode analysis`) judges {record}#1",
            nxt,
        )
        self.adopt(ok=False)
        self.answered(
            f"FIX · {record}#1 · resolved · the field names the count\n\n"
            f"{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
            ok=True,
        )
        self.assertIn("labkit-adopt", self.run_(".venv/bin/labkit-next", AREA))
        self.assertIn("finalized, audited, checked", self.adopt(ok=True))
        self.assertEqual(self.runs(), 1)

    def test_the_twin_an_undecided_rewrite_is_not_sent_to_a_follow_up(self):
        """No finding decided `fixed` names the field: no follow-up judges
        it, and the way back stays first."""
        self.scope_corrected(decided=False)
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("next:  restore Data / scope", nxt)
        self.assertNotIn("the follow-up analysis audit on the run", nxt)

    def test_the_twin_an_unresolved_follow_up_releases_nothing_and_is_not_named_again(
        self,
    ):
        """The follow-up judges the correction `unresolved`: the adoption
        stays refused, and the step no longer names a follow-up — the open
        BLOCKER it carried is the step."""
        record = self.scope_corrected(decided=True)
        self.answered(
            f"FIX · {record}#1 · unresolved · the count is still missing\n\n"
            f"{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
        )
        self.adopt(ok=False)
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertNotIn("the follow-up analysis audit on the run", nxt)

    def code_repaired_after_the_adoption(self) -> str:
        """The run adopted, a later audit's BLOCKER on the code, the code
        repaired and the finding decided `fixed` — no withdrawal yet, so the
        commit would hold the repair; the record's name (taken as the new file: two records of one
        minute do not sort by time)."""
        self.adopted()
        audits = self.lab / AREA / "audits"
        before = set(audits.glob("*-analysis*.toml"))
        self.answered(
            "BLOCKER · scripts/01_measure.py:130 · evaluate_rows() drops cases · the "
            "adopted mean is over 11 cases · LAB-050 Analysis audit before reporting "
            "· remove the filter, measure again\nverdict: 1 blockers, 0 warnings, 0 "
            f"notes\nscope:\n{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        (record,) = set(audits.glob("*-analysis*.toml")) - before
        script = self.lab / AREA / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "# repaired\n", encoding="utf-8"
        )
        self.decide(record.name, "fixed", "evaluate_rows averages over every case")
        return record.name

    def run_named(self, said: str, flag: str, why: str) -> str:
        """The first `protocol-fill … FLAG …` command SAID names, its
        `<placeholder>` replaced by WHY, run; its output."""
        named = re.search(rf"`(protocol-fill [^`]*{flag}[^`]*)`", said)
        assert named is not None, said
        args = [
            why if a.startswith("<") and a.endswith(">") else a
            for a in shlex.split(named.group(1))
        ]
        return self.run_(f".venv/bin/{args[0]}", *args[1:])

    def withdraw_as_named(self) -> str:
        """`labkit-next` names the withdrawal alone, into the registered
        report; the command it names, run with a reason; its output."""
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("--into REPORT.md", nxt)
        self.assertIn("then `labkit-next` again", nxt)
        return self.run_named(nxt, "--withdraw", WITHDRAWN)

    def test_the_gates_name_the_withdrawal_into_the_registered_report(self):
        """The withdrawal report-check names first left the withdrawn run's
        result block in the registered report, and the commit refused it.
        Named with `--into`, the gate's command, then the account
        `labkit-next` asks for, commit; the next step is the measurement
        the repair owes. The gate is not loosened: before the withdrawal,
        and after one without `--into`, the commit refuses."""
        self.code_repaired_after_the_adoption()
        self.assertIn("changed since", self.commit("repair", ok=False))
        held = self.run_(".venv/bin/report-check", AREA, ok=False)
        self.assertIn(
            f'withdraw the adoption first (`protocol-fill {P} --withdraw --why "<why>" '
            "--into REPORT.md`)",
            held,
        )
        bare = Path(tempfile.mkdtemp()) / "lab"
        shutil.copytree(self.lab, bare, symlinks=True)
        self.run_named(held, "--withdraw", WITHDRAWN)
        self.run_named(self.run_(".venv/bin/labkit-next", AREA), "--discuss", WITHDRAWN)
        self.commit("withdrawn")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("01_measure.py", nxt)
        self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        self.assertEqual(self.runs(), 2)
        # the twin: the bare withdrawal leaves the result block, and the
        # commit holds it
        self.lab = bare
        self.run_(".venv/bin/protocol-fill", P, "--withdraw", "--why", WITHDRAWN)
        run1 = sorted(p.name for p in (bare / AREA / "runs").iterdir())[-1]
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run1,
            "--why",
            WITHDRAWN,
            "--into",
            "REPORT.md",
        )
        self.assertIn("the result block", self.commit("withdrawn", ok=False))

    def test_a_code_repair_measured_before_the_withdrawal_is_withdrawn_not_measured_again(
        self,
    ):
        """The repaired code measured while the faulty run stood adopted:
        `labkit-next` advised a renamed output and a third measurement
        (probe 2026-11-02, case 5). The step is the withdrawal; after it,
        the steps it names adopt the run already measured. Nothing is let
        through: the new run is not adopted over the standing adoption."""
        record = self.code_repaired_after_the_adoption()
        self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        run2 = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertNotIn("01_measure.py", nxt)
        self.assertNotIn("_v2", nxt)
        self.run_(".venv/bin/labkit-adopt", AREA, run2, ok=False)
        self.withdraw_as_named()
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(f"--discuss {run2}", nxt)
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run2,
            "--why",
            "measured after the repair; the follow-up audit is open",
            "--into",
            "REPORT.md",
        )
        self.commit("withdrawn; run 2 discussed")
        self.assertIn("--mode analysis", self.run_(".venv/bin/labkit-next", AREA))
        self.answered(
            f"FIX · {record}#1 · resolved · the filter is gone\n\n{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
            ok=True,
        )
        self.assertIn(
            f"labkit-adopt {AREA} {run2}", self.run_(".venv/bin/labkit-next", AREA)
        )
        self.run_(".venv/bin/labkit-adopt", AREA, run2)
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.commit("run 2 adopted")
        self.assertIn("nothing", self.run_(".venv/bin/labkit-next", AREA))
        self.assertEqual(self.runs(), 2)

    def test_the_twin_a_code_repair_not_measured_yet_is_withdrawn_then_measured(
        self,
    ):
        """Without a run of the repaired code the same withdrawal comes
        first; after it, and the account of the withdrawn run it asks for,
        the step is the measurement the repair owes."""
        self.code_repaired_after_the_adoption()
        self.withdraw_as_named()
        run1 = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        self.assertIn(f"--discuss {run1}", self.run_(".venv/bin/labkit-next", AREA))
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run1,
            "--why",
            "withdrawn: the mean dropped cases; the code is repaired",
            "--into",
            "REPORT.md",
        )
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertNotIn("--withdraw", nxt)
        self.assertIn("01_measure.py", nxt)
        self.assertEqual(self.runs(), 1)

    def test_a_correction_then_a_code_repair_is_measured_judged_and_reported(self):
        """Data / scope corrected in place, released and adopted for run 1;
        later a code fault repaired. Each step is the one the step before
        named: the decision's line, `--withdraw`, `labkit-next` — withdraw,
        measure again, the follow-up on run 2 that judges the correction
        again, the adoption and the report review. The verdict on run 1
        releases nothing for run 2 (probe 2026-11-03, the correction then a
        code fault: run 2 was held whatever its follow-up said, and the
        decision's line said restore and decide `limitation`)."""
        correction = self.scope_corrected(decided=True)
        self.answered(
            f"FIX · {correction}#1 · resolved · twelve cases, as run 1 read\n\n"
            f"{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
            ok=True,
        )
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        run1 = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        self.run_(".venv/bin/labkit-adopt", AREA, run1)
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.commit("run 1 adopted with the correction")
        audits = self.lab / AREA / "audits"
        before = set(audits.glob("*-analysis*.toml"))
        self.answered(
            "BLOCKER · scripts/01_measure.py:130 · evaluate_rows() drops cases · the "
            "adopted mean is over 11 cases · LAB-050 Analysis audit before reporting "
            "· remove the filter, measure again\nverdict: 1 blockers, 0 warnings, 0 "
            f"notes\nscope:\n{AREA}/scripts/01_measure.py",
            "--mode",
            "analysis",
        )
        ((code_record),) = set(audits.glob("*-analysis*.toml")) - before
        code = code_record.name
        script = self.lab / AREA / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text(encoding="utf-8") + "# repaired\n", encoding="utf-8"
        )
        said = self.decide(code, "fixed", "evaluate_rows averages over every case")
        # the decision's line points to labkit-next, which withdraws first
        # (`withdraw_as_named`); it names no action of its own (review
        # 2026-11-03, M2)
        self.assertIn("names the step this repair owes now", said)
        self.assertNotIn("measure again", said)
        self.assertNotIn("limitation", said)
        out = self.withdraw_as_named()
        self.assertIn(
            f"2. the measuring code changed since {run1} ran: measure again", out
        )
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run1,
            "--why",
            "withdrawn: the mean dropped cases; the code is repaired",
            "--into",
            "REPORT.md",
        )
        self.commit("withdrawn; run 1 discussed")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(
            f"the measuring code changed since {run1} ran: measure again", nxt
        )
        self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        run2 = sorted(p.name for p in (self.lab / AREA / "runs").iterdir())[-1]
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run2,
            "--why",
            "measured after the repair; the follow-up audit is open",
            "--into",
            "REPORT.md",
        )
        self.commit("run 2 discussed")
        follow_up = f"the follow-up analysis audit on {run2}"
        self.assertIn(follow_up, self.run_(".venv/bin/labkit-next", AREA))
        # the follow-up judges the repair alone: the verdict on run 1 is not run 2's
        self.answered(
            f"FIX · {code}#1 · resolved · the filter is gone\n\n{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
            ok=True,
        )
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn(follow_up, nxt)
        self.assertIn(f"{correction}#1", nxt)
        self.run_(".venv/bin/labkit-adopt", AREA, run2, ok=False)
        self.answered(
            f"FIX · {code}#1 · resolved · the filter is gone\n"
            f"FIX · {correction}#1 · resolved · twelve cases, as run 2 read\n\n"
            f"{CLEAN_ANALYSIS}",
            "--mode",
            "analysis",
            ok=True,
        )
        self.assertIn(
            f"labkit-adopt {AREA} {run2}", self.run_(".venv/bin/labkit-next", AREA)
        )
        self.run_(".venv/bin/labkit-adopt", AREA, run2)
        self.answered(CLEAN_REPORT_REVIEW, "--report-review", "REPORT.md", ok=True)
        self.commit("run 2 adopted")
        self.assertIn("nothing", self.run_(".venv/bin/labkit-next", AREA))
        self.assertIn("corrected in place", self.run_(".venv/bin/finalize", AREA))
        self.assertEqual(self.runs(), 2)


@unittest.skipUnless(
    (VENV / "bin" / "usability").is_file() and shutil.which("git"),
    "needs the suite's venv with labkit's commands, and git",
)
class BeforeTheFirstMeasurement(unittest.TestCase):
    """The registration written and not committed: `labkit-next` named
    "measure", and runlog refused the measurement — its start gate holds
    the first measurement to the registration as committed (probe
    2026-11-02, docs/notes/2026-11-02-repair-path-probe.md, "Smaller")."""

    def setUp(self) -> None:
        self.lab = Path(tempfile.mkdtemp()) / "lab"
        rc, out = sh(
            self.lab.parent,
            str(VENV / "bin" / "usability"),
            "stage",
            str(self.lab),
            "--task",
            "count",
            "--venv",
            str(VENV),
        )
        assert rc == 0, out
        for step in (
            [".venv/bin/python", str(EXAMPLES / "count-fill.py")],
            [
                ".venv/bin/protocol-fill",
                P,
                "type=exploratory",
                "kept.key=mean_docs_per_case",
                "kept.unit=documents",
                f"Terms of this protocol={TERMS}",
                "Question / hypothesis=What is the mean number of input documents per case?",
                "Data / scope=data/raw/cases.jsonl (12 cases) and data/raw/inputs/<case_id>/",
                "Exclusions / filters=hidden files and nested directories are not counted",
                f"Unit={UNIT}",
            ],
        ):
            rc, out = sh(self.lab, *step)
            assert rc == 0, (step, out)

    def run_(self, *args: str, ok: bool = True) -> str:
        rc, out = sh(self.lab, *args)
        (self.assertEqual if ok else self.assertNotEqual)(rc, 0, out)
        return out

    def test_the_step_commits_the_registration_before_it_measures(self):
        """The step names the refusal and its way out, not the measurement;
        the measurement stays refused until the commit (nothing is let
        through); committed, the step is the measurement, and it runs."""
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("a measurement would be refused now", nxt)
        self.assertIn("the registration as committed (HEAD) lacks", nxt)
        self.assertIn("commit the registration", nxt)
        self.assertNotIn("opens a run bound to", nxt)
        refused = self.run_(
            ".venv/bin/python", f"{AREA}/scripts/01_measure.py", ok=False
        )
        self.assertIn("the registration as committed (HEAD) lacks", refused)
        self.assertFalse((self.lab / AREA / "runs").is_dir())
        self.run_("git", "add", AREA, "tests")
        self.run_("git", "commit", "-q", "-m", "register", "--", AREA, "tests")
        nxt = self.run_(".venv/bin/labkit-next", AREA)
        self.assertNotIn("would be refused", nxt)
        self.assertIn("opens a run bound to", nxt)
        self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        self.assertEqual(len(list((self.lab / AREA / "runs").iterdir())), 1)

    def test_a_report_draft_commits_before_measurement_then_owes_progress(self):
        self.run_(".venv/bin/protocol-fill", P, "report=REPORT.md")
        (self.lab / "REPORT.md").write_text(
            "# Report\n\nThe question and method; no measurement yet.\n", "utf-8"
        )
        self.run_("git", "add", AREA, "tests", "REPORT.md")
        self.run_(
            "git",
            "commit",
            "-q",
            "-m",
            "register with a report draft",
            "--",
            AREA,
            "tests",
            "REPORT.md",
        )
        step = self.run_(".venv/bin/labkit-next", AREA)
        self.assertIn("opens a run bound to", step)
        report = self.lab / "REPORT.md"
        draft = report.read_text(encoding="utf-8")
        report.write_text(draft + "\n<!-- /labkit result -->\n", encoding="utf-8")
        malformed = self.run_(
            ".venv/bin/report-check", "--if-reported", "REPORT.md", ok=False
        )
        self.assertIn("its blocks do not read", malformed)
        report.write_text(draft, encoding="utf-8")
        measured = self.run_(".venv/bin/python", f"{AREA}/scripts/01_measure.py")
        run_id = re.search(r"run: (\S+)", measured)
        self.assertIsNotNone(run_id, measured)
        assert run_id is not None
        self.run_("git", "add", AREA, "REPORT.md")
        held = self.run_(
            "git",
            "commit",
            "-q",
            "-m",
            "measurement without progress",
            "--",
            AREA,
            "REPORT.md",
            ok=False,
        )
        self.assertIn("carries neither", held)
        self.run_(
            ".venv/bin/protocol-fill",
            P,
            "--discuss",
            run_id.group(1),
            "--why",
            "measured; audit and adoption remain open",
            "--into",
            "REPORT.md",
        )
        self.run_("git", "add", AREA, "REPORT.md")
        self.run_(
            "git",
            "commit",
            "-q",
            "-m",
            "measurement and progress",
            "--",
            AREA,
            "REPORT.md",
        )
