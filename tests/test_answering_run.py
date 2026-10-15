"""`runs.bound_answering_run` and `runs.model_provenance_run` — the one
choice of the run that answers, and the walk to the run that recorded the
model (2026-10-08).

    .venv/bin/python -m pytest tests/test_answering_run.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from labkit import runs

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
    cfg: dict = {
        "schema_version": 2,
        "script": "01_measure.py",
        "pid": 1,
        "protocol": {"id": pid, "path": "x.md"},
        "derived_from": derived_from,
        "models_resolved": models_resolved or {},
        "config": {},
    }
    (d / "config.json").write_text(
        config_text if config_text is not None else json.dumps(cfg), encoding="utf-8"
    )
    (d / "metrics.json").write_text(
        json.dumps({"c1_pass": True} if metrics is None else metrics), encoding="utf-8"
    )
    if completion:
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
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
        choice = runs.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, chosen)
        self.assertEqual(
            (choice.skipped_newer, choice.exclusions, choice.blocker), (0, (), None)
        )

    def test_a_newer_probe_without_intent_keys_is_skipped_and_counted(self) -> None:
        chosen = _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", metrics={"n_rows": 3})
        choice = runs.bound_answering_run(self.area, PID)
        self.assertEqual((choice.run_dir, choice.skipped_newer), (chosen, 1))

    def test_runs_bound_elsewhere_or_unfinished_are_excluded_with_a_reason(
        self,
    ) -> None:
        chosen = _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", pid="p-0002")
        _run(self.area, "2026-10-03T10-00-00_cccc", completion=False)
        choice = runs.bound_answering_run(self.area, PID)
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
        choice = runs.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)
        self.assertIn("no completed run bound to p-0001", choice.blocker or "")
        self.assertEqual(len(choice.exclusions), 1)

    def test_a_newer_unreadable_run_blocks_the_choice(self) -> None:
        """Mutant: the newer run's binding cannot be read — it may be the one
        that answers, so the older one must not answer past it."""
        _run(self.area, "2026-10-01T10-00-00_aaaa")
        _run(self.area, "2026-10-02T10-00-00_bbbb", config_text="{not json")
        choice = runs.bound_answering_run(self.area, PID)
        self.assertIsNone(choice.run_dir)  # blocked: no run_dir to take by mistake
        self.assertIn("cannot say which protocol", choice.blocker or "")

    def test_no_bound_run_with_intent_keys_is_named_not_passed_as_an_answer(
        self,
    ) -> None:
        """Mutant: every bound run is a probe — the newest is returned, but
        the choice says it reports no intent key (2026-10-09)."""
        _run(self.area, "2026-10-01T10-00-00_aaaa", metrics={"n_rows": 3})
        newest = _run(self.area, "2026-10-02T10-00-00_bbbb", metrics={"n_rows": 4})
        choice = runs.bound_answering_run(self.area, PID)
        self.assertEqual(choice.run_dir, newest)
        self.assertFalse(choice.reports_intent_keys)
        self.assertEqual(choice.skipped_newer, 0)

    def test_no_runs_directory(self) -> None:
        choice = runs.bound_answering_run(self.area / "nowhere", PID)
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
        self.assertEqual(runs.model_provenance_run(fresh), fresh)

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
        found = runs.model_provenance_run(child)
        self.assertEqual(found, parent)
        assert found is not None
        cfg = runs.read_run_config(found) or {}
        self.assertEqual(cfg["models_resolved"], {"m": {"model": "A"}})

    def test_a_chain_without_any_model_record_is_none(self) -> None:
        parent = _run(self.area, "2026-10-01T10-00-00_aaaa")
        child = _run(self.area, "2026-10-02T10-00-00_bbbb", derived_from=parent.name)
        self.assertIsNone(runs.model_provenance_run(child))

    def test_a_missing_ancestor_is_loud(self) -> None:
        child = _run(
            self.area,
            "2026-10-02T10-00-00_bbbb",
            derived_from="2026-10-01T10-00-00_gone",
        )
        with self.assertRaisesRegex(ValueError, "not under"):
            runs.model_provenance_run(child)

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
            runs.model_provenance_run(b)


if __name__ == "__main__":
    unittest.main()


class Explain(unittest.TestCase):
    """`AnsweringRun.explain` is the one telling of the choice: finalize,
    intent-check, recheck, params and the audit rendered it four ways with
    four semantics (audit 2026-10-15)."""

    def test_no_run_blocker_and_exclusions(self):
        choice = runs.AnsweringRun(
            None,
            0,
            (runs.RunExclusion(Path("r/x"), "bound to p-b"),),
            "no completed run bound to p-a",
        )
        self.assertEqual(
            choice.explain(True), ("no completed run bound to p-a", ["x: bound to p-b"])
        )

    def test_a_probe_run_blocks_only_when_ids_are_registered(self):
        choice = runs.AnsweringRun(Path("r/x"), 0, (), None, reports_intent_keys=False)
        blocker, lines = choice.explain(True)
        self.assertIn("probe or producer run", blocker or "")
        self.assertEqual(choice.explain(False), (None, []))  # a count registers no id

    def test_skipped_runs_are_said(self):
        choice = runs.AnsweringRun(Path("r/x"), 2, (), None)
        self.assertEqual(
            choice.explain(True),
            (None, ["skipped 2 newer bound run(s) without intent keys"]),
        )
