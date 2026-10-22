"""The stamped measure scripts account for every item of their source.

Pairing: a shorter answer list than the items it answers is refused, never
cut to the shorter length — `zip` without `strict=True` dropped the
unanswered items, and the output looked like a complete run of fewer items.

Balance: before a number, the kept rows are held to the source (`balance`,
`batch.Ledger`) — a missing, doubled or stray row, or one made from an
item as it was before an edit, stops the evaluation; the complete,
unchanged file passes. Counted from rows alone, six of twelve items could
be missing and every check of the stamp still passed (review 2026-10-20).

The scripts are the real stamp (`scaffold.stamp_area`), loaded as the
area's own test loads them; only the model call or the estimator is
replaced.

    .venv/bin/python -m pytest tests/test_template_items.py
"""

from __future__ import annotations

import functools
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
    area, _ = scaffold.stamp_area(
        root, name, cost="minutes", kind="apply" if model else "fit", model=model
    )
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


@functools.cache
def _lab() -> tuple[ModuleType, ModuleType]:
    """(estimator, judge): `01_measure.py` of two areas of one stamped lab."""
    root = Path(tempfile.mkdtemp())
    scaffold.stamp_lab(root, "lab")
    return _stamped(root, "est", model=False), _stamped(root, "judge", model="haiku")


class Pairing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.estimator, cls.judge = _lab()

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

    def test_estimator_refuses_fewer_or_more_predictions_than_items(self) -> None:
        m = self.estimator
        for short_by in (1, -1):
            with self.subTest(short_by=short_by):
                with self._predicting(short_by), self.assertRaises(ValueError):
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

        return mock.patch.object(self.judge.lanes.llm, "complete_many", complete_many)

    def test_judge_refuses_fewer_or_more_answers_than_prompts(self) -> None:
        m = self.judge
        jobs = m.plan(self.JOBS_FROM)
        for short_by in (1, -1):
            with self.subTest(short_by=short_by):
                with self._answering(short_by), self.assertRaises(ValueError):
                    m.measure(m.CONFIG, jobs, self.out)

    def test_judge_writes_a_row_per_job(self) -> None:
        m = self.judge
        jobs = m.plan(self.JOBS_FROM)
        with self._answering(short_by=0):
            m.measure(m.CONFIG, jobs, self.out)
        rows = [json.loads(ln) for ln in self.out.read_text().splitlines()]
        self.assertEqual(sorted(r["id"] for r in rows), sorted(j["id"] for j in jobs))


def _edit_rows(path: Path, edit) -> None:
    """Rewrite the output file through EDIT(rows) -> rows."""
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    path.write_text("".join(json.dumps(r) + "\n" for r in edit(rows)), encoding="utf-8")


#: the three ways a file stops matching its source, applied to a complete one
GAPS = {
    "missing": lambda rows: rows[1:],
    "duplicate": lambda rows: rows + rows[:1],
    "stray": lambda rows: rows + [{**rows[0], "id": "registered:ghost"}],
}


