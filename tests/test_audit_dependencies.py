"""The analysis audit sees the run's declared dependencies: in the repair
case (2026-10-28) the follow-up could not confirm a repair against
model.json, which no piece showed, and three decision reviews said
insufficient.

    .venv/bin/python -m pytest tests/test_audit_dependencies.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record  # noqa: E402
from labkit.checks import audit_binding
from labkit.formats import runs, scope_sha

MODEL = {"weights": [0.8, 0.6], "mean": [52.0, 128.0], "std": [12.0, 16.0]}


class DeclaredDependencies(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".git").mkdir()  # the layout root recorded paths resolve against
        self.model = self.root / "data" / "model.json"
        self.model.parent.mkdir()
        self.model.write_text(json.dumps(MODEL), encoding="utf-8")
        self.prepared = self.root / "data" / "items.jsonl"
        self.prepared.write_text('{"id": 1}\n', encoding="utf-8")
        self.run_dir = (
            self.root / "experiments" / "01-x" / "runs" / "2026-01-01T00-00-00_0001"
        )
        self.run_dir.mkdir(parents=True)

    def record(self, **data: dict) -> None:
        (self.run_dir / "config.json").write_text(
            json.dumps(run_record(data=data)), encoding="utf-8"
        )

    def entry(self, path: Path, rows: int | None) -> dict:
        return {
            "path": path.relative_to(self.root).as_posix(),
            "sha256": scope_sha.file_digest(path)[: runs.RECORD_SHA_CHARS],
            "rows": rows,
        }

    def test_a_small_text_dependency_is_shown_whole_and_a_dataset_is_not(self):
        self.record(
            predictor_primary=self.entry(self.model, None),
            prepared=self.entry(self.prepared, 1),
        )
        ((label, text),) = audit_binding.dependency_pieces(self.run_dir)
        self.assertTrue(
            label.startswith("DEPENDENCY data/model.json (predictor_primary")
        )
        self.assertEqual(json.loads(text), MODEL)

    def test_a_dependency_changed_since_the_run_is_named_not_shown(self):
        self.record(predictor_primary=self.entry(self.model, None))
        self.model.write_text(json.dumps({**MODEL, "std": [144.0, 256.0]}))
        ((_, text),) = audit_binding.dependency_pieces(self.run_dir)
        self.assertIn("not shown: changed since the run", text)
        self.assertNotIn("144", text)

    def test_a_binary_dependency_is_named_by_its_digest(self):
        blob = self.root / "data" / "forest.pkl"
        blob.write_bytes(b"\x80\x04\xff\xfe")
        self.record(predictor_primary=self.entry(blob, None))
        ((label, text),) = audit_binding.dependency_pieces(self.run_dir)
        self.assertIn("the run recorded sha", label)
        self.assertEqual(text, "not shown: not text — named by its digest")

    def test_the_shown_dependency_is_part_of_what_the_record_binds(self):
        """A model file changed after the audit changes what was shown, so
        the audit no longer covers the state (`RunShown.sha`)."""
        self.record(predictor_primary=self.entry(self.model, None))
        area = self.run_dir.parents[1]
        before = audit_binding.run_shown(area, self.run_dir, "")
        self.assertTrue(any(lab.startswith("DEPENDENCY ") for lab, _ in before.pieces))
        self.model.write_text(json.dumps({**MODEL, "weights": [0.0, 0.0]}))
        self.assertNotEqual(
            before.sha, audit_binding.run_shown(area, self.run_dir, "").sha
        )


if __name__ == "__main__":
    unittest.main()
