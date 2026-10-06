"""code-check reads keyword-argument keys, not only string literals (2026-10-06).

`r.metrics(c1_pass=...)` reaches metrics.json as "c1_pass" without being a
string literal. Reading literals only produced a BLOCKER against correct
code ("no script mentions a 'c1' key") — found in the first promise-block
run, and the same for `k1_pass=` since the check existed.

The decisive fixture is a twin pair: the same report written as a dict
literal and as keyword arguments must get the same verdict. A local
assignment `c1_pass = ...` is not a reported key and must stay invisible.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.code_check import check_intent_ids  # noqa: E402
from labkit.intent_check import code_ids  # noqa: E402

PROTOCOL = "Criterion [C1]; admissibility [A1]; legacy [K1].\n"
LITERAL = 'r.metrics(**{"c1_pass": ok, "a1_anchor_ok": a, "k1_pass": ok})\n'
KEYWORD = "r.metrics(c1_pass=ok,\n          a1_anchor_ok=a, k1_pass=ok)\n"


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
                self.assertEqual(check_intent_ids(area, protocol), [])

    def test_keyword_hit_carries_its_line(self):
        area, _ = area_with(KEYWORD)
        hits = code_ids(area)
        self.assertEqual(hits["c1"], ["01_measure.py:1"])
        self.assertEqual(hits["a1"], ["01_measure.py:2"])

    def test_assignment_is_not_a_reported_key(self):
        area, protocol = area_with("c1_pass = ok\nr.metrics(**{'a1_anchor_ok': a, 'k1_pass': ok})\n")
        findings = check_intent_ids(area, protocol)
        self.assertEqual(len(findings), 1)
        self.assertIn("[C1] is registered, but no script mentions", findings[0])

    def test_suffixed_only_drops_a_bare_keyword(self):
        area, _ = area_with("f(s65=1, c1_pass=2)\n")
        self.assertEqual(set(code_ids(area, suffixed_only=True)), {"c1"})
        self.assertEqual(set(code_ids(area)), {"s65", "c1"})

    def test_unparsable_file_keeps_its_literal_hits(self):
        area, _ = area_with('x = {"c1_pass": 1}\nr.metrics(a1_ok=1\n')
        self.assertEqual(set(code_ids(area)), {"c1"})


if __name__ == "__main__":
    unittest.main()