class Balance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.estimator, cls.judge = _lab()

    def setUp(self) -> None:
        self.out = Path(tempfile.mkdtemp()) / "rows.jsonl"

    # -- the judge: a fingerprint per item, since each call stands alone
    def _items(self) -> list[dict]:
        golds = list(self.judge.ANSWERS.values())
        return [
            {"id": f"x{i}", "text": f"item {i}", "gold": golds[i % 2]} for i in range(6)
        ]

    def _judged(self, items: list[dict]) -> list[dict]:
        m = self.judge
        jobs = m.plan(items)
        answer = lambda model, prompts: ["Yes"] * len(prompts)  # noqa: E731
        with mock.patch.object(m.lanes.llm, "complete_many", answer):
            m.measure(m.CONFIG, jobs, self.out)
        return jobs

    def test_judge_evaluates_the_complete_unchanged_file(self) -> None:
        m = self.judge
        jobs = self._judged(self._items())
        metrics = m.evaluate(self.out, m.CONFIG, jobs)
        self.assertEqual(metrics["n_items"], 6)

    def test_judge_refuses_a_missing_doubled_or_stray_row(self) -> None:
        m = self.judge
        for gap, edit in GAPS.items():
            with self.subTest(gap=gap):
                self.out = Path(tempfile.mkdtemp()) / "rows.jsonl"
                jobs = self._judged(self._items())
                _edit_rows(self.out, edit)
                with self.assertRaises(SystemExit) as cm:
                    m.evaluate(self.out, m.CONFIG, jobs)
                self.assertIn(gap, str(cm.exception))

    def test_judge_refuses_a_row_made_from_the_item_before_its_edit(self) -> None:
        """The resume skips the id it has; the ledger sees the old fingerprint."""
        m = self.judge
        items = self._items()
        self._judged(items)
        items[0] = {**items[0], "text": "item 0, corrected"}
        jobs = self._judged(items)
        with self.assertRaises(SystemExit) as cm:
            m.evaluate(self.out, m.CONFIG, jobs)
        self.assertIn("item_sha", str(cm.exception))

    def test_judge_probe_shows_the_answer_to_the_item_as_it_is_now(self) -> None:
        """The probe resumed its file: an item edited since the last probe
        made no new call and showed the old answer (review 2026-10-20)."""
        m = self.judge
        answer = lambda model, prompts: [  # noqa: E731
            "Yes" if "corrected" in p else "No" for p in prompts
        ]
        items = self._items()
        with mock.patch.object(m.lanes.llm, "complete_many", answer):
            first = m.probe(m.CONFIG, items, 2)
            items[0] = {**items[0], "text": "item 0, corrected"}
            again = m.probe(m.CONFIG, items, 2)
        x0 = lambda rows: {r["answer"] for r in rows if r["id"].endswith(":x0")}  # noqa: E731
        self.assertEqual((x0(first), x0(again)), ({"No"}, {"Yes"}))
        self.assertEqual(len(again), 4)  # two jobs per lane, nothing of the last probe

    # -- the estimator: one fingerprint over all items, since each fit uses them all
    ITEMS = Pairing.ITEMS

    def _predicted(self, items: list[dict]) -> None:
        m = self.estimator
        predict = lambda cfg, fit, predict, permute, probe: ["pos"] * len(predict)  # noqa: E731
        with mock.patch.object(m, "fit_predict", predict):
            m.measure(m.CONFIG, items, self.out)

    def test_estimator_evaluates_the_complete_unchanged_file(self) -> None:
        m = self.estimator
        self._predicted(self.ITEMS)
        metrics = m.evaluate(self.out, m.CONFIG, self.ITEMS)
        self.assertEqual((metrics["n_items"], metrics["n_test"]), (10, 2))

    def test_estimator_refuses_a_missing_doubled_or_stray_row(self) -> None:
        m = self.estimator
        for gap, edit in GAPS.items():
            with self.subTest(gap=gap):
                self.out = Path(tempfile.mkdtemp()) / "rows.jsonl"
                self._predicted(self.ITEMS)
                _edit_rows(self.out, edit)
                with self.assertRaises(SystemExit) as cm:
                    m.evaluate(self.out, m.CONFIG, self.ITEMS)
                self.assertIn(gap, str(cm.exception))

    def test_estimator_refuses_rows_fitted_on_other_items(self) -> None:
        """An edited item changes every fit: the resume refuses the file, and
        so does the balance when the evaluation alone is asked for."""
        m = self.estimator
        self._predicted(self.ITEMS)
        edited = [{**self.ITEMS[0], "features": [99.0]}, *self.ITEMS[1:]]
        with self.assertRaises(m.batch.InstrumentError):
            self._predicted(edited)
        with self.assertRaises(SystemExit) as cm:
            m.evaluate(self.out, m.CONFIG, edited)
        self.assertIn("_instrument", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
