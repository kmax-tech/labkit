"""A high-cost computation reaches release through its real stamped workflow.

The audit records are simulated, without a model call. The measurement is
started by runlog's detached launcher and its report is held by the real gates.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import test_end_to_end as e2e
from labkit.checks import protocol_report
from labkit.formats import protocol_block, standard_contract
from labkit.gates import preflight, report_check
from labkit.run import runlog_command
from labkit.tools import protocol_fill


class HighComputeWorkflow(unittest.TestCase):
    def test_frozen_computation_runs_and_releases_without_promise_tables(self):
        lab = e2e.Lab()
        self.addCleanup(lab.close)
        source = lab.root / "data" / "raw" / "counts.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('{"a": 1, "b": 2, "c": 6}\n', encoding="utf-8")
        area, protocol = lab.exp(
            "counts", repeat_cost="high", kind="compute", report=True
        )
        script = area / "scripts" / "01_measure.py"
        e2e._replace(
            script,
            [
                (
                    'SOURCE = REPO / "data" / "TODO"',
                    'SOURCE = REPO / "data" / "raw" / "counts.json"',
                ),
                ('COUNT_FIELD = "TODO_count"', 'COUNT_FIELD = "count"'),
                ('METRIC_KEY = "TODO_mean"', 'METRIC_KEY = "mean_count"'),
                (
                    'raise NotImplementedError("expected_ids(): the ids SOURCE lists")',
                    'return sorted(json.loads(SOURCE.read_text(encoding="utf-8")))',
                ),
                (
                    'raise NotImplementedError("rows(): one dict per id, fail loud on a missing one")',
                    'counts = json.loads(SOURCE.read_text(encoding="utf-8"))\n'
                    '    return [{"id": i, COUNT_FIELD: counts[i]} for i in ids]',
                ),
                (
                    'raise NotImplementedError("evaluate_rows(): compute the number(s) from items")',
                    "return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(ids)}",
                ),
            ],
        )
        lab.fill(protocol, "type=exploratory")
        lab.fill_open(
            protocol,
            **{
                "Terms of this protocol": "n/a — no coinage",
                "Question / hypothesis": "What is the mean count over the three cases?",
                "Data / scope": "data/raw/counts.json, three cases",
                "Exclusions / filters": "none",
                "Unit": "one case",
                "Timebox": "1h",
            },
        )
        lab.commit("Register the computation and its implementation")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = preflight.main([str(area)])
        self.assertEqual(rc, 0, output.getvalue())
        lab.record(area, protocol, standard_contract.PREFLIGHT_AUDIT)
        (record,) = (area / "audits").glob("*-preflight.toml")
        e2e._replace(
            protocol,
            [
                ('preflight_audit = ""', f'preflight_audit = "{record.name}"'),
                ("frozen = false", "frozen = true"),
            ],
        )
        self.assertNotIn("[[promise]]", protocol.read_text(encoding="utf-8"))
        # the freeze commit: the lab's pre-commit runs protocol-check on the
        # staged protocol, which held the compute lane to an example its
        # skeleton never makes (labkit-paper area 15, round 2, t21 and t34)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = protocol_report.main([str(protocol)])
        self.assertEqual(rc, 0, output.getvalue())
        lab.commit("Freeze the audited computation")
        output = io.StringIO()
        children: list[subprocess.Popen] = []
        popen = subprocess.Popen

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            children.append(child)
            return child

        with (
            contextlib.chdir(lab.root),
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(lab.root)}),
            mock.patch.object(runlog_command.subprocess, "Popen", side_effect=launch),
            contextlib.redirect_stdout(output),
        ):
            rc = runlog_command.main(
                ["start", str(area), "--", sys.executable, str(script)]
            )
            self.assertEqual(rc, 0, output.getvalue())
            self.addCleanup(children[0].wait, timeout=30)
            log = next((area / "output").glob("start-*.log"))
            self.assertEqual(
                children[0].wait(timeout=30),
                0,
                log.read_text(encoding="utf-8"),
            )
            rc = runlog_command.main(
                [str(area), "--wait", "--interval", "0.1", "--max-seconds", "30"]
            )
        self.assertEqual(rc, 0, output.getvalue())
        (run,) = (area / "runs").iterdir()
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["mean_count"], 3.0)
        rc, out = lab.finalize(area)
        self.assertEqual(rc, 0, out)
        lab.record(area, protocol, standard_contract.ANALYSIS_AUDIT, run.name)
        lab.fill(protocol, "Conclusion=The mean count is three per case.")
        rc, out = lab.adopt(protocol, run.name)
        self.assertEqual(rc, 0, out)
        self.assertEqual(
            protocol_block.declared_run(protocol.read_text(encoding="utf-8")), run.name
        )
        report = lab.root / "REPORT.md"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = protocol_fill.main([str(protocol), "--into", str(report)])
        self.assertEqual(rc, 0, output.getvalue())
        self.assertIn("mean_count = 3.0", report.read_text(encoding="utf-8"))
        rc, out = lab.stop_hook()
        self.assertEqual(rc, 0, out)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(protocol, report, script)
        self.assertEqual(rc, 0, out)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = report_check.main([str(area)])
        self.assertEqual(rc, 0, output.getvalue())
