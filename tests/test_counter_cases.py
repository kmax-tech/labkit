"""The correct ways through the whole chain, after the contracts the repair
case gave rise to (K1–K3, docs/notes/2026-10-27-new-registration-contracts.md):
a fix measured again under unchanged promises, and a missed criterion
reported as the result, each released — run, analysis audit, decision,
follow-up, adoption, report-check, the stop and the commit.

Every audit answer here is SIMULATED: no model is called; the answer is a
text written for the counter-case and goes through `labkit-audit`'s own
parser and record writer, as a real answer would. It checks the mechanical
release chain, not an auditor's judgement. The judge skeleton of
`test_end_to_end.Judge` is the area, its model faked.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import findings  # noqa: E402
from labkit.gates import audit, report_check  # noqa: E402
from labkit.run import llm  # noqa: E402
import test_end_to_end as e2e  # noqa: E402 — the module, so its tests are not collected here

SIMULATED = "SIMULATED answer for a counter-case — no model was called.\n"
CLEAN = (
    SIMULATED
    + "verdict: 0 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
)
SWAPPED = 'ANSWERS = {"Yes": "not_causal", "No": "causal"}'
RIGHT = 'ANSWERS = {"Yes": "causal", "No": "not_causal"}'


class _Chain(unittest.TestCase):
    """One judge area per class, as `test_end_to_end.Judge` stamps it."""

    GOLD = e2e.Judge.GOLD
    lab: e2e.Lab
    area: Path
    protocol: Path

    @classmethod
    def setUpClass(cls) -> None:
        e2e.Judge.setUpClass.__func__(cls)  # type: ignore[attr-defined]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def run_measure(self, model) -> str:
        """Run the measure script with MODEL answering; the run id."""
        out = io.StringIO()
        with (
            mock.patch.object(llm, "complete_many", model),
            mock.patch.object(
                llm,
                "provenance",
                lambda alias: {"model": "fake@e2e", "endpoint": "fake"},
            ),
            mock.patch.object(sys, "argv", [str(self.measure_script)]),
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.lab.root)}),
            contextlib.redirect_stdout(out),
        ):
            e2e._load(self.measure_script, f"counter_{id(model)}").main()
        return self.lab.run_id_of(out.getvalue())

    @property
    def measure_script(self) -> Path:
        return self.area / "scripts" / "01_measure.py"

    def audit(self, answer: str) -> tuple[int, str]:
        """`labkit-audit AREA --mode analysis`, the model's answer SIMULATED."""
        out = io.StringIO()
        with (
            mock.patch.object(audit.llm, "complete", lambda *a, **k: answer),
            mock.patch.object(audit.llm, "takes_max_tokens", lambda alias: True),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            rc = audit.main([str(self.area), "--mode", "analysis"])
        return rc, out.getvalue()

    def decide(self, record: Path, *argv: str) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = audit.main(
                [str(self.area), "--decide", "1", *argv, "--record", str(record)]
            )
        self.assertEqual(rc, 0, out.getvalue())

    def released(self, run_id: str) -> str:
        """Adopt RUN_ID, then report-check, the stop and the commit — each
        clean; the protocol's text."""
        lab = self.lab
        rc, out = lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        rc, out = lab.adopt(self.protocol, run_id)
        self.assertEqual(rc, 0, out)
        lab.fill(self.protocol, "Raw output=one pair per finding, from the run")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = report_check.main([str(self.area)])
        self.assertEqual(rc, 0, buf.getvalue())
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(self.protocol, self.measure_script)
        self.assertEqual(rc, 0, out)
        lab.commit("the result, adopted")
        return self.protocol.read_text(encoding="utf-8")


class RepairUnderUnchangedPromises(_Chain):
    """An implementation error found by the analysis audit, fixed, measured
    again under the same promises and followed up: released. The twin of
    the repair case, which moved its bars instead (K3 holds that)."""

    def test_a_fix_measured_again_and_followed_up_is_released(self):
        e2e._replace(self.measure_script, [(RIGHT, SWAPPED)])
        self.lab.commit("the labels swapped: an implementation error")
        first = self.run_measure(e2e.Judge._model)
        rc, out = self.audit(
            SIMULATED
            + "BLOCKER · scripts/01_measure.py:82 · ANSWERS reads Yes as not_causal · "
            "c1_accuracy counts every causal sentence wrong · LAB-038 What the prompt "
            "demands · map Yes to causal\n"
            "verdict: 1 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
        )
        self.assertEqual(rc, 1, out)
        (record,) = [r for r in findings.area_records(self.area) if r.run_id == first]
        e2e._replace(self.measure_script, [(SWAPPED, RIGHT)])
        self.decide(record.path, "fixed", "ANSWERS maps Yes to causal again")
        self.lab.commit("the labels fixed")
        second = self.run_measure(e2e.Judge._model)
        rc, out = self.audit(
            SIMULATED
            + f"FIX · {record.path.name}#1 · resolved · scripts/01_measure.py:82 maps Yes "
            f"to causal; c1_accuracy 1.0 in run {second}\n"
            + CLEAN.removeprefix(SIMULATED)
        )
        self.assertEqual(rc, 0, out)
        text = self.released(second)
        self.assertIn(
            "- **Recorded results:** C1 met; A1 met; A2 met · recorded: ", text
        )
        self.assertIn(f"(run {second})", text)


class HonestMiss(_Chain):
    """The code does what it says and the criterion is missed: that is the
    result, reported as a miss and released — never not assessable, never
    a pass."""

    @staticmethod
    def _misses(alias: str, prompts: list[str]) -> list[str]:
        """A model that answers No on the registered lane: accuracy at the
        null's, below the margin; the placebo at chance as registered."""
        return [
            "Yes" if p.startswith("Is this text written in English?") else "No"
            for p in prompts
        ]

    def test_a_missed_criterion_is_released_as_a_miss(self):
        run_id = self.run_measure(self._misses)
        rc, out = self.audit(CLEAN)
        self.assertEqual(rc, 0, out)
        text = self.released(run_id)
        self.assertIn(
            "- **Recorded results:** C1 missed; A1 met; A2 met · recorded: ", text
        )


if __name__ == "__main__":
    unittest.main()
