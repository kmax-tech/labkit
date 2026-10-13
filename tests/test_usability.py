"""usability (2026-10-05): the fixture has the answer it claims, the log
parser counts what the contract names and nothing twice, and the score
is an identity on the named key of the bound run."""

from __future__ import annotations

import contextlib
import io
import json
import os
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


class LoadProbeRun(unittest.TestCase):
    """One loader for the probe and its latest run (score and the reading probes)."""

    def test_a_bound_run_names_its_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "probe"
            root.mkdir()
            _probe(root, {"mean_docs_per_case": 3.5}, tier="minutes")
            pr = usability.load_probe_run(root)
            self.assertTrue(pr.bound)
            self.assertEqual(pr.protocol, pr.area / "PROTOCOL-docs-per-case.md")
            self.assertEqual(pr.protocol_as_recorded, "PROTOCOL-docs-per-case.md")
            self.assertEqual(pr.cost_tier, "minutes")

    def test_a_path_without_an_id_is_not_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "probe"
            root.mkdir()
            _probe(root, {"mean_docs_per_case": 3.5})
            cfg = next(root.glob("experiments/*/runs/*/config.json"))
            data = json.loads(cfg.read_text())
            del data["protocol"]["id"]
            cfg.write_text(json.dumps(data))
            pr = usability.load_probe_run(root)
            self.assertFalse(pr.bound)
            self.assertIsNotNone(pr.protocol)

    def test_an_unstaged_dir_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                usability.load_probe_run(Path(tmp) / "nothing")


class ScoreVerdict(unittest.TestCase):
    def _score(self, metrics: dict, agent: str | None = None) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "probe"
            root.mkdir()
            usability.plant_fixture(root)
            _probe(root, metrics)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = usability.score(root, agent=agent)
            return rc, json.loads(usability._sidecar(root, "score.json").read_text())

    def test_the_score_carries_the_agent_the_operator_names(self):
        _, sc = self._score({"mean_docs_per_case": 3.5}, agent="fable-5.1")
        self.assertEqual(sc["agent"], "fable-5.1")
        _, sc = self._score({"mean_docs_per_case": 3.5})
        self.assertIsNone(sc["agent"])  # not guessed: a cloud draw leaves no transcript

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


