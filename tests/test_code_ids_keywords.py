"""code-check reads keyword-argument keys, not only string literals.

`r.metrics(criterion_1_pass=...)` reaches metrics.json as "criterion_1_pass" without being a
string literal. Reading literals only would give a BLOCKER against correct
code ("no script names a 'c1' key literal").

The decisive fixture is a twin pair: the same report written as a dict
literal and as keyword arguments must get the same verdict. A local
assignment `criterion_1_pass = ...` is not a reported key and must stay invisible.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks.code_check import check_intent_ids  # noqa: E402
from labkit.checks.intent_check import code_ids  # noqa: E402
from labkit.formats.gate import BLOCKER, VIOLATED, WARNING, cited_rule  # noqa: E402

PROTOCOL = "Criterion [criterion-1]; admissibility [quality-check-1].\n"
LITERAL = 'r.metrics(**{"criterion_1_pass": ok, "quality_check_1_anchor_ok": a})\n'
KEYWORD = "r.metrics(criterion_1_pass=ok,\n          quality_check_1_anchor_ok=a)\n"


def area_with(script: str) -> tuple[Path, Path]:
    area = Path(tempfile.mkdtemp())
    (area / "scripts").mkdir()
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    protocol = area / "PROTOCOL-x.md"
    protocol.write_text(PROTOCOL, encoding="utf-8")
    return area, protocol


class KeywordKeys(unittest.TestCase):
    def test_twin_pair_gets_the_same_verdict(self):
        for script in (LITERAL, KEYWORD):
            area, protocol = area_with(script)
            with self.subTest(script=script):
                self.assertEqual(
                    check_intent_ids(
                        area, protocol, protocol.read_text(encoding="utf-8")
                    ),
                    [],
                )

    def test_keyword_hit_carries_its_line(self):
        area, _ = area_with(KEYWORD)
        hits = code_ids(area)
        self.assertEqual(hits["criterion-1"], ["01_measure.py:1"])
        self.assertEqual(hits["quality-check-1"], ["01_measure.py:2"])

    def test_assignment_is_not_a_reported_key(self):
        area, protocol = area_with(
            "criterion_1_pass = ok\nr.metrics(**{'quality_check_1_anchor_ok': a})\n"
        )
        findings = [
            f.line
            for f in check_intent_ids(
                area, protocol, protocol.read_text(encoding="utf-8")
            )
        ]
        self.assertEqual(len(findings), 1)
        self.assertIn("[criterion-1] is registered, but no script names", findings[0])

    def test_a_registered_id_without_a_key_literal_records_the_literal_duty(self):
        """CODE-016 states the duty the check decides exactly; the reverse
        direction, a key nobody registered, stays under LAB-004."""
        area, protocol = area_with(
            "r.metrics(criterion_2_pass=ok, quality_check_1_anchor_ok=a)\n"
        )
        missing, unregistered = check_intent_ids(
            area, protocol, protocol.read_text(encoding="utf-8")
        )
        self.assertIn("[criterion-1] is registered, but no script names", missing.text)
        self.assertEqual(
            (missing.grade, missing.rule, missing.outcome),
            (
                BLOCKER,
                cited_rule("CODE-016 The experiment area reconstructs itself"),
                VIOLATED,
            ),
        )
        self.assertIn("CODE-016 The experiment area reconstructs itself", missing.line)
        self.assertIn(
            "'criterion_2_*' is in the intent-id namespace", unregistered.text
        )
        self.assertEqual(
            (unregistered.grade, unregistered.rule),
            (
                WARNING,
                cited_rule("LAB-004 Identifiers make the intent addressable"),
            ),
        )

    def test_suffixed_only_drops_a_bare_keyword(self):
        area, _ = area_with("f(quality_check_65=1, criterion_1_pass=2)\n")
        self.assertEqual(set(code_ids(area, suffixed_only=True)), {"criterion-1"})
        self.assertEqual(set(code_ids(area)), {"quality-check-65", "criterion-1"})

    def test_unparsable_file_keeps_its_literal_hits(self):
        area, _ = area_with(
            'x = {"criterion_1_pass": 1}\nr.metrics(quality_check_1_ok=1\n'
        )
        self.assertEqual(set(code_ids(area)), {"criterion-1"})


if __name__ == "__main__":
    unittest.main()
