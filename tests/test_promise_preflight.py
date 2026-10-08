"""code-check (and so preflight) holds the promise block to the code before
any run (Durchstich 2026-10-06: a renamed key surfaced only after the run,
in intent-check, when the tokens were spent).

Twin pair: the clean script passes; renaming the reported key from the
declared `c1_pass` to `c1_passed` is a blocker, though the id `c1` is still
in the code. A scope naming a missing function is a blocker too.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.code_check import check_intent_ids  # noqa: E402

SCRIPT = """def evaluate(rows):
    macro = 0.7
    return {"c1_macro_f1": macro, "c1_pass": macro >= 0.6, "a1_anchor_ok": True}
"""
PROTOCOL = """Criterion [C1], admissibility [A1].

```toml
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "macro-F1 >= min_f1"
scope = ["scripts/01_measure.py:evaluate"]

[[promise]]
id = "A1"
key = "a1_anchor_ok"
sentence = "anchors hold"
scope = ["scripts/01_measure.py:evaluate"]
```
"""


def area_with(script: str, protocol: str = PROTOCOL) -> tuple[Path, Path]:
    area = Path(tempfile.mkdtemp())
    (area / "scripts").mkdir()
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    p = area / "PROTOCOL-x.md"
    p.write_text(protocol, encoding="utf-8")
    return area, p


class PromisePreflight(unittest.TestCase):
    def test_clean_twin_passes(self):
        self.assertEqual(check_intent_ids(*area_with(SCRIPT)), [])

    def test_renamed_key_blocks_though_the_id_is_present(self):
        findings = check_intent_ids(
            *area_with(SCRIPT.replace('"c1_pass"', '"c1_passed"'))
        )
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("declares key 'c1_pass'", findings[0])
        self.assertIn("c1_passed", findings[0])

    def test_keyword_argument_answers_the_key(self):
        script = "r.metrics(c1_pass=True, a1_anchor_ok=True)\ndef evaluate(rows):\n    return 1\n"
        self.assertEqual(check_intent_ids(*area_with(script)), [])

    def test_dangling_scope_blocks(self):
        findings = check_intent_ids(
            *area_with(SCRIPT.replace("def evaluate", "def score"))
        )
        self.assertTrue(any("declared scope" in f for f in findings), findings)

    def test_malformed_block_blocks(self):
        findings = check_intent_ids(
            *area_with(SCRIPT, PROTOCOL.replace('id = "A1"', 'id = "K1"'))
        )
        self.assertTrue(any("promise block" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
