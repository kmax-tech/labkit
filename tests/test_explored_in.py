"""`[explored_in]`, a confirmation's link to its exploration: the table read
from the protocol head (`protocol_block.explored_in`); the link's validity
(`exploration_link.linked_exploration`) — a confirmatory protocol, one other
protocol of the repo whose first measurements were exploratory, its
completed and adopted run —, held where `protocol-fill --explored-in`
writes the link and at the start of the first confirming measurement
(`start_check.require_exploration_link`), then compared as a registration
part (`protocol_history.scope_differences`); the runs the named state rests
on (`exploration_state.basis_closure`); the area stamp that follows that
state and no run beside it (`scope_sha.exploration_basis`); what the
confirming audit is shown (`audit_prompt.exploration_evidence`); the
warning report-check gives for a run of the exploration that audit was not
shown (`report_exploration.later_use_findings`); and the blocker it gives
for a link whose id names no one protocol (`report_exploration.link_gaps`;
the rule from data in memory: tests/test_rules_report_exploration.py), with
the restore of a protocol no file carries read from the history
(`protocol_then.last_held_with_id`, `report_exploration.last_held`)."""

from __future__ import annotations

import contextlib
import dataclasses
import io
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from command_fixture import run_main
from protocol_fixture import head, scope_file
from repo_fixture import git as _git
from state_fixture import audit_record

from labkit.formats import protocol_block, runs, scope_sha
from labkit.formats.exploration_link import (
    LinkedExploration,
    NotLinked,
    adopted_link,
    linked_exploration,
)
from labkit.formats.area_state import HistoryUnread, state_of
from labkit.formats.attempts import Attempt
from labkit.formats.exploration_state import (
    SharedInput,
    basis_closure,
    not_shown_since,
    shared_inputs,
)
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    NOT_EXECUTABLE,
    Findings,
    STATIC_EVIDENCE,
    SUSPECTED,
    TECHNICAL_RULE,
    WARNING,
)
from labkit.formats.protocol_block import BlockError, ExploredIn
from labkit.formats.protocol_history import scope_differences
from labkit.formats.protocol_then import last_held_with_id
from labkit.gates import preflight, registration_hold, report_check, report_exploration
from labkit.gates.audit_prompt import _closure_lines, exploration_evidence
from labkit.gates.report_exploration import (
    LAB_050,
    LastHeld,
    audit_began,
    last_held,
    later_use_findings,
    link_gaps,
    use_after_audit_findings,
)
from labkit.run import runlog
from labkit.tools import protocol_fill

EXPLORATION = "p-aaaaaaaaaaaaaaaa"
CONFIRMATION = "p-cccccccccccccccc"
OTHER = "p-bbbbbbbbbbbbbbbb"
RUN = "2026-11-17T10-00-00_aaaa"


def link_toml(protocol: str = EXPLORATION, run: str = RUN, more: str = "") -> str:
    """An `[explored_in]` table as TOML, MORE appended verbatim."""
    return f'\n[explored_in]\nprotocol = "{protocol}"\nrun = "{run}"\n{more}'


def protocol(
    pid: str,
    type: str,
    *,
    tables: str = "",
    result: str | None = None,
    conclusion: str = "",
    step: str = "",
    exclusions: str = "none",
) -> str:
    """A computation at low repeat cost — its question is its whole
    registration —, its head carrying TABLES and STEP verbatim, RESULT as
    its adopted run and CONCLUSION as its Conclusion field."""
    return head(
        id=pid,
        type=type,
        repeat_cost="low",
        promises=(tables + step) or None,
        result=result,
    ) + (
        "\n- **Question / hypothesis:** how many documents per case?\n"
        f"- **Exclusions / filters:** {exclusions}\n"
        + (f"- **Conclusion:** {conclusion}\n" if conclusion else "")
    )


class Parse(unittest.TestCase):
    """The table from data in memory: each field and its refusal."""

    def test_a_link_reads_both_references(self) -> None:
        text = protocol(CONFIRMATION, "confirmatory", tables=link_toml())
        self.assertEqual(protocol_block.explored_in(text), ExploredIn(EXPLORATION, RUN))

    def test_the_twin_no_table_is_no_link(self) -> None:
        self.assertIsNone(
            protocol_block.explored_in(protocol(CONFIRMATION, "confirmatory"))
        )

    def test_each_malformed_field_is_named(self) -> None:
        cases = {
            "[explored_in] protocol": link_toml(protocol="PROTOCOL-x.md"),
            "[explored_in] run": link_toml(run="runs/2026-11-17"),
            "unknown field": link_toml(more='area = "01-explore"\n'),
        }
        for named, table in cases.items():
            with self.subTest(named), self.assertRaises(BlockError) as cm:
                protocol_block.explored_in(
                    protocol(CONFIRMATION, "confirmatory", tables=table)
                )
            self.assertIn(named, str(cm.exception))

    def test_the_table_writes_as_it_reads(self) -> None:
        link = ExploredIn(EXPLORATION, RUN)
        text = protocol(CONFIRMATION, "confirmatory").replace(
            "```\n", protocol_block.explored_in_toml(link) + "```\n"
        )
        self.assertEqual(protocol_block.explored_in(text), link)


