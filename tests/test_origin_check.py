"""An input held to the origin run its record names (`origin_check`): the
part of the promise that fails, decided from facts in memory; finalize's
input-origins station on real runs through `runlog.run`, where it holds and
where station 6 already holds the bytes; and the piece the analysis audit
is shown."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from labkit.checks import audit_binding, origin_check
from labkit.checks.audit_binding import (
    NO_TEXT_IN_ITS_PLACE,
    NO_TEXT_OF_A_PREPARATION,
    NOT_RECONSTRUCTED,
    PREPARATION_THEN,
    SOURCE_PROTOCOL_LABEL,
    SOURCE_THEN,
    SourceProtocolThen,
    run_rows,
    source_protocol_finding,
    source_protocol_pieces,
)
from labkit.checks.origin_check import (
    BYTES_CHANGED,
    GONE,
    LOOKED_UP_WITHIN_AREA,
    NEVER_REWRITTEN,
    NOT_COMPLETED,
    NOT_REGISTERED,
    ORIGINS_LABEL,
    OTHER_BYTES,
    UNREAD,
    OriginNow,
    origin_finding,
    origin_gap,
    origin_notes,
)
from labkit.formats.files import MALFORMED
from labkit.formats.gate import BLOCKER, TECHNICAL_RULE, Findings
from labkit.formats.runs import (
    COMPLETED,
    OTHER_SCHEMA,
    UNREADABLE,
    DataEntry,
    RunState,
    OutputEntry,
    UnreadableRun,
)
from labkit.gates import finalize
from labkit.gates.finalize import check_input_origins
from labkit.run import runlog
from labkit.run.input_origins import AreaRun

A = "2026-11-17T10-00-00_aaaa"
FILE = Path("/lab/area/out.jsonl")
SHA = "0123456789abcdef"


def entry(
    origin_run: str | None = A,
    *,
    chosen: bool = False,
    skipped: tuple[UnreadableRun, ...] = (),
) -> DataEntry:
    """The input out.jsonl as a run recorded it, with SHA and ORIGIN_RUN."""
    return DataEntry("items", "out.jsonl", SHA, 1, origin_run, chosen, skipped)


def wrote(*outputs: tuple[Path, str | None], state: RunState = COMPLETED) -> AreaRun:
    """Origin run A as the lookup reads it, its outputs registered."""
    return AreaRun(A, state, None, tuple(OutputEntry(p, s, 1) for p, s in outputs))


def gap_part(origin: AreaRun | None, drift: str | None = None) -> str | None:
    """The failing part for the input read from ORIGIN, or None."""
    gap = origin_gap(OriginNow(entry(), FILE, origin, drift))
    return None if gap is None else gap.part


class Gap(unittest.TestCase):
    """`origin_gap` from facts in memory: each part of the promise."""

    def test_the_twin_the_registered_output_with_its_bytes_holds(self) -> None:
        self.assertIsNone(gap_part(wrote((FILE, SHA))))

    def test_an_origin_that_is_gone(self) -> None:
        self.assertEqual(gap_part(None), GONE)

    def test_an_origin_whose_record_does_not_read_names_its_cause(self) -> None:
        unread = AreaRun(A, UNREADABLE, None, (), "config.json: bad", OTHER_SCHEMA)
        gap = origin_gap(OriginNow(entry(), FILE, unread))
        assert gap is not None
        self.assertEqual(gap.part, UNREAD)
        self.assertIn("of a schema version this labkit does not read", gap.told)

    def test_an_origin_that_is_not_completed(self) -> None:
        self.assertEqual(gap_part(wrote((FILE, SHA), state="crashed")), NOT_COMPLETED)

    def test_an_origin_that_registered_no_such_output(self) -> None:
        self.assertEqual(gap_part(wrote((FILE.with_name("x"), SHA))), NOT_REGISTERED)

    def test_an_origin_that_registered_other_bytes(self) -> None:
        self.assertEqual(gap_part(wrote((FILE, "f" * 16))), OTHER_BYTES)
        self.assertEqual(
            gap_part(wrote((FILE, None))), OTHER_BYTES
        )  # absent at its end

    def test_bytes_changed_since_both_records(self) -> None:
        self.assertEqual(
            gap_part(wrote((FILE, SHA)), "its sha256 is now ff"), BYTES_CHANGED
        )

    def test_the_first_failing_part_is_named(self) -> None:
        # a record part fails before the bytes are looked at
        self.assertEqual(
            gap_part(wrote((FILE, "f" * 16)), "its sha256 is now ff"), OTHER_BYTES
        )


class Ways(unittest.TestCase):
    """`origin_finding`: the way out its part owes, never a rewrite."""

    def test_changed_bytes_are_restored_from_the_evidence_or_measured_anew(
        self,
    ) -> None:
        gap = origin_gap(
            OriginNow(entry(), FILE, wrote((FILE, SHA)), "its sha256 is now ff")
        )
        assert gap is not None
        f = origin_finding(gap, Path("/lab/area"))
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        assert f.fix is not None
        self.assertIn("restore the bytes the run read", f.fix)
        self.assertIn("measure anew", f.fix)
        self.assertIn(NEVER_REWRITTEN, f.fix)

    def test_a_record_part_is_restored_not_edited(self) -> None:
        gap = origin_gap(OriginNow(entry(), FILE, None))
        assert gap is not None
        fix = origin_finding(gap, Path("/lab/area")).fix
        assert fix is not None
        self.assertIn("from git or a backup", fix)
        self.assertIn(NEVER_REWRITTEN, fix)


class SourceProtocolHeld(unittest.TestCase):
    """`source_protocol_finding` from facts in memory: a bound origin run
    owes its protocol as it started, a run bound to none owes nothing."""

    def test_a_bound_origin_without_its_text_then_blocks(self) -> None:
        then = SourceProtocolThen(
            A, True, False, None, f"origin run {A} recorded no commit"
        )
        f = source_protocol_finding(then, Path("/lab/area"))
        assert f is not None and f.fix is not None
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertIn(f"the protocol origin run {A} was measured under", f.text)
        self.assertIn("recorded no commit", f.text)
        self.assertIn("never show or write today's text in its place", f.fix)
        self.assertIn("measure anew", f.fix)

    def test_a_bound_preparation_without_its_text_blocks_as_a_preparation(
        self,
    ) -> None:
        # missing evidence is its own blocker; the run stays a preparation in it
        then = SourceProtocolThen(
            A, True, True, None, f"preparation run {A} recorded no commit"
        )
        f = source_protocol_finding(then, Path("/lab/area"))
        assert f is not None
        self.assertEqual((f.grade, f.rule), (BLOCKER, TECHNICAL_RULE))
        self.assertIn(f"the protocol preparation run {A} was bound to", f.text)
        self.assertNotIn("measured under", f.text)

    def test_the_twin_a_bound_origin_whose_text_reads_passes(self) -> None:
        then = SourceProtocolThen(
            A, True, False, "# protocol", "as origin run … saw it"
        )
        self.assertIsNone(source_protocol_finding(then, Path("/lab/area")))

    def test_an_origin_whose_record_does_not_stand_is_held(self) -> None:
        # whether a protocol is owed is unknown: held, never read as unbound
        then = SourceProtocolThen(A, None, False, None, f"origin run {A} is gone")
        f = source_protocol_finding(then, Path("/lab/area"))
        assert f is not None
        # its own problem, the kind unknown: never told as a measured source
        self.assertIn(f"the record of origin run {A} does not stand", f.text)
        self.assertNotIn("measured under", f.text)

    def test_a_run_bound_to_no_protocol_owes_none(self) -> None:
        then = SourceProtocolThen(
            A, False, False, None, f"origin run {A} was started bound"
        )
        self.assertIsNone(source_protocol_finding(then, Path("/lab/area")))


class Notes(unittest.TestCase):
    """`origin_notes`: facts for the auditor, never findings."""

    def test_a_plain_input_is_told(self) -> None:
        (line,) = origin_notes(entry(None))
        self.assertIn("an input without origin", line)

    def test_the_skipped_runs_are_grouped_by_cause(self) -> None:
        skipped = (UnreadableRun("r1", MALFORMED), UnreadableRun("r2", OTHER_SCHEMA))
        (line,) = origin_notes(entry(A, skipped=skipped))
        self.assertIn("(damaged or hand-edited): r1;", line)
        self.assertIn("does not read: r2", line)

    def test_the_twin_a_chosen_origin_owes_no_note(self) -> None:
        self.assertEqual(origin_notes(entry(A, chosen=True)), [])


class _Area(unittest.TestCase):
    """A real area: run W writes out.jsonl, run R reads it as its input."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name) / "area"
        self.area.mkdir()
        self.aside = Path(tmp.name) / "aside"
        self.out = self.area / "out.jsonl"
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS) as w:
            w.output(self.out)
            self.out.write_text('{"id": 1}\n', encoding="utf-8")
            w.metrics(n=1)
        self.writer = w
        self.reader = self.read(self.out)

    def read(self, path: Path) -> Path:
        """A completed run of the area that reads PATH; its directory."""
        with runlog.run("r", {}, self.area, data={"items": path}) as r:
            r.metrics(n=1)
        return r.dir

    def station(
        self, run_dir: Path | None = None, *, provenance_holds_bytes: bool = False
    ) -> tuple[list[str], str]:
        """(blockers, told) of the input-origins station on RUN_DIR (the reader)."""
        told: list[str] = []
        findings = Findings(told.append)
        check_input_origins(
            findings,
            self.area,
            run_dir or self.reader,
            provenance_holds_bytes=provenance_holds_bytes,
        )
        return findings.blocked, "\n".join(told)


