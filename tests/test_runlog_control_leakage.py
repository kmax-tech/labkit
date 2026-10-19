"""runlog data= leakage beyond splits (2026-10-05): a control set (anchor,
gate, placebo) sharing an id with the measured set is a refusal."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.run import provenance  # noqa: E402


def _jsonl(path: Path, ids: list[str]) -> Path:
    path.write_text(
        "".join(json.dumps({"id": i, "x": 1}) + "\n" for i in ids), encoding="utf-8"
    )
    return path


class ControlLeakage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_shared_id_between_anchor_and_items_is_refused(self):
        items = _jsonl(self.d / "items.jsonl", ["a", "b", "c"])
        anchors = _jsonl(self.d / "anchors.jsonl", ["c", "z"])
        with self.assertRaises(RuntimeError) as cm:
            provenance.describe_data({"items": items, "anchors": anchors}, self.d)
        self.assertIn("control leakage", str(cm.exception))
        self.assertIn("'c'", str(cm.exception))

    def test_disjoint_sets_pass_and_say_so(self):
        items = _jsonl(self.d / "items.jsonl", ["a", "b"])
        placebo = _jsonl(self.d / "placebo_v1.jsonl", ["y", "z"])
        out = provenance.describe_data({"items": items, "placebo_v1": placebo}, self.d)
        self.assertTrue(out["leakage_check"].startswith("ok:"))
        self.assertIn("placebo_v1", out["leakage_check"])

    def test_two_controls_may_overlap(self):
        gate = _jsonl(self.d / "gate.jsonl", ["a"])
        anchor = _jsonl(self.d / "anchor.jsonl", ["a"])
        provenance.describe_data(
            {"gate": gate, "anchor": anchor}, self.d
        )  # no measured set: nothing to leak into

    def test_split_leakage_still_refused(self):
        train = _jsonl(self.d / "train.jsonl", ["a"])
        test = _jsonl(self.d / "test.jsonl", ["a"])
        with self.assertRaises(RuntimeError) as cm:
            provenance.describe_data({"train": train, "test": test}, self.d)
        self.assertIn("split leakage", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
