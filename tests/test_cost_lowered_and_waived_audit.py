"""Two ways round the audit at minutes/hours, both reported (third haiku round
on 0.99.0, labkit-paper area 09): t18 wrote `preflight_audit = "n/a — …"`
and runlog took it (now refused: `findings.waived_audit_gap`, in preflight
and protocol-check too); the next move is lowering `cost` to seconds, where
nothing is owed before the run — exact over git, the head as first committed
against the head now (`protocol_check.cost_lowered`, a WARNING in
protocol-check and preflight). Twins: a raised or unchanged tier, a file git
does not know, a line with a real stamp.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.formats import findings, protocol_block, protocol_check  # noqa: E402
from labkit import preflight  # noqa: E402
from protocol_fixture import DEFAULT_BLOCK, head, scope_file  # noqa: E402

BODY = """
- **Model / tool:** haiku
- **Question / hypothesis:** does the register beat the trivial decider?
- **Success / failure criterion:** [C1] accuracy above the trivial decider
- **Admissibility condition:** [A1] every case parsed
- **Null condition / anchors (in the same run):** [A2] shuffled labels stay at chance
"""


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return r.stdout.strip()


def _repo(cost: str) -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    area = root / "experiments" / "01-x"
    area.mkdir(parents=True)
    scope_file(area)
    protocol = area / "PROTOCOL-x.md"
    protocol.write_text(
        head(cost=cost, promises=DEFAULT_BLOCK) + BODY, encoding="utf-8"
    )
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "register")
    return root, protocol


def _set_cost(protocol: Path, cost: str) -> protocol_block.Head:
    text = protocol.read_text(encoding="utf-8")
    old = next(ln for ln in text.splitlines() if ln.startswith("cost = "))
    text = text.replace(old, f'cost = "{cost}"', 1)
    protocol.write_text(text, encoding="utf-8")
    return protocol_block.head(text)


class CostLowered(unittest.TestCase):
    def test_lowered_since_the_first_commit_warns_and_names_both_tiers(self):
        root, protocol = _repo("minutes")
        first = _git(root, "rev-parse", "HEAD")
        warning = protocol_check.cost_lowered(protocol, _set_cost(protocol, "seconds"))
        assert warning is not None
        self.assertIn("WARNING: cost tier lowered", warning)
        self.assertIn(f"{first[:7]}: minutes -> seconds", warning)
        self.assertIn("LAB-017", warning)

    def test_a_later_commit_does_not_launder_the_tier(self):
        """The first commit is the registration; a committed lowering still warns."""
        root, protocol = _repo("hours")
        _set_cost(protocol, "seconds")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "lower")
        self.assertIsNotNone(
            protocol_check.cost_lowered(
                protocol, protocol_block.head(protocol.read_text())
            )
        )

    def test_raised_unchanged_or_unknown_to_git_is_silent(self):
        root, protocol = _repo("minutes")
        self.assertIsNone(
            protocol_check.cost_lowered(protocol, _set_cost(protocol, "hours"))
        )
        self.assertIsNone(
            protocol_check.cost_lowered(protocol, _set_cost(protocol, "minutes"))
        )
        fresh = protocol.with_name("PROTOCOL-y.md")
        fresh.write_text(head(cost="seconds") + BODY, encoding="utf-8")
        self.assertIsNone(
            protocol_check.cost_lowered(fresh, protocol_block.head(fresh.read_text()))
        )
        outside = Path(tempfile.mkdtemp()) / "PROTOCOL-z.md"
        outside.write_text(head(cost="seconds") + BODY, encoding="utf-8")
        self.assertIsNone(
            protocol_check.cost_lowered(
                outside, protocol_block.head(outside.read_text())
            )
        )

    def test_protocol_check_and_preflight_carry_the_warning(self):
        root, protocol = _repo("minutes")
        _set_cost(protocol, "seconds")
        report = protocol_check.check_protocol(
            protocol, protocol.read_text(encoding="utf-8"), set(), {}
        )
        self.assertIn("cost tier lowered", report.cost_lowered or "")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            protocol_check.print_report(report)
        self.assertIn("WARNING: cost tier lowered", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            preflight.preflight_area(protocol.parent)
        self.assertIn("WARNING: ", out.getvalue())
        self.assertIn("cost tier lowered", out.getvalue())


class WaivedAudit(unittest.TestCase):
    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        scope_file(self.area)

    def _protocol(self, cost: str, line: str, frozen: bool = True) -> Path:
        p = self.area / "PROTOCOL-x.md"
        p.write_text(
            head(cost=cost, frozen=frozen, preflight_audit=line, promises=DEFAULT_BLOCK)
            + BODY
            + "\n```text\nprompt\n```\n",
            encoding="utf-8",
        )
        return p

    def test_the_gap_names_the_honest_ways_and_offers_no_word(self):
        gap = findings.waived_audit_gap(
            "n/a — RF model training does not require external audit"
        )
        assert gap is not None
        self.assertIn("nobody waives their own", gap)
        self.assertIn("labkit-audit <area> --mode preflight", gap)
        self.assertIn("records the failed attempt", gap)
        self.assertIn("the cost tier is wrong, not the line", gap)
        self.assertIsNone(
            findings.waived_audit_gap("2026-10-07 · scope sha abc · 0 findings")
        )

    def test_audit_line_gap_reads_waived_then_drift_then_coverage(self):
        text = self._protocol("minutes", "n/a — x").read_text(encoding="utf-8")
        gap = findings.audit_line_gap(self.area, "n/a — x", text)
        self.assertIn("nobody waives", gap or "")
        gap = findings.audit_line_gap(
            self.area, "2026 · scope sha 000000000000 · 0", text
        )
        self.assertIn("the code now stamps", gap or "")

    def test_preflight_blocks_a_frozen_waiver_at_minutes_and_passes_seconds(self):
        self._protocol("minutes", "n/a — not needed")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = preflight.preflight_area(self.area)
        self.assertEqual(rc, 1)
        self.assertIn(
            "BLOCKER: preflight_audit: `preflight_audit` says n/a", out.getvalue()
        )
        self._protocol("seconds", "n/a — seconds")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            preflight.preflight_area(self.area)
        self.assertNotIn("says n/a", out.getvalue())

    def test_protocol_check_warns_on_a_frozen_waiver_at_minutes(self):
        p = self._protocol("minutes", "n/a — not needed")
        report = protocol_check.check_protocol(
            p, p.read_text(encoding="utf-8"), set(), {}
        )
        self.assertIn("nobody waives", report.audit_drift or "")
        p = self._protocol("minutes", "n/a — not needed", frozen=False)
        report = protocol_check.check_protocol(
            p, p.read_text(encoding="utf-8"), set(), {}
        )
        self.assertIsNone(report.audit_drift)  # unfrozen: the line is not held yet


if __name__ == "__main__":
    unittest.main()