class Station(_Area):
    """finalize's input-origins station on real runs."""

    def test_the_twin_an_intact_origin_passes_with_a_note(self) -> None:
        blocked, told = self.station()
        self.assertEqual(blocked, [])
        self.assertIn(f"the output of {self.writer.run_id} (decided by digest)", told)
        self.assertIn(LOOKED_UP_WITHIN_AREA, told)
        # the writer is bound to no protocol (a preparation run): none is owed
        self.assertIn("bound to no protocol", told)
        self.assertIn("none is owed", told)

    def test_a_changed_file_blocks_where_no_other_station_holds_its_bytes(self) -> None:
        self.out.write_text('{"id": 2}\n', encoding="utf-8")
        blocked, _ = self.station()
        (line,) = blocked
        self.assertIn(
            f"not the output of its origin run {self.writer.run_id} any more", line
        )
        # at low repeat cost station 6 holds the same bytes: one cause, one blocker
        blocked, told = self.station(provenance_holds_bytes=True)
        self.assertEqual(blocked, [])
        self.assertIn("the provenance station names it", told)

    def test_an_origin_moved_away_blocks_and_restored_passes(self) -> None:
        shutil.move(self.writer.dir, self.aside)
        (line,) = self.station(provenance_holds_bytes=True)[0]
        self.assertIn(f"its origin run {self.writer.run_id} is gone", line)
        shutil.move(self.aside, self.writer.dir)
        self.assertEqual(self.station()[0], [])

    def test_an_origin_record_edited_after_the_run_blocks(self) -> None:
        outputs = self.writer.dir / "outputs.json"
        registered = json.loads(outputs.read_text(encoding="utf-8"))
        registered[0]["sha256"] = "f" * len(registered[0]["sha256"])
        outputs.write_text(json.dumps(registered), encoding="utf-8")
        (line,) = self.station()[0]
        self.assertIn(
            f"{self.writer.run_id} registered out.jsonl with sha256 ffff", line
        )

    def test_a_later_writer_does_not_change_the_stored_origin(self) -> None:
        with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS) as later:
            later.output(self.out)
            self.out.write_text('{"id": 1}\n', encoding="utf-8")
            later.metrics(n=1)
        blocked, told = self.station()
        self.assertEqual(blocked, [])
        self.assertIn(f"the output of {self.writer.run_id}", told)
        self.assertNotIn(later.run_id, told)

    def test_a_plain_input_is_a_note_and_holds_nothing(self) -> None:
        copied = self.area / "copied.jsonl"
        copied.write_text('{"id": 9}\n', encoding="utf-8")
        blocked, told = self.station(self.read(copied))
        self.assertEqual(blocked, [])
        self.assertIn("an input without origin", told)

    def test_a_record_that_does_not_read_is_told_once(self) -> None:
        cfg = self.reader / "config.json"
        record = json.loads(cfg.read_text(encoding="utf-8"))
        del record["data"]["items"]["origin_run"]
        cfg.write_text(json.dumps(record), encoding="utf-8")
        (line,) = self.station()[0]
        self.assertIn("has no origin_run", line)
        blocked, told = self.station(provenance_holds_bytes=True)
        self.assertEqual(blocked, [])
        self.assertIn("the provenance station names the record", told)


