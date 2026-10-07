"""usability (2026-10-05): the fixture has the answer it claims, the log
parser counts what the contract names and nothing twice, and the score
is an identity on the named key of the bound run."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import usability  # noqa: E402
from protocol_fixture import head  # noqa: E402

LOG = """\
18:12:32 · read · CLAUDE.md
18:12:40 · read · PROTOCOL
18:12:50 · read · labkit/runlog.py (freeze gate)
18:13:03 · unsure · short form or long form?
18:13:30 · edit · 01_measure.py
18:14:00 · run · 01_measure.py --show 3
18:14:20 · gate · pre-run hook: preflight blockers
some line without the contract
18:14:40 · foo · a tag outside the contract
18:15:02 · run · 01_measure.py
"""


class Fixture(unittest.TestCase):
    def test_truth_is_recounted_from_the_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(usability.plant_fixture(root), 3.5)
            rows = (root / "data/raw/cases.jsonl").read_text().splitlines()
            self.assertEqual(len(rows), 12)
            self.assertEqual(usability.recount(root), 3.5)


class LogParser(unittest.TestCase):
    def test_counts_wall_clock_and_no_double_count(self):
        got = usability.parse_log(LOG)
        self.assertEqual(got.wall_seconds, 150)
        self.assertEqual(
            (got.read, got.run, got.edit, got.unsure, got.gate), (3, 2, 1, 1, 1)
        )
        self.assertEqual(got.source_reads, 1)
        self.assertEqual(got.untagged, 2)
        self.assertEqual(got.lines, 10)
        self.assertTrue(got.monotonic)

    def test_a_long_silence_is_reported_beside_the_span(self):
        got = usability.parse_log(
            "18:00:00 · read · a\n18:01:00 · run · b\n"
            "18:31:00 · run · c\n18:32:00 · edit · d\n"
        )
        self.assertEqual(got.wall_seconds, 1920)
        self.assertEqual(got.gap_seconds, 1800)

    def test_one_line_has_no_wall_clock(self):
        self.assertIsNone(usability.parse_log("18:00:00 · read · x\n").wall_seconds)

    def test_backwards_stamps_are_flagged_not_wrapped(self):
        got = usability.parse_log("18:00:00 · read · a\n17:00:00 · run · b\n")
        self.assertFalse(got.monotonic)
        self.assertEqual(got.wall_seconds, 3600)


def _probe(
    root: Path, metrics: dict, frozen: bool = False, tier: str = "seconds"
) -> None:
    area = root / "experiments" / "01-docs-per-case"
    run = area / "runs" / "2026-10-05T18-00-00_ab12"
    run.mkdir(parents=True)
    (area / "PROTOCOL-docs-per-case.md").write_text(
        head(cost=tier, frozen=frozen), encoding="utf-8"
    )
    (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (run / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "protocol": {
                    "id": "p-0123456789abcdef",
                    "path": "PROTOCOL-docs-per-case.md",
                },
                "cost_tier": tier,
            }
        ),
        encoding="utf-8",
    )
    (run / "completion.json").write_text("{}", encoding="utf-8")
    usability._sidecar(root, "probe.json").write_text(
        json.dumps(
            {
                "staged": "2026-10-05T17:59:00",
                "task": "count",
                "area": "01-docs-per-case",
                "metric_key": "mean_docs_per_case",
                "labkit_installed": "labkit @ x",
                "scaffold_sha": "abc",
                "scaffold_flags": [],
                "target_minutes": 5,
            }
        ),
        encoding="utf-8",
    )
    usability._sidecar(root, "log.md").write_text(LOG, encoding="utf-8")


class ScoreVerdict(unittest.TestCase):
    def _score(self, metrics: dict) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "probe"
            root.mkdir()
            usability.plant_fixture(root)
            _probe(root, metrics)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = usability.score(root)
            return rc, json.loads(usability._sidecar(root, "score.json").read_text())

    def test_right_number_under_the_named_key(self):
        rc, sc = self._score({"mean_docs_per_case": 3.5, "n_cases": 12})
        self.assertEqual(rc, 0)
        self.assertTrue(sc["number_ok"])
        self.assertEqual(sc["bound_to"], "PROTOCOL-docs-per-case.md")
        self.assertFalse(sc["frozen"])
        self.assertEqual(sc["cost_tier"], "seconds")
        self.assertEqual(sc["log"]["wall_seconds"], 150)

    def test_right_number_under_another_key_does_not_count(self):
        rc, sc = self._score({"mean": 3.5})
        self.assertEqual(rc, 1)
        self.assertIsNone(sc["number"])

    def test_wrong_number(self):
        rc, sc = self._score({"mean_docs_per_case": 3.3333})
        self.assertEqual(rc, 1)
        self.assertFalse(sc["number_ok"])


class StampFlags(unittest.TestCase):
    """The probe stamps each task as the house route does (probe 2026-10-07:
    staged without --cost the count got the model skeleton)."""

    def test_count_gets_the_seconds_cut_without_a_model(self):
        self.assertEqual(
            usability.stamp_flags("count", None, False), ("seconds", False)
        )

    def test_judge_gets_the_seconds_cut_with_a_model(self):
        self.assertEqual(usability.stamp_flags("judge", None, False), ("seconds", True))

    def test_an_explicit_tier_wins_and_unset_stamps_none(self):
        self.assertEqual(
            usability.stamp_flags("count", "hours", False), ("hours", False)
        )
        self.assertEqual(usability.stamp_flags("count", "unset", False), (None, False))


class AgentPrompt(unittest.TestCase):
    """The agent gets CLAUDE.md the way a session loads it, not a pointer it
    must `cat` (re-measure 2026-10-07: every agent read all of it by tool)."""

    def test_claude_md_comes_first_then_the_task_pointer(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "CLAUDE.md").write_text("# CLAUDE.md — probe\n\nrule one\n")
            prompt = usability.agent_prompt(root)
        self.assertTrue(prompt.startswith(f"Contents of {root / 'CLAUDE.md'}"))
        self.assertLess(prompt.index("rule one"), prompt.index("Read TASK.md"))

    def test_a_repo_without_claude_md_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                usability.agent_prompt(Path(d))


if __name__ == "__main__":
    unittest.main()
