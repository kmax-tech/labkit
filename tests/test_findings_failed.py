"""A failed audit attempt as data (0.99.0): written by labkit-audit when the
backend does not answer, read by runlog's freeze gate, never a record of findings."""

import tempfile
import unittest
from pathlib import Path
from typing import Any

from labkit.formats import findings
from protocol_fixture import registration_of  # noqa: E402

SHA, BLOCK = "abc123def456", "b10c0000000a"


def attempt(area: Path, **kw: Any) -> Path:
    args: dict[str, Any] = dict(
        mode="preflight",
        model="opus",
        scope_sha=SHA,
        block_sha=BLOCK,
        timeout_s=findings.ATTEMPT_TIMEOUT_S,
        error='claude-cli exit 1: "quota"',
        command="labkit-audit experiments/01-x --mode preflight",
        cause="unavailable",
    )
    args.update(kw)
    return findings.write_failed(area, **args)


class WriteRead(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)

    def test_roundtrip(self):
        path = attempt(self.area, now=1_700_000_000)
        self.assertTrue(path.name.endswith(f"-preflight{findings.FAILED_SUFFIX}"))
        got = findings.read_failed(path)
        self.assertEqual(
            (got.mode, got.model, got.scope_sha, got.block_sha, got.timeout_s),
            ("preflight", "opus", SHA, BLOCK, findings.ATTEMPT_TIMEOUT_S),
        )
        self.assertEqual(got.error, 'claude-cli exit 1: "quota"')
        self.assertIn("--mode preflight", got.command)

    def test_a_second_attempt_in_the_same_minute_does_not_overwrite(self):
        a = attempt(self.area, now=1_700_000_000)
        b = attempt(self.area, now=1_700_000_030)
        self.assertNotEqual(a, b)
        self.assertEqual(len(findings.failed_attempts(self.area)), 2)

    def test_records_and_attempts_are_read_apart(self):
        attempt(self.area)
        findings.write(
            self.area,
            "preflight",
            "opus",
            SHA,
            BLOCK,
            (0, 0, 0),
            [],
            registration=registration_of(self.area),
        )
        self.assertEqual(len(findings.area_records(self.area)), 1)
        self.assertEqual(len(findings.failed_attempts(self.area)), 1)

    def test_wrong_mode_refuses_to_write(self):
        with self.assertRaises(ValueError):
            attempt(self.area, mode="clarity")

    def test_an_unknown_cause_refuses_to_write(self):
        with self.assertRaises(ValueError):
            attempt(self.area, cause="maybe")

    def test_a_damaged_file_is_loud(self):
        path = attempt(self.area)
        for broken, said in (
            ("not = [toml", "not TOML"),
            ("[audit]\nx = 1\n", "no [failed] table"),
            (
                path.read_text().replace("timeout_s = 900", 'timeout_s = "900"'),
                "timeout_s",
            ),
            (path.read_text().replace('mode = "preflight"', 'mode = "x"'), "mode"),
            (path.read_text().replace('cause = "unavailable"', 'cause = "x"'), "cause"),
            (
                path.read_text().replace('cause = "unavailable"\n', ""),
                "cause is missing",
            ),
        ):
            path.write_text(broken, encoding="utf-8")
            with self.assertRaises(findings.FindingsError) as cm:
                findings.failed_attempts(self.area)
            self.assertIn(said, str(cm.exception))


class Unavailable(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)

    def test_the_fitting_attempt_is_found_and_other_ones_are_not(self):
        self.assertIsNone(
            findings.audit_unavailable(self.area, SHA, "preflight", BLOCK)
        )
        attempt(self.area, scope_sha="000000000000", now=1_700_000_000)
        attempt(self.area, block_sha="000000000000", now=1_700_000_060)
        attempt(self.area, mode="analysis", now=1_700_000_120)
        attempt(self.area, timeout_s=findings.ATTEMPT_TIMEOUT_S - 1, now=1_700_000_180)
        self.assertIsNone(
            findings.audit_unavailable(self.area, SHA, "preflight", BLOCK)
        )
        fitting = attempt(self.area, now=1_700_000_240)
        got = findings.audit_unavailable(self.area, SHA, "preflight", BLOCK)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.path, fitting)

    def test_without_a_block_the_code_alone_is_held(self):
        attempt(self.area)
        self.assertIsNotNone(
            findings.audit_unavailable(self.area, SHA, "preflight", None)
        )

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            findings.audit_unavailable(self.area, SHA, "clarity", BLOCK)


class CoverageNamesTheStop(unittest.TestCase):
    """report-check and the freeze read `audit_coverage`: where the auditor
    did not write its answer whole, the refusal says so instead of only
    "no audit"."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)

    def test_an_unproven_attempt_at_this_state_is_named(self):
        attempt(self.area, cause="unproven", model="opus")
        why = findings.audit_coverage(
            self.area, SHA, "preflight", BLOCK, registration=registration_of(self.area)
        )
        assert why is not None
        self.assertIn(
            "1 attempt(s) unproven — opus did not write the answer whole", why
        )
        self.assertIn("--model <alias>", why)

    def test_an_unavailable_or_other_state_keeps_the_plain_refusal(self):
        attempt(self.area, cause="unavailable")
        attempt(self.area, cause="unproven", scope_sha="other" * 3)
        why = findings.audit_coverage(
            self.area, SHA, "preflight", BLOCK, registration=registration_of(self.area)
        )
        assert why is not None
        self.assertNotIn("unproven", why)
        self.assertIn("no preflight audit saw the area as it is now", why)


if __name__ == "__main__":
    unittest.main()