class SourceHeldAtTheStation(_Area):
    """What the station adds to `intent_check.origin_intent_findings` (tested from
    data in tests/test_intent_check.py): an origin run whose protocol then
    reads is held to that text, a blocker of the reading run's finalize;
    one that reports what the text registered is a note."""

    def told_under(
        self, text: str, *, preparation: bool = False
    ) -> tuple[list[str], str]:
        """(blockers, told) of the source-protocol part with the writer's
        protocol then read back as TEXT, the writer a preparation where
        PREPARATION says so."""
        then = SourceProtocolThen(
            self.writer.run_id,
            True,
            preparation,
            text,
            f"as origin run {self.writer.run_id} saw it",
        )
        told: list[str] = []
        findings = Findings(told.append)
        with mock.patch.object(finalize, "source_protocol_then", return_value=then):
            finalize.check_source_protocols(findings, self.area, [self.writer.run_id])
        return findings.blocked, "\n".join(told)

    def test_a_source_that_does_not_report_its_texts_promise_blocks(self) -> None:
        blocked, told = self.told_under(
            "- **Criterion:** [criterion-1] n is at least 1\n"
        )
        self.assertEqual(len(blocked), 1, told)
        self.assertIn(
            f"origin run {self.writer.run_id}, held to the protocol as it saw it: "
            f"its protocol then: [criterion-1] registered",
            told,
        )

    def test_a_preparation_source_owes_none_of_its_texts_promises(self) -> None:
        # the twin above: the same text, a measurement source, blocks
        blocked, told = self.told_under(
            "- **Criterion:** [criterion-1] n is at least 1\n", preparation=True
        )
        self.assertEqual(blocked, [], told)
        self.assertIn(f"{self.writer.run_id} is a preparation", told)
        self.assertIn("its protocol then:", told)  # its text is still read back

    def test_a_source_under_a_text_without_ids_is_a_note(self) -> None:
        blocked, told = self.told_under("- **Question:** how many rows\n")
        self.assertEqual(blocked, [], told)
        self.assertIn(f"{self.writer.run_id}, held to that text: no mismatch", told)


