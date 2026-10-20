"""recheck (2026-10-05): the three mechanics a `--check` needs, each at its edge —
prefix sha, intent keys, vanished keys, rounding in the note, the run_id."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol_fixture import PID, head  # noqa: E402

from labkit.checks import recheck  # noqa: E402

ROWS = [{"case": "a", "n": 4}, {"case": "b", "n": 3}]


def evaluate(rows: list[dict]) -> dict:
    return {"mean_n": sum(r["n"] for r in rows) / len(rows), "n_cases": len(rows)}


class Area(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.area = Path(self._tmp.name)
        self.out = self.area / "output" / "rows.jsonl"
        self.out.parent.mkdir()
        self.out.write_text(
            "".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8"
        )
        self.run_dir = self.area / "runs" / "2026-10-05T19-00-00_ab12"
        self.run_dir.mkdir(parents=True)
        # a current run: schema_version 2 plus a completion record — metrics
        # alone (a legacy run) is never completed since labkit 0.48
        (self.run_dir / "config.json").write_text(
            json.dumps(
                {"schema_version": 2, "protocol": {"id": PID, "path": "PROTOCOL-x.md"}}
            )
        )
        (self.run_dir / "completion.json").write_text(
            json.dumps({"status": "completed"})
        )
        self._record(evaluate(ROWS))
        self.note = self.area / "PROTOCOL-x.md"
        self.note.write_text(
            "- **Result:** 3,5 über 2 Fälle, run 2026-10-05T19-00-00_ab12\n\n" + head(),
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
        v = recheck.holds(
            self.area, self.out, lambda rows: {**evaluate(rows), "max_n": 4}, self.note
        )
        self.assertEqual(v.grown, ["max_n"])

    def test_intent_key_on_one_side_fails(self):
        self._record({**evaluate(ROWS), "c1_pass": True})
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("c1_pass", str(cm.exception))

    def test_note_missing_number_or_run(self):
        self.note.write_text(
            "- **Result:** 3.5, run 2026-10-05T19-00-00_ab12\n" + "\n" + head()
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("numbers not in", str(cm.exception))  # 2 (n_cases) is absent
        self.note.write_text("- **Result:** 3.5 over 2 cases\n" + "\n" + head())
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("does not cite run", str(cm.exception))

    def test_an_unwritten_answer_line_names_the_write_back(self):
        self.note.write_text(
            "- **Answer to the question:** <!-- s --> <per registered id its verdict>\n"
            + "\n"
            + head()
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.note)
        self.assertIn("has no answer yet", str(cm.exception))
        self.assertIn("--from-run", str(cm.exception))

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

    def test_a_value_of_another_json_type_differs(self):
        """Review 2026-10-20: `true` and `1` were equal to Python's `==`."""
        for stored, again in (
            (True, 1),
            (1, 1.0),
            ([True], [1]),
            ({"a": 0}, {"a": False}),
        ):
            with self.assertRaises(SystemExit, msg=f"{stored!r} vs {again!r}"):
                recheck.agree({"c1_pass": stored}, {"c1_pass": again})
        self.assertEqual(recheck.agree({"c1_pass": True}, {"c1_pass": True}), [])

    def test_a_tuple_is_the_list_the_run_recorded(self):
        """evaluate() returns a tuple, metrics.json holds a list: the same
        value after the JSON round trip, not a difference (audit 2026-10-15)."""
        self.assertEqual(recheck.agree({"a": [1, 2]}, {"a": (1, 2)}), [])
        with self.assertRaises(SystemExit):
            recheck.agree({"a": [1, 2]}, {"a": (1, 3)})

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
