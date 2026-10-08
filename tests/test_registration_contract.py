"""The registration's contract (0.71.0): a frozen protocol carries its
promises as data, and a run under a block records every registered constant
unchanged — refused by runlog before mkdir, a MUST finding in protocol-check,
a blocker in finalize.

    .venv/bin/python -m pytest tests/test_registration_contract.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import PID, head, scope_file

from labkit import finalize, protocol_check, runlog

AUDIT = "n/a — contract test, no code to audit"
C1 = """[[promise]]
id = "C1"
key = "c1_pass"
sentence = "accuracy >= min_acc"
scope = ["scripts/01_measure.py"]
constants = { min_acc = 0.7 }
"""
BODY = (
    "\n- **Question / hypothesis:** q\n- **Success / failure criterion:** [C1] c\n"
    "- **Admissibility condition:** none\n"
)


def _area(d: str, text: str) -> Path:
    area = Path(d)
    (area / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
    scope_file(area)
    return area


def _start(area: Path, config: dict) -> runlog.Run:
    with contextlib.redirect_stdout(io.StringIO()):
        return runlog.Run("t", config, area, long=False)


class RunlogRefusesBeforeMkdir(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("CLAUDECODE", None)
        self.unfrozen = os.environ.pop("LABKIT_UNFROZEN", None)

    def tearDown(self) -> None:
        if self.unfrozen is not None:
            os.environ["LABKIT_UNFROZEN"] = self.unfrozen

    def test_twin_a_config_carrying_the_constant_starts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(promises=C1) + BODY)
            r = _start(area, {"min_acc": 0.7, "model": "m"})
            cfg = json.loads((r.dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["config"]["min_acc"], 0.7)

    def test_a_missing_constant_is_refused_and_no_directory_is_made(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(promises=C1) + BODY)
            with self.assertRaises(SystemExit) as cm:
                _start(area, {"model": "m"})
            self.assertIn(
                "[C1] min_acc = 0.7 is registered, the config carries no such key",
                str(cm.exception),
            )
            self.assertIn("promises.all_constants()", str(cm.exception))
            self.assertFalse((area / "runs").exists())

    def test_a_differing_type_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(promises=C1.replace("0.7", "1")) + BODY)
            with self.assertRaises(SystemExit) as cm:
                _start(area, {"min_acc": True})
            self.assertIn("the config says True", str(cm.exception))

    def test_frozen_without_a_block_is_refused_even_when_acknowledged(self) -> None:
        """Not a freeze-gate finding: LABKIT_UNFROZEN=1 does not reach it."""
        os.environ["LABKIT_UNFROZEN"] = "1"
        with tempfile.TemporaryDirectory() as d:
            area = _area(
                d, head(frozen=True, preflight_audit=AUDIT, promises=None) + BODY
            )
            with self.assertRaises(SystemExit) as cm:
                _start(area, {})
            self.assertIn(
                "frozen = true, but the protocol declares no [[promise]]",
                str(cm.exception),
            )
            self.assertFalse((area / "runs").exists())

    def test_unfrozen_without_a_block_still_runs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(frozen=False) + BODY)
            r = _start(area, {})
            self.assertTrue((r.dir / "config.json").is_file())


class ProtocolCheckOwesTheBlock(unittest.TestCase):
    def test_frozen_without_a_block_is_a_must_finding(self) -> None:
        report = protocol_check.check_fields(
            head(frozen=True, preflight_audit=AUDIT, promises=None)
        )
        self.assertTrue(
            any("declares no [[promise]]" in m for m in report.missing_must),
            report.missing_must,
        )

    def test_frozen_with_a_block_is_quiet_on_that_point(self) -> None:
        report = protocol_check.check_fields(head(frozen=True, preflight_audit=AUDIT))
        self.assertFalse(
            any("[[promise]]" in m for m in report.missing_must), report.missing_must
        )

    def test_a_malformed_block_is_named(self) -> None:
        report = protocol_check.check_fields(
            head(
                frozen=True,
                preflight_audit=AUDIT,
                promises=C1.replace("min_acc", "MIN_ACC"),
            )
        )
        self.assertTrue(
            any(
                "[[promise]] block" in m and "MIN_ACC" in m for m in report.missing_must
            )
        )


class FinalizeBlocksAnUnrecordedBlock(unittest.TestCase):
    def _run(self, area: Path, recorded: dict | None) -> Path:
        d = area / "runs" / "2026-10-08T10-00-00_aaaa"
        d.mkdir(parents=True)
        cfg = {
            "schema_version": 2,
            "script": "01_measure.py",
            "pid": 1,
            "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
            "promises": recorded,
            "config": {},
        }
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return d

    def test_frozen_run_without_a_recorded_block_is_a_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(frozen=True, preflight_audit=AUDIT) + BODY)
            run = self._run(area, None)
            findings = finalize.Findings()
            with contextlib.redirect_stdout(io.StringIO()):
                finalize.check_declared_scopes(findings, area, run, frozen=True)
            self.assertTrue(
                any(
                    "recorded no promise block" in b and "0.70.0" in b
                    for b in findings.blocked
                ),
                findings.blocked,
            )

    def test_unfrozen_run_without_a_block_is_a_line_not_a_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, head(frozen=False) + BODY)
            run = self._run(area, None)
            findings = finalize.Findings()
            with contextlib.redirect_stdout(io.StringIO()):
                finalize.check_declared_scopes(findings, area, run, frozen=False)
            self.assertEqual(findings.blocked, [])


if __name__ == "__main__":
    unittest.main()