class Piece(_Area):
    """What MODE analysis is shown of the inputs' origins."""

    def piece(self, run_dir: Path) -> str:
        (text,) = [
            t for label, t in run_rows(self.area, run_dir, "") if label == ORIGINS_LABEL
        ]
        return text

    def test_the_origin_its_repeat_and_the_lookups_reach_are_shown(self) -> None:
        with runlog.run(
            "w", {}, self.area, data=runlog.NO_INPUTS, repeat_of=self.writer.run_id
        ) as again:
            again.output(self.out)
            self.out.write_text('{"id": 3}\n', encoding="utf-8")
            again.metrics(n=1)
        text = self.piece(self.read(self.out))
        self.assertIn(LOOKED_UP_WITHIN_AREA, text)
        self.assertIn(f"the output of {again.run_id} (decided by digest)", text)
        self.assertIn(f"a repeat of {self.writer.run_id}", text)

    def test_a_failing_part_and_a_plain_input_are_shown(self) -> None:
        self.out.write_text('{"id": 2}\n', encoding="utf-8")
        self.assertIn("any more", self.piece(self.reader))
        copied = self.area / "copied.jsonl"
        copied.write_text('{"id": 9}\n', encoding="utf-8")
        self.assertIn("an input without origin", self.piece(self.read(copied)))

    def test_a_run_without_input_files_shows_no_piece(self) -> None:
        labels = [label for label, _ in run_rows(self.area, self.writer.dir, "")]
        self.assertNotIn(ORIGINS_LABEL, labels)
        self.assertEqual(origin_check.origin_piece(self.area, self.writer.dir), [])
        self.assertEqual(source_protocol_pieces(self.area, self.writer.dir), [])


