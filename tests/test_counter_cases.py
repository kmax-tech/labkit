"""The correct ways through the whole chain, after the contracts the repair
case gave rise to (K1–K3, docs/notes/2026-10-27-new-registration-contracts.md):
a fix measured again under unchanged promises, and a missed criterion
reported as the result, each released — run, analysis audit, decision,
follow-up, adoption, report-check, the stop and the commit. And the two
ways out of first measurements that saw different registrations (K3): a
handover without a number passes the stop and the commit while a declared
result is held; a new registration that declares its changes against each
is released.

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
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import findings, protocol_block  # noqa: E402
from labkit.gates import audit, report_check  # noqa: E402
from labkit.run import llm  # noqa: E402
import test_end_to_end as e2e  # noqa: E402 — the module, so its tests are not collected here

SIMULATED = "SIMULATED answer for a counter-case — no model was called.\n"
CLEAN = (
    SIMULATED
    + "verdict: 0 blockers, 0 warnings, 0 notes\nscope:\nscripts/01_measure.py"
)
MARGIN = "constants = { margin = 0.25 }"
SWAPPED = 'ANSWERS = {"Yes": "not_causal", "No": "causal"}'
RIGHT = 'ANSWERS = {"Yes": "causal", "No": "not_causal"}'


class _Chain(unittest.TestCase):
    """One judge area per class, as `test_end_to_end.Judge` registers it."""

    lab: e2e.Lab
    area: Path
    protocol: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = e2e.Lab()
        cls.area, cls.protocol = e2e.judge_area(cls.lab, "judge")
        cls.lab.commit("the judge, registered")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def run_measure(self, model) -> str:
        """Run the measure script with MODEL answering; the run id. Starts in
        a second of its own: two runs in one second have run ids that cannot
        say which is newest, and the answering run is then refused."""
        time.sleep(1 - time.time() % 1)
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

    def conflict(self) -> tuple[str, str]:
        """Two first measurements at one commit that saw different
        registrations: the first under the committed margin 0.25, the second
        with the margin raised to 0.3 in the tree (runlog keeps the
        uncommitted.patch); then committed. The two run ids."""
        first = self.run_measure(e2e.Judge._model)
        e2e._replace(self.protocol, [(MARGIN, MARGIN.replace("0.25", "0.3"))])
        second = self.run_measure(e2e.Judge._model)
        self.lab.commit("the margin raised after a measurement")
        return first, second

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


class ConflictHandedOver(_Chain):
    """No run answers a registered question; the agent hands over
    (`audit.HANDOVER`): no [result] table, a report that names the protocol
    and says what stands in the way, no number. The stop and the commit let
    it through; a report that cites the answering run is held, and the
    adoption of a run as the result is refused."""

    def test_a_handover_passes_a_cited_run_and_an_adoption_do_not(self):
        first, second = self.conflict()
        report = self.lab.root / "REPORT.md"
        handover = (
            "# Report\n\nThe judge question (experiments/01-judge/PROTOCOL-judge.md) "
            "is handed over unresolved: its first measurements recorded different "
            "registrations, so no run answers a registered question. Tried: "
            "report-check named both. No number is reported.\n"
        )
        report.write_text(handover, encoding="utf-8")
        rc, err = self.lab.stop_hook()
        self.assertEqual(rc, 0, err)
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(report, self.protocol)
        self.assertEqual(rc, 0, out)
        self.lab.commit("handed over")
        # a twin: the report cites the answering run — read as its number
        report.write_text(
            handover + f"\nThe runs: {first}, {second}.\n", encoding="utf-8"
        )
        self.lab.git("add", "-A")
        rc, out = self.lab.pre_commit(report)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"cites {second}, the answering run", out)
        self.lab.git("checkout", "HEAD", "--", "REPORT.md")
        # the other twin: the adoption of the second run as the result is refused
        rc, out = self.audit(CLEAN)
        self.assertEqual(rc, 0, out)
        rc, out = self.lab.adopt(self.protocol, second)
        self.assertEqual(rc, 1, out)
        self.assertIn("the first measurements recorded different registrations", out)
        self.assertIn("not adopted", out)
        self.assertIsNone(
            protocol_block.declared_run(self.protocol.read_text(encoding="utf-8"))
        )


class ConflictRegisteredAnew(_Chain):
    """A new registration, exploratory, that declares its changes against
    each registration the first measurements saw — held while one is
    missing, then released, the predecessor's question shown as unresolved
    before its own."""

    def test_a_replacement_declared_against_each_is_released(self):
        first, second = self.conflict()
        pid = protocol_block.head(self.protocol.read_text(encoding="utf-8")).id
        self.area, self.protocol = e2e.judge_area(self.lab, "judge-v2")
        e2e._replace(self.protocol, [(MARGIN, MARGIN.replace("0.25", "0.2"))])
        self._declare(f'[replaces]\nprotocol = "{pid}"\n' + _change("0.25"))
        self.lab.commit("registered anew, against the first registration only")
        (gap,) = report_check.replacement_gaps(
            report_check.checked(self.area, self.protocol)
        )
        self.assertIn(f"as its first measurement {second} saw it", gap.line)
        self.assertIn("with its uncommitted.patch", gap.line)
        self.assertIn("not declared: C1 margin 0.3 → 0.2", gap.line)
        self._declare(_change("0.3"))
        self.lab.commit("registered anew, against each")
        run_id = self.run_measure(e2e.Judge._model)
        rc, out = self.audit(CLEAN)
        self.assertEqual(rc, 0, out)
        text = self.released(run_id)
        self.assertIn(
            f"- **Recorded results:** replaces {pid} (01-judge/PROTOCOL-judge.md): "
            "no result declared — unresolved · this question: C1 met; A1 met; A2 met",
            text,
        )

    def _declare(self, tables: str) -> None:
        """TABLES into the protocol's TOML block, before its first promise."""
        text = self.protocol.read_text(encoding="utf-8")
        assert "\n[[promise]]\n" in text
        self.protocol.write_text(
            text.replace("\n[[promise]]\n", f"\n{tables}\n[[promise]]\n", 1),
            encoding="utf-8",
        )


def _change(was: str) -> str:
    """One [[replaces.change]]: the margin from WAS to 0.2."""
    return (
        f'\n[[replaces.change]]\nwhat = "C1 margin"\nfrom = "{was}"\nto = "0.2"\n'
        f'why = "the first measurements saw {was}"\n'
    )


if __name__ == "__main__":
    unittest.main()
