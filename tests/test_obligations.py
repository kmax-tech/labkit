"""The separation of obligations (docs/notes/2026-11-14-exploratory-workflow-plan.md,
"Separation of obligations"): the number of a fit or an apply stands under
`[kept]` at every type; a criterion is an offer in exploration and owed in
confirmation, and judges exactly that number. One test per case of the
plan's table — exploration without a criterion, with one, a failed quality
check, confirmation — from data in memory; the stamped skeleton beside it.
The command chain is `tests/test_obligations_scenario.py`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import result_render
from labkit.formats import promises, protocol_block, protocol_check, standard_contract
from labkit.formats.protocol_history import registration_missing
from labkit.tools import scaffold
from protocol_fixture import DEFAULT_BLOCK, head, take_criterion_offer

RUN = "2026-11-17T10-00-00_abcd"
#: the default block without its criterion: the quality checks alone
QUALITY_ONLY = DEFAULT_BLOCK.split("\n\n", 1)[1]
QUESTION = "- **Question / hypothesis:** does feature 0 predict the label?\n"
CHECKS = (
    "- **Quality check:** [quality-check-1] the yield suffices\n"
    "- **Null condition / anchors:** [quality-check-2] the null lane sits at chance\n"
)
CRITERION = "- **Inference criterion:** [criterion-1] the kept score clears its bar\n"


def protocol(protocol_type: str, *, criterion: bool) -> str:
    """A low fit of PROTOCOL_TYPE (`[kept]` n, unit 1), its quality checks
    registered, with or without CRITERION — table and prose together."""
    block = DEFAULT_BLOCK if criterion else QUALITY_ONLY
    return (
        head(repeat_cost="low", kind="fit", type=protocol_type, promises=block)
        + QUESTION
        + CHECKS
        + (CRITERION if criterion else "")
    )


def criterion_gaps(text: str) -> list[str]:
    """The must gaps of TEXT that name the criterion, field or table."""
    return [
        g
        for g in protocol_check.check_fields(text).missing_must
        if "criterion" in g.casefold()
    ]


def recorded(text: str, metrics: dict) -> tuple[list[str], str]:
    """(verdicts, Recorded results line) of TEXT's promises over METRICS,
    as `result_render` writes them, the kept number first."""
    block = promises.parse_block(text)
    assert block is not None
    line = result_render.recorded_results_line(
        metrics,
        RUN,
        frozenset(p.key for p in block.promises),
        kept=protocol_block.kept(text),
    )
    return result_render.verdicts(block, metrics, {}), line


class ExplorationWithoutACriterion(unittest.TestCase):
    """The score and its unit; no success verdict."""

    TEXT = protocol("exploratory", criterion=False)

    def test_nothing_is_owed_for_the_criterion(self):
        self.assertEqual(protocol_check.low_registration_missing(self.TEXT), [])
        self.assertEqual(criterion_gaps(self.TEXT), [])
        head_ = protocol_block.head(self.TEXT)
        must, _ = protocol_check.owed(self.TEXT, head_)
        self.assertNotIn(standard_contract.CRITERION_FIELD, [f.label for f in must])

    def test_the_kept_number_is_reported_without_a_verdict(self):
        metrics = {"n": 0.8, "quality_check_1_pass": True, "quality_check_2_pass": True}
        verdicts, line = recorded(self.TEXT, metrics)
        self.assertEqual(verdicts, ["quality-check-1 met", "quality-check-2 met"])
        self.assertEqual(line, f"kept number: n = 0.8 (run {RUN})")

    def test_the_rest_of_the_registration_stays_owed(self):
        """The quality checks and the null condition: an exploration is no
        licence to measure without them."""
        bare = head(repeat_cost="low", kind="fit", promises=QUALITY_ONLY) + QUESTION
        self.assertEqual(
            protocol_check.low_registration_missing(bare),
            ["Quality check", "Null condition / anchors"],
        )


class ExplorationWithACriterion(unittest.TestCase):
    """The score and the verdict against the registered bar."""

    TEXT = protocol("exploratory", criterion=True)

    def test_the_criterion_judges_the_kept_number(self):
        self.assertEqual(protocol_check.low_registration_missing(self.TEXT), [])
        metrics = {
            "n": 0.8,
            "criterion_1_threshold": 0.75,
            "criterion_1_pass": True,
            "quality_check_1_pass": True,
            "quality_check_2_pass": True,
        }
        verdicts, line = recorded(self.TEXT, metrics)
        self.assertEqual(
            verdicts, ["criterion-1 met", "quality-check-1 met", "quality-check-2 met"]
        )
        self.assertTrue(line.startswith("kept number: n = 0.8; also recorded: "), line)


class AQualityCheckFails(unittest.TestCase):
    """The value stays visible; a stored value is no released result, and
    the existing limit on its judgement is kept."""

    def test_the_kept_number_stays_and_the_criterion_is_not_assessable(self):
        text = protocol("exploratory", criterion=True)
        metrics = {
            "n": 0.8,
            "criterion_1_threshold": None,
            "criterion_1_pass": None,
            "quality_check_1_pass": False,
            "quality_check_2_pass": True,
        }
        verdicts, line = recorded(text, metrics)
        self.assertTrue(verdicts[0].startswith("criterion-1 not assessable"), verdicts)
        self.assertEqual(verdicts[1], "quality-check-1 not met")
        self.assertTrue(line.startswith("kept number: n = 0.8"), line)

    def test_without_a_criterion_the_failed_check_is_the_verdict(self):
        text = protocol("exploratory", criterion=False)
        metrics = {
            "n": 0.8,
            "quality_check_1_pass": False,
            "quality_check_2_pass": True,
        }
        verdicts, line = recorded(text, metrics)
        self.assertEqual(verdicts, ["quality-check-1 not met", "quality-check-2 met"])
        self.assertEqual(line, f"kept number: n = 0.8 (run {RUN})")


class Confirmation(unittest.TestCase):
    """The present strict requirements: the criterion's field and table are
    owed before a run and at the freeze; the twin with both passes."""

    def test_a_confirmatory_fit_without_a_criterion_is_held(self):
        text = protocol("confirmatory", criterion=False)
        missing = protocol_check.low_registration_missing(text)
        self.assertIn(standard_contract.CRITERION_FIELD, missing)
        self.assertTrue(
            any(
                m.startswith('[[promise]] criterion — kind = "fit" with type')
                for m in missing
            ),
            missing,
        )
        (gap,) = [
            g
            for g in protocol_check.check_fields(text).must_gaps
            if g.label.startswith("[[promise]] criterion")
        ]
        self.assertEqual(gap.rule, protocol_check.LAB_003)
        self.assertIn("uncomment the offered `criterion-1` table", gap.label)

    def test_the_twin_with_its_criterion_passes(self):
        text = protocol("confirmatory", criterion=True)
        self.assertEqual(protocol_check.low_registration_missing(text), [])
        self.assertEqual(criterion_gaps(text), [])

    def test_an_undecided_type_owes_the_most(self):
        text = protocol("<exploratory | confirmatory>", criterion=False)
        self.assertIn(
            standard_contract.CRITERION_FIELD,
            protocol_check.low_registration_missing(text),
        )

    def test_a_type_turned_confirmatory_after_the_measurement_owes_it_then(self):
        """The first measurement's commit held an exploration without a
        criterion; the protocol says confirmatory today: the release reads
        the registration under the stricter type, so renaming the type
        loosens nothing. The twin: still exploratory, nothing missing."""
        then = protocol("exploratory", criterion=False)
        self.assertIn(
            standard_contract.CRITERION_FIELD,
            registration_missing(then, "fit", "confirmatory"),
        )
        self.assertEqual(registration_missing(then, "fit", "exploratory"), [])

    def test_the_registration_stamp_is_unchanged_by_the_type(self):
        """The lock still records the criterion field at every fit: the
        registration locks are rebuilt in their own step."""
        for protocol_type in ("exploratory", "confirmatory"):
            stamp = protocol_check.registration_stamp(
                protocol(protocol_type, criterion=False)
            )
            self.assertIn(standard_contract.CRITERION_FIELD, stamp)


class StampedSkeleton(unittest.TestCase):
    """The stamped estimator skeleton computes the score once under the
    head's `[kept]` key; the offered criterion, once taken in both steps,
    adds only its threshold and verdict over that very value."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            scaffold.stamp_lab(self.root, "lab")
            self.area, _ = scaffold.stamp_area(
                self.root, "screen", repeat_cost="low", kind="apply"
            )

    def load(self):
        name = f"obligations_{id(self)}_{len(sys.modules)}"
        spec = importlib.util.spec_from_file_location(
            name, self.area / "scripts" / "01_measure.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def rows(measure, correct: int) -> list[dict]:
        golds = ["pos", "neg"] * 6
        flip = {"pos": "neg", "neg": "pos"}
        reg = [
            measure.lane_row(
                "registered", {"id": str(i)}, g if i < correct else flip[g], g
            )
            for i, g in enumerate(golds)
        ]
        null = [
            measure.lane_row(
                "null",
                {"id": str(i)},
                g,
                golds[(i + 1) % 12],
                gold_of=str((i + 1) % 12),
            )
            for i, g in enumerate(golds)
        ]
        return reg + null

    def test_as_stamped_the_score_has_no_verdict(self):
        measure = self.load()
        self.assertEqual(measure.KEPT_KEY, "score")
        self.assertFalse(measure.CONFIG.bar_criterion)
        m = measure.evaluate_rows(self.rows(measure, 12))
        self.assertEqual(m["score"], 1.0)
        self.assertFalse([k for k in m if k.startswith("criterion_")])

    def test_the_offer_taken_judges_the_kept_score(self):
        take_criterion_offer(self.area)
        measure = self.load()
        self.assertTrue(measure.CONFIG.bar_criterion)
        for correct in (12, 6):
            # the run's permitted deviation held wide: [quality-check-2]
            # passes whatever the null draw, so the criterion judges
            with mock.patch.object(measure, "run_null_band", return_value=1.0):
                m = measure.evaluate_rows(self.rows(measure, correct))
            self.assertEqual(m["score"], correct / 12)
            self.assertIs(
                m["criterion_1_pass"], m["score"] >= m["criterion_1_threshold"]
            )


if __name__ == "__main__":
    unittest.main()