class SourceProtocol(_Area):
    """The source protocol piece where none can be read back: told why, and
    no other text in its place. The text as an origin run saw it, read from
    git, is shown in tests/test_origin_scenario.py (`TwoProtocolsOfOneArea`)."""

    def source_piece(self) -> str:
        (text,) = [
            t
            for label, t in run_rows(self.area, self.reader, "")
            if label == f"{SOURCE_PROTOCOL_LABEL}{self.writer.run_id}"
        ]
        return text

    def test_a_source_run_bound_to_no_protocol_is_told(self) -> None:
        text = self.source_piece()
        self.assertTrue(text.startswith(NOT_RECONSTRUCTED), text)
        self.assertIn("bound to no protocol", text)
        self.assertIn(NO_TEXT_IN_ITS_PLACE, text)

    def test_a_preparation_source_without_text_is_told_as_a_preparation(
        self,
    ) -> None:
        prepared = self.area / "prepared.jsonl"
        with runlog.run(
            "p", {}, self.area, data=runlog.NO_INPUTS, run_kind="preparation"
        ) as p:
            p.output(prepared)
            prepared.write_text('{"id": 2}\n', encoding="utf-8")
            p.metrics(n=1)
        with runlog.run("r", {}, self.area, data={"prepared": prepared}) as r:
            r.metrics(n=1)
        text = dict(source_protocol_pieces(self.area, r.dir))[
            f"{SOURCE_PROTOCOL_LABEL}{p.run_id}"
        ]
        self.assertTrue(text.startswith(NOT_RECONSTRUCTED), text)
        self.assertIn(f"preparation run {p.run_id} was started bound to no", text)
        # the role holds for what the missing text leaves the judgement too
        self.assertIn(NO_TEXT_OF_A_PREPARATION, text)
        self.assertNotIn(NO_TEXT_IN_ITS_PLACE, text)

    def test_a_gone_source_run_is_told_not_replaced(self) -> None:
        shutil.move(self.writer.dir, self.aside)
        text = self.source_piece()
        self.assertTrue(text.startswith(NOT_RECONSTRUCTED), text)
        self.assertIn(f"origin run {self.writer.run_id} is gone", text)

    def test_a_source_directory_without_its_record_is_told(self) -> None:
        (self.writer.dir / "config.json").rename(self.aside)
        text = self.source_piece()
        self.assertTrue(text.startswith(NOT_RECONSTRUCTED), text)
        self.assertIn(f"origin run {self.writer.run_id} has no record", text)

    def pieces_of_two_sources(
        self, *, preparation_first: bool = False
    ) -> tuple[str, dict[str, str]]:
        """A run reading the writer's output and a preparation's, both read
        back under one text (`source_protocol_then` stood in), the writer's
        input first unless PREPARATION_FIRST: (the preparation's run id, the
        source pieces by label)."""
        prepared = self.area / "prepared.jsonl"
        with runlog.run(
            "p", {}, self.area, data=runlog.NO_INPUTS, run_kind="preparation"
        ) as p:
            p.output(prepared)
            prepared.write_text('{"id": 2}\n', encoding="utf-8")
            p.metrics(n=1)
        inputs = {"items": self.out, "prepared": prepared}
        if preparation_first:
            inputs = {"prepared": prepared, "items": self.out}
        with runlog.run("r", {}, self.area, data=inputs) as r:
            r.metrics(n=1)

        def then(area: Path, run_id: str, root: Path | None) -> SourceProtocolThen:
            return SourceProtocolThen(
                run_id, True, run_id == p.run_id, "# one text", f"as {run_id} saw it"
            )

        with mock.patch.object(audit_binding, "source_protocol_then", then):
            return p.run_id, dict(source_protocol_pieces(self.area, r.dir))

    def test_a_preparation_source_is_shown_as_context_it_owes_nothing_of(self) -> None:
        prep, pieces = self.pieces_of_two_sources()
        told = pieces[f"{SOURCE_PROTOCOL_LABEL}{prep}"]
        # the text is shown once, under the writer; the preparation points
        # to it and still says what its text is to it
        self.assertIn(f"the same text as under {SOURCE_PROTOCOL_LABEL}", told)
        self.assertIn(PREPARATION_THEN, told)
        self.assertNotIn(SOURCE_THEN, told)

    def test_the_twin_a_measurement_source_keeps_its_sentence(self) -> None:
        _, pieces = self.pieces_of_two_sources()
        told = pieces[f"{SOURCE_PROTOCOL_LABEL}{self.writer.run_id}"]
        self.assertIn(f"— {SOURCE_THEN}\n\n# one text", told)
        self.assertNotIn(PREPARATION_THEN, told)

    def test_a_measurement_pointing_to_a_preparations_text_says_its_own(self) -> None:
        # the first piece calls the text context; the measurement after it
        # must not read as context too
        _, pieces = self.pieces_of_two_sources(preparation_first=True)
        told = pieces[f"{SOURCE_PROTOCOL_LABEL}{self.writer.run_id}"]
        self.assertIn(f"the same text as under {SOURCE_PROTOCOL_LABEL}", told)
        self.assertIn(SOURCE_THEN, told)
        self.assertNotIn(PREPARATION_THEN, told)

    def test_one_piece_per_source_run_however_many_inputs_it_wrote(self) -> None:
        with runlog.run(
            "r", {}, self.area, data={"items": self.out, "again": self.out}
        ) as r:
            r.metrics(n=1)
        labels = [
            label
            for label, _ in source_protocol_pieces(self.area, r.dir)
            if label.startswith(SOURCE_PROTOCOL_LABEL)
        ]
        self.assertEqual(labels, [f"{SOURCE_PROTOCOL_LABEL}{self.writer.run_id}"])


if __name__ == "__main__":
    unittest.main()
