"""Tests for finalize — the read-only gate after a run.

The individual checks (intent-check, protocol-fill) have their own tests.
These tests verify that finalize sequences them correctly and that the
exit code reflects the worst finding.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import finalize  # noqa: E402
from protocol_fixture import PID, head  # noqa: E402

BODY = """\
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [C1] p < .05
- **Admissibility condition:** [A1] parse yield above 80%
- **Null condition / anchors (in the same run):** [A2] shuffled labels stay at chance
- **Raw output:** one real example
- **Outcome:** 0.03

```text
prompt
```
"""


def _protocol(**head_fields) -> str:
    return "# Experiment protocol: x\n\n" + head(frozen=True, **head_fields) + "\n" + BODY


CLEAN_PROTOCOL = _protocol()
CLEAN_METRICS = {"c1_pass": True, "a1_pass": True, "a2_pass": True}

PROTOCOL_WITH_HOLES = CLEAN_PROTOCOL.replace(
    "- **Outcome:** 0.03",
    "- **Outcome:** <result here>")


def _run(area, name, *, pid=PID, metrics=None, completion=True):
    d = area / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    cfg = {"script": "01_measure.py", "pid": 1, "schema_version": 2,
           "protocol": {"id": pid, "path": "PROTOCOL-x.md"}}
    (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if metrics is not None:
        (d / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    if completion:
        (d / "completion.json").write_text(
            json.dumps({"schema_version": 2, "finished": "x",
                        "git": "g", "git_full": "g", "note": ""}),
            encoding="utf-8")
    return d


def _run_finalize(area, protocol=None):
    argv = [str(area)]
    if protocol:
        argv += ["--protocol", str(protocol)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = finalize.main(argv)
    return code, buf.getvalue()


class TestFinalize(unittest.TestCase):

    def test_clean_area_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("all clear", out)

    def test_no_completed_run_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "r1", metrics={"c1_pass": True}, completion=False)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no completed run bound to", out)
        self.assertIn("blocker", out)

    def test_no_runs_dir_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no runs/", out)

    def test_missing_intent_key_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(CLEAN_PROTOCOL)
            _run(area, "r1", metrics={"c1_pass": True, "a1_pass": True})
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("[A2] registered", out)

    def test_open_fields_are_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(PROTOCOL_WITH_HOLES)
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("Outcome", out)
        self.assertIn("warning", out.lower())

    def test_no_protocol_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_finalize(Path(d))
        self.assertEqual(code, 2, out)
        self.assertIn("no PROTOCOL", out)

    def test_help_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = finalize.main(["--help"])
        self.assertEqual(code, 0)

    def test_no_args_exits_two(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = finalize.main([])
        self.assertEqual(code, 2)

    def test_no_intent_ids_skips_check(self):
        proto = CLEAN_PROTOCOL.replace("[C1] ", "").replace("[A1] ", "").replace("[A2] ", "")
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(proto)
            _run(area, "r1", metrics={"something": 1})
            code, out = _run_finalize(area)
        self.assertEqual(code, 0, out)
        self.assertIn("no intent ids registered", out)

    def test_unreadable_head_exits_two(self):
        """A prose head (Standard 0.16/0.17) is read by labkit 0.47; here it
        is a usage error naming the [protocol] table (TODO 8)."""
        prose = ("# Experiment protocol: x\n\n- **Standard:** 0.16\n"
                 f"- **Protocol id:** {PID}\n- **Frozen before run:** yes\n" + BODY)
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(prose)
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 2, out)
        self.assertIn("no [protocol] table", out)

    def test_unstamped_id_is_a_blocker(self):
        """No stamped id binds no run: a number cannot be traced to this
        protocol, so finalize blocks instead of skipping the completion check."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(_protocol(id="<protocol-id>"))
            _run(area, "r1", metrics=CLEAN_METRICS)
            code, out = _run_finalize(area)
        self.assertEqual(code, 1, out)
        self.assertIn("no stamped protocol id", out)


if __name__ == "__main__":
    unittest.main()
