"""The origin of a run's input files: a `data=` value taken apart once
(`provenance.declared_input`), `runlog.RunOutput` as the script's explicit
choice, and the lookup among the completed runs of the same area
(`input_origins`). The origin changes nothing recorded about the file —
digest, rows, binary mark and the leakage checks are the same with and
without it — and is checked at start, not yet written to the record."""

from __future__ import annotations

import contextlib
import io
import json
import os
import pickle
import tempfile
import unittest
from pathlib import Path

from labkit.formats import runs
from labkit.formats.runs import COMPLETED, OutputEntry
from labkit.run import input_origins, provenance, runlog
from labkit.formats.files import ACCESS, MALFORMED
from labkit.formats.runs import OTHER_SCHEMA, UnreadableRun
from labkit.run.input_origins import AreaRun, InputOrigin, OriginRefused

A, B, C = (
    "2026-11-16T10-00-00_aaaa",
    "2026-11-16T10-00-01_bbbb",
    "2026-11-16T10-00-02_cccc",
)
FILE = Path("/lab/area/data/out.jsonl")
SHA = "0123456789abcdef"


def done(run_id: str, *outputs: tuple[Path, str | None], repeat_of=None) -> AreaRun:
    """A completed run of the area that registered OUTPUTS (path, digest)."""
    return AreaRun(
        run_id,
        COMPLETED,
        repeat_of,
        tuple(OutputEntry(p, sha, 1) for p, sha in outputs),
    )


def origin(runs: list[AreaRun], chosen: str | None = None) -> InputOrigin:
    """The origin of FILE with digest SHA among RUNS."""
    return input_origins.decide_origin(
        "items", "data/out.jsonl", FILE, SHA, chosen, runs, Path("/lab/area/runs")
    )


class Lookup(unittest.TestCase):
    """`decide_origin` from runs in memory: one eligible run, several, none."""

    def test_the_one_run_that_wrote_the_file_is_its_origin(self) -> None:
        got = origin([done(A, (FILE, SHA)), done(B, (FILE, "f" * 16))])
        self.assertEqual(got, InputOrigin(A, False, None))

    def test_no_eligible_run_is_a_plain_input_not_a_refusal(self) -> None:
        self.assertEqual(origin([]), input_origins.NO_ORIGIN)
        other = Path("/lab/area/data/other.jsonl")
        self.assertEqual(
            origin([done(A, (other, SHA)), done(B, (FILE, None))]),
            input_origins.NO_ORIGIN,
        )

    def test_a_run_that_is_not_completed_is_never_looked_up(self) -> None:
        crashed = AreaRun(A, "crashed", None, (OutputEntry(FILE, SHA, 1),))
        self.assertEqual(origin([crashed]), input_origins.NO_ORIGIN)

    def test_a_run_that_does_not_read_is_never_eligible(self) -> None:
        damaged = AreaRun(
            A, COMPLETED, None, (OutputEntry(FILE, SHA, 1),), "bad json", MALFORMED
        )
        skipped = (UnreadableRun(A, MALFORMED),)
        self.assertEqual(origin([damaged]), InputOrigin(None, False, None, skipped))
        self.assertEqual(
            origin([damaged, done(B, (FILE, SHA))]),
            InputOrigin(B, False, None, skipped),
        )
        with self.assertRaisesRegex(OriginRefused, f"{A} does not read: bad json"):
            origin([damaged], chosen=A)

    def test_a_chosen_origin_skips_no_unreadable_run(self) -> None:
        damaged = AreaRun(A, "unreadable", None, (), "bad json", MALFORMED)
        self.assertEqual(
            origin([damaged, done(B, (FILE, SHA))], chosen=B),
            InputOrigin(B, True, None),
        )

    def test_an_unread_run_names_its_cause(self) -> None:
        with self.assertRaises(ValueError):
            AreaRun(A, "unreadable", None, (), "bad json")
        with self.assertRaises(ValueError):
            AreaRun(A, "unreadable", None, (), "bad json", "broken")

    def test_one_warning_names_each_input_and_groups_the_skipped_runs_by_cause(
        self,
    ) -> None:
        skipped = (UnreadableRun(A, OTHER_SCHEMA), UnreadableRun(C, ACCESS))
        told = input_origins.unreadable_warning(
            [
                ("items", "data/out.jsonl", InputOrigin(B, False, None, skipped)),
                ("extra", "data/x.jsonl", InputOrigin(None, False, None, skipped)),
            ]
        )
        self.assertEqual(told.count("WARNING"), 1)
        self.assertIn(f"data['items'] = data/out.jsonl as {B}", told)
        self.assertIn("data['extra'] = data/x.jsonl as an input without origin", told)
        self.assertIn(f"of a schema version this labkit does not read: {A}", told)
        self.assertIn(f"could not be opened (permissions or I/O): {C}", told)
        self.assertNotIn("damaged", told.split("Decided:")[0].split("(", 1)[1][:60])
        self.assertIn("runlog.RunOutput(", told)
        self.assertIn("repair a record", told)  # the access failure
        self.assertIn("read with the labkit that wrote it", told)
        schema_only = input_origins.unreadable_warning(
            [("items", "x", InputOrigin(B, False, None, skipped[:1]))]
        )
        self.assertNotIn("repair", schema_only)

    def test_two_runs_with_the_same_file_and_bytes_need_a_choice(self) -> None:
        runs = [done(A, (FILE, SHA)), done(B, (FILE, SHA), repeat_of=A)]
        with self.assertRaises(OriginRefused) as cm:
            origin(runs)
        said = str(cm.exception)
        self.assertIn("data['items']", said)
        self.assertIn(A, said)
        self.assertIn(f"{B} (repeat of {A})", said)
        self.assertIn("Next: ", said)
        self.assertIn('runlog.RunOutput("data/out.jsonl", run=', said)

    def test_a_choice_among_several_is_decided_as_chosen(self) -> None:
        runs = [done(A, (FILE, SHA)), done(B, (FILE, SHA))]
        self.assertEqual(origin(runs, chosen=B), InputOrigin(B, True, None))

    def test_a_choice_is_allowed_where_one_run_is_eligible(self) -> None:
        self.assertEqual(
            origin([done(A, (FILE, SHA))], chosen=A), InputOrigin(A, True, None)
        )

    def test_a_repeat_is_an_eligible_origin_and_keeps_its_repeat_of(self) -> None:
        runs = [done(A, (FILE, "f" * 16)), done(B, (FILE, SHA), repeat_of=A)]
        self.assertEqual(origin(runs), InputOrigin(B, False, A))
        self.assertEqual(origin(runs, chosen=B), InputOrigin(B, True, A))


