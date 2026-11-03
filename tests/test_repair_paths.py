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

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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
        self.assertIn("next: a correction in place — Unit", said)
        self.assertIn("owes no new measurement", said)
        self.assertIn(
            "only its `resolved` on this finding, for exactly this text", said
        )
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
        is bound to it, the line names the way back and the route."""
        _, said = self.rewritten(
            "Terms of this protocol", "Terms", "case: one line of cases.jsonl"
        )
        self.assertIn("held: this repair changes what the first measurement", said)
        self.assertIn("a new measurement would carry the change, not repair it", said)
        self.assertIn("names the field as its place", said)

    def test_the_twin_a_conclusion_rewritten_owes_no_measurement_and_no_audit(self):
        record = self.audit(
            "Summary", "the Conclusion claims completeness nothing measured"
        )
        self.fill("Conclusion=The twelve cases hold 3.5 documents each on average.")
        said = self.decide(record, "fixed", "dropped the completeness claim")
        self.assertIn(
            "A repair written after the audit — the Conclusion, the other Summary "
            "fields — owes no new measurement and no new analysis audit by itself.",
            said,
        )
        self.assertIn("The decision and report reviews the protocol owes stand", said)
        self.assertNotIn("held:", said)
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
        self.assertIn("next: the repair is in the area — measure again", said)
        self.commit("rows() repaired; finding 1 decided")
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
        are unchanged. (A record edited in place passes: no check reads a
        record's content against its kept copy — the limit
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
        self.assertIn("--review", said)
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
