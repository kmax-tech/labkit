"""Acceptance case 14 of the exploratory workflow plan
(docs/notes/2026-11-14-exploratory-workflow-plan.md), with real commands:
an exploratory apply without a success criterion, with the null
comparison its task asks for (the offered comparison with chance,
criterion-2, both steps taken). The run starts, finalize passes, the
adoption writes the kept number and the comparison's verdict, and no
criterion-1 verdict. The confirmatory twin of the same protocol is
refused at the run's start, naming the criterion it owes.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest

import pytest

from labkit.formats import promises, protocol_block
from labkit.formats import standard_contract as sc
from test_end_to_end import Lab, _replace, _strip_promise_placeholders, points_area

pytestmark = pytest.mark.slow

#: the unchanged predictor: the sign of feature 0 (points_area puts pos above
#: zero, neg below)
PREDICTOR = (
    "    return SignOfFeature0()\n\n\n"
    "class SignOfFeature0:\n"
    '    """pos when feature 0 is above zero — fixed, never fitted."""\n\n'
    "    def predict(self, X):\n"
    '        return ["pos" if x[0] > 0 else "neg" for x in X]'
)


def take_chance_comparison(area, protocol) -> None:
    """The two steps of the offered criterion-2: its table uncommented and
    its id named in the Inference criterion field (whatever it held), then
    its block in evaluate_rows uncommented. criterion-1 stays offered."""
    lines = protocol.read_text(encoding="utf-8").split("\n")
    start = lines.index('# id = "criterion-2"') - 1
    end = start
    while end < len(lines) and lines[end].startswith("# "):
        lines[end] = lines[end][2:]
        end += 1
    text = "\n".join(lines)
    text = re.sub(
        r"^- \*\*Inference criterion:\*\* [^\n]*$",
        "- **Inference criterion:** [criterion-2] the score strictly above the "
        "comparison threshold the permuted labels give",
        text,
        count=1,
        flags=re.M,
    )
    protocol.write_text(text, encoding="utf-8")
    script = area / "scripts" / "01_measure.py"
    out, inside = [], False
    for line in script.read_text(encoding="utf-8").split("\n"):
        if line.strip() in ("# --- criterion-2 begin", "# --- criterion-2 end"):
            inside = line.strip().endswith("begin")
        elif inside:
            line = line.replace("# ", "", 1)
        out.append(line)
    script.write_text("\n".join(out), encoding="utf-8")


class ExploratoryApplyWithoutCriterion(unittest.TestCase):
    """Acceptance 14: passes without a criterion; the null comparison the
    task requires is still owed and judged."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = points_area(self.lab, "low", "apply")
        self.measure = self.area / "scripts" / "01_measure.py"
        _replace(
            self.measure,
            [
                (
                    'ITEMS = AREA / "data" / "prepared" / "TODO_v1.jsonl"',
                    'ITEMS = AREA / "data" / "prepared" / "points_v1.jsonl"',
                ),
                (
                    'ESTIMATOR = "TODO: e.g. RandomForestClassifier(n_estimators=500, random_state=seed)"',
                    'ESTIMATOR = "SignOfFeature0()"',
                ),
                (
                    '    raise NotImplementedError(f"make_estimator(): {ESTIMATOR}")',
                    PREDICTOR,
                ),
            ],
        )
        _strip_promise_placeholders(self.protocol)
        self.lab.fill(self.protocol, "type=exploratory")
        self.lab.fill_open(
            self.protocol,
            **{
                "Terms of this protocol": "n/a — no coinage",
                "Question / hypothesis": "Does the sign of feature 0 agree with the label beyond chance?",
                "Quality check": "[quality-check-1] at most max_empty items without a prediction",
                "Null condition / anchors (in the same run)": "[quality-check-2] the permuted-label lane within the run's permitted deviation of the expectation",
                "Data / scope": "data/prepared/points_v1.jsonl, 12 labelled and 4 test points, 00_prepare.py",
                "Exclusions / filters": "none",
                "Unit": "one point",
            },
        )
        self.lab.script(self.area, "00_prepare.py")

    def start(self) -> subprocess.CompletedProcess[str]:
        """The full run as an agent starts it, its exit and output kept."""
        return subprocess.run(
            [sys.executable, str(self.measure)],
            cwd=self.lab.root,
            capture_output=True,
            text=True,
            env=self.lab.env,
        )

    def test_the_confirmatory_twin_is_refused_and_the_exploration_is_adopted(self):
        text = self.protocol.read_text(encoding="utf-8")
        block = promises.parse_block(text)
        assert block is not None
        self.assertEqual(sorted(block.by_id()), ["quality-check-1", "quality-check-2"])
        self.assertEqual(protocol_block.kept(text), sc.stamped_kept(sc.ESTIMATOR))
        # the twin: confirmatory without any criterion — no run starts
        _replace(
            self.protocol, [('\ntype = "exploratory"\n', '\ntype = "confirmatory"\n')]
        )
        self.lab.commit("a confirmatory registration without a criterion")
        before = sorted((self.area / "runs").iterdir())
        refused = self.start()
        self.assertNotEqual(refused.returncode, 0, refused.stdout)
        said = refused.stdout + refused.stderr
        self.assertIn("Inference criterion", said)
        # no run beside the preparation run 00_prepare.py recorded
        self.assertEqual(sorted((self.area / "runs").iterdir()), before, said)
        # exploratory, with the comparison with chance the task asks for:
        # criterion-1 stays offered
        _replace(
            self.protocol, [('\ntype = "confirmatory"\n', '\ntype = "exploratory"\n')]
        )
        take_chance_comparison(self.area, self.protocol)
        _strip_promise_placeholders(self.protocol)
        self.lab.commit("the registration, exploratory, with its null comparison")
        out = self.lab.script(self.area, "01_measure.py")
        run_id = self.lab.run_id_of(out)
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, run_id)
        rc, out = self.lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        line = next(
            ln
            for ln in self.protocol.read_text(encoding="utf-8").splitlines()
            if ln.startswith("- **Recorded results:**")
        )
        # the comparison the task asks for is judged; no success verdict
        self.assertRegex(line, r"criterion-2 (met|missed)")
        self.assertNotIn("criterion-1", line)
        self.assertIn("· recorded: kept number: score = ", line)
        self.assertIn(f"(run {run_id})", line)


if __name__ == "__main__":
    unittest.main()
