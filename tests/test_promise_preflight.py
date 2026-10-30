"""code-check (and so preflight) holds the promise block to the code before
any run (Durchstich 2026-10-06: a renamed key surfaced only after the run,
in intent-check, when the tokens were spent).

Twin pair: the clean script passes; renaming the reported key from the
declared `criterion_1_pass` to `criterion_1_passed` is a blocker, though the id `c1` is still
in the code. A scope naming a missing function is a blocker too.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks.code_check import check_intent_ids  # noqa: E402
from labkit.formats.gate import Findings  # noqa: E402
from labkit.gates import preflight  # noqa: E402
from protocol_fixture import head  # noqa: E402


def intent_id_lines(area: Path, protocol: Path) -> list[str]:
    """`check_intent_ids` as the lines a gate tells."""
    return [f.line for f in check_intent_ids(area, protocol)]


SCRIPT = """def evaluate(rows):
    macro = 0.7
    m = {"criterion_1_macro_f1": macro, "quality_check_1_anchor_ok": True}
    m["criterion_1_pass"] = macro >= 0.6 if m["quality_check_1_anchor_ok"] else None
    return m
"""
PROTOCOL = """Criterion [criterion-1], admissibility [quality-check-1].

```toml
[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
sentence = "macro-F1 >= min_f1"
scope = ["scripts/01_measure.py:evaluate"]

[[promise]]
id = "quality-check-1"
key = "quality_check_1_anchor_ok"
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
            *area_with(SCRIPT.replace('"criterion_1_pass"', '"criterion_1_passed"'))
        )
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("declares key 'criterion_1_pass'", findings[0])
        self.assertIn("criterion_1_passed", findings[0])

    def test_keyword_argument_answers_the_key(self):
        script = (
            "quality_check_1_anchor_ok = True\n"
            "r.metrics(criterion_1_pass=True if quality_check_1_anchor_ok else None, quality_check_1_anchor_ok=quality_check_1_anchor_ok)\n"
            "def evaluate(rows):\n    return 1\n"
        )
        self.assertEqual(intent_id_lines(*area_with(script)), [])

    def test_an_admissibility_key_never_read_is_a_warning(self):
        """[quality-check-1] computed, reported, and nothing hangs on it: the C verdict
        is reported whether the anchors held or not (probe 11, "a label
        without effect"). Static evidence, so a WARNING."""
        label_only = SCRIPT.replace(' if m["quality_check_1_anchor_ok"] else None', "")
        findings = intent_id_lines(*area_with(label_only))
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(
            findings[0].startswith("WARNING · static evidence · 01_measure.py:"),
            findings,
        )
        self.assertIn(
            "[quality-check-1] key 'quality_check_1_anchor_ok' is written but nothing decides on it",
            findings[0],
        )

    def test_passing_the_value_into_its_own_key_is_not_a_read(self):
        script = (
            "quality_check_1_anchor_ok = True\n"
            "r.metrics(criterion_1_pass=True, quality_check_1_anchor_ok=quality_check_1_anchor_ok)\n"
            "row = {'quality_check_1_anchor_ok': quality_check_1_anchor_ok}\n"
            "def evaluate(rows):\n    return 1\n"
        )
        findings = intent_id_lines(*area_with(script))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("nothing decides on it", findings[0])

    def test_a_read_through_get_or_in_a_helper_counts(self):
        script = (
            "from lib.gate import admissible\n"
            "def evaluate(rows):\n"
            "    m = {'quality_check_1_anchor_ok': True, 'criterion_1_pass': True}\n"
            "    return admissible(m)\n"
        )
        area, protocol = area_with(script)
        repo = area
        (repo / ".git").mkdir()
        (repo / "lib").mkdir()
        (repo / "lib" / "gate.py").write_text(
            "def admissible(m):\n"
            "    if not m.get('quality_check_1_anchor_ok'):\n"
            "        m['criterion_1_pass'] = None\n"
            "    return m\n",
            encoding="utf-8",
        )
        self.assertEqual(intent_id_lines(area, protocol), [])

    def test_a_loop_over_a_key_tuple_decides(self):
        """uniagent 16: `if not all(metrics[k] for k in ADMISSIBILITY)` holds
        the verdict; the first version of the check called it unread."""
        script = (
            "ADMISSIBILITY = ('quality_check_1_anchor_ok',)\n"
            "def evaluate(rows):\n"
            "    metrics = {'quality_check_1_anchor_ok': True, 'criterion_1_pass': True}\n"
            "    if not all(metrics[k] for k in ADMISSIBILITY):\n"
            "        metrics['criterion_1_pass'] = None\n"
            "    return metrics\n"
        )
        self.assertEqual(intent_id_lines(*area_with(script)), [])

    def test_a_print_is_not_a_decision(self):
        script = (
            "def evaluate(rows):\n"
            "    m = {'quality_check_1_anchor_ok': True, 'criterion_1_pass': True}\n"
            "    for k in ('quality_check_1_anchor_ok', 'criterion_1_pass'):\n"
            "        print(k, m[k])\n"
            "    print(m['quality_check_1_anchor_ok'])\n"
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
            *area_with(SCRIPT, PROTOCOL.replace('id = "quality-check-1"', 'id = "K1"'))
        )
        self.assertTrue(any("promise block" in f for f in findings), findings)


class PromiseSentencesBeforeTheFreeze(unittest.TestCase):
    """preflight names the [[promise]] sentences the freeze owes before the
    freeze: a sentence still the stamp's `<…>` is a warning while the head
    is unfrozen, and the field report's blocker once frozen = true — the
    same refusal `protocol-check` gives (`promises.promise_tables_owed`).
    Twin: a written sentence warns of nothing."""

    PROSE, BLOCK = PROTOCOL.split("```toml\n")
    BLOCK = BLOCK.split("```")[0]
    STAMPED = BLOCK.replace('sentence = "macro-F1 >= min_f1"', 'sentence = "<…>"')

    def _preflight(self, block: str, *, frozen: bool = False) -> Findings:
        # the area under experiments/: preflight reads its siblings as the
        # repo's other areas; no git repo, the hooks station tells n/a
        area = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        area.mkdir(parents=True)
        (area / "scripts").mkdir()
        (area / "scripts" / "01_measure.py").write_text(SCRIPT, encoding="utf-8")
        text = self.PROSE + head(repeat_cost="high", frozen=frozen, promises=block)
        (area / "PROTOCOL-x.md").write_text(text, encoding="utf-8")
        found = Findings(tell=None)
        preflight.preflight_area(area, None, found)
        return found

    def test_a_stamped_sentence_warns_before_the_freeze(self):
        found = self._preflight(self.STAMPED)
        (warning,) = [w for w in found.warned if "[[promise]] criterion-1" in w]
        self.assertIn("still carries the stamp's `<…>` sentence", warning)
        self.assertFalse(any("[[promise]] criterion-1" in b for b in found.blocked))

    def test_a_stamped_sentence_blocks_once_frozen(self):
        found = self._preflight(self.STAMPED, frozen=True)
        self.assertTrue(
            any("[[promise]] criterion-1 still carries" in b for b in found.blocked),
            found.blocked,
        )
        self.assertFalse(
            any("[[promise]] criterion-1" in w for w in found.warned), found.warned
        )

    def test_a_written_sentence_warns_of_nothing(self):
        found = self._preflight(self.BLOCK)
        self.assertFalse(any("[[promise]]" in w for w in found.warned), found.warned)


if __name__ == "__main__":
    unittest.main()
