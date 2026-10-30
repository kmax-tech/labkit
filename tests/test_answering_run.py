"""`answering_run.bound_answering_run` and `answering_run.model_provenance_run` — the one
choice of the run that answers, and the walk to the run that recorded the
model (2026-10-08).

    .venv/bin/python -m pytest tests/test_answering_run.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record  # noqa: E402
from labkit.formats import runs, answering_run

PID = "p-0001"


def _run(
    area: Path,
    name: str,
    *,
    pid: str | None = PID,
    metrics: dict | None = None,
    completion: bool = True,
    config_text: str | None = None,
    models_resolved: dict | None = None,
    derived_from: str | None = None,
) -> Path:
    d = area / "runs" / name
    d.mkdir(parents=True)
    cfg = run_record(
        protocol={"id": pid, "path": "x.md"},
        derived_from=derived_from,
        models_resolved=models_resolved or {},
    )
    (d / "config.json").write_text(
        config_text if config_text is not None else json.dumps(cfg), encoding="utf-8"
    )
    (d / "metrics.json").write_text(
        json.dumps({"criterion_1_pass": True} if metrics is None else metrics),
        encoding="utf-8",
    )
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "run_kind": "measurement",
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
    return d


class AnsweringRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_newest_bound_completed_run_with_intent_keys_answers(self) -> None:
        """Twin: a clean area — no blocker, nothing excluded."""
        _run(self.area, "2026-10-01T10-00-00_aaaa")
        chosen = _run(self.area, "2026-10-02T10-00-00_bbbb")
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, chosen)
        self.assertEqual(
            (choice.skipped_newer, choice.exclusions, choice.blocker), (0, (), None)
        )

    def test_a_newer_probe_without_intent_keys_is_skipped_and_counted(self) -> None:
        chosen = _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", metrics={"n_rows": 3})
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual((choice.run_dir, choice.skipped_newer), (chosen, 1))

    def test_runs_bound_elsewhere_or_unfinished_are_excluded_with_a_reason(
        self,
    ) -> None:
        chosen = _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", pid="p-0002")
        _run(self.area, "2026-10-03T10-00-00_cccc", completion=False)
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, chosen)
        self.assertEqual(
            {x.run_dir.name: x.why for x in choice.exclusions},
            {
                "2026-10-02T10-00-00_bbbb": "bound to p-0002",
                "2026-10-03T10-00-00_cccc": "unfinalized",
            },
        )
        self.assertIsNone(choice.blocker)

    def test_no_bound_run_is_a_blocker_not_a_guess(self) -> None:
        _run(self.area, "2026-10-01T10-00-00_aaaa", pid="p-0002")
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)
        self.assertIn("no completed run bound to p-0001", choice.blocker or "")
        self.assertIn(
            "scripts/01_measure.py` opens a run bound to p-0001", choice.way_out or ""
        )
        self.assertEqual(len(choice.exclusions), 1)

    def test_a_newer_unreadable_run_blocks_the_choice(self) -> None:
        """Mutant: the newer run's binding cannot be read — it may be the one
        that answers, so the older one must not answer past it."""
        _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", config_text="{not json")
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)  # blocked: no run_dir to take by mistake
        self.assertIn("cannot say which protocol", choice.blocker or "")
        self.assertIn("repair or move them aside", choice.way_out or "")

    def test_no_bound_run_with_intent_keys_is_named_not_passed_as_an_answer(
        self,
    ) -> None:
        """Mutant: every bound run is a probe — the newest is returned, but
        the choice says it reports no intent key (2026-10-09)."""
        _run(self.area, "2026-10-01T10-00-00_aaaa", metrics={"n_rows": 3})
        newest = _run(self.area, "2026-10-02T10-00-00_bbbb", metrics={"n_rows": 4})
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, newest)
        self.assertFalse(choice.reports_intent_keys)
        self.assertEqual(choice.skipped_newer, 0)

    def test_two_answers_started_in_one_second_block_the_choice(self) -> None:
        """Mutant: the run id carries the start second and a random suffix, so
        two runs started in one second sort by chance — `_0000` may have
        started after `_ffff`. Neither may answer by being "newest"."""
        _run(self.area, "2026-10-01T10-00-00_ffff")
        _run(self.area, "2026-10-01T10-00-00_0000")
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)
        self.assertIn("started in the same second", choice.blocker or "")
        self.assertIn("move the one that does not answer", choice.way_out or "")

    def test_a_probe_in_the_same_second_does_not_block(self) -> None:
        """Twin: only one of the two reports an intent key — it answers
        whichever started first."""
        chosen = _run(self.area, "2026-10-01T10-00-00_0000")
        _run(self.area, "2026-10-01T10-00-00_ffff", metrics={"n_rows": 3})
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, chosen)
        self.assertIsNone(choice.blocker)

    def test_an_unreadable_run_in_the_same_second_blocks(self) -> None:
        """Mutant: the unreadable run sorts before the bound one by suffix,
        but may have started after it."""
        _run(self.area, "2026-10-01T10-00-00_0000", config_text="{not json")
        _run(self.area, "2026-10-01T10-00-00_ffff")
        choice = answering_run.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)
        self.assertIn("cannot say which protocol", choice.blocker or "")

    def test_no_runs_directory(self) -> None:
        choice = answering_run.bound_answering_run(self.area / "nowhere", PID)
        self.assertIsNone(choice.run_dir)
        self.assertIn("no runs/ directory", choice.blocker or "")


class ModelProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_fresh_run_is_its_own_provenance(self) -> None:
        fresh = _run(
            self.area, "2026-10-01T10-00-00_aaaa", models_resolved={"m": {"model": "A"}}
        )
        self.assertEqual(answering_run.model_provenance_run(fresh), fresh)

    def test_a_derived_run_points_to_the_ancestor_that_recorded_the_model(self) -> None:
        """Parent resolved alias m to A; the chain of derived runs recorded
        nothing (models.toml may now say B) — the answer is the parent and A."""
        parent = _run(
            self.area, "2026-10-01T10-00-00_aaaa", models_resolved={"m": {"model": "A"}}
        )
        _run(self.area, "2026-10-02T10-00-00_bbbb", derived_from=parent.name)
        child = _run(
            self.area,
            "2026-10-03T10-00-00_cccc",
            derived_from="2026-10-02T10-00-00_bbbb",
        )
        found = answering_run.model_provenance_run(child)
        self.assertEqual(found, parent)
        assert found is not None
        cfg = runs.read_run_config(found)
        assert cfg is not None
        self.assertEqual(cfg.models_resolved, {"m": {"model": "A"}})

    def test_a_chain_without_any_model_record_is_none(self) -> None:
        parent = _run(self.area, "2026-10-01T10-00-00_aaaa")
        child = _run(self.area, "2026-10-02T10-00-00_bbbb", derived_from=parent.name)
        self.assertIsNone(answering_run.model_provenance_run(child))

    def test_a_missing_ancestor_is_loud(self) -> None:
        child = _run(
            self.area,
            "2026-10-02T10-00-00_bbbb",
            derived_from="2026-10-01T10-00-00_dead",
        )
        with self.assertRaisesRegex(ValueError, "not under"):
            answering_run.model_provenance_run(child)

    def test_a_loop_is_loud(self) -> None:
        _run(
            self.area,
            "2026-10-01T10-00-00_aaaa",
            derived_from="2026-10-02T10-00-00_bbbb",
        )
        b = _run(
            self.area,
            "2026-10-02T10-00-00_bbbb",
            derived_from="2026-10-01T10-00-00_aaaa",
        )
        with self.assertRaisesRegex(ValueError, "loops"):
            answering_run.model_provenance_run(b)


if __name__ == "__main__":
    unittest.main()


class Explain(unittest.TestCase):
    """`AnsweringRun.explain` is the one telling of the choice: finalize,
    intent-check, recheck, params and the audit rendered it four ways with
    four semantics (audit 2026-10-15)."""

    def test_no_run_blocker_and_exclusions(self):
        choice = answering_run.AnsweringRun(
            None,
            0,
            (answering_run.RunExclusion(Path("r/x"), "bound to p-b"),),
            "no completed run bound to p-a",
            way_out="measure",
        )
        blocker, lines = choice.explain(True)
        assert blocker is not None
        self.assertEqual(
            (blocker.grade, blocker.text, blocker.fix, lines),
            (
                "BLOCKER",
                "no completed run bound to p-a",
                "measure",
                ["x: bound to p-b"],
            ),
        )

    def test_a_probe_run_blocks_only_when_ids_are_registered(self):
        choice = answering_run.AnsweringRun(
            Path("r/x"), 0, (), None, reports_intent_keys=False
        )
        blocker, lines = choice.explain(True)
        assert blocker is not None
        self.assertIn("probe or producer run", blocker.text)
        self.assertIn("scripts/01_measure.py", blocker.fix or "")
        self.assertEqual(
            choice.explain(False), (None, [])
        )  # a computation registers no id

    def test_skipped_runs_are_said(self):
        choice = answering_run.AnsweringRun(Path("r/x"), 2, (), None)
        self.assertEqual(
            choice.explain(True),
            (None, ["skipped 2 newer bound run(s) without intent keys"]),
        )


class NewestCompleted(unittest.TestCase):
    """`answering_run.newest_completed` is the one reading of "the newest run" for the
    scorer and runlog's last-finished line; a tie in the start second is
    refused there, by the same rule the answering choice uses
    (`answering_run.same_second`) — the scorer compared seconds itself (0.97.0)."""

    def _run(self, area: Path, name: str) -> Path:
        d = area / "runs" / name
        d.mkdir(parents=True)
        (d / "config.json").write_text(
            json.dumps(run_record({"schema_version": 4, "run_kind": "measurement"}))
        )
        (d / "metrics.json").write_text("{}")
        (d / "completion.json").write_text("{}")
        return d

    def test_the_newest_or_none(self):
        area = Path(tempfile.mkdtemp())
        self.assertIsNone(answering_run.newest_completed(area, with_repeats=True))
        self._run(area, "2026-10-15T10-00-00_aaaa")
        b = self._run(area, "2026-10-15T10-00-01_bbbb")
        self.assertEqual(answering_run.newest_completed(area, with_repeats=True), b)

    def test_two_newest_in_one_second_are_refused(self):
        area = Path(tempfile.mkdtemp())
        self._run(area, "2026-10-15T10-00-00_aaaa")
        self._run(area, "2026-10-15T10-00-00_bbbb")
        with self.assertRaises(runs.RunConfigError) as cm:
            answering_run.newest_completed(area, with_repeats=True)
        self.assertIn("started in the same second", str(cm.exception))
        self.assertTrue(
            answering_run.same_second(
                Path("2026-10-15T10-00-00_aaaa"), Path("2026-10-15T10-00-00_bbbb")
            )
        )
        self.assertFalse(
            answering_run.same_second(Path("x_aaaa"), Path("x_aaaa"))
        )  # itself