class Archive(unittest.TestCase):
    """A probe is kept for debugging: transcript, timeline, score — and a
    second archive of other bytes under the same name is refused."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "count-1"
        self.root.mkdir()
        (base / "count-1.score.json").write_text('{"number": 3.5}')
        self.transcript = base / "agent.jsonl"
        self.transcript.write_text(
            json.dumps(
                {"type": "user", "timestamp": "2026-10-07T14:00:00Z", "message": {}}
            )
            + "\n"
        )
        self.dest = base / "traces"

    def test_three_files_and_a_rerun_changes_nothing(self):
        import gzip

        written = usability.archive(self.root, self.transcript, self.dest)
        self.assertEqual(
            sorted(p.name for p in written),
            ["count-1.jsonl.gz", "count-1.score.json", "count-1.timeline.txt"],
        )
        self.assertEqual(
            gzip.decompress((self.dest / "count-1.jsonl.gz").read_bytes()),
            self.transcript.read_bytes(),
        )
        usability.archive(self.root, self.transcript, self.dest)  # same bytes: fine

    def test_other_bytes_under_the_same_name_are_refused(self):
        usability.archive(self.root, self.transcript, self.dest)
        (self.root.parent / "count-1.score.json").write_text('{"number": 4.0}')
        with self.assertRaises(SystemExit):
            usability.archive(self.root, self.transcript, self.dest)


class RestampLaysTheStampOverTheProbe(unittest.TestCase):
    """`stage --restamp` (2026-10-13): a changed stamped file is overwritten,
    a new one added, an equal one untouched, a kept hand edit left alone; a
    kept path the stamp does not produce is refused, not silently ignored."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fresh, self.probe = base / "fresh", base / "probe"
        for rel, text in (
            ("AGENTS.md", "new agents\n"),
            ("TASK.md", "stamped task\n"),
            ("same.txt", "same\n"),
            ("experiments/01/new.py", "added\n"),
        ):
            (self.fresh / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.fresh / rel).write_text(text)
        (self.fresh / "CLAUDE.md").symlink_to("AGENTS.md")
        self.probe.mkdir()
        (self.probe / "AGENTS.md").write_text("old agents\n")
        (self.probe / "TASK.md").write_text("hand-edited task\n")
        (self.probe / "same.txt").write_text("same\n")
        (self.probe / "log.md").write_text("the agent's own file\n")
        self.files = [
            "AGENTS.md",
            "CLAUDE.md",
            "TASK.md",
            "same.txt",
            "experiments/01/new.py",
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_overwritten_added_kept_unchanged(self):
        done = usability.restamp_files(self.fresh, self.probe, self.files, ["TASK.md"])
        self.assertEqual(done.overwritten, ["AGENTS.md"])
        self.assertEqual(done.added, ["CLAUDE.md", "experiments/01/new.py"])
        self.assertEqual(done.kept, ["TASK.md"])
        self.assertEqual(done.unchanged, ["same.txt"])
        self.assertEqual((self.probe / "AGENTS.md").read_text(), "new agents\n")
        self.assertEqual((self.probe / "TASK.md").read_text(), "hand-edited task\n")
        self.assertEqual((self.probe / "experiments/01/new.py").read_text(), "added\n")
        self.assertEqual(os.readlink(self.probe / "CLAUDE.md"), "AGENTS.md")
        self.assertEqual((self.probe / "log.md").read_text(), "the agent's own file\n")

    def test_a_kept_path_that_equals_the_stamp_is_unchanged_not_kept(self):
        done = usability.restamp_files(self.fresh, self.probe, self.files, ["same.txt"])
        self.assertEqual(done.kept, [])
        self.assertIn("same.txt", done.unchanged)

    def test_a_second_pass_changes_nothing(self):
        usability.restamp_files(self.fresh, self.probe, self.files, ["TASK.md"])
        done = usability.restamp_files(self.fresh, self.probe, self.files, ["TASK.md"])
        self.assertEqual((done.overwritten, done.added), ([], []))
        self.assertEqual(done.kept, ["TASK.md"])

    def test_a_kept_path_the_stamp_does_not_produce_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            usability.restamp_files(self.fresh, self.probe, self.files, ["TASKS.md"])
        self.assertIn("TASKS.md", str(cm.exception))
        self.assertEqual((self.probe / "AGENTS.md").read_text(), "old agents\n")


class LogStepWritesBeforeItRuns(unittest.TestCase):
    """`usability log` (2026-10-13): one line with the time, then the command,
    whose exit code it returns; a tag outside the contract is refused."""

    def test_line_then_command_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log.md"
            rc = usability.log_step(
                log, "run", "the count", [sys.executable, "-c", "raise SystemExit(3)"]
            )
            self.assertEqual(rc, 3)
            self.assertEqual(usability.log_step(log, "read", "TASK.md", []), 0)
            lines = log.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertRegex(lines[0], r"^\d\d:\d\d:\d\d · run · the count$")
            self.assertRegex(lines[1], r"^\d\d:\d\d:\d\d · read · TASK\.md$")

    def test_a_foreign_tag_or_empty_text_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log.md"
            with self.assertRaises(SystemExit):
                usability.log_step(log, "note", "x", [])
            with self.assertRaises(SystemExit):
                usability.log_step(log, "run", "  ", [])
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()


class SourceReadsCountTheStandard(unittest.TestCase):
    """A read of the packaged standard counts like a read of labkit's source;
    a read of the area's own files does not (the metric: did the README card suffice?)."""

    def test_the_packaged_standard_and_a_rules_lookup_count(self) -> None:
        log = (
            "18:00:00 · read · labkit/docs/standard.md (LAB-015)\n"
            "18:00:10 · run · python -m labkit.rules show LAB-015\n"
            "18:00:20 · read · python -m labkit.rules show LAB-017\n"
            "18:00:30 · read · experiments/01-x/README.md\n"
        )
        self.assertEqual(usability.parse_log(log).source_reads, 2)


class OtherRequirements(unittest.TestCase):
    def test_every_line_but_labkit_and_comments(self):
        text = "# pinned\nlabkit @ git+https://x/labkit.git@v0.86.0\n\n# tests\npytest\nmarimo\n"
        self.assertEqual(usability.other_requirements(text), ["pytest", "marimo"])
        self.assertEqual(usability.other_requirements("labkit==1.0\n"), [])
