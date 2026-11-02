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
