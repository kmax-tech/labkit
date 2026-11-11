"""code-check reads keyword-argument keys, not only string literals.

`r.metrics(criterion_1_pass=...)` reaches metrics.json as "criterion_1_pass" without being a
string literal. Reading literals only would give a BLOCKER against correct
code ("no script names a 'c1' key literal").

The decisive fixture is a twin pair: the same report written as a dict
literal and as keyword arguments must get the same verdict. A local
assignment `criterion_1_pass = ...` is not a reported key and must stay invisible.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks.code_check import check_intent_ids  # noqa: E402
from labkit.checks.intent_check import code_ids  # noqa: E402
from labkit.formats.gate import (  # noqa: E402
    BLOCKER,
    NOT_EXECUTABLE,
    VIOLATED,
    WARNING,
    cited_rule,
)
from labkit.formats.scope_sha import SourceError  # noqa: E402

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

    def test_a_script_that_cannot_be_read_is_not_told_as_a_missing_key(self):
        """The script sets the key and is not UTF-8: the search did not see
        it, so the finding is the unreadable file, never "no script names
        the key" — that would be a blocker against correct code."""
        area, protocol = area_with(LITERAL)
        script = area / "scripts" / "01_measure.py"
        script.write_bytes(LITERAL.encode() + b"# \xff\xfe\n")
        (f,) = check_intent_ids(area, protocol, protocol.read_text(encoding="utf-8"))
        self.assertIn("cannot be read", f.text)
        self.assertNotIn("is registered, but no script names", f.text)
        self.assertEqual((f.grade, f.outcome), (BLOCKER, VIOLATED))
        with self.assertRaises(SourceError):
            code_ids(area)

    def test_an_imported_helper_that_cannot_be_read_is_the_finding(self):
        """With a `lib/` in the repo the import walk reads the helper first:
        the helper sets both keys and is not UTF-8, and the one finding
        names it."""
        repo = Path(tempfile.mkdtemp()).resolve()
        (repo / "tests").mkdir()  # what `layout_root` takes for the repo root
        (repo / "lib").mkdir()
        area = repo / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "01_measure.py").write_text(
            "from lib import report\nreport.write(r)\n", encoding="utf-8"
        )
        helper = repo / "lib" / "report.py"
        helper.write_text("def write(r):\n    " + LITERAL, encoding="utf-8")
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(PROTOCOL, encoding="utf-8")
        # the twin: read, the helper's literals answer both ids
        self.assertEqual(check_intent_ids(area, protocol, PROTOCOL), [])
        helper.write_bytes(helper.read_bytes() + b"# \xff\xfe\n")
        (f,) = check_intent_ids(area, protocol, PROTOCOL)
        self.assertIn("lib/report.py: cannot be read", f.text)
        self.assertEqual((f.grade, f.outcome), (BLOCKER, VIOLATED))

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_a_script_refused_leaves_the_check_not_executed(self):
        area, protocol = area_with(LITERAL)
        script = area / "scripts" / "01_measure.py"
        script.chmod(0)
        self.addCleanup(script.chmod, 0o644)
        (f,) = check_intent_ids(area, protocol, protocol.read_text(encoding="utf-8"))
        self.assertEqual((f.grade, f.outcome), (BLOCKER, NOT_EXECUTABLE))
        self.assertNotIn("is registered, but no script names", f.text)


if __name__ == "__main__":
    unittest.main()
