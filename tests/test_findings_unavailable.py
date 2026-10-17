"""An audit that did not run is not passed (2026-10-17).

Two records beside the findings file: the `.running` marker an audit leaves
before its model call, and the `outcome = "unavailable"` record of a call
that got no result. `audit_stops` reads both, with every open BLOCKER, as
the reasons no full run may start whatever LABKIT_UNFROZEN says (Haiku on bulk modulus (labkit-paper 09, Haiku round, t3-labkit-r1, 2026-10-16): a killed second audit call read as "the
audit failed", the first call's BLOCKER landed unread).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from findings_fixture import decide  # noqa: E402
from labkit import findings

SHA = "abc123def456"
BLOCKER = ("BLOCKER", "BLOCKER · a.py:1 · x · y · LAB-038 What the prompt demands · z")
WARNING = (
    "WARNING",
    "WARNING · b.py:2 · x · y · LAB-019 The stamp covers everything · z",
)


def area() -> Path:
    a = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    a.mkdir(parents=True)
    return a


class UnavailableRecord(unittest.TestCase):
    def test_roundtrip_carries_the_reason_and_no_findings(self):
        a = area()
        p = findings.write_unavailable(
            a, "preflight", "opus", SHA, "claude-cli: not logged in"
        )
        [r] = findings.area_records(a)
        self.assertEqual(r.path, p)
        self.assertEqual(r.unavailable, "claude-cli: not logged in")
        self.assertEqual(r.findings, ())
        self.assertEqual(r.verdict, (0, 0, 0))
        self.assertEqual(r.open, [])

    def test_a_result_record_has_no_reason(self):
        a = area()
        findings.write(a, "preflight", "opus", SHA, (0, 0, 0), [])
        [r] = findings.area_records(a)
        self.assertIsNone(r.unavailable)

    def test_an_empty_reason_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            findings.write_unavailable(area(), "preflight", "opus", SHA, "  ")
        self.assertIn("reason", str(cm.exception))

    def test_reading_is_loud(self):
        a = area()
        p = findings.write_unavailable(a, "analysis", "opus", SHA, "timeout")
        text = p.read_text(encoding="utf-8")
        cases = {
            "other outcome": text.replace(
                'outcome = "unavailable"', 'outcome = "failed"'
            ),
            "no reason": text.replace('reason = "timeout"', 'reason = ""'),
            "findings on it": text
            + '\n[[finding]]\ngrade = "NOTE"\ntext = "x"\nstatus = "open"\nreason = ""\n',
        }
        for name, bad in cases.items():
            with self.subTest(name):
                p.write_text(bad, encoding="utf-8")
                with self.assertRaises(findings.FindingsError) as cm:
                    findings.read(p)
                self.assertIn(p.name, str(cm.exception))

    def test_only_a_record_with_a_result_covers_the_stamp(self):
        a = area()
        findings.write_unavailable(a, "preflight", "opus", SHA, "timeout")
        gap = findings.audit_coverage(a, SHA, "preflight")
        self.assertIsNotNone(gap)
        assert gap is not None
        self.assertIn("got no result", gap)
        self.assertIn("timeout", gap)
        # the twin: a decided result record of the same stamp covers it
        findings.write(a, "preflight", "opus", SHA, (0, 0, 0), [], now=1_800_000_000)
        self.assertIsNone(findings.audit_coverage(a, SHA, "preflight"))


class RunningMarker(unittest.TestCase):
    def test_roundtrip(self):
        a = area()
        p = findings.mark_running(
            a, "preflight", "opus", SHA, pid=4711, script="labkit-audit"
        )
        self.assertTrue(p.name.endswith(findings.RUNNING_SUFFIX))
        [m] = findings.area_running(a)
        self.assertEqual(
            (m.pid, m.script, m.mode, m.scope_sha),
            (4711, "labkit-audit", "preflight", SHA),
        )
        self.assertEqual(findings.area_records(a), [])  # a marker is no record

    def test_defaults_name_this_process(self):
        a = area()
        findings.mark_running(a, "analysis", "opus", SHA)
        [m] = findings.area_running(a)
        import os
        import sys

        self.assertEqual(m.pid, os.getpid())
        self.assertEqual(m.script, Path(sys.argv[0]).name)

    def test_a_broken_marker_is_loud(self):
        a = area()
        p = findings.mark_running(a, "preflight", "opus", SHA, pid=1, script="x")
        p.write_text(
            p.read_text(encoding="utf-8").replace("pid = 1", 'pid = "1"'),
            encoding="utf-8",
        )
        with self.assertRaises(findings.FindingsError) as cm:
            findings.area_running(a)
        self.assertIn("pid", str(cm.exception))

    def test_removed_with_the_record(self):
        a = area()
        p = findings.mark_running(a, "preflight", "opus", SHA, pid=1, script="x")
        p.unlink()
        self.assertEqual(findings.area_running(a), [])


class AuditStops(unittest.TestCase):
    def test_no_audits_directory_stops_nothing(self):
        self.assertEqual(findings.audit_stops(area()), [])

    def test_an_open_blocker_in_any_record_stops(self):
        a = area()
        p = findings.write(a, "analysis", "opus", SHA, (1, 0, 0), [BLOCKER])
        [stop] = findings.audit_stops(a)
        self.assertIn(p.name, stop)
        self.assertIn("LABKIT_UNFROZEN=1 does not pass", stop)
        decide(p, "accepted")  # the twin: decided, the stop is gone
        self.assertEqual(findings.audit_stops(a), [])

    def test_an_open_warning_is_no_stop_but_named(self):
        a = area()
        p = findings.write(a, "preflight", "opus", SHA, (0, 1, 0), [WARNING])
        self.assertEqual(findings.audit_stops(a), [])
        [line] = findings.open_warnings(a)
        self.assertIn(p.name, line)
        decide(p, "fixed", "")
        self.assertEqual(findings.open_warnings(a), [])

    def test_the_newest_unavailable_record_of_a_mode_stops(self):
        a = area()
        findings.write(a, "preflight", "opus", SHA, (0, 0, 0), [], now=1_700_000_000)
        findings.write_unavailable(
            a, "preflight", "opus", SHA, "backend down", now=1_700_000_060
        )
        [stop] = findings.audit_stops(a)
        self.assertIn("backend down", stop)
        self.assertIn("rerun `labkit-audit <area> --mode preflight`", stop)
        # the twin: a later result lifts it
        findings.write(a, "preflight", "opus", SHA, (0, 0, 0), [], now=1_700_000_120)
        self.assertEqual(findings.audit_stops(a), [])

    def test_a_live_marker_says_wait_a_dead_one_says_rerun(self):
        a = area()
        p = findings.mark_running(
            a, "preflight", "opus", SHA, pid=4711, script="labkit-audit"
        )
        [wait] = findings.audit_stops(a, alive=lambda pid, script: True)
        self.assertIn("running since", wait)
        self.assertIn("pid 4711", wait)
        for undecidable in (False, None):
            with self.subTest(alive=undecidable):
                [dead] = findings.audit_stops(a, alive=lambda pid, script: undecidable)
                self.assertIn("died", dead)
                self.assertIn(p.name, dead)
                self.assertIn("deleting it does not", dead)

    def test_order_blocker_then_unavailable_then_waiting(self):
        a = area()
        findings.mark_running(
            a, "analysis", "opus", SHA, pid=1, script="x", now=1_700_000_000
        )
        findings.write_unavailable(
            a, "preflight", "opus", SHA, "timeout", now=1_700_000_060
        )
        findings.write(
            a, "analysis", "opus", SHA, (1, 0, 0), [BLOCKER], now=1_700_000_120
        )
        stops = findings.audit_stops(a, alive=lambda pid, script: True)
        self.assertEqual(len(stops), 3)
        self.assertIn("BLOCKER", stops[0])
        self.assertIn("unavailable", stops[1])
        self.assertIn("running", stops[2])


if __name__ == "__main__":
    unittest.main()