class WrongChoice(unittest.TestCase):
    """A chosen run that is not eligible is refused with the reason, and the
    way out lists the eligible runs."""

    def refusal(self, runs: list[AreaRun], chosen: str) -> str:
        with self.assertRaises(OriginRefused) as cm:
            origin(runs, chosen=chosen)
        said = str(cm.exception)
        self.assertIn(
            f"data['items'] = RunOutput(data/out.jsonl, run={chosen!r})", said
        )
        return said

    def test_a_third_run_that_did_not_write_the_file(self) -> None:
        other = Path("/lab/area/data/other.jsonl")
        runs = [done(A, (FILE, SHA)), done(B, (FILE, SHA)), done(C, (other, SHA))]
        said = self.refusal(runs, C)
        self.assertIn(f"{C} registered no output data/out.jsonl", said)
        self.assertIn(f"name an eligible run: {A}, {B}", said)

    def test_a_run_whose_recorded_bytes_differ_from_the_file(self) -> None:
        said = self.refusal([done(A, (FILE, "f" * 16))], A)
        self.assertIn(f"{A} recorded data/out.jsonl with sha256 ffff", said)
        self.assertIn("other bytes", said)
        self.assertIn("pass the plain path", said)

    def test_a_run_that_is_not_completed(self) -> None:
        crashed = AreaRun(A, "crashed", None, ())
        said = self.refusal([crashed], A)
        self.assertIn(f"{A} is not completed (crashed", said)

    def test_a_run_outside_the_area(self) -> None:
        said = self.refusal([done(A, (FILE, SHA))], C)
        self.assertIn("no run of this area has that id", said)
        self.assertIn("/lab/area/runs", said)
        self.assertIn(f"name an eligible run: {A}", said)


