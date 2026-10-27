"""Report fields written before any run (2026-10-17, plan P step B1).

Sonnet t18 (labkit-paper area 09, v2 and v3) filled "Did" with the grid
search and the 55 labelled test molecules while `runs/` held only the
preparation. Whether the text claims a run is semantics; that it was written
while no completed run is bound and the head declares no `[result] run` is
exact — a warning, never a blocker.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import protocol_block, protocol_check  # noqa: E402
from labkit.checks import protocol_report  # noqa: E402
from protocol_fixture import run_record, PID, head  # noqa: E402
from test_protocol_check import PILOT_FIELDS  # noqa: E402

DID = "- **Did †:** Ran the 81-point grid and labelled the 55 test molecules.\n"
RESULT = "- **Conclusion:** AUC 0.83 in every task.\n"


def protocol(*lines: str, declared: str | None = None) -> str:
    """A complete pilot registration plus the Result lines under test; DECLARED
    is the run the head's `[result]` names (None: none yet)."""
    return (
        "# x\n\n"
        + head(repeat_cost="high", result=declared)
        + "\n"
        + PILOT_FIELDS
        + "".join(lines)
    )


def completed_run(area: Path) -> None:
    run = area / "runs" / "2026-10-16T13-00-00_ab12"
    run.mkdir(parents=True)
    (run / "config.json").write_text(
        json.dumps(
            run_record(
                {
                    "schema_version": 4,
                    "run_kind": "measurement",
                    "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                }
            )
        ),
        encoding="utf-8",
    )
    (run / "metrics.json").write_text(json.dumps({"c1_pass": True}), encoding="utf-8")
    (run / "completion.json").write_text(
        json.dumps({"status": "completed"}), encoding="utf-8"
    )


def before_run(text: str, area: Path) -> list[tuple[int, str]]:
    return protocol_check.written_before_run(area, text, protocol_block.head(text))


class WrittenBeforeRun(unittest.TestCase):
    def test_a_filled_report_field_without_a_run_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            found = before_run(protocol(DID, RESULT), Path(d))
            self.assertEqual([label for _, label in found], ["Did †", "Conclusion"])

    def test_a_completed_bound_run_silences_it(self):
        with tempfile.TemporaryDirectory() as d:
            completed_run(Path(d))
            self.assertEqual(before_run(protocol(DID, RESULT), Path(d)), [])

    def test_placeholders_dashes_and_na_claim_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            text = protocol(
                "- **Did †:** <what was done>\n",
                "- **Outcome †:** —\n",
                "- **Rival check †:** n/a — no rivals named\n",
            )
            self.assertEqual(before_run(text, Path(d)), [])

    def test_a_declared_run_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            named = protocol(DID, declared="2026-10-16T13-00-00_ab12")
            self.assertEqual(before_run(named, Path(d)), [])

    def test_the_check_prints_a_warning_and_does_not_block(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            p.write_text(protocol(DID), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = protocol_report.main([str(p)])
            out = buf.getvalue()
            self.assertIn("WARNING: Did † written before any run", out)
            self.assertIn("PROTOCOL-x.md --from-run <run_id>` after the run", out)
            self.assertEqual(rc, 0, out)
            # the twin: with the run, the line is gone
            completed_run(Path(d))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                protocol_report.main([str(p)])
            self.assertNotIn("written before any run", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
