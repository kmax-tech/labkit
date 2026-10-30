"""repeat_of: the same measurement drawn again, never the answer.

`derived_from` re-reads a parent's rows without a model call; `repeat_of`
asks the model again with the same instrument on the same items, so the
spread of the number becomes visible (TODO item 4: every audit of the cloud
judge probe named "one unseeded draw", 2026-10-14). A repeat is supporting
evidence: the primary run keeps answering the protocol in every default
choice, and a run that differs in protocol, block, config or inputs is no
repeat at all.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record, DEFAULT_BLOCK, PID, head, scope_file

from labkit.checks import recheck
from labkit.run import runlog, provenance
from labkit.formats import runs, answering_run


def _read(table: dict) -> runs.RunConfig:
    """A parent run as the reader gives it: TABLE's fields in a schema-3
    measurement record."""
    return runs.parse_run_config(run_record(table))


class Repeats(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)
        (self.area / "PROTOCOL-x.md").write_text(
            head(promises=DEFAULT_BLOCK) + "\n- **Question / hypothesis:** q\n",
            encoding="utf-8",
        )
        self.data = self.area / "items.jsonl"
        self.data.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")

    def _run(
        self,
        config: dict | None = None,
        repeat_of: str | None = None,
        derived_from: str | None = None,
    ) -> str:
        cfg = config or {"prompt_sha": "aaaaaaaaaaaa", "model_alias": "x"}
        r = runlog.run(
            "m",
            config=cfg,
            base_dir=self.area,
            data={"items": self.data},
            repeat_of=repeat_of,
            derived_from=derived_from,
        )
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            run.metrics(
                criterion_1_pass=True,
                quality_check_1_pass=True,
                quality_check_2_pass=True,
            )
        return run.run_id

    def _cfg(self, run_id: str) -> dict:
        return json.loads((self.area / "runs" / run_id / "config.json").read_text())

    def test_a_repeat_records_its_parent_and_counts_its_draw(self):
        first = self._run()
        second = self._run(repeat_of=first)
        third = self._run(repeat_of=first)
        self.assertEqual(
            [
                (self._cfg(r)["repeat_of"], self._cfg(r)["draw"])
                for r in (first, second, third)
            ],
            [(None, None), (first, 2), (first, 3)],
        )
        self.assertEqual(
            [p.name for p in answering_run.repeats_of(self.area, first)],
            [second, third],
        )

    def test_draws_number_the_run_and_its_repeats(self):
        first = self._run()
        self.assertEqual(answering_run.next_draw(self.area, first), 2)
        self.assertEqual([n for n, _ in answering_run.draws(self.area, first)], [1])
        second = self._run(repeat_of=first)
        self.assertEqual(answering_run.next_draw(self.area, first), 3)
        self.assertEqual(
            [(n, d.name) for n, d in answering_run.draws(self.area, first)],
            [(1, first), (2, second)],
        )

    def test_finalize_warns_on_one_draw_of_a_model_run_and_not_after_a_repeat(self):
        """The spread is static evidence: a warning until a repeat exists,
        nothing for a run that asked no model."""
        from labkit.checks import run_record_check

        first = self._run()
        primary = self.area / "runs" / first
        self.assertIsNone(
            run_record_check.single_draw(self.area, primary)
        )  # no model calls
        metrics = primary / "metrics.json"
        m = json.loads(metrics.read_text())
        metrics.write_text(json.dumps({**m, "llm_retries": 0}), encoding="utf-8")
        self.assertIn(
            "is one draw — no spread",
            run_record_check.single_draw(self.area, primary) or "",
        )
        self._run(repeat_of=first)
        self.assertIsNone(run_record_check.single_draw(self.area, primary))

    def test_a_named_repeat_is_never_written_back_not_even_with_force(self):
        """`protocol-fill --from-run <repeat>` wrote a repeat's number into
        Answer, Result and Runs (review 2026-10-15). recheck.run_dir, the one
        choice behind --from-run and --check, refuses it; the primary is
        written."""
        from labkit.tools import protocol_fill

        first = self._run()
        second = self._run(repeat_of=first)
        text = (self.area / "PROTOCOL-x.md").read_text(encoding="utf-8")
        text += "\n## Result\n\n- **Recorded results:** <the answer>\n\n## Runs\n\n- <run_id> — <one sentence>\n"
        for force in (False, True):
            with self.subTest(force=force), self.assertRaises(SystemExit) as cm:
                protocol_fill.from_run(text, self.area, second, force=force)
            self.assertIn("never the answer", str(cm.exception))
        written, _, run_id = protocol_fill.from_run(text, self.area, first)
        self.assertEqual(run_id, first)
        self.assertIn(f"(run {first})", written)

    def test_damaged_repeat_fields_are_unreadable_not_a_primary(self):
        first = self._run()
        cfg_path = self.area / "runs" / first / "config.json"
        cfg = json.loads(cfg_path.read_text())
        for damage, needle in (
            ({"repeat_of": 17, "draw": 2}, "repeat_of = 17, not a string"),
            ({"repeat_of": None, "draw": 2}, "draw = 2 without repeat_of"),
            ({"repeat_of": first, "draw": 1}, "not an integer >= 2"),
        ):
            with self.subTest(damage=damage):
                cfg_path.write_text(json.dumps({**cfg, **damage}), encoding="utf-8")
                with self.assertRaises(runs.RunConfigError) as cm:
                    runs.read_run_config(cfg_path.parent)
                self.assertIn(needle, str(cm.exception))

    def test_the_primary_keeps_answering_and_rechecking(self):
        first = self._run()
        self._run(repeat_of=first)
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir.name if choice.run_dir else None, first)
        self.assertIn("a repeat of", " ".join(e.why for e in choice.exclusions))
        self.assertEqual(
            recheck.run_dir(self.area, self.area / "PROTOCOL-x.md").name, first
        )
        self.assertEqual(len(runs.completed_runs(self.area, with_repeats=True)), 2)
        self.assertEqual(len(runs.completed_runs(self.area, with_repeats=False)), 1)

    def test_a_run_that_measures_something_else_is_no_repeat(self):
        first = self._run()
        with self.assertRaises(SystemExit) as cm:
            self._run(
                {"prompt_sha": "bbbbbbbbbbbb", "model_alias": "x"}, repeat_of=first
            )
        self.assertIn("config prompt_sha", str(cm.exception))
        self.data.write_text('{"id": "a"}\n', encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self._run(repeat_of=first)
        self.assertIn("the inputs (data=) differ", str(cm.exception))
        self.assertEqual(
            len(runs.completed_runs(self.area, with_repeats=True)), 1
        )  # nothing made

    def test_a_tuple_in_the_config_repeats_as_the_list_it_was_stored_as(self):
        cfg = {"prompt_sha": "aaaaaaaaaaaa", "model_alias": "x", "labels": ("a", "b")}
        first = self._run(cfg)
        second = self._run(cfg, repeat_of=first)
        self.assertEqual(self._cfg(second)["draw"], 2)

    def test_type_and_presence_of_a_config_value_count(self):
        parent = {"config": {"greedy": 1, "seed": None}}
        for new, needle in (
            ({"config": {"greedy": True, "seed": None}}, "config greedy: 1 → true"),
            ({"config": {"greedy": 1}}, "config seed: null → (absent)"),
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, answering_run.repeat_mismatch(_read(parent), new))

    def test_a_damaged_table_is_not_an_empty_one(self):
        """Review 2026-10-20: a parent recording `"config": ["invalid-record"]`
        read as an empty config, and a repeat with an empty one passed."""
        with self.assertRaises(runs.RunConfigError) as cm:
            answering_run.repeat_mismatch(_read({}), {"config": ["invalid-record"]})
        self.assertIn("config = ['invalid-record'], not an object", str(cm.exception))
        with self.assertRaises(runs.RunConfigError) as cm:
            _read({"config": ["invalid-record"]})  # a parent never gets this far
        self.assertIn("config = ['invalid-record'], not an object", str(cm.exception))
        # the reader refuses the record before anything compares it
        first = self._run()
        cfg_path = self.area / "runs" / first / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg_path.write_text(
            json.dumps({**cfg, "config": ["invalid-record"]}), encoding="utf-8"
        )
        with self.assertRaises(runs.RunConfigError):
            runs.read_run_config(cfg_path.parent)
        with self.assertRaises(SystemExit) as cm:
            self._run(repeat_of=first)
        self.assertIn("config = ['invalid-record'], not an object", str(cm.exception))

    def test_absent_null_and_an_object_are_three_forms(self):
        """On the side of the run about to start; a read parent states every
        table (the writer writes all), absent or null alike reading None."""
        for parent, new, needle in (
            (
                {"promises": None},
                {"promises": {}},
                "promises: null in the parent, an object here",
            ),
            ({"data": {}}, {}, "data: an object in the parent, absent here"),
            ({"promises": None}, {}, "promises: null in the parent, absent here"),
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, answering_run.repeat_mismatch(_read(parent), new))
        # the twin: the same form on both sides says nothing
        parent = _read({"promises": None})
        self.assertEqual(
            answering_run.repeat_mismatch(parent, parent.repeat_basis()), []
        )

    def test_same_block_other_code_script_or_model_is_no_repeat(self):
        """A record with the same block but another declared_scope_sha came
        back comparable (review 2026-10-15): plan() could change and the new
        run still count as a draw of the old. The whole promise snapshot, the
        measure script and the resolved model are compared too."""
        first = self._run()
        parent = runs.read_run_config(self.area / "runs" / first)
        assert parent is not None
        base = {
            k: parent.as_record().get(k)
            for k in (
                "protocol",
                "promises",
                "config",
                "data",
                "script_sha",
                "models_resolved",
            )
        }
        self.assertEqual(answering_run.repeat_mismatch(parent, base), [])
        moved = json.loads(json.dumps(base))
        some_id = next(iter(moved["promises"]["ids"]))
        moved["promises"]["ids"][some_id]["declared_scope_sha"] = "000000000000"
        for new, needle in (
            (moved, "declared_scope_sha"),
            ({**base, "script_sha": "000000000000"}, "script_sha"),
            ({**base, "models_resolved": {"x": {"model": "other"}}}, "models_resolved"),
        ):
            with self.subTest(needle=needle):
                self.assertTrue(
                    any(
                        needle in m for m in answering_run.repeat_mismatch(parent, new)
                    ),
                    answering_run.repeat_mismatch(parent, new),
                )

    def test_the_draw_is_reserved_once_and_a_crashed_draw_keeps_its_number(self):
        first = self._run()
        r = runlog.run(
            "m",
            config={"prompt_sha": "aaaaaaaaaaaa", "model_alias": "x"},
            base_dir=self.area,
            data={"items": self.data},
            repeat_of=first,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            run = r.__enter__()
        self.assertEqual(run.draw, 2)  # the number the script names its file by
        # left unfinished, like a crash: draw 2 stays taken
        self.assertEqual(answering_run.next_draw(self.area, first), 3)
        self.assertEqual(self._cfg(self._run(repeat_of=first))["draw"], 3)

    def test_every_draw_is_held_like_the_kept_number(self):
        """--draws read each draw's file unchecked: an edited repeat file
        changed the flipped items (review 2026-10-15). recheck.verified pins
        a draw's output to its recorded digest before anything is shown."""
        from labkit.run import batch
        from labkit.checks import recheck

        def recompute(rows: list[dict]) -> dict:
            return {"n": len(rows)}

        first = self._run()
        second = self._run(repeat_of=first)
        out = self.area / "draw2.jsonl"
        with batch.Store(out) as store:
            store.append({"id": "a", "answer": "Yes"})
        run = self.area / "runs" / second
        (run / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": runs.recorded_path(out, run),
                        "sha256": provenance.source_digest(out)[:16],
                        "lines": 1,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (run / "metrics.json").write_text(json.dumps({"n": 1}), encoding="utf-8")
        metrics, _ = recheck.verified(run, self.area, out, recompute)
        self.assertEqual(metrics["n"], 1)
        out.write_text('{"id": "a", "answer": "No"}\n', encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            recheck.verified(run, self.area, out, recompute)
        self.assertIn("is not the file run", str(cm.exception))

    def test_no_repeat_of_a_repeat_a_missing_run_or_with_derived_from(self):
        first = self._run()
        second = self._run(repeat_of=first)
        for kw, needle in (
            ((second, None), "is itself a repeat"),
            (("2026-01-01T00-00-00_0000", None), "names no completed run"),
            ((first, first), "exclude each other"),
        ):
            with self.subTest(kw=kw), self.assertRaises(SystemExit) as cm:
                self._run(repeat_of=kw[0], derived_from=kw[1])
            self.assertIn(needle, str(cm.exception))

    def test_an_unreadable_run_refuses_the_next_draw_with_a_sentence(self):
        """Mutant: a run that cannot say whether it is a draw — its number
        may be the next one. Refused with the field named, not a traceback
        and not a reused number (2026-10-15)."""
        first = self._run()
        bad = self.area / "runs" / "2026-10-15T00-00-00_dead"
        bad.mkdir()
        (bad / "config.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self._run(repeat_of=first)
        self.assertIn("next draw number cannot be counted", str(cm.exception))

    def test_finalize_says_the_draws_cannot_be_counted(self):
        """Mutant and twin: the single-draw warning names an unreadable run
        instead of raising; with the area clean it is the usual warning."""

        from labkit.checks import run_record_check

        first = self._run()
        run = self.area / "runs" / first
        (run / "metrics.json").write_text(
            json.dumps({"criterion_1_pass": True, "model_calls": 2}), encoding="utf-8"
        )
        self.assertIn("is one draw", run_record_check.single_draw(self.area, run) or "")
        bad = self.area / "runs" / "2026-10-15T00-00-00_dead"
        bad.mkdir()
        (bad / "config.json").write_text("{not json", encoding="utf-8")
        self.assertIn(
            "cannot be counted", run_record_check.single_draw(self.area, run) or ""
        )

    def test_a_derived_run_needs_a_completed_primary_parent(self):
        """Every kind of parent a derived run can name. A derived run is no
        repeat, so it may answer — derived from a repeat, it would let the
        best of several draws answer through the back door (2026-10-15).
        Twin: a completed primary parent, and a derived one, are taken."""
        primary = self._run()
        repeat = self._run(repeat_of=primary)
        derived = self._run(derived_from=primary)
        unfinalized = self.area / "runs" / "2026-10-15T00-00-01_0001"
        unfinalized.mkdir()
        (unfinalized / "config.json").write_text(
            json.dumps(run_record(self._cfg(primary))), encoding="utf-8"
        )
        unreadable = self.area / "runs" / "2026-10-15T00-00-02_0002"
        unreadable.mkdir()
        (unreadable / "config.json").write_text("{not json", encoding="utf-8")
        for parent, needle in (
            (primary, None),
            (derived, None),
            (repeat, "is a repeat of"),
            (unfinalized.name, "names no completed run"),
            (unreadable.name, "derived_from="),
            ("2026-01-01T00-00-00_0000", "names no completed run"),
            # a path to a run, even the right one, is no run id (review 2026-10-20)
            (f"./{primary}", "is not a run id"),
            (f"../../elsewhere/runs/{primary}", "is not a run id"),
        ):
            with self.subTest(parent=parent):
                if needle is None:
                    self._run(derived_from=parent)
                    continue
                with self.assertRaises(SystemExit) as cm:
                    self._run(derived_from=parent)
                self.assertIn(needle, str(cm.exception))


def _area(block: str) -> tuple[Path, Path]:
    """(area, its items file): a fresh area whose protocol carries BLOCK."""
    area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    area.mkdir(parents=True)
    scope_file(area)
    (area / "PROTOCOL-x.md").write_text(
        head(promises=block) + "\n- **Question / hypothesis:** q\n", encoding="utf-8"
    )
    data = area / "items.jsonl"
    data.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")
    return area, data


class Reseed(unittest.TestCase):
    """A fit's spread over seeds (audit 2026-10-27, C1 and A13): with
    `reseed`, runlog sets the repeat's seed to `repeat_seed` of the parent
    and the draw and records it; every other config key stays the
    parent's, and a seed the script or the protocol fixes is not drawn."""

    CFG = {"estimator_sha": "aaaaaaaaaaaa", "seed": 0, "n_folds": 5}

    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.area, self.data = _area(DEFAULT_BLOCK)

    def _run(
        self, config: dict, repeat_of: str | None = None, reseed: bool = False
    ) -> tuple[str, dict]:
        """(run id, the config the script saw through `Run.config`)."""
        r = runlog.run(
            "m",
            config=config,
            base_dir=self.area,
            data={"items": self.data},
            repeat_of=repeat_of,
            reseed=reseed,
        )
        seen: dict = {}
        with contextlib.redirect_stdout(io.StringIO()), r as run:
            seen = run.config
            run.metrics(
                criterion_1_pass=True,
                quality_check_1_pass=True,
                quality_check_2_pass=True,
            )
        return run.run_id, seen

    def _recorded(self, run_id: str) -> dict:
        path = self.area / "runs" / run_id / "config.json"
        return json.loads(path.read_text(encoding="utf-8"))["config"]

    def test_the_seed_is_a_function_of_the_run_and_the_draw(self):
        run = "2026-10-27T10-00-00_ab12"
        seed = answering_run.repeat_seed(run, 2)
        # pinned (`shasum -a 256` of "<run>:2", first four bytes): the
        # derivation is part of what a recorded seed means
        self.assertEqual(seed, 562606026)
        self.assertEqual(seed, answering_run.repeat_seed(run, 2))
        self.assertNotEqual(seed, answering_run.repeat_seed(run, 3))
        self.assertNotEqual(
            seed, answering_run.repeat_seed("2026-10-27T10-00-00_cd34", 2)
        )
        self.assertLess(answering_run.repeat_seed(run, 3), 2**32)
        with self.assertRaises(ValueError):
            answering_run.repeat_seed(run, 1)

    def test_each_draw_records_its_derived_seed_and_the_parent_keeps_its_own(self):
        first, _ = self._run(self.CFG)
        second, seen2 = self._run(self.CFG, repeat_of=first, reseed=True)
        third, seen3 = self._run(self.CFG, repeat_of=first, reseed=True)
        for run_id, draw, seen in ((second, 2, seen2), (third, 3, seen3)):
            want = {**self.CFG, "seed": answering_run.repeat_seed(first, draw)}
            self.assertEqual(self._recorded(run_id), want)
            self.assertEqual(seen, want)  # what the script measures with
        self.assertNotEqual(
            self._recorded(second)["seed"], self._recorded(third)["seed"]
        )
        self.assertEqual(self._recorded(first), self.CFG)
        answering, _ = answering_run.bound_runs(self.area, PID)
        self.assertEqual([f.dir.name for f in answering], [first])

    def test_the_seed_passed_is_replaced_and_every_other_key_held(self):
        first, _ = self._run(self.CFG)
        second, _ = self._run({**self.CFG, "seed": 7}, repeat_of=first, reseed=True)
        self.assertEqual(
            self._recorded(second)["seed"], answering_run.repeat_seed(first, 2)
        )
        with self.assertRaises(SystemExit) as cm:
            self._run({**self.CFG, "n_folds": 3}, repeat_of=first, reseed=True)
        self.assertIn("config n_folds: 5 → 3", str(cm.exception))

    def test_the_twin_without_reseed_another_seed_is_no_repeat(self):
        first, _ = self._run(self.CFG)
        with self.assertRaises(SystemExit) as cm:
            self._run({**self.CFG, "seed": 7}, repeat_of=first)
        self.assertIn("config seed: 0 → 7", str(cm.exception))
        same, _ = self._run(self.CFG, repeat_of=first)
        self.assertEqual(self._recorded(same), self.CFG)

    def test_reseed_needs_an_integer_seed_and_a_repeat_before_any_directory(self):
        bare = {"estimator_sha": "aaaaaaaaaaaa"}
        first, _ = self._run(bare)
        before = sorted((self.area / "runs").iterdir())
        with self.assertRaises(SystemExit) as cm:
            self._run(bare, repeat_of=first, reseed=True)
        self.assertIn("no integer `seed`", str(cm.exception))
        with self.assertRaises(SystemExit) as cm:
            self._run(self.CFG, reseed=True)
        self.assertIn("it goes with repeat_of", str(cm.exception))
        self.assertEqual(sorted((self.area / "runs").iterdir()), before)

    def test_a_seed_the_protocol_registers_is_not_drawn_anew(self):
        sentence = 'sentence = "the criterion holds"\n'
        self.assertEqual(DEFAULT_BLOCK.count(sentence), 1)
        self.area, self.data = _area(
            DEFAULT_BLOCK.replace(sentence, sentence + "constants = { seed = 0 }\n")
        )
        first, _ = self._run(self.CFG)
        with self.assertRaises(SystemExit) as cm:
            self._run(self.CFG, repeat_of=first, reseed=True)
        self.assertIn(
            "registers `seed` = 0 — a spread over seeds needs a seed the protocol "
            "does not fix",
            str(cm.exception),
        )
        same, _ = self._run(self.CFG, repeat_of=first)  # the twin: the same seed
        self.assertEqual(self._recorded(same), self.CFG)

    def test_the_comparison_derives_the_seed_itself(self):
        parent = _read({"config": {"seed": 0, "n": 1}})
        base = parent.repeat_basis()
        derived = answering_run.repeat_seed("P", 2)

        def mismatch(cfg: dict, of: runs.RunConfig = parent) -> list[str]:
            return answering_run.repeat_mismatch(
                of, {**of.repeat_basis(), "config": cfg}, reseed_of=("P", 2)
            )

        self.assertEqual(mismatch({"seed": derived, "n": 1}), [])
        self.assertEqual(
            mismatch({"seed": 98, "n": 1}),
            [f"config seed: 98, the derived seed of this draw is {derived}"],
        )
        self.assertEqual(
            mismatch({"seed": derived, "n": 2}), ["config n: 1 → 2"]
        )  # every other key stays the parent's
        unseeded = _read({"config": {"n": 1}})
        self.assertIn(
            "config seed: the parent records (absent), no integer seed — a repeat "
            "draws only a seed the parent had",
            mismatch({"seed": derived, "n": 1}, unseeded),
        )
        # the twin: without reseed the seed is held to the parent's
        self.assertEqual(answering_run.repeat_mismatch(parent, base), [])

    def test_a_recorded_seed_no_runlog_wrote_is_refused_where_draws_are_read(self):
        first, _ = self._run(self.CFG)
        reseeded, _ = self._run(self.CFG, repeat_of=first, reseed=True)
        plain, _ = self._run(self.CFG, repeat_of=first)
        self.assertEqual(
            [d.name for _, d in answering_run.draws(self.area, first)],
            [first, reseeded, plain],
        )  # the twin: the parent's seed and the derived one both read
        path = self.area / "runs" / reseeded / "config.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["config"]["seed"] = 7
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(runs.RunConfigError) as cm:
            answering_run.draws(self.area, first)
        self.assertIn("config seed: 7 is neither the parent's (0)", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
