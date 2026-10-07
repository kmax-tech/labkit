"""finalize station 4 (2026-10-05): at cost = "seconds" the run must have frozen
its source and every source/output file must be tracked in git; elsewhere
the station is n/a."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import finalize  # noqa: E402
from protocol_fixture import PID, head  # noqa: E402

BODY = """
- **Question / hypothesis:** how many documents per case?
- **Answer to the question:** 3.5, run r1
"""
SHORT = "# Experiment protocol: x\n\n" + head(cost="seconds") + BODY
HOURS = "# Experiment protocol: x\n\n" + head(cost="hours", frozen=True) + BODY


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class Provenance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", ".")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "t")
        self.area = self.repo / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.src = self.repo / "data" / "raw" / "cases.jsonl"
        self.src.parent.mkdir(parents=True)
        self.src.write_text('{"id": 1}\n', encoding="utf-8")
        self.out = self.area / "output" / "x.jsonl"
        self.out.parent.mkdir()
        self.out.write_text('{"id": 1, "n": 4}\n', encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, protocol: str, data: dict | None, commit: bool) -> Path:
        (self.area / "PROTOCOL-x.md").write_text(protocol, encoding="utf-8")
        d = self.area / "runs" / "2026-10-05T19-00-00_ab12"
        d.mkdir(parents=True)
        cfg = {
            "script": "01_measure.py",
            "pid": 1,
            "schema_version": 2,
            "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
            "data": data or {},
        }
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (d / "metrics.json").write_text(json.dumps({"mean": 3.5}), encoding="utf-8")
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
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(self.out), "sha256": "ab"}]), encoding="utf-8"
        )
        if commit:
            _git(self.repo, "add", "-A")
            _git(self.repo, "commit", "-qm", "x")
        return d

    def _finalize(self) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = finalize.main([str(self.area)])
        return rc, buf.getvalue()

    def _frozen(self) -> dict:
        return {"cases": {"path": str(self.src), "rows": 1, "sha256": "ab"}}

    def test_frozen_and_tracked_is_clean(self):
        self._run(SHORT, self._frozen(), commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("source frozen in the run; source and output tracked", out)

    def test_no_data_is_a_blocker(self):
        self._run(SHORT, None, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("source not frozen", out)

    def test_untracked_source_is_a_blocker(self):
        self._run(SHORT, self._frozen(), commit=False)
        rc, out = self._finalize()
        self.assertEqual(rc, 1)
        self.assertIn("source", out)
        self.assertIn("not tracked in git", out)

    def test_untracked_output_after_the_run_is_a_warning_naming_git_add(self):
        d = self._run(SHORT, self._frozen(), commit=True)
        self.out.write_text(
            '{"id": 1, "n": 5}\n', encoding="utf-8"
        )  # rows born after the commit
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(self.out), "sha256": "ab"}])
        )
        fresh = self.area / "output" / "fresh.jsonl"
        fresh.write_text("{}\n", encoding="utf-8")
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(fresh), "sha256": "ab"}])
        )
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("git add", out)

    def test_hours_is_not_the_stations_business(self):
        self._run(HOURS, None, commit=True)
        rc, out = self._finalize()
        self.assertEqual(rc, 0, out)
        self.assertIn("n/a — not a run of seconds", out)


if __name__ == "__main__":
    unittest.main()
