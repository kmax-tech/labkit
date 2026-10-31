"""Two ways round the audit at high repeat cost, both reported (third haiku round
on 0.99.0, labkit-paper area 09): t18 wrote `preflight_audit = "n/a — …"`
and runlog took it (now refused: `findings.waived_audit_gap`, in preflight
and protocol-check too); the next move is lowering `repeat_cost` to `low`, where
nothing is owed before the run — exact over git, the head as first committed
against the head now (`protocol_history.repeat_cost_lowered`, a WARNING in
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

from labkit.formats import (
    audit_gaps,
    findings,
    promises,
    protocol_block,
    protocol_history,
    scope_sha,
)
from labkit.checks import protocol_report  # noqa: E402
from labkit.gates import preflight  # noqa: E402
from protocol_fixture import registration_of, DEFAULT_BLOCK, head, scope_file  # noqa: E402

BODY = """
- **Model / tool:** haiku
- **Question / hypothesis:** does the register beat the trivial decider?
- **Inference criterion:** [criterion-1] accuracy above the trivial decider
- **Quality check:** [quality-check-1] every case parsed
- **Null condition / anchors (in the same run):** [quality-check-2] shuffled labels stay at chance
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
        head(repeat_cost=cost, promises=DEFAULT_BLOCK) + BODY, encoding="utf-8"
    )
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "register")
    return root, protocol


def _set_cost(protocol: Path, cost: str) -> protocol_block.Head:
    text = protocol.read_text(encoding="utf-8")
    old = next(ln for ln in text.splitlines() if ln.startswith("repeat_cost = "))
    text = text.replace(old, f'repeat_cost = "{cost}"', 1)
    protocol.write_text(text, encoding="utf-8")
    return protocol_block.head(text)


