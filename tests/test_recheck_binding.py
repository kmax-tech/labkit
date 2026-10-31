"""recheck chooses the run by the protocol's binding, like finalize.

Audit 2026-10-15: `recheck.run_dir` took the area's newest completed run
with no look at the binding, so in an area holding two protocols (the
series rule: s1, s2, …) `protocol-fill PROTOCOL-a.md --from-run` wrote the
number of the run bound to protocol B into A, and `--check` of a correct
area blocked on a newer producer run. The twin: the run bound to A, older
and with the number A's note cites, is the one chosen.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record, head

from labkit.tools import protocol_result
from labkit.checks import recheck
from labkit.formats import answering_run
from labkit.formats.scope_sha import file_digest

PID_A = "p-aaaaaaaaaaaaaaaa"
PID_B = "p-bbbbbbbbbbbbbbbb"
RUN_A = "2026-10-15T10-00-00_aaaa"
RUN_B = "2026-10-15T11-00-00_bbbb"
BODY = (
    "- **Recorded results:** <the number (run <run_id>)>\n\n"
    "## Runs\n\n- <run_id> — <what>\n\n"
)


def evaluate(rows: list[dict]) -> dict:
    return {"n_items": len(rows)}


class TwoProtocols(unittest.TestCase):
    def setUp(self) -> None:
        self.area = Path(tempfile.mkdtemp())
        (self.area / "runs").mkdir()
        self.a = self.area / "PROTOCOL-a.md"
        self.a.write_text(BODY + head(id=PID_A), encoding="utf-8")
        (self.area / "PROTOCOL-b.md").write_text(
            BODY + head(id=PID_B), encoding="utf-8"
        )
        self.out = self.area / "rows.jsonl"
        self.out.write_text('{"id": 1}\n', encoding="utf-8")
        self._run(RUN_A, PID_A, {"n_items": 1})
        self._run(RUN_B, PID_B, {"n_items": 99})

    def _run(self, run_id: str, pid: str, metrics: dict) -> None:
        r = self.area / "runs" / run_id
        r.mkdir()
        (r / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 4,
                        "run_kind": "measurement",
                        "protocol": {"id": pid, "path": "x"},
                    }
                )
            )
        )
        (r / "metrics.json").write_text(json.dumps(metrics))
        (r / "outputs.json").write_text(
            json.dumps(
                [
                    {
                        "path": str(self.out),
                        "sha256": file_digest(self.out)[:16],
                        "lines": 1,
                    }
                ]
            )
        )
        (r / "completion.json").write_text("{}")

    def test_the_run_bound_to_the_protocol_answers_not_the_newest(self):
        self.assertEqual(recheck.run_dir(self.area, self.a).name, RUN_A)
        self.assertEqual(
            answering_run.bound_answering_run(self.area, PID_A, None).run_dir,
            self.area / "runs" / RUN_A,
        )

    def test_from_run_writes_the_bound_runs_number(self):
        text, _, run_id = protocol_result.from_run(
            self.a.read_text(encoding="utf-8"), self.area
        )
        self.assertEqual(run_id, RUN_A)
        self.assertIn(f"n_items = 1 (run {RUN_A})", text)
        self.assertNotIn("99", text)

    def test_holds_passes_for_the_bound_run(self):
        text, _, _ = protocol_result.from_run(
            self.a.read_text(encoding="utf-8"), self.area
        )
        self.a.write_text(text, encoding="utf-8")
        v = recheck.holds(self.area, self.out, evaluate, self.a)
        self.assertEqual(v.run_id, RUN_A)

    def test_a_named_run_bound_elsewhere_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, self.a, RUN_B)
        self.assertIn(f"bound to {PID_B}, not to {PID_A}", str(cm.exception))

    def test_no_bound_run_names_every_exclusion(self):
        c = self.area / "PROTOCOL-c.md"
        c.write_text(BODY + head(id="p-cccccccccccccccc"), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, c)
        self.assertIn("no completed run bound to p-cccccccccccccccc", str(cm.exception))
        self.assertIn(f"{RUN_B}: bound to {PID_B}", str(cm.exception))

    def test_an_unstamped_protocol_binds_no_run(self):
        u = self.area / "PROTOCOL-u.md"
        u.write_text(BODY + head(id="<protocol-id>"), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, u)
        self.assertIn("no stamped id", str(cm.exception))

    def test_a_producer_run_without_intent_keys_is_no_answer(self):
        """The protocol registers [criterion-1]; the newest bound run reports no intent
        key — finalize skips it, and so does recheck (not: picks it)."""
        self.a.write_text(
            "- **Question:** does [criterion-1] hold?\n\n" + BODY + head(id=PID_A),
            encoding="utf-8",
        )
        self._run("2026-10-15T12-00-00_cccc", PID_A, {"criterion_1_pass": True})
        self._run("2026-10-15T13-00-00_dddd", PID_A, {"rows_written": 5})
        self.assertEqual(
            recheck.run_dir(self.area, self.a).name, "2026-10-15T12-00-00_cccc"
        )
        for r in ("2026-10-15T12-00-00_cccc",):
            (self.area / "runs" / r / "metrics.json").write_text('{"rows_written": 1}')
        with self.assertRaises(SystemExit) as cm:
            recheck.run_dir(self.area, self.a)
        self.assertIn("no bound run reports an intent key", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