class Declared(unittest.TestCase):
    """`declared_input`: the one unwrapping of a `data=` value."""

    def test_the_origin_wraps_the_handling(self) -> None:
        p = Path("w.bin")
        self.assertEqual(
            provenance.declared_input(
                "m", runlog.RunOutput(provenance.BinaryInput(p), run=A)
            ),
            provenance.DeclaredInput(p, True, A),
        )
        self.assertEqual(
            provenance.declared_input("m", runlog.RunOutput("x.jsonl", run=A)),
            provenance.DeclaredInput(Path("x.jsonl"), False, A),
        )
        self.assertEqual(
            provenance.declared_input("m", provenance.BinaryInput(p)),
            provenance.DeclaredInput(p, True, None),
        )

    def test_a_nesting_without_meaning_is_refused_naming_the_key(self) -> None:
        inner = runlog.RunOutput("x.jsonl", run=A)
        cases = {
            "RunOutput(RunOutput(…))": runlog.RunOutput(inner, run=B),  # type: ignore[arg-type]  # the wrong nesting under test
            "BinaryInput(RunOutput(…))": provenance.BinaryInput(inner),  # type: ignore[arg-type]  # the wrong nesting under test
        }
        for shape, value in cases.items():
            with self.subTest(shape), self.assertRaises(ValueError) as cm:
                provenance.declared_input("predictions", value)
            self.assertIn("data['predictions']", str(cm.exception))
            self.assertIn(shape, str(cm.exception))

    def test_a_choice_that_names_no_run_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, r"data\['p'\]: RunOutput\(…, run=''\)"):
            provenance.declared_input("p", runlog.RunOutput("x.jsonl", run=""))

    def test_the_run_is_named_by_keyword(self) -> None:
        with self.assertRaises(TypeError):
            runlog.RunOutput("x.jsonl", A)  # type: ignore[misc]  # positional run under test