class RepeatCostLowered(unittest.TestCase):
    def test_lowered_since_the_first_commit_warns_and_names_both_tiers(self):
        root, protocol = _repo("high")
        first = _git(root, "rev-parse", "HEAD")
        warning = protocol_history.repeat_cost_lowered(
            protocol, _set_cost(protocol, "low")
        )
        assert warning is not None
        self.assertIn("WARNING: repeat cost lowered", warning)
        self.assertIn(f"{first[:7]}: high -> low", warning)
        self.assertIn("LAB-017", warning)

    def test_a_later_commit_does_not_launder_the_tier(self):
        """The first commit is the registration; a committed lowering still warns."""
        root, protocol = _repo("high")
        _set_cost(protocol, "low")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "lower")
        self.assertIsNotNone(
            protocol_history.repeat_cost_lowered(
                protocol, protocol_block.head(protocol.read_text())
            )
        )

    def test_lowered_after_a_migration_warns_from_the_migration_commit(self):
        """A protocol first committed under standard 0.22 (`cost = "hours"`)
        is compared from the first commit this standard reads; the warning
        counts the earlier commits it could not compare."""
        root, protocol = _repo("high")
        old = (
            protocol.read_text(encoding="utf-8")
            .replace('standard = "0.23"', 'standard = "0.22"')
            .replace('repeat_cost = "high"', 'cost = "hours"')
        )
        protocol.write_text(old, encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "--amend", "-m", "registered at 0.22")
        protocol.write_text(
            old.replace('standard = "0.22"', 'standard = "0.23"').replace(
                'cost = "hours"', 'repeat_cost = "high"'
            ),
            encoding="utf-8",
        )
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "migrated to 0.23")
        migration = _git(root, "rev-parse", "HEAD")
        warning = protocol_history.repeat_cost_lowered(
            protocol, _set_cost(protocol, "low")
        )
        assert warning is not None
        self.assertIn(f"{migration[:7]}: high -> low", warning)
        self.assertIn("1 earlier at another standard, not compared", warning)

    def test_a_placeholder_committed_first_is_no_base_to_compare_against(self):
        """Stamp committed with `repeat_cost = "<low | high>"`, then declared
        `high`, then lowered: the warning compares against the first
        declaration, not the placeholder (review 2026-10-25)."""
        root, protocol = _repo("high")
        text = protocol.read_text(encoding="utf-8")
        protocol.write_text(
            text.replace('repeat_cost = "high"', 'repeat_cost = "<low | high>"'),
            encoding="utf-8",
        )
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "--amend", "-m", "stamped")
        protocol.write_text(text, encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "declared high")
        declared = _git(root, "rev-parse", "HEAD")
        warning = protocol_history.repeat_cost_lowered(
            protocol, _set_cost(protocol, "low")
        )
        assert warning is not None
        self.assertIn(f"{declared[:7]}: high -> low", warning)

    def test_raised_unchanged_or_unknown_to_git_is_silent(self):
        root, protocol = _repo("high")
        self.assertIsNone(
            protocol_history.repeat_cost_lowered(protocol, _set_cost(protocol, "high"))
        )
        self.assertIsNone(
            protocol_history.repeat_cost_lowered(protocol, _set_cost(protocol, "high"))
        )
        fresh = protocol.with_name("PROTOCOL-y.md")
        fresh.write_text(head(repeat_cost="low") + BODY, encoding="utf-8")
        self.assertIsNone(
            protocol_history.repeat_cost_lowered(
                fresh, protocol_block.head(fresh.read_text())
            )
        )
        outside = Path(tempfile.mkdtemp()) / "PROTOCOL-z.md"
        outside.write_text(head(repeat_cost="low") + BODY, encoding="utf-8")
        self.assertIsNone(
            protocol_history.repeat_cost_lowered(
                outside, protocol_block.head(outside.read_text())
            )
        )

    def test_protocol_check_and_preflight_carry_the_warning(self):
        root, protocol = _repo("high")
        _set_cost(protocol, "low")
        report = protocol_report.check_protocol(
            protocol, protocol.read_text(encoding="utf-8"), set(), {}
        )
        self.assertIn("repeat cost lowered", report.repeat_cost_lowered or "")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            protocol_report.print_report(report)
        self.assertIn("WARNING: repeat cost lowered", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            preflight.preflight_area(protocol.parent)
        self.assertIn("WARNING: ", out.getvalue())
        self.assertIn("repeat cost lowered", out.getvalue())


class WaivedAudit(unittest.TestCase):
    def setUp(self):
        # inside an experiments folder of its own: preflight reads the
        # area's siblings, and the shared temp directory holds every test's
        self.area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        scope_file(self.area)

    def _protocol(self, cost: str, line: str, frozen: bool = True) -> Path:
        p = self.area / "PROTOCOL-x.md"
        p.write_text(
            head(
                repeat_cost=cost,
                frozen=frozen,
                preflight_audit=line,
                promises=DEFAULT_BLOCK,
            )
            + BODY
            + "\n```text\nprompt\n```\n",
            encoding="utf-8",
        )
        return p

    def test_the_gap_names_the_honest_ways_and_offers_no_word(self):
        text = self._protocol("high", "n/a — x").read_text(encoding="utf-8")
        gap = audit_gaps.audit_record_gap(
            self.area, "n/a — RF model training does not require external audit", text
        )
        assert gap is not None
        self.assertIn("names no record", gap.why)
        self.assertIn("nobody waives their own", gap.why)
        self.assertIn("labkit-audit <area> --mode preflight", gap.why)
        self.assertIn("records the failed attempt", gap.why)
        self.assertIn("the repeat cost is wrong, not the field", gap.why)

    def test_audit_record_gap_reads_name_existence_code_block_then_decisions(self):
        """The record named in the head, held step by step: a name of
        another form, a record nobody wrote, one of other code, one of
        another promise block, one with an open finding, and the twin."""
        text = self._protocol("high", "x").read_text(encoding="utf-8")
        block = promises.block_stamp(text)
        gap = audit_gaps.audit_record_gap(
            self.area, "2026 · scope sha 000000000000 · 0", text
        )
        self.assertIn("names no record", gap.why if gap else "")
        gap = audit_gaps.audit_record_gap(
            self.area, "2026-10-07T10-00-preflight.toml", text
        )
        self.assertIn("there is no such record", gap.why if gap else "")
        other = findings.write(
            self.area,
            "preflight",
            "opus",
            "000000000000",
            block,
            (0, 0, 0),
            [],
            registration=registration_of(self.area),
        )
        gap = audit_gaps.audit_record_gap(self.area, other.name, text)
        self.assertIn("the code now stamps", gap.why if gap else "")
        sha = scope_sha.area_stamp(self.area)[0]
        stale = findings.write(
            self.area,
            "preflight",
            "opus",
            sha,
            "otherblock00",
            (0, 0, 0),
            [],
            registration=registration_of(self.area),
        )
        gap = audit_gaps.audit_record_gap(self.area, stale.name, text)
        self.assertIn("saw the promise block otherblock00", gap.why if gap else "")
        open_ = findings.write(
            self.area,
            "preflight",
            "opus",
            sha,
            block,
            (1, 0, 0),
            [
                (
                    "BLOCKER",
                    "BLOCKER · scripts/01_measure.py:1 · x · y · LAB-015 Preflight audit before freezing · z",
                )
            ],
            registration=registration_of(self.area),
        )
        gap = audit_gaps.audit_record_gap(self.area, open_.name, text)
        self.assertIn("still `open`", gap.why if gap else "")
        good = findings.write(
            self.area,
            "preflight",
            "opus",
            sha,
            block,
            (0, 0, 0),
            [],
            registration=registration_of(self.area),
        )
        self.assertIsNone(audit_gaps.audit_record_gap(self.area, good.name, text))
        analysis = findings.write(
            self.area,
            "analysis",
            "opus",
            sha,
            block,
            (0, 0, 0),
            [],
            run_id=findings.NO_RUN,
            shown_sha="0" * 12,
            registration=registration_of(self.area),
        )
        gap = audit_gaps.audit_record_gap(self.area, analysis.name, text)
        self.assertIn(
            "names no record", gap.why if gap else ""
        )  # an analysis record's name is not a preflight one

    def test_preflight_blocks_a_frozen_waiver_at_minutes_and_passes_seconds(self):
        self._protocol("high", "n/a — not needed")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = preflight.preflight_area(self.area)
        self.assertEqual(rc, 1)
        self.assertIn(
            "BLOCKER: preflight_audit: `preflight_audit` names no record",
            out.getvalue(),
        )
        self._protocol("low", "n/a — low")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            preflight.preflight_area(self.area)
        self.assertNotIn("names no record", out.getvalue())

    def test_protocol_check_warns_on_a_frozen_waiver_at_minutes(self):
        p = self._protocol("high", "n/a — not needed")
        report = protocol_report.check_protocol(
            p, p.read_text(encoding="utf-8"), set(), {}
        )
        assert report.audit_drift is not None
        self.assertIn("nobody waives", report.audit_drift.why)
        p = self._protocol("high", "n/a — not needed", frozen=False)
        report = protocol_report.check_protocol(
            p, p.read_text(encoding="utf-8"), set(), {}
        )
        self.assertIsNone(report.audit_drift)  # unfrozen: the line is not held yet


if __name__ == "__main__":
    unittest.main()
