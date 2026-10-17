"""`finalize --write-back`: the post-run lane in one command (2026-10-17, plan P: write-back, row E).

The gate first and read-only; a blocker there writes nothing. Then the
number into the protocol, the area's --check under the repo's interpreter,
protocol-check on the written protocol — each step stops the lane. Evidence:
every one of nine pilot attempts (labkit-paper 09, 2026-10-16) stopped
somewhere inside the five commands this replaces.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import finalize  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head  # noqa: E402
from test_finalize import CLEAN_METRICS, _run  # noqa: E402
from test_protocol_check import PILOT_FIELDS  # noqa: E402

RUN = "2026-10-16T13-10-11_99d9"
#: the Summary for a person: Limits and Next step are owed after a documented
#: run (protocol-check's "after" fields) — the person writes them, write-back
#: writes the number
SUMMARY = """\
## Summary (after the run, for a person)

- **Result:** <the answer to the question above, in at most two plain sentences…>
- **Limits:** one seed, one split
- **Next step:** none planned

"""
RESULT_LINES = """\
## Result (after the run — write back, don't go quiet)

- **Answer to the question:** <per registered id its verdict, and the run_id…>
- **Answering run:** none yet — the run `finalize` holds this protocol to
- **Raw output:** one real prompt+answer pair, see output/

## Runs (documented runs — via `runlog`, cite run_ids instead of retyping numbers)

- <run_id> — <one sentence: what this run was>

"""


def area_with(
    check_exit: int | None = 0, run: bool = True, summary: str = SUMMARY
) -> Path:
    """A lab-shaped area: a clean pilot protocol with the Result lines and the
    promise block, a completed run bound to it that reports the intent keys
    (test_finalize's `_run`), and a 02_analyze.py whose --check exits
    CHECK_EXIT (None: no script)."""
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    area = repo / "experiments" / "01-x"
    (area / "scripts").mkdir(parents=True)
    (area / "PROTOCOL-x.md").write_text(
        "# Experiment protocol: x\n\n"
        + summary
        + RESULT_LINES
        + PILOT_FIELDS
        + "\n"
        + head(cost="minutes", promises=DEFAULT_BLOCK),
        encoding="utf-8",
    )
    if check_exit is not None:
        (area / "scripts" / "02_analyze.py").write_text(
            f"import sys\nsys.exit({check_exit} if '--check' in sys.argv else 0)\n",
            encoding="utf-8",
        )
    if run:
        _run(area, RUN, metrics=CLEAN_METRICS)
    return area


def run_write_back(area: Path, *extra: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = finalize.main([str(area), "--write-back", *extra])
    return rc, buf.getvalue()


def protocol_text(area: Path) -> str:
    return (area / "PROTOCOL-x.md").read_text(encoding="utf-8")


class WriteBack(unittest.TestCase):
    def test_the_lane_in_one_command(self):
        area = area_with()
        rc, out = run_write_back(area)
        text = protocol_text(area)
        self.assertEqual(rc, 0, out)
        self.assertIn(
            f"c1_pass = True, a1_pass = True, a2_pass = True (run {RUN})", text
        )
        self.assertIn(f"- {RUN} — the kept run", text)
        self.assertIn("02_analyze.py --check passes", out)
        self.assertIn("write-back: done", out)
        # the second call writes nothing and still passes
        rc, out = run_write_back(area)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"already written: the answer cites run {RUN}", out)
        self.assertEqual(text, protocol_text(area))

    def test_what_the_person_still_owes_is_named_after_the_write(self):
        """Limits and Next step are owed after a documented run; write-back
        writes the number, and protocol-check names the rest — exit 1 with
        the number safely in the protocol."""
        area = area_with(summary=SUMMARY.split("- **Limits:**")[0])
        rc, out = run_write_back(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("02_analyze.py --check passes", out)
        self.assertIn("Limits", out)
        self.assertIn(f"(run {RUN})", protocol_text(area))

    def test_a_blocker_in_the_gate_writes_nothing(self):
        area = area_with(run=False)
        before = protocol_text(area)
        rc, out = run_write_back(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("nothing is written", out)
        self.assertEqual(before, protocol_text(area))

    def test_a_failing_check_stops_after_the_write(self):
        area = area_with(check_exit=3)
        rc, out = run_write_back(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("02_analyze.py --check exits 3", out)
        self.assertIn(f"(run {RUN})", protocol_text(area))

    def test_no_check_script_is_a_blocker(self):
        area = area_with(check_exit=None)
        rc, out = run_write_back(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("the check that holds the note to the run is owed", out)

    def test_a_named_run_must_be_bound_and_completed(self):
        area = area_with()
        rc, out = run_write_back(area, "--run", "2026-10-16T09-00-00_ffff")
        self.assertEqual(rc, 1, out)
        rc, out = run_write_back(area, "--run", RUN)
        self.assertEqual(rc, 0, out)

    def test_run_without_write_back_is_refused(self):
        area = area_with()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = finalize.main([str(area), "--run", RUN])
        self.assertEqual(rc, 2)
        self.assertIn("--run goes with --write-back", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
