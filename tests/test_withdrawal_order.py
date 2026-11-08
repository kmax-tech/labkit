"""The withdrawal of a declared result comes first because finalize found
the declared run's code (or that of a run it derives from, or a declared
scope) changed — carried as data by the comparison that found it
(`GateFinding.changed_since`), never read off the blockers' words.

Read off the words `changed since <declared run>`, a reworded phrase would
drop the withdrawal-first order and `labkit-next` would advise a third
measurement; a blocker about a predecessor run, naming another id, would
lose it; an unrelated blocker quoting the phrase would gain it. Code that
could not be compared (a commit the clone lacks) is no change and keeps no
withdrawal-first order."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

from labkit.formats.gate import blocker, withdrawn_first
from labkit.formats import area_state
from labkit.formats.commands import withdraw_command
from labkit.gates import report_check, report_context
from test_end_to_end import CountCommands

RUN = "2026-01-02T00-00-00_b000"
PREDECESSOR = "2026-01-01T00-00-00_a000"


def context(protocol: Path, state: str = area_state.TREE) -> Any:
    """What `held_declaration` reads of a `Checked`: the state, the answering
    run and the run the protocol declares — the same one."""
    return cast(
        Any,
        SimpleNamespace(
            file_state=state, run=Path("runs") / RUN, declared=RUN, protocol=protocol
        ),
    )


class HeldDeclaration(unittest.TestCase):
    PROTOCOL = Path("experiments/01-x/PROTOCOL-x.md")

    def held(self, *found, state: str = area_state.TREE) -> Path | None:
        return report_check.held_declaration(context(self.PROTOCOL, state), list(found))

    def changed(self, text: str, run: str = RUN):
        return replace(blocker(text, fix="`x`"), changed_since=run)

    def test_a_reworded_change_still_puts_the_withdrawal_first(self):
        found = self.changed(f"finalize: the measuring code differs from {RUN}")
        self.assertEqual(self.held(found), self.PROTOCOL)

    def test_a_predecessor_runs_change_puts_it_first_too(self):
        """The changed code of a run the answer derives from names that
        run, not the declared one."""
        found = self.changed("finalize: code changed", run=PREDECESSOR)
        self.assertEqual(self.held(found), self.PROTOCOL)

    def test_an_unrelated_blocker_quoting_the_phrase_does_not(self):
        quoting = blocker(f"finalize: a note changed since {RUN}", fix="`x`")
        self.assertIsNone(self.held(quoting))

    def test_code_that_could_not_be_compared_does_not(self):
        """A commit the clone lacks: its way out may name the withdrawal
        (`gate.withdrawn_first`), but nothing changed — fetching it may be
        all that is owed."""
        unread = withdrawn_first(
            [
                blocker(
                    f"finalize: {RUN} started at a commit this clone lacks", fix="`x`"
                )
            ],
            withdraw_command(self.PROTOCOL),
        )[0]
        self.assertIsNone(self.held(unread))

    def test_the_adoptions_own_proposal_withdraws_nothing(self):
        found = self.changed("finalize: code changed")
        self.assertIsNone(self.held(found, state=area_state.PROPOSED))


class RewordedInTheChain(CountCommands):
    """In the real chain: adopt A, change the measuring
    code, measure B; finalize's blockers reworded keep the withdrawal
    first (`chain_gaps`' held_by), the twin unreworded alike."""

    def held_by(self) -> Path | None:
        ctx = report_context.checked(self.area, self.protocol)
        return report_check.chain_gaps(ctx).held_by

    def test_rewording_finalize_keeps_the_withdrawal_first(self):
        self.adopted_a()
        self.change_code()
        self.measure()
        self.assertEqual(self.held_by(), self.protocol)
        finalized = report_check.finalize_findings

        def reworded(area: Path, protocol: Path, state, held):
            return [
                replace(f, text=f.text.replace("changed since", "differs from"))
                for f in finalized(area, protocol, state, held)
            ]

        with mock.patch.object(report_check, "finalize_findings", reworded):
            self.assertEqual(self.held_by(), self.protocol)


if __name__ == "__main__":
    unittest.main()
