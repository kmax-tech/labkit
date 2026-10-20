"""The stamped measure scripts pair every item with its answer: a shorter
answer list than the items it answers is refused, never cut to the shorter
length. `zip` without `strict=True` dropped the unanswered items silently,
and the output looked like a complete run of fewer items.

The scripts are the real stamp (`scaffold.stamp_area`), loaded as the
area's own test loads them; only the model call or the estimator is
replaced.

    .venv/bin/python -m pytest tests/test_template_pairing.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

from labkit.tools import scaffold


def _stamped(root: Path, name: str, model: bool | str) -> ModuleType:
    """`01_measure.py` of a freshly stamped area at minutes, imported."""
    area, _ = scaffold.stamp_area(root, name, cost="minutes", model=model)
    spec = importlib.util.spec_from_file_location(
        f"measure_{name}", area / "scripts" / "01_measure.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass in the script looks itself up here
    spec.loader.exec_module(module)
    return module


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


class Pairing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp())
        scaffold.stamp_lab(cls.root, "lab")
        cls.estimator = _stamped(cls.root, "est", model=False)
        cls.judge = _stamped(cls.root, "judge", model="haiku")

    def setUp(self) -> None:
        self.out = Path(tempfile.mkdtemp()) / "rows.jsonl"

    # -- the estimator: fit_predict is the author's code
    ITEMS = [
        {"id": f"p{i}", "features": [float(i)], "gold": "pos" if i % 2 else "neg"}
        for i in range(10)
    ] + [{"id": f"t{i}", "features": [float(i)], "gold": None} for i in range(2)]

    def _predicting(self, short_by: int):
        def fit_predict(cfg, fit, predict, permute, probe):
            return ["pos"] * (len(predict) - short_by)

        return mock.patch.object(self.estimator, "fit_predict", fit_predict)

    def test_estimator_refuses_fewer_predictions_than_items(self) -> None:
        m = self.estimator
        with self._predicting(short_by=1), self.assertRaises(ValueError):
            m.measure(m.CONFIG, self.ITEMS, self.out)

    def test_estimator_writes_a_row_per_item_and_lane(self) -> None:
        m = self.estimator
        with self._predicting(short_by=0):
            rows = m.measure(m.CONFIG, self.ITEMS, self.out)
        self.assertEqual(len(rows), 2 * 10 + 2)  # registered + null, then test
        self.assertEqual(_lines(self.out), 2 * 10 + 2)

    # -- the judge: one answer per prompt from llm.complete_many
    JOBS_FROM = [{"id": f"x{i}", "text": f"item {i}"} for i in range(5)]

    def _answering(self, short_by: int):
        def complete_many(model, prompts):
            return ["Yes"] * (len(prompts) - short_by)

        return mock.patch.object(self.judge.llm, "complete_many", complete_many)

    def test_judge_refuses_fewer_answers_than_prompts(self) -> None:
        m = self.judge
        jobs = m.plan(self.JOBS_FROM)
        with self._answering(short_by=1), self.assertRaises(ValueError):
            m.measure(m.CONFIG, jobs, self.out)

    def test_judge_writes_a_row_per_job(self) -> None:
        m = self.judge
        jobs = m.plan(self.JOBS_FROM)
        with self._answering(short_by=0):
            m.measure(m.CONFIG, jobs, self.out)
        rows = [json.loads(ln) for ln in self.out.read_text().splitlines()]
        self.assertEqual(sorted(r["id"] for r in rows), sorted(j["id"] for j in jobs))


if __name__ == "__main__":
    unittest.main()
