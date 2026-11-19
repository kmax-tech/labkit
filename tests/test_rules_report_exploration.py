"""Rule tests of `report_exploration.unresolved_link_hold`: a confirmation's
link to its exploration (`[explored_in]`) whose id names no protocol of the
repo, or several, holds the release; an id that names exactly one, and a
protocol without the link, hold nothing — each from a link and the repo's
protocol ids in memory (docs/architecture.md, "Checks and their tests").
The station that reads them for report-check is `report_exploration.link_gaps`,
tested in tests/test_report_check_stations.py.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from check_guards import pure_call
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    NOT_EXECUTABLE,
    TECHNICAL_RULE,
    GateFinding,
)
from labkit.formats.protocol_block import ExploredIn
from labkit.gates.report_exploration import unresolved_link_hold
from state_fixture import AREA

pytestmark = pytest.mark.rule

EXPLORATION = "p-aaaaaaaaaaaaaaaa"
CONFIRMATION = "p-cccccccccccccccc"
LINK = ExploredIn(EXPLORATION, "2026-11-17T10-00-00_aaaa")
PROTOCOL = AREA / "PROTOCOL-confirm.md"
THEIRS = Path("experiments") / "01-explore" / "PROTOCOL-explore.md"
COPY = Path("experiments") / "03-copy" / "PROTOCOL-explore.md"
HANDOVER = "hand over: `the handover command`"


def held(
    link: ExploredIn | None, ids: dict[str, list[Path]], *, has_measured: bool = True
) -> list[GateFinding]:
    """`unresolved_link_hold` for LINK against IDS, with no file read."""
    return pure_call(
        unresolved_link_hold,
        link,
        ids,
        AREA,
        PROTOCOL,
        CONFIRMATION,
        HANDOVER,
        has_measured=has_measured,
    )


class ALinkThatNamesNoOneProtocolHoldsTheRelease(unittest.TestCase):
    """The violation in its two forms, and the two valid twins."""

    def test_an_id_no_protocol_carries_is_a_check_that_did_not_run(self):
        (f,) = held(LINK, {"p-bbbbbbbbbbbbbbbb": [COPY]})
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome, f.rule),
            (BLOCKER, GUARANTEED, NOT_EXECUTABLE, TECHNICAL_RULE),
        )
        self.assertIn(
            f"[explored_in] protocol = {EXPLORATION} names no protocol of this repo",
            f.text,
        )
        self.assertIn("the result is not released over it", f.text)
        self.assertIn("BLOCKER (check not executable): exploration link:", f.line)
        assert f.fix is not None
        self.assertIn(
            "bring the exploratory protocol back from the commit that holds it "
            "(`git checkout <commit> -- <EXPLORATION_PROTOCOL>`)",
            f.fix,
        )
        self.assertIn("then `report-check area`", f.fix)

    def test_an_id_two_protocols_carry_is_a_check_that_did_not_run(self):
        (f,) = held(LINK, {EXPLORATION: [THEIRS, COPY]})
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome, f.rule),
            (BLOCKER, GUARANTEED, NOT_EXECUTABLE, TECHNICAL_RULE),
        )
        self.assertIn(
            f"[explored_in] protocol = {EXPLORATION} names 2 protocols "
            f"({THEIRS}, {COPY})",
            f.text,
        )
        assert f.fix is not None
        self.assertIn("re-stamp the copy", f.fix)
        self.assertIn(f"`protocol-check {THEIRS}`, `protocol-check {COPY}`", f.fix)

    def test_the_twin_an_id_exactly_one_protocol_carries_holds_nothing(self):
        self.assertEqual(held(LINK, {EXPLORATION: [THEIRS]}), [])

    def test_the_twin_a_protocol_without_the_link_holds_nothing(self):
        self.assertEqual(held(None, {}), [])
        self.assertEqual(held(None, {EXPLORATION: [THEIRS, COPY]}), [])


class TheWayOutFollowsWhetherTheProtocolMeasured(unittest.TestCase):
    """The link is written anew only before the first measurement; after
    it the link is registered, and the alternatives are a new registration
    or the handover."""

    def test_after_a_measurement_the_link_stays_and_the_ways_are_named(self):
        (f,) = held(LINK, {}, has_measured=True)
        assert f.fix is not None
        self.assertIn("the link itself is registered and stays as written", f.fix)
        self.assertIn("register anew: a new protocol", f.fix)
        # the new registration replaces this confirmation, not the exploration
        self.assertIn(f'`[replaces] protocol = "{CONFIRMATION}"`', f.fix)
        self.assertTrue(f.fix.endswith(f"; or {HANDOVER}"), f.fix)
        self.assertNotIn("--explored-in", f.fix)

    def test_before_the_first_measurement_the_link_is_written_anew(self):
        (f,) = held(LINK, {}, has_measured=False)
        assert f.fix is not None
        self.assertIn(
            "`protocol-fill area/PROTOCOL-confirm.md --explored-in "
            "<EXPLORATION_PROTOCOL>`",
            f.fix,
        )
        self.assertNotIn(HANDOVER, f.fix)


if __name__ == "__main__":
    unittest.main()