class RegistrationPart(unittest.TestCase):
    """After the first measurement the link is compared like `[kept]`."""

    def test_a_changed_link_is_a_difference_and_the_twin_none(self) -> None:
        old = protocol(CONFIRMATION, "confirmatory", tables=link_toml())
        new = protocol(
            CONFIRMATION, "confirmatory", tables=link_toml(run=RUN[:-4] + "bbbb")
        )
        self.assertEqual([d[0] for d in scope_differences(old, new)], ["[explored_in]"])
        self.assertEqual(scope_differences(old, old), [])

    def test_a_link_added_later_is_a_difference(self) -> None:
        old = protocol(CONFIRMATION, "confirmatory")
        new = protocol(CONFIRMATION, "confirmatory", tables=link_toml())
        ((what, was, now),) = scope_differences(old, new)
        self.assertEqual((what, was), ("[explored_in]", "(none)"))
        self.assertIn(RUN, now)

    def test_the_hold_on_it_cites_the_rule_that_names_the_link(self) -> None:
        self.assertEqual(
            registration_hold.scope_rule([("[explored_in]", "a", "b")]),
            registration_hold.LAB_003,
        )


class _TwoAreas(unittest.TestCase):
    """A repository with an exploratory protocol in one area, measured once
    (run A, committed, adopted), and a confirmatory one in another."""

    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("LABKIT_UNFROZEN", None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        _git(self.root, "init", "-q")
        self.explore = self.area("01-explore")
        self.confirm = self.area("02-confirm")
        self.theirs = self.explore / "PROTOCOL-explore.md"
        self.ours = self.confirm / "PROTOCOL-confirm.md"
        self.theirs.write_text(protocol(EXPLORATION, "exploratory"), encoding="utf-8")
        self.ours.write_text(protocol(CONFIRMATION, "confirmatory"), encoding="utf-8")
        self.commit("stamp")
        self.a = self.measure(self.explore)
        self.adopt(self.a)
        self.commit("A")

    def area(self, name: str) -> Path:
        area = self.root / "experiments" / name
        area.mkdir(parents=True)
        scope_file(area)
        return area

    def commit(self, message: str) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", message)

    def measure(
        self,
        area: Path,
        *,
        data: dict[str, Path] | None = None,
        output: str | None = None,
        repeat_of: str | None = None,
        protocol: Path | None = None,
    ) -> str:
        """A completed measurement of AREA, reading DATA (None: no input)
        and writing OUTPUT; its id."""
        r = runlog.run(
            "m",
            config={},
            base_dir=area,
            data=data if data is not None else runlog.NO_INPUTS,
            run_kind="measurement",
            repeat_of=repeat_of,
            protocol=protocol,
        )
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            if output is not None:
                run.output(area / output)
                (area / output).write_text('{"id": 1}\n', encoding="utf-8")
            run.metrics(n=1)
        return run.run_id

    def adopt(
        self, run: str | None, *, conclusion: str = "short ones carry it"
    ) -> None:
        """The exploratory protocol with RUN adopted (None: withdrawn)."""
        self.theirs.write_text(
            protocol(EXPLORATION, "exploratory", result=run, conclusion=conclusion),
            encoding="utf-8",
        )

    def link(self, run: str | None = None, *, pid: str = EXPLORATION) -> str:
        """The confirmatory protocol's text with a link to RUN (A)."""
        return protocol(
            CONFIRMATION, "confirmatory", tables=link_toml(pid, run or self.a)
        )

    def linked(self, text: str) -> LinkedExploration | NotLinked | None:
        return linked_exploration(text, protocol_block.repo_protocol_ids(self.root))

    def refused(self, text: str) -> str:
        """Why TEXT's link is not valid."""
        found = self.linked(text)
        assert isinstance(found, NotLinked), found
        return found.why


class Link(_TwoAreas):
    """`linked_exploration`: each condition, and the valid twin."""

    def test_the_twin_an_adopted_exploratory_run_is_linked(self) -> None:
        found = self.linked(self.link())
        assert isinstance(found, LinkedExploration), found
        self.assertEqual((found.protocol, found.run.dir.name), (self.theirs, self.a))

    def test_no_table_is_no_link(self) -> None:
        self.assertIsNone(self.linked(protocol(CONFIRMATION, "confirmatory")))

    def test_an_exploratory_protocol_names_no_exploration(self) -> None:
        text = self.link().replace('type = "confirmatory"', 'type = "exploratory"')
        self.assertIn("a confirmation's link", self.refused(text))

    def test_its_own_id_is_refused(self) -> None:
        self.assertIn("own id", self.refused(self.link(pid=CONFIRMATION)))

    def test_an_id_no_protocol_carries_is_refused(self) -> None:
        self.assertIn("no protocol of this repo", self.refused(self.link(pid=OTHER)))

    def test_an_exploration_that_measured_nothing_is_refused(self) -> None:
        other = self.explore / "PROTOCOL-other.md"
        other.write_text(
            protocol(OTHER, "exploratory", result=self.a), encoding="utf-8"
        )
        self.assertIn("measured nothing", self.refused(self.link(pid=OTHER)))

    def test_a_first_measurement_that_was_confirmatory_is_refused(self) -> None:
        strict = self.area("03-strict")
        theirs = strict / "PROTOCOL-strict.md"
        theirs.write_text(protocol(OTHER, "confirmatory"), encoding="utf-8")
        self.commit("strict")
        run = self.measure(strict)
        # relabelled after its first measurement: the type then decides
        theirs.write_text(protocol(OTHER, "exploratory", result=run), encoding="utf-8")
        told = self.refused(self.link(run, pid=OTHER))
        self.assertIn("registered type confirmatory", told)

    def test_a_first_measurement_whose_text_is_lost_is_refused(self) -> None:
        loose = self.area("04-loose")
        theirs = loose / "PROTOCOL-loose.md"
        theirs.write_text(protocol(OTHER, "exploratory"), encoding="utf-8")
        self.commit("loose")
        theirs.write_text(
            protocol(OTHER, "exploratory", exclusions="tried"), encoding="utf-8"
        )
        run = self.measure(loose)  # from a changed tree
        (loose / "runs" / run / "uncommitted.patch").unlink()
        theirs.write_text(protocol(OTHER, "exploratory", result=run), encoding="utf-8")
        told = self.refused(self.link(run, pid=OTHER))
        self.assertIn("cannot be read", told)
        self.assertIn("no exploration is assumed", told)

    def test_a_run_of_another_protocol_is_refused(self) -> None:
        self.assertIn("is no run of", self.refused(self.link(RUN)))

    def test_a_repeat_is_refused(self) -> None:
        again = self.measure(self.explore, repeat_of=self.a)
        self.adopt(again)
        self.assertIn(f"a repeat of {self.a}", self.refused(self.link(again)))

    def test_a_run_not_adopted_is_refused(self) -> None:
        b = self.measure(self.explore)
        self.assertIn(f"has adopted {self.a}, not {b}", self.refused(self.link(b)))

    def test_a_withdrawn_adoption_is_refused(self) -> None:
        self.adopt(None)
        self.assertIn("has adopted no run", self.refused(self.link()))


class Command(_TwoAreas):
    """`protocol-fill --explored-in`: both references written, read once."""

    def fill(self, exploration: Path) -> tuple[int, str]:
        return run_main(
            protocol_fill.main, [str(self.ours), "--explored-in", str(exploration)]
        )

    def test_the_link_names_the_id_and_the_adopted_run(self) -> None:
        code, told = self.fill(self.theirs)
        self.assertEqual(code, 0, told)
        self.assertIn(self.a, told)
        written = protocol_block.explored_in(self.ours.read_text(encoding="utf-8"))
        self.assertEqual(written, ExploredIn(EXPLORATION, self.a))

    def test_a_second_link_replaces_the_first(self) -> None:
        self.assertEqual(self.fill(self.theirs)[0], 0)
        code, told = self.fill(self.theirs)
        self.assertEqual(code, 0, told)
        self.assertEqual(
            self.ours.read_text(encoding="utf-8").count("[explored_in]"), 1
        )

    def test_an_exploration_without_an_adoption_leaves_the_file_untouched(self) -> None:
        self.adopt(None)
        before = self.ours.read_text(encoding="utf-8")
        code, told = self.fill(self.theirs)
        self.assertEqual(code, 2, told)
        self.assertIn("has adopted no run", told)
        self.assertEqual(self.ours.read_text(encoding="utf-8"), before)

    def test_an_exploratory_protocol_is_refused_the_link(self) -> None:
        self.ours.write_text(protocol(CONFIRMATION, "exploratory"), encoding="utf-8")
        code, told = self.fill(self.theirs)
        self.assertEqual(code, 2, told)
        self.assertIn("a confirmation's link", told)

    def test_a_protocol_without_an_adoption_reads_as_not_linked(self) -> None:
        found = adopted_link(protocol(EXPLORATION, "exploratory"))
        assert isinstance(found, NotLinked)
        self.assertIn("has adopted no run", found.why)


class Start(_TwoAreas):
    """The first confirming measurement is refused under an invalid link,
    before its run directory exists; later ones do not ask again."""

    def started(self, text: str) -> str:
        """The refusal of a measurement under TEXT, "" when it starts."""
        self.ours.write_text(text, encoding="utf-8")
        self.commit("the confirmation's registration")
        runs_dir = self.confirm / "runs"
        held = set(runs_dir.iterdir()) if runs_dir.is_dir() else set()
        try:
            self.measure(self.confirm)
        except SystemExit as exc:
            now = set(runs_dir.iterdir()) if runs_dir.is_dir() else set()
            self.assertEqual(now, held)
            return str(exc.code)
        return ""

    def test_the_twin_a_valid_link_starts(self) -> None:
        self.assertEqual(self.started(self.link()), "")

    def test_the_twin_no_link_starts(self) -> None:
        self.assertEqual(self.started(protocol(CONFIRMATION, "confirmatory")), "")

    def test_a_link_typed_by_hand_with_the_right_values_starts(self) -> None:
        """The values are held, not who wrote them: a table in another
        spelling than the command's reads as the same link and starts."""
        typed = f'\n[explored_in]\nrun   = "{self.a}"\nprotocol = "{EXPLORATION}"\n'
        self.assertNotIn(
            protocol_block.explored_in_toml(ExploredIn(EXPLORATION, self.a)), typed
        )
        text = protocol(CONFIRMATION, "confirmatory", tables=typed)
        self.assertEqual(
            protocol_block.explored_in(text), ExploredIn(EXPLORATION, self.a)
        )
        self.assertEqual(self.started(text), "")

    def test_a_withdrawn_adoption_refuses_the_first_measurement(self) -> None:
        self.adopt(None)
        told = self.started(self.link())
        self.assertIn("is no valid link to an exploration", told)
        self.assertIn("has adopted no run", told)
        self.assertIn("--explored-in", told)

    def test_no_acknowledgement_passes_it(self) -> None:
        self.adopt(None)
        os.environ["LABKIT_UNFROZEN"] = "1"
        self.addCleanup(os.environ.pop, "LABKIT_UNFROZEN", None)
        self.assertIn("is no valid link to an exploration", self.started(self.link()))

    def test_after_the_first_measurement_the_link_is_not_asked_again(self) -> None:
        self.assertEqual(self.started(self.link()), "")
        self.adopt(None)
        self.assertEqual(self.started(self.link()), "")

    def test_a_table_that_does_not_read_is_refused(self) -> None:
        told = self.started(
            protocol(
                CONFIRMATION, "confirmatory", tables=link_toml(run="runs/2026-11-17")
            )
        )
        self.assertIn("[explored_in] run", told)


class _WithSource(_TwoAreas):
    """The adopted run C reads a source run's output and builds on A by a
    step; a side run D stands beside it."""

    def setUp(self) -> None:
        super().setUp()
        self.source = self.measure(self.explore, output="rows.jsonl", protocol=None)
        step = (
            f'\n[builds_on]\nid = "filter"\nrun = "{self.a}"\n'
            'occasion = "observation"\nwhy = "errors cluster"\n'
            '[[builds_on.change]]\nwhat = "Exclusions / filters"\n'
            'from = "none"\nto = "short documents"\n'
        )
        self.theirs.write_text(
            protocol(
                EXPLORATION, "exploratory", step=step, exclusions="short documents"
            ),
            encoding="utf-8",
        )
        self.commit("the step")
        self.c = self.measure(self.explore, data={"rows": self.explore / "rows.jsonl"})
        self.theirs.write_text(
            protocol(
                EXPLORATION,
                "exploratory",
                step=step,
                exclusions="short documents",
                result=self.c,
                conclusion="short ones carry it",
            ),
            encoding="utf-8",
        )
        self.commit("C adopted")
        self.ours.write_text(self.link(self.c), encoding="utf-8")
        self.commit("the link")

    def stamp(self) -> str:
        return scope_sha.area_snapshot(self.confirm).sha


class Closure(_WithSource):
    """`basis_closure`: the named run, its inputs' origins, its basis."""

    def test_the_closure_holds_the_origin_and_the_basis_and_no_side_run(self) -> None:
        side = self.measure(self.explore)
        closure = basis_closure(self.explore, self.c)
        reached = {m.run_id: m.reached for m in closure}
        self.assertEqual(set(reached), {self.c, self.source, self.a})
        self.assertNotIn(side, reached)
        self.assertEqual(reached[self.c], "the named run")
        self.assertEqual(reached[self.source], f"origin of {self.c} (rows)")
        self.assertEqual(reached[self.a], f"basis of {self.c}")
        self.assertEqual([m.unread for m in closure], [(), (), ()])

    def test_a_run_whose_text_is_lost_stays_in_it_with_why(self) -> None:
        self.theirs.write_text(
            self.theirs.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
        d = self.measure(self.explore)  # from a changed tree
        (self.explore / "runs" / d / "uncommitted.patch").unlink()
        (member,) = basis_closure(self.explore, d)
        self.assertEqual(len(member.unread), 1)
        self.assertIn("its uncommitted.patch is gone", member.unread[0])

    def test_a_run_that_is_gone_is_named_not_skipped(self) -> None:
        (member,) = basis_closure(self.explore, RUN)
        self.assertIn(f"run {RUN} does not read", member.unread[0])


class Stamp(_WithSource):
    """The confirmation's area stamp follows the named state — basis,
    selection, conclusion — and no run beside it."""

    def test_an_independent_side_run_leaves_the_stamp(self) -> None:
        before = self.stamp()
        self.measure(self.explore)
        self.assertEqual(self.stamp(), before)

    def test_a_changed_conclusion_changes_it(self) -> None:
        before = self.stamp()
        self.theirs.write_text(
            self.theirs.read_text(encoding="utf-8").replace(
                "short ones carry it", "long ones carry it"
            ),
            encoding="utf-8",
        )
        self.assertNotEqual(self.stamp(), before)

    def test_a_withdrawn_adoption_changes_it(self) -> None:
        before = self.stamp()
        self.theirs.write_text(
            self.theirs.read_text(encoding="utf-8").replace(
                f'[result]\nrun = "{self.c}"\n', ""
            ),
            encoding="utf-8",
        )
        self.assertIsNone(
            protocol_block.declared_run(self.theirs.read_text(encoding="utf-8"))
        )
        self.assertNotEqual(self.stamp(), before)

    def test_a_changed_output_of_the_origin_run_changes_it(self) -> None:
        before = self.stamp()
        (self.explore / "rows.jsonl").write_text('{"id": 2}\n', encoding="utf-8")
        self.assertNotEqual(self.stamp(), before)

    def test_a_changed_record_of_the_basis_changes_it(self) -> None:
        before = self.stamp()
        record = self.explore / "runs" / self.a / runs.CONFIG_FILE
        record.write_text(
            record.read_text(encoding="utf-8").replace('"m"', '"m2"', 1),
            encoding="utf-8",
        )
        self.assertNotEqual(self.stamp(), before)

    def test_a_changed_patch_of_a_run_in_the_closure_changes_it(self) -> None:
        """The text a run started under is its recorded commit plus its
        uncommitted.patch; the stamp holds both files."""
        before = self.stamp()
        patch = runs.patch_path(runs.run_path(self.explore, self.c))
        patch.write_bytes(
            patch.read_bytes() + b"+ a line\n" if patch.is_file() else b"+ a line\n"
        )
        self.assertNotEqual(self.stamp(), before)

    def test_the_stamp_says_what_it_covers(self) -> None:
        (told,) = scope_sha.area_snapshot(self.confirm).validation
        self.assertIn("names the exploration", told)
        self.assertIn(f"run {self.c} with the runs it rests on, 3 in all", told)

    def test_an_area_without_a_link_keeps_its_stamp(self) -> None:
        self.assertEqual(scope_sha.exploration_basis(self.explore), ([], ()))


class PreflightStamp(_WithSource):
    """preflight blocks a stamp it cannot compute from the named
    exploration, at station 5, and runs every later station."""

    def preflight(self) -> tuple[int, list[str], list[str]]:
        """(exit, lines told, blockers) of the whole preflight on the
        confirmation."""
        told: list[str] = []
        found = Findings(tell=told.append)
        return (
            preflight.preflight_area(self.confirm, findings=found),
            told,
            found.blocked,
        )

    @unittest.skipIf(os.geteuid() == 0, "root reads a file of mode 0")
    def test_an_output_of_the_closure_that_does_not_read_blocks(self) -> None:
        rows = self.explore / "rows.jsonl"
        rows.chmod(0)
        self.addCleanup(rows.chmod, 0o644)
        code, told, blocked = self.preflight()
        self.assertEqual(code, 1)
        (stamp,) = [m for m in blocked if m.startswith("cannot stamp")]
        self.assertIn("rows.jsonl", stamp)
        self.assertIn("── tests ──", told)  # the stations after it ran

    def test_the_twin_a_readable_closure_is_stamped_and_not_blocked(self) -> None:
        _, told, blocked = self.preflight()
        self.assertEqual([m for m in blocked if m.startswith("cannot stamp")], [])
        self.assertIn(f"  {self.stamp()}", told)


class Evidence(_WithSource):
    """What the confirming audit is shown of the exploration."""

    def pieces(self) -> dict[str, str]:
        text = self.ours.read_text(encoding="utf-8")
        return dict(exploration_evidence(self.confirm, text))

    def test_the_named_state_is_shown(self) -> None:
        pieces = self.pieces()
        selection = pieces["EXPLORATION: the selection and the conclusion"]
        self.assertIn(f"names run {self.c}", selection)
        self.assertIn(f"adopts now: {self.c}", selection)
        self.assertIn("short ones carry it", selection)
        basis = pieces["EXPLORATION: the named run and the runs it rests on"]
        self.assertIn(f'step "filter" on {self.a} (observation)', basis)
        self.assertIn('Exclusions / filters: "none" → "short documents"', basis)
        self.assertIn(f"run {self.source} (origin of {self.c} (rows))", basis)
        self.assertTrue(
            any("its registration as its first measurement" in k for k in pieces),
            list(pieces),
        )

    def test_an_unbound_run_is_not_called_a_preparation(self) -> None:
        """A run of the basis bound to no protocol: the audit is told it is
        bound to none, not what it was for — binding and a run's kind are
        two facts (a preparation can be bound, as the source run here is)."""
        (source,) = [
            m for m in basis_closure(self.explore, self.c) if m.run_id == self.source
        ]
        lines = _closure_lines(dataclasses.replace(source, protocol=None, then=None))
        self.assertEqual(
            lines,
            [
                f"- run {self.source} ({source.reached})",
                "  bound to no protocol: it owes no text",
            ],
        )

    def test_the_record_stamp_binds_the_basis_not_the_wording_shown(self) -> None:
        """An audit record stays current across a change of how the prompt
        words the basis: the stamp (`scope_sha`) covers the closure's
        records and outputs, not the rendered lines. The twin of the stale
        record a changed basis gives (`Closure`)."""
        before = self.stamp()
        with mock.patch(
            "labkit.gates.audit_prompt._closure_lines", lambda m: [f"- {m.run_id}"]
        ):
            basis = self.pieces()["EXPLORATION: the named run and the runs it rests on"]
            self.assertNotIn("bound to no protocol", basis)
            self.assertEqual(self.stamp(), before)

    def test_the_text_a_run_of_the_basis_started_under_is_shown_in_full(self) -> None:
        """C started under another text than the first measurement: the
        audit is shown that text whole, not only the step's lines."""
        own = [
            body
            for label, body in self.pieces().items()
            if label.startswith("EXPLORATION: its protocol ")
        ]
        self.assertTrue(
            any("- **Exclusions / filters:** short documents" in t for t in own), own
        )

    def test_a_text_changed_without_a_commit_is_shown_as_the_run_saw_it(self) -> None:
        """A run started from an uncommitted protocol edit: its own text
        is the commit's with the run's patch, and that text is shown."""
        self.theirs.write_text(
            self.theirs.read_text(encoding="utf-8").replace(
                "short documents\n- **", "short and empty documents\n- **"
            ),
            encoding="utf-8",
        )
        d = self.measure(self.explore, data={"rows": self.explore / "rows.jsonl"})
        # the tree goes back to the commit: only the run's patch holds the edit
        _git(self.root, "checkout", "--", str(self.theirs))
        self.assertNotIn("short and empty", self.theirs.read_text(encoding="utf-8"))
        self.ours.write_text(self.link(d), encoding="utf-8")
        own = [
            body
            for label, body in self.pieces().items()
            if label.startswith("EXPLORATION: its protocol ")
        ]
        self.assertTrue(
            any(
                "- **Exclusions / filters:** short and empty documents" in t
                for t in own
            ),
            own,
        )

    def test_a_withdrawn_adoption_is_said(self) -> None:
        self.theirs.write_text(
            self.theirs.read_text(encoding="utf-8").replace(
                f'[result]\nrun = "{self.c}"\n', ""
            ),
            encoding="utf-8",
        )
        self.assertIn(
            "adopts now: no run",
            self.pieces()["EXPLORATION: the selection and the conclusion"],
        )

    def test_a_shared_input_digest_is_named_and_the_twin_is_not(self) -> None:
        label = "EXPLORATION: input digests shared with this confirmation"
        self.assertIn("no run of the exploration's area", self.pieces()[label])
        fresh = self.confirm / "fresh.jsonl"
        fresh.write_text('{"id": 9}\n', encoding="utf-8")
        ours = self.measure(self.confirm, data={"cases": fresh})
        # a side run of the exploration reads the same bytes
        copy = self.explore / "copy.jsonl"
        copy.write_text('{"id": 9}\n', encoding="utf-8")
        side = self.measure(self.explore, data={"peek": copy})
        told = self.pieces()[label]
        self.assertIn(f"exploration run {side} (outside the named state): peek", told)
        self.assertIn(f"confirmation run {ours}: cases", told)

    def test_no_link_shows_nothing(self) -> None:
        self.assertEqual(
            exploration_evidence(self.confirm, protocol(CONFIRMATION, "confirmatory")),
            (),
        )


class SharedInputs(unittest.TestCase):
    """`shared_inputs` from records in memory."""

    def test_an_unreadable_record_contributes_nothing(self) -> None:
        gone = runs.RunDir(Path("runs") / RUN, None, None)
        self.assertEqual(shared_inputs([gone], [gone], set()), [])


def shared(run: str) -> SharedInput:
    """One shared input whose exploring run is RUN."""
    return SharedInput(
        run, "peek", "2026-11-18T09-00-00_cccc", "cases", "0" * 64, False
    )


class NotShown(unittest.TestCase):
    """`not_shown_since`: which shared inputs an audit was not shown, by
    the start its exploring run's id carries."""

    BEGAN = datetime(2026, 11, 18, 12, 0, 0)

    def test_a_run_started_after_the_audit_began_was_not_shown(self) -> None:
        later = shared("2026-11-18T12-00-01_aaaa")
        self.assertEqual(not_shown_since([later], self.BEGAN), [later])

    def test_the_twin_a_run_started_before_it_was_shown(self) -> None:
        earlier = shared("2026-11-18T11-59-59_aaaa")
        self.assertEqual(not_shown_since([earlier], self.BEGAN), [])

    def test_a_run_started_in_the_audit_s_own_second_was_not_shown(self) -> None:
        same = shared("2026-11-18T12-00-00_aaaa")
        self.assertEqual(not_shown_since([same], self.BEGAN), [same])

    def test_a_run_whose_id_carries_no_time_is_not_taken_as_shown(self) -> None:
        unordered = shared("2026-02-30T12-00-00_aaaa")
        self.assertEqual(not_shown_since([unordered], self.BEGAN), [unordered])

    def test_an_audit_of_unknown_start_has_seen_no_run(self) -> None:
        earlier = shared("2026-11-18T11-59-59_aaaa")
        self.assertEqual(not_shown_since([earlier], None), [earlier])


class AuditBegan(unittest.TestCase):
    """`audit_began`: the start of the covering record's attempt."""

    RECORD = audit_record("2026-11-18T12-05-analysis.toml", mode="analysis", run_id=RUN)

    def attempt(self, file: str, started: str) -> Attempt:
        return Attempt(
            "a1", "analysis", "m", "s", started, "here", outcome="record", file=file
        )

    def test_the_attempt_that_wrote_the_record_gives_its_start(self) -> None:
        journal = [
            self.attempt("another.toml", "2026-11-19T08:00:00"),
            self.attempt(self.RECORD.path.name, "2026-11-18T12:00:02"),
        ]
        self.assertEqual(
            audit_began([self.RECORD], journal), datetime(2026, 11, 18, 12, 0, 2)
        )

    def test_the_latest_of_several_covering_records_counts(self) -> None:
        newer = dataclasses.replace(
            self.RECORD,
            path=self.RECORD.path.with_name("2026-11-19T09-05-analysis.toml"),
        )
        journal = [
            self.attempt(self.RECORD.path.name, "2026-11-18T12:00:02"),
            self.attempt(newer.path.name, "2026-11-19T09:00:00"),
        ]
        self.assertEqual(
            audit_began([self.RECORD, newer], journal), datetime(2026, 11, 19, 9, 0, 0)
        )

    def test_no_attempt_for_the_record_gives_no_start(self) -> None:
        self.assertIsNone(audit_began([self.RECORD], []))
        other = [self.attempt("another.toml", "2026-11-19T08:00:00")]
        self.assertIsNone(audit_began([self.RECORD], other))

    def test_a_start_that_is_no_time_gives_no_start(self) -> None:
        journal = [self.attempt(self.RECORD.path.name, "yesterday")]
        self.assertIsNone(audit_began([self.RECORD], journal))


class WhereAGoneProtocolWasLastHeld(_TwoAreas):
    """`protocol_then.last_held_with_id`: the file and the commit a
    checkout brings a protocol back from, found by the id its head named
    there; and `report_exploration.last_held`, which asks it for the
    link's blocker and says why where the history was not read."""

    def head_commit(self) -> str:
        return _git(self.root, "rev-parse", "HEAD")

    def test_a_file_deleted_in_the_tree_is_held_by_head(self) -> None:
        self.theirs.unlink()
        self.assertEqual(
            last_held_with_id(self.root, EXPLORATION),
            [(self.theirs, self.head_commit())],
        )

    def test_a_committed_deletion_names_its_parent_and_the_checkout_restores(
        self,
    ) -> None:
        held = self.head_commit()
        self.theirs.unlink()
        self.commit("the exploratory protocol removed")
        self.commit("a later commit")
        self.assertEqual(
            last_held_with_id(self.root, EXPLORATION), [(self.theirs, held)]
        )
        _git(self.root, "checkout", held, "--", str(self.theirs))
        self.assertEqual(
            protocol_block.repo_protocol_ids(self.root)[EXPLORATION], [self.theirs]
        )
        # the twin: a protocol that stands is not named
        self.assertEqual(last_held_with_id(self.root, EXPLORATION), [])

    def test_an_id_no_commit_held_gives_none(self) -> None:
        self.assertEqual(last_held_with_id(self.root, OTHER), [])
        self.theirs.unlink()
        self.assertEqual(last_held_with_id(self.root, OTHER), [])

    def test_an_id_changed_in_a_file_that_stands_is_not_looked_into(self) -> None:
        self.theirs.write_text(protocol(OTHER, "exploratory"), encoding="utf-8")
        self.assertEqual(last_held_with_id(self.root, EXPLORATION), [])

    def test_only_a_gone_file_that_carried_the_id_and_no_copy_in_a_run(self) -> None:
        """A protocol copied into a run directory is a record, not a
        protocol of the repo (`repo.SKIP_DIRS`), and a gone protocol of
        another id is not this one."""
        in_run = self.explore / "runs" / self.a / self.theirs.name
        shutil.copy(self.theirs, in_run)
        self.commit("a copy in the run")
        in_run.unlink()
        self.theirs.unlink()
        self.ours.unlink()
        self.assertEqual(
            last_held_with_id(self.root, EXPLORATION),
            [(self.theirs, self.head_commit())],
        )

    def test_the_gate_asks_the_history_of_the_area_s_repository(self) -> None:
        self.theirs.unlink()
        self.assertEqual(
            last_held(self.confirm, EXPLORATION),
            LastHeld(((self.theirs, self.head_commit()),)),
        )

    def test_outside_a_repository_the_reason_is_told(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp).resolve() / "area"
            area.mkdir()
            told = last_held(area, EXPLORATION)
        self.assertEqual(told, LastHeld(unknown=f"{area} lies in no git repository"))

    def test_a_history_git_cannot_list_is_told_in_its_words_not_as_none(self) -> None:
        words = (
            "what git holds under the repository cannot be listed: fatal: bad object"
        )
        with mock.patch.object(
            report_exploration, "last_held_with_id", side_effect=HistoryUnread(words)
        ):
            told = last_held(self.confirm, EXPLORATION)
        self.assertEqual(told, LastHeld(unknown=words))


class LaterUse(_WithSource):
    """report-check's warning for a run of the exploration that shares an
    input digest and that the covering audit was not shown, and its
    blocker for a link that names no one protocol, where no search ran."""

    def setUp(self) -> None:
        super().setUp()
        fresh = self.confirm / "fresh.jsonl"
        fresh.write_text('{"id": 9}\n', encoding="utf-8")
        self.ours_run = self.measure(self.confirm, data={"cases": fresh})
        # a side run of the exploration reads the same bytes
        copy = self.explore / "copy.jsonl"
        copy.write_text('{"id": 9}\n', encoding="utf-8")
        self.side = self.measure(self.explore, data={"peek": copy})
        started = runs.run_started(self.side)
        assert started is not None
        self.side_started: datetime = started

    def found(self, began: datetime | None, area: Path | None = None) -> list:
        area = area or self.confirm
        return later_use_findings(
            area,
            self.ours,
            self.ours.read_text(encoding="utf-8"),
            state_of(area),
            began,
        )

    def test_a_run_started_after_the_audit_is_warned_of_and_holds_nothing(self) -> None:
        (f,) = self.found(self.side_started - timedelta(seconds=1))
        self.assertEqual(
            (f.grade, f.evidence_kind, f.rule), (WARNING, STATIC_EVIDENCE, LAB_050)
        )
        self.assertIn(f"run {self.side} of 01-explore", f.text)
        self.assertIn(
            f"its input peek with the sha256 of cases of run {self.ours_run}", f.text
        )
        self.assertIn("not decided here, either way", f.text)
        assert f.fix is not None
        self.assertIn("--mode analysis", f.fix)

    def test_the_twin_a_run_the_audit_was_shown_is_not(self) -> None:
        self.assertEqual(self.found(self.side_started + timedelta(seconds=1)), [])

    def test_a_later_run_that_shares_no_input_is_not_warned_of(self) -> None:
        began = datetime.now().replace(microsecond=0) - timedelta(days=1)
        other = self.explore / "other.jsonl"
        other.write_text('{"id": 7}\n', encoding="utf-8")
        apart = self.measure(self.explore, data={"other": other})
        self.assertNotIn(apart, " ".join(f.text for f in self.found(began)))

    def test_an_audit_of_unknown_start_warns_of_every_sharing_run(self) -> None:
        (f,) = self.found(None)
        self.assertIn("the attempt journal gives no start", f.text)

    def chain(self) -> list:
        """What report-check holds the confirmation to, before an adoption."""
        ctx = report_check.checked(self.confirm, self.ours)
        self.assertIsNotNone(ctx.run)
        return report_check.chain_gaps(ctx, undeclared=True, review=False).found

    def test_a_link_that_names_no_protocol_holds_the_release_once(self) -> None:
        """The exploratory protocol is gone after the confirming run:
        report-check's chain holds the release with the one blocker of the
        link, and the search for shared inputs, which did not run, adds no
        finding of its own. The twin: while the id names one protocol, the
        chain tells no finding of the link."""
        twin = [f for f in self.chain() if "[explored_in]" in f.text]
        self.assertEqual(twin, [])
        (searched,) = self.found(None)
        self.assertEqual(searched.outcome, SUSPECTED)
        self.theirs.unlink()
        (f,) = [f for f in self.chain() if "[explored_in]" in f.text]
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome, f.rule),
            (BLOCKER, GUARANTEED, NOT_EXECUTABLE, TECHNICAL_RULE),
        )
        self.assertIn(
            f"BLOCKER (check not executable): exploration link: [explored_in] "
            f"protocol = {EXPLORATION} names no protocol of this repo",
            f.line,
        )
        assert f.fix is not None
        # the restore as the history gives it: the file, and HEAD's commit
        # while the deletion is not committed
        held = _git(self.root, "rev-parse", "HEAD")
        self.assertIn(
            f"bring the exploratory protocol back from the last commit that "
            f"held it (`git checkout {held} -- {self.theirs}`), then ",
            f.fix,
        )
        self.assertIn("the link itself is registered and stays as written", f.fix)
        self.assertEqual(self.found(None), [])

    def test_a_link_that_names_two_protocols_holds_the_release(self) -> None:
        copy = self.confirm / "PROTOCOL-copy.md"
        shutil.copy(self.theirs, copy)
        ctx = report_check.checked(self.confirm, self.ours)
        (f,) = link_gaps(ctx)
        self.assertEqual(
            (f.grade, f.evidence_kind, f.outcome), (BLOCKER, GUARANTEED, NOT_EXECUTABLE)
        )
        self.assertIn(
            f"[explored_in] protocol = {EXPLORATION} names 2 protocols", f.text
        )
        self.assertIn(str(copy), f.text)
        self.assertIn(str(self.theirs), f.text)
        self.assertEqual(self.found(None), [])
        # the twin: the copy gone, the id names one protocol and the search runs
        copy.unlink()
        self.assertEqual(link_gaps(report_check.checked(self.confirm, self.ours)), [])
        (twin,) = self.found(None)
        self.assertEqual(twin.evidence_kind, STATIC_EVIDENCE)

    def test_the_twin_a_link_that_names_one_protocol_and_shares_nothing_is_clean(
        self,
    ) -> None:
        """Clean means searched and nothing found: with the audit begun
        after the sharing run, the resolved link gives no finding."""
        self.assertEqual(self.found(self.side_started + timedelta(seconds=1)), [])

    def test_the_warning_s_station_adds_nothing_for_an_unresolved_link(self) -> None:
        """One cause, one finding: under a covering audit the station of
        the warnings is silent for a link that names no protocol — the
        registration station's blocker is the finding."""
        self.theirs.unlink()
        ctx = report_check.checked(self.confirm, self.ours)
        self.assertIsNotNone(ctx.run)
        self.assertEqual(use_after_audit_findings(ctx), [])
        self.assertEqual(len(link_gaps(ctx)), 1)

    def test_no_link_warns_of_nothing(self) -> None:
        self.ours.write_text(protocol(CONFIRMATION, "confirmatory"), encoding="utf-8")
        self.assertEqual(self.found(None), [])

    def test_a_run_of_the_confirmation_is_no_exploring_run(self) -> None:
        """Both protocols in one area: the confirmation's own run, in the
        area's runs too, does not pair with itself."""
        ours = self.explore / "PROTOCOL-confirm.md"
        ours.write_text(self.link(self.c), encoding="utf-8")
        self.commit("a confirmation beside its exploration")
        fresh = self.explore / "fresh.jsonl"
        fresh.write_text('{"id": 5}\n', encoding="utf-8")
        self.measure(self.explore, data={"cases": fresh}, protocol=ours)
        found = later_use_findings(
            self.explore,
            ours,
            ours.read_text(encoding="utf-8"),
            state_of(self.explore),
            None,
        )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
