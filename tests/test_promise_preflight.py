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

from labkit.checks.code_check import check_intent_ids  # noqa: E402


def intent_id_lines(area: Path, protocol: Path) -> list[str]:
    """`check_intent_ids` as the lines a gate tells."""
    return [f.line for f in check_intent_ids(area, protocol)]


SCRIPT = """def evaluate(rows):
    macro = 0.7
    m = {"c1_macro_f1": macro, "a1_anchor_ok": True}
    m["c1_pass"] = macro >= 0.6 if m["a1_anchor_ok"] else None
    return m
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
        self.assertEqual(intent_id_lines(*area_with(SCRIPT)), [])

    def test_renamed_key_blocks_though_the_id_is_present(self):
        findings = intent_id_lines(
            *area_with(SCRIPT.replace('"c1_pass"', '"c1_passed"'))
        )
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("declares key 'c1_pass'", findings[0])
        self.assertIn("c1_passed", findings[0])

    def test_keyword_argument_answers_the_key(self):
        script = (
            "a1_anchor_ok = True\n"
            "r.metrics(c1_pass=True if a1_anchor_ok else None, a1_anchor_ok=a1_anchor_ok)\n"
            "def evaluate(rows):\n    return 1\n"
        )
        self.assertEqual(intent_id_lines(*area_with(script)), [])

    def test_an_admissibility_key_never_read_is_a_warning(self):
        """[A1] computed, reported, and nothing hangs on it: the C verdict
        is reported whether the anchors held or not (probe 11, "a label
        without effect"). Static evidence, so a WARNING."""
        label_only = SCRIPT.replace(' if m["a1_anchor_ok"] else None', "")
        findings = intent_id_lines(*area_with(label_only))
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(
            findings[0].startswith("WARNING · static evidence · 01_measure.py:"),
            findings,
        )
        self.assertIn(
            "[A1] key 'a1_anchor_ok' is written but nothing decides on it", findings[0]
        )

    def test_passing_the_value_into_its_own_key_is_not_a_read(self):
        script = (
            "a1_anchor_ok = True\n"
            "r.metrics(c1_pass=True, a1_anchor_ok=a1_anchor_ok)\n"
            "row = {'a1_anchor_ok': a1_anchor_ok}\n"
            "def evaluate(rows):\n    return 1\n"
        )
        findings = intent_id_lines(*area_with(script))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("nothing decides on it", findings[0])

    def test_a_read_through_get_or_in_a_helper_counts(self):
        script = (
            "from lib.gate import admissible\n"
            "def evaluate(rows):\n"
            "    m = {'a1_anchor_ok': True, 'c1_pass': True}\n"
            "    return admissible(m)\n"
        )
        area, protocol = area_with(script)
        repo = area
        (repo / ".git").mkdir()
        (repo / "lib").mkdir()
        (repo / "lib" / "gate.py").write_text(
            "def admissible(m):\n"
            "    if not m.get('a1_anchor_ok'):\n"
            "        m['c1_pass'] = None\n"
            "    return m\n",
            encoding="utf-8",
        )
        self.assertEqual(intent_id_lines(area, protocol), [])

    def test_a_loop_over_a_key_tuple_decides(self):
        """uniagent 16: `if not all(metrics[k] for k in ADMISSIBILITY)` holds
        the verdict; the first version of the check called it unread."""
        script = (
            "ADMISSIBILITY = ('a1_anchor_ok',)\n"
            "def evaluate(rows):\n"
            "    metrics = {'a1_anchor_ok': True, 'c1_pass': True}\n"
            "    if not all(metrics[k] for k in ADMISSIBILITY):\n"
            "        metrics['c1_pass'] = None\n"
            "    return metrics\n"
        )
        self.assertEqual(intent_id_lines(*area_with(script)), [])

    def test_a_print_is_not_a_decision(self):
        script = (
            "def evaluate(rows):\n"
            "    m = {'a1_anchor_ok': True, 'c1_pass': True}\n"
            "    for k in ('a1_anchor_ok', 'c1_pass'):\n"
            "        print(k, m[k])\n"
            "    print(m['a1_anchor_ok'])\n"
            "    return m\n"
        )
        findings = intent_id_lines(*area_with(script))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("nothing decides on it", findings[0])

    def test_dangling_scope_blocks(self):
        findings = intent_id_lines(
            *area_with(SCRIPT.replace("def evaluate", "def score"))
        )
        self.assertTrue(any("declared scope" in f for f in findings), findings)

    def test_malformed_block_blocks(self):
        findings = intent_id_lines(
            *area_with(SCRIPT, PROTOCOL.replace('id = "A1"', 'id = "K1"'))
        )
        self.assertTrue(any("promise block" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