class SameFileChecks(unittest.TestCase):
    """`describe_data` records and checks a file alike with and without an
    origin: digest, rows, the binary mark and the leakage refusal."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name)

    def write(self, name: str, text: str) -> Path:
        p = self.area / name
        p.write_text(text, encoding="utf-8")
        return p

    def both(self, value: object, **more: object) -> tuple[dict, dict]:
        """describe_data of {"items": VALUE} plain and wrapped in RunOutput."""
        plain = provenance.describe_data({"items": value, **more}, self.area)
        wrapped = provenance.describe_data(
            {"items": runlog.RunOutput(value, run=A), **more},  # type: ignore[arg-type]
            self.area,
        )
        return plain, wrapped

    def test_a_text_input_counts_the_same_rows(self) -> None:
        items = self.write("items.jsonl", '{"_meta": {}}\n{"id": 1}\n\n{"id": 2}\n')
        plain, wrapped = self.both(items)
        self.assertEqual(plain, wrapped)
        self.assertEqual(wrapped["items"]["rows"], 2)

    def test_a_binary_input_keeps_its_mark(self) -> None:
        weights = self.area / "weights.jsonl"
        weights.write_bytes(pickle.dumps({"w": 2.0}))
        plain, wrapped = self.both(provenance.BinaryInput(weights))
        self.assertEqual(plain, wrapped)
        self.assertIsNone(wrapped["items"]["rows"])
        with self.assertRaises(UnicodeDecodeError):  # unwrapped from BinaryInput: text
            provenance.describe_data(
                {"items": runlog.RunOutput(weights, run=A)}, self.area
            )

    def test_the_split_leakage_refusal_is_the_same(self) -> None:
        train = self.write("train.jsonl", '{"id": "same"}\n')
        test = self.write("test.jsonl", '{"id": "same"}\n')
        for data in (
            {"train": train, "test": test},
            {
                "train": runlog.RunOutput(train, run=A),
                "test": runlog.RunOutput(test, run=B),
            },
        ):
            with (
                self.subTest(data=data),
                self.assertRaisesRegex(RuntimeError, "split leakage"),
            ):
                provenance.describe_data(data, self.area)

    def test_a_clean_pair_with_origins_passes_as_without(self) -> None:
        train = self.write("train.jsonl", '{"id": 1}\n')
        test = self.write("test.jsonl", '{"id": 2}\n')
        plain = provenance.describe_data({"train": train, "test": test}, self.area)
        wrapped = provenance.describe_data(
            {
                "train": runlog.RunOutput(train, run=A),
                "test": runlog.RunOutput(test, run=B),
            },
            self.area,
        )
        self.assertEqual(plain, wrapped)
        self.assertTrue(wrapped["leakage_check"].startswith("ok: no shared ids"))


class AtStart(unittest.TestCase):
    """Through `runlog.run` in a real area: origins looked up among the
    completed runs, refusals before a run directory exists, nothing new in
    the record."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.area = Path(tmp.name) / "area"
        self.area.mkdir()
        self.out = self.area / "out.jsonl"
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def write_run(self, text: str, **kw: object) -> runlog.Run:
        """A completed run that writes TEXT into out.jsonl and registers it."""
        with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS, **kw) as r:  # type: ignore[arg-type]
            r.output(self.out)
            self.out.write_text(text, encoding="utf-8")
            r.metrics(n=1)
        return r

    def read_run(self, value: object) -> runlog.Run:
        """A completed run that reads VALUE as its input."""
        with runlog.run("r", {}, self.area, data={"items": value}) as r:
            r.metrics(n=1)
        return r

    def origins(self, value: object) -> dict[str, InputOrigin]:
        data = {"items": value}
        return input_origins.input_origins(
            self.area, data, provenance.describe_data(data, self.area)
        )

    def runs_now(self) -> set[str]:
        return {p.name for p in (self.area / "runs").iterdir()}

    def recorded(self, r: runlog.Run) -> runs.DataEntry:
        """The one input entry R's record holds, as a reader reads it back."""
        (entry,) = runs.read_data(r.dir) or []
        return entry

    def test_the_writer_is_found_and_recorded(self) -> None:
        w = self.write_run('{"id": 1}\n')
        self.assertEqual(
            self.origins(self.out), {"items": InputOrigin(w.run_id, False, None)}
        )
        got = self.recorded(self.read_run(self.out))
        self.assertEqual(
            (got.origin_run, got.origin_chosen, got.origin_unreadable_runs),
            (w.run_id, False, ()),
        )

    def test_a_file_no_run_wrote_is_a_plain_input(self) -> None:
        copied = self.area / "copied.jsonl"
        copied.write_text('{"id": 1}\n', encoding="utf-8")
        self.assertEqual(self.origins(copied), {"items": input_origins.NO_ORIGIN})
        got = self.recorded(self.read_run(copied))
        self.assertEqual(
            (got.origin_run, got.origin_chosen, got.origin_unreadable_runs),
            (None, False, ()),
        )

    def test_two_writers_refuse_the_start_until_one_is_chosen(self) -> None:
        first = self.write_run('{"id": 1}\n')
        second = self.write_run('{"id": 1}\n')
        before = self.runs_now()
        with self.assertRaises(SystemExit) as cm:
            self.read_run(self.out)
        said = str(cm.exception.code)
        self.assertIn(first.run_id, said)
        self.assertIn(second.run_id, said)
        self.assertEqual(self.runs_now(), before)  # refused before mkdir
        chosen = runlog.RunOutput(self.out, run=first.run_id)
        self.assertEqual(
            self.origins(chosen), {"items": InputOrigin(first.run_id, True, None)}
        )
        got = self.recorded(self.read_run(chosen))
        self.assertEqual((got.origin_run, got.origin_chosen), (first.run_id, True))

    def test_a_wrong_choice_refuses_the_start(self) -> None:
        self.write_run('{"id": 1}\n')
        before = self.runs_now()
        with self.assertRaises(SystemExit) as cm:
            self.read_run(runlog.RunOutput(self.out, run=C))
        self.assertIn("no run of this area has that id", str(cm.exception.code))
        self.assertEqual(self.runs_now(), before)

    def test_a_run_of_another_area_is_no_origin(self) -> None:
        other = self.area.parent / "other"
        other.mkdir()
        with runlog.run("w", {}, other, data=runlog.NO_INPUTS) as there:
            there.output(self.out)
            self.out.write_text('{"id": 1}\n', encoding="utf-8")
            there.metrics(n=1)
        self.assertEqual(self.origins(self.out), {"items": input_origins.NO_ORIGIN})
        with self.assertRaises(SystemExit) as cm:
            self.read_run(runlog.RunOutput(self.out, run=there.run_id))
        self.assertIn("no run of this area has that id", str(cm.exception.code))

    def test_a_run_that_broke_off_is_no_origin(self) -> None:
        started: list[runlog.Run] = []
        with self.assertRaises(RuntimeError):
            with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS) as r:
                started.append(r)
                r.output(self.out)
                self.out.write_text('{"id": 1}\n', encoding="utf-8")
                raise RuntimeError("stopped")
        broke = started[0]
        self.assertEqual(self.origins(self.out), {"items": input_origins.NO_ORIGIN})
        with self.assertRaises(SystemExit) as cm:
            self.read_run(runlog.RunOutput(self.out, run=broke.run_id))
        self.assertIn(f"{broke.run_id} is not completed", str(cm.exception.code))

    def test_a_damaged_run_holds_no_other_start_and_is_warned_of(self) -> None:
        w = self.write_run('{"id": 1}\n')
        damaged = self.area / "runs" / "2026-10-15T00-00-00_dead"
        damaged.mkdir()
        (damaged / "config.json").write_text("{not json", encoding="utf-8")
        skipped = (UnreadableRun(damaged.name, MALFORMED),)
        self.assertEqual(
            self.origins(self.out),
            {"items": InputOrigin(w.run_id, False, None, skipped)},
        )
        told = io.StringIO()
        with contextlib.redirect_stdout(told):
            r = self.read_run(self.out)
        self.assertEqual(self.recorded(r).origin_unreadable_runs, skipped)
        self.assertIn(
            f"is not what labkit writes (damaged or hand-edited): {damaged.name}",
            told.getvalue(),
        )
        self.assertIn(f"data['items'] = out.jsonl as {w.run_id}", told.getvalue())
        told = io.StringIO()
        with contextlib.redirect_stdout(told):
            self.read_run(runlog.RunOutput(self.out, run=w.run_id))
        self.assertNotIn("does not read (", told.getvalue())  # chosen
        with self.assertRaises(SystemExit) as cm:
            self.read_run(runlog.RunOutput(self.out, run=damaged.name))
        self.assertIn(f"{damaged.name} does not read", str(cm.exception.code))

    def skipped_as(self, run_dir: Path) -> tuple[UnreadableRun, ...]:
        """What the record of a run reading out.jsonl says it skipped, with
        RUN_DIR among the area's runs."""
        with contextlib.redirect_stdout(io.StringIO()):
            return self.recorded(self.read_run(self.out)).origin_unreadable_runs

    def test_a_record_of_another_schema_is_skipped_as_such_not_as_damage(self) -> None:
        w = self.write_run('{"id": 1}\n')
        cfg = w.dir / "config.json"
        record = json.loads(cfg.read_text(encoding="utf-8"))
        for version in (4, 6, None):
            with self.subTest(schema_version=version):
                record["schema_version"] = version
                cfg.write_text(json.dumps(record), encoding="utf-8")
                self.assertEqual(
                    self.skipped_as(w.dir), (UnreadableRun(w.run_id, OTHER_SCHEMA),)
                )
        record["schema_version"] = "5"  # no version at all: malformed
        cfg.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.skipped_as(w.dir), (UnreadableRun(w.run_id, MALFORMED),))

    def test_a_record_that_cannot_be_opened_is_skipped_as_access(self) -> None:
        w = self.write_run('{"id": 1}\n')
        cfg = w.dir / "config.json"
        cfg.chmod(0)
        self.addCleanup(cfg.chmod, 0o644)
        if os.access(cfg, os.R_OK):
            self.skipTest("this user reads a file of mode 000 (root)")
        self.assertEqual(self.skipped_as(w.dir), (UnreadableRun(w.run_id, ACCESS),))

    def test_a_completed_run_whose_outputs_do_not_read_is_skipped_as_malformed(
        self,
    ) -> None:
        w = self.write_run('{"id": 1}\n')
        (w.dir / "outputs.json").write_text("[{", encoding="utf-8")
        self.assertEqual(self.skipped_as(w.dir), (UnreadableRun(w.run_id, MALFORMED),))

    def test_a_chosen_binary_origin_records_bytes_only(self) -> None:
        weights = self.area / "model.bin"
        with runlog.run("w", {}, self.area, data=runlog.NO_INPUTS) as w:
            w.output(weights)
            weights.write_bytes(b"\xff\xfe")
            w.metrics(n=1)
        got = self.recorded(
            self.read_run(
                runlog.RunOutput(provenance.BinaryInput(weights), run=w.run_id)
            )
        )
        self.assertEqual(
            (got.rows, got.origin_run, got.origin_chosen), (None, w.run_id, True)
        )

    def test_a_file_changed_after_its_run_matches_no_run(self) -> None:
        w = self.write_run('{"id": 1}\n')
        self.out.write_text('{"id": 2}\n', encoding="utf-8")
        self.assertEqual(self.origins(self.out), {"items": input_origins.NO_ORIGIN})
        with self.assertRaises(SystemExit) as cm:
            self.read_run(runlog.RunOutput(self.out, run=w.run_id))
        self.assertIn("other bytes", str(cm.exception.code))

    def test_a_repeat_that_wrote_the_file_is_its_origin(self) -> None:
        primary = self.write_run('{"id": 1}\n')
        repeat = self.write_run('{"id": 2}\n', repeat_of=primary.run_id)
        self.assertEqual(
            self.origins(self.out),
            {"items": InputOrigin(repeat.run_id, False, primary.run_id)},
        )
        chosen = runlog.RunOutput(self.out, run=repeat.run_id)
        self.assertEqual(
            self.origins(chosen),
            {"items": InputOrigin(repeat.run_id, True, primary.run_id)},
        )
        got = self.recorded(self.read_run(chosen))
        # the repeat's own record says what it repeats; the entry names it only
        self.assertEqual((got.origin_run, got.origin_chosen), (repeat.run_id, True))
        self.assertEqual(runs.read_run_config(repeat.dir).repeat_of, primary.run_id)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
