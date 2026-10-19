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

from protocol_fixture import DEFAULT_BLOCK, PID, head, scope_file

from labkit.checks import recheck
from labkit.run import runlog, provenance
from labkit.formats import runs, answering_run


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
            run.metrics(c1_pass=True, a1_pass=True, a2_pass=True)
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
        text += "\n## Result\n\n- **Answer to the question:** <the answer>\n\n## Runs\n\n- <run_id> — <one sentence>\n"
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
            ({"repeat_of": 17, "draw": 2}, "repeat_of = 17, not a run id"),
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

    def test_same_block_other_code_script_or_model_is_no_repeat(self):
        """A record with the same block but another declared_scope_sha came
        back comparable (review 2026-10-15): plan() could change and the new
        run still count as a draw of the old. The whole promise snapshot, the
        measure script and the resolved model are compared too."""
        first = self._run()
        parent = self._cfg(first)
        base = {
            k: parent.get(k)
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
                        "sha256": provenance.sha256_file(out)[:16],
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
            json.dumps({"c1_pass": True, "model_calls": 2}), encoding="utf-8"
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
            json.dumps(self._cfg(primary)), encoding="utf-8"
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
        ):
            with self.subTest(parent=parent):
                if needle is None:
                    self._run(derived_from=parent)
                    continue
                with self.assertRaises(SystemExit) as cm:
                    self._run(derived_from=parent)
                self.assertIn(needle, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
