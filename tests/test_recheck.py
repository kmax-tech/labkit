"""recheck: the three mechanics a `--check` needs, each at its edge —
prefix sha, intent keys, vanished keys, rounding in the note, the run_id."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol_fixture import run_record, PID, head, recheck_without_git  # noqa: E402

from labkit.formats.runs import RUN_SCHEMA  # noqa: E402
from labkit.checks import recheck, result_render  # noqa: E402

ROWS = [{"case": "a", "n": 4}, {"case": "b", "n": 3}]


def evaluate(rows: list[dict]) -> dict:
    return {"mean_n": sum(r["n"] for r in rows) / len(rows), "n_cases": len(rows)}


class Area(unittest.TestCase):
    def setUp(self):
        self.require_run_code = recheck.require_run_code
        recheck_without_git(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name)
        self.out = self.area / "output" / "rows.jsonl"
        self.out.parent.mkdir()
        self.out.write_text(
            "".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8"
        )
        self.run_dir = self.area / "runs" / "2026-10-05T19-00-00_ab12"
        self.run_dir.mkdir(parents=True)
        # a current run: the current schema_version plus a completion record — metrics
        # alone is never a completed run
        (self.run_dir / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": RUN_SCHEMA,
                        "run_kind": "measurement",
                        "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                    }
                )
            )
        )
        (self.run_dir / "completion.json").write_text(
            json.dumps({"status": "completed"})
        )
        self._record(evaluate(ROWS))
        self.note = self.area / "PROTOCOL-x.md"
        self.note.write_text(
            "- **Conclusion:** 3,5 über 2 Fälle, run 2026-10-05T19-00-00_ab12\n\n"
            + head(),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, metrics: dict, sha: str | None = None) -> None:
        sha = (
            sha
            if sha is not None
            else hashlib.sha256(self.out.read_bytes()).hexdigest()[:16]
        )
        (self.run_dir / "metrics.json").write_text(
            json.dumps({**metrics, "duration_s": 0.1})
        )
        (self.run_dir / "outputs.json").write_text(
            json.dumps([{"path": str(self.out), "sha256": sha}])
        )

    def test_a_run_whose_code_is_not_recorded_is_not_verifiable(self):
        """No script recorded: the numbers agree with today's code, and the
        note cites them — the recalculation still does not hold, and
        nothing is recomputed in its place."""
        calls: list[int] = []

        def counted(rows: list[dict]) -> dict:
            calls.append(1)
            return evaluate(rows)

        with (
            mock.patch.object(recheck, "require_run_code", self.require_run_code),
            self.assertRaises(recheck.NotVerifiable) as cm,
        ):
            recheck.holds(self.area, self.out, counted, self.note)
        told = str(cm.exception.code)
        self.assertIn("is not verifiable", told)
        self.assertIn("recorded no script", told)
        self.assertIn("not a failed comparison", told)
        self.assertIn("or measure anew", told)
        self.assertEqual(calls, [])

    def test_holds(self):
        v = recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertEqual(v.run_id, "2026-10-05T19-00-00_ab12")
        self.assertEqual(v.grown, [])
        self.assertEqual(v.keys_compared, 2)

    def test_prefix_sha_is_enough(self):
        self._record(
            evaluate(ROWS), sha=hashlib.sha256(self.out.read_bytes()).hexdigest()[:12]
        )
        recheck.holds(self.area, self.out, evaluate, self.note)

    def test_rows_not_the_runs_rows(self):
        self.out.write_text(json.dumps({"case": "a", "n": 9}) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("not the file", str(cm.exception))

    def test_vanished_key_fails_grown_key_is_reported(self):
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, lambda rows: {"mean_n": 3.5}, self.note)
        self.assertIn("vanished ['n_cases']", str(cm.exception))
        # the way out: a key the rows' evaluation does not produce is computed
        # there, so a required check is moved into it, not dropped
        self.assertIn("compute each in `evaluate_rows()`", str(cm.exception))
        v = recheck.holds(
            self.area, self.out, lambda rows: {**evaluate(rows), "max_n": 4}, self.note
        )
        self.assertEqual(v.grown, ["max_n"])

    def test_intent_key_on_one_side_fails(self):
        self._record({**evaluate(ROWS), "criterion_1_pass": True})
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("criterion_1_pass", str(cm.exception))

    def test_note_missing_number_or_run(self):
        self.note.write_text(
            "- **Conclusion:** 3.5, run 2026-10-05T19-00-00_ab12\n" + "\n" + head()
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("numbers not in", str(cm.exception))  # 2 (n_cases) is absent
        self.note.write_text("- **Conclusion:** 3.5 over 2 cases\n" + "\n" + head())
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("does not cite run", str(cm.exception))

    def test_an_unwritten_answer_line_names_the_write_back(self):
        self.note.write_text(
            "- **Recorded results:** <per registered id its verdict>\n" + "\n" + head()
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("has no answer yet", str(cm.exception))
        self.assertIn("labkit-adopt", str(cm.exception))
        # the adoption is the last step: its precondition stands beside it
        self.assertIn("report-check shows no other blocker", str(cm.exception))

    def test_number_must_be_a_token(self):
        self.assertFalse(recheck._present("3.5", "13.57"))
        self.assertFalse(recheck._present("2", "run 2026-10-05"))
        # the run id is in every note: its parts are never a cited number
        self.assertFalse(recheck._present("10", "run 2026-10-05T10-22-33_ab12"))
        self.assertFalse(recheck._present("22", "run 2026-10-05T10-22-33_ab12"))
        self.assertFalse(recheck._present("2026", "frozen 2026-10-05T10:22"))
        self.assertFalse(recheck._present("12", "mean 12.7"))
        self.assertTrue(recheck._present("12", "n = 12."))
        self.assertTrue(recheck._present("10", "10 of 2026-10-05T10-22-33_ab12"))
        self.assertTrue(recheck._present("3.5", "mean 3,5 docs"))
        self.assertTrue(recheck._present("-0.2", "delta −0.2"))
        self.assertTrue(recheck._present("+0.2", "delta 0.2"))

    def test_sign_and_exponent_belong_to_the_number(self):
        """A number is found whole: `0.5` not in `-0.5`, `1` and `5` not in `1e-5`."""
        self.assertFalse(recheck._present("0.5", "delta -0.5"))
        self.assertFalse(recheck._present("0.5", "delta −0.5"))
        self.assertFalse(recheck._present("1", "p = 1e-5"))
        self.assertFalse(recheck._present("5", "p = 1e-5"))
        self.assertTrue(recheck._present("1e-5", "p = 1e-5"))
        self.assertTrue(recheck._present("-0.5", "(-0.5)"))
        # a hyphen between numbers is no sign: both ends are cited
        self.assertTrue(recheck._present("3", "range 3-5"))
        self.assertTrue(recheck._present("5", "range 3-5"))

    def test_a_value_that_is_not_finite_is_a_word_of_the_note(self):
        """`plain_numbers` writes NaN and the infinities as Python prints
        them, the same spelling `protocol-fill --from-run` writes into
        Recorded results; the check finds that word, whole and in any case,
        never a digit run. The twin: a note without the word is refused."""
        self.assertEqual(recheck.plain_numbers({"a": float("nan")}), ["nan"])
        self.assertEqual(
            result_render.recorded_results_line({"a": float("nan")}, "r"),
            "a = nan (run r)",
        )
        self.assertTrue(recheck._present("nan", "mean = nan"))
        self.assertTrue(recheck._present("nan", "mean NaN over 3 cases"))
        self.assertTrue(recheck._present("inf", "ratio = inf"))
        self.assertTrue(recheck._present("-inf", "log = -inf"))
        self.assertFalse(recheck._present("nan", "3 nanometres"))
        self.assertFalse(recheck._present("inf", "see the info line"))
        self.assertFalse(recheck._present("inf", "log = -inf"))
        self.assertFalse(recheck._present("-inf", "ratio = inf"))
        self.assertFalse(recheck._present("nan", "mean = 3.5"))

    def test_a_nan_the_run_recorded_is_cited_or_refused(self):
        nan_metrics = {"mean_n": float("nan"), "n_cases": 2}
        self._record(nan_metrics)
        self.note.write_text(
            "- **Recorded results:** "
            + result_render.recorded_results_line(
                nan_metrics, "2026-10-05T19-00-00_ab12"
            )
            + "\n\n"
            + head(),
            encoding="utf-8",
        )
        v = recheck.holds(self.area, self.out, lambda rows: nan_metrics, self.note)
        self.assertEqual(v.numbers, ["nan", "2"])
        self.note.write_text(
            "- **Recorded results:** mean_n = 3.5, n_cases = 2 "
            "(run 2026-10-05T19-00-00_ab12)\n\n" + head(),
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, lambda rows: nan_metrics, self.note)
        self.assertIn("numbers not in PROTOCOL-x.md: ['nan']", str(cm.exception))

    def test_a_note_with_the_wrong_sign_is_refused(self):
        self._record({"delta": -0.5})
        self.note.write_text(
            "delta 0.5 · run 2026-10-05T19-00-00_ab12\n" + "\n" + head()
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, lambda rows: {"delta": -0.5}, self.note)
        self.assertIn("numbers not in", str(cm.exception))

    def test_a_value_of_another_json_type_differs(self):
        """`true` and `1` differ, though Python's `==` holds them equal."""
        for stored, again in (
            (True, 1),
            (1, 1.0),
            ([True], [1]),
            ({"a": 0}, {"a": False}),
        ):
            with self.assertRaises(SystemExit, msg=f"{stored!r} vs {again!r}"):
                recheck.require_agreement(
                    {"criterion_1_pass": stored}, {"criterion_1_pass": again}
                )
        self.assertEqual(
            recheck.require_agreement(
                {"criterion_1_pass": True}, {"criterion_1_pass": True}
            ),
            [],
        )

    def test_a_tuple_is_the_list_the_run_recorded(self):
        """evaluate() returns a tuple, metrics.json holds a list: the same
        value after the JSON round trip, not a difference."""
        self.assertEqual(
            recheck.require_agreement(
                {"criterion_1_pass": [1, 2]}, {"criterion_1_pass": (1, 2)}
            ),
            [],
        )
        with self.assertRaises(SystemExit):
            recheck.require_agreement(
                {"criterion_1_pass": [1, 2]}, {"criterion_1_pass": (1, 3)}
            )

    def test_the_kept_number_is_compared_exactly(self):
        """A computation's `[kept]` key is the number it reports: exact, as
        an identifier."""
        with self.assertRaisesRegex(SystemExit, "kept number"):
            recheck.require_agreement(
                {"mean": 3.5}, {"mean": 4.5}, kept=frozenset({"mean"})
            )
        self.assertEqual(recheck.require_agreement({"mean": 3.5}, {"mean": 4.5}), [])

    def test_a_kept_number_on_one_side_only_is_refused(self):
        """The kept number missing from metrics.json or from the
        recomputation fails the check. The twins: the same key unreported
        grows and passes; absent from both, finalize blocks, not agree."""
        for metrics, recomputed, side in (
            ({"n": 3}, {"n": 3, "mean": 4.5}, "metrics.json"),
            ({"n": 3, "mean": 4.5}, {"n": 3}, "recomputation"),
        ):
            with self.assertRaisesRegex(
                SystemExit, rf"kept number is missing — \{{'mean': \['{side}'\]\}}"
            ):
                recheck.require_agreement(metrics, recomputed, kept=frozenset({"mean"}))
        self.assertEqual(
            recheck.require_agreement({"n": 3}, {"n": 3, "mean": 4.5}), ["mean"]
        )
        self.assertEqual(
            recheck.require_agreement({"n": 3}, {"n": 3}, kept=frozenset({"mean"})), []
        )

    def test_a_descriptive_value_may_differ_and_may_not_vanish(self):
        """LAB-041 Generate numbers, don't retype them: identifiers exact;
        of the descriptive keys none may disappear."""
        self.assertEqual(
            recheck.require_agreement(
                {"criterion_1_pass": True, "funnel": [3, 2]},
                {"criterion_1_pass": True, "funnel": [3, 1], "table": "new"},
            ),
            ["table"],
        )
        with self.assertRaisesRegex(SystemExit, "vanished"):
            recheck.require_agreement(
                {"criterion_1_pass": True, "funnel": [3, 2]}, {"criterion_1_pass": True}
            )

    def _second_output(self, text: str) -> Path:
        """A second output file holding TEXT, registered by the run beside
        the rows with its sha256."""
        second = self.area / "output" / "judged.json"
        second.write_text(text, encoding="utf-8")
        (self.run_dir / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": str(p),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16],
                    }
                    for p in (self.out, second)
                ]
            )
        )
        return second

    def test_holds_outputs_hands_the_rows_of_each_file_by_its_key(self):
        second = self._second_output('{"case": "a"}\n{"case": "b"}\n')
        handed: list[dict] = []

        def both(rows):
            handed.append(dict(rows))
            assert len(rows["judged"]) == len(rows["counted"])
            return evaluate(rows["counted"])

        outs = {"counted": self.out, "judged": second}
        v = recheck.holds_outputs(self.area, outs, both, self.note)
        self.assertEqual(v.outs, outs)
        self.assertEqual(v.keys_compared, 2)
        self.assertEqual(
            handed, [{"counted": ROWS, "judged": [{"case": "a"}, {"case": "b"}]}]
        )

    def test_a_json_document_is_no_row_file_and_is_refused_by_its_key(self):
        """A stagekit stage output is one indented JSON document
        (`stage_outputs/<stage>/<key>.json`), not one row per line: the
        recheck names the output and reads nothing in its place."""
        second = self._second_output(json.dumps([{"case": "a"}], indent=2))
        calls: list[int] = []
        with self.assertRaises(SystemExit) as cm:
            recheck.holds_outputs(
                self.area,
                {"counted": self.out, "judged": second},
                lambda rows: calls.append(1) or {},
                self.note,
            )
        told = str(cm.exception)
        self.assertIn("output 'judged' (judged.json) is no row file", told)
        self.assertIn("not JSON", told)
        self.assertEqual(calls, [])

    def test_no_output_named_is_refused(self):
        with self.assertRaisesRegex(ValueError, "names no output file"):
            recheck.holds_outputs(self.area, {}, lambda rows: {}, self.note)

    def test_custom_number_format_for_a_rounding_note(self):
        self._record({"ratio": 0.857142857})
        self.note.write_text(
            "ratio 0.86 · run 2026-10-05T19-00-00_ab12\n" + "\n" + head()
        )
        recheck.holds(
            self.area,
            self.out,
            lambda rows: {"ratio": 0.857142857},
            self.note,
            numbers=lambda m: [f"{m['ratio']:.2f}"],
        )


if __name__ == "__main__":
    unittest.main()
