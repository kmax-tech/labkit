"""Tests for code-check — the mechanical half of the preflight.

Two duties, and the second is the one that decides whether the tool gets
used: it must FIRE on a real omission, and it must stay SILENT on the shapes
that made the first three calibration rounds unusable (2026-09-10, areas
60-73) — a bare `"s65"` naming a source session, a runtime-built result
dict, a field staged by a later step.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "labkit" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


intent_check = _load("intent_check")
sys.modules["labkit.intent_check"] = intent_check
code_check = _load("code_check")
rules = code_check.rules  # the module the bundle quotes from


class AreaFixture:
    """A throwaway experiment area: protocol, scripts, materialized data."""

    def __init__(self, protocol: str, scripts: dict, data: dict | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        (self.path / "scripts").mkdir()
        (self.path / "PROTOCOL-fixture.md").write_text(protocol, encoding="utf-8")
        for name, body in scripts.items():
            (self.path / "scripts" / name).write_text(body, encoding="utf-8")
        if data:
            (self.path / "data" / "prepared").mkdir(parents=True)
            for name, rows in data.items():
                (self.path / "data" / "prepared" / name).write_text(
                    "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
                )

    def run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = code_check.main([str(self.path)])
        return rc, buf.getvalue()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()


PROTOCOL_TWO = (
    "- **Success / failure criterion:** [C1] trifft und [C2] haelt.\n"
    "- **Admissibility condition:** [A1] Ausbeute > 90%.\n"
)
CLEAN_CODE = 'm = {"c1_pass": True, "c2_pass": False, "a1_pass": True}\n'


class TestIntentIdsAgainstCode(unittest.TestCase):
    def test_registered_id_absent_from_code_is_a_blocker(self):
        """[C2] promised, never mentioned — the run reports nothing for it."""
        with AreaFixture(
            PROTOCOL_TWO, {"03_evaluate.py": 'm = {"c1_pass": 1, "a1_pass": 1}\n'}
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 1)
        self.assertIn("[C2] is registered", out)
        self.assertIn("BLOCKER", out)
        self.assertNotIn("[C1] is registered", out)

    def test_all_ids_present_is_silent(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)
        self.assertNotIn("BLOCKER", out)

    def test_unregistered_metric_key_warns(self):
        """A number gets reported that no registration promised."""
        with AreaFixture(
            PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE + 'm["a9_pass"] = 3\n'}
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 1)
        self.assertIn("[A9]", out)
        self.assertIn("WARNING", out)

    def test_bare_id_string_is_not_an_unregistered_promise(self):
        """The 72er scar: source sessions named after the areas they come from.

        `"s65"` without a suffix is a name, not a metric key. Reading it as a
        promise produced three findings and no defect. The S letter is gone;
        the same bare form in today's namespace is `"a65"`.
        """
        with AreaFixture(
            PROTOCOL_TWO,
            {
                "00_prepare.py": 'SESSIONS = ["a65", "a68", "a69"]\n',
                "03_evaluate.py": CLEAN_CODE,
            },
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("A65", out)

    def test_protocol_without_ids_is_not_audited(self):
        with AreaFixture(
            "Kein Intent-Kennzeichen hier.", {"03_evaluate.py": "x = 1\n"}
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)


class TestSchemaFacts(unittest.TestCase):
    """The field table states facts; it never claims a finding of its own."""

    def test_unexplained_read_is_listed_not_accused(self):
        with AreaFixture(
            PROTOCOL_TWO,
            {
                "00_prepare.py": 'row = {"claim": "x"}\n',
                "03_evaluate.py": CLEAN_CODE + 'v = row["verdict"]\n',
            },
            data={"items_v1.jsonl": [{"claim": "x", "id": 1}]},
        ) as a:
            facts = code_check.schema_facts(a.path)
            rc, out = a.run()
        self.assertIn("'verdict'", facts)
        self.assertIn("not in the area's data", facts)
        self.assertNotIn("BLOCKER", facts)
        self.assertEqual(rc, 0, "schema facts must not fail the run")

    def test_runtime_built_dict_is_not_listed(self):
        """The 65er scar: `R["one|forbidden"]` is a result dict, not a row."""
        with AreaFixture(
            PROTOCOL_TWO,
            {
                "03_evaluate.py": CLEAN_CODE
                + 'R = {}\nR["alpha"] = 1\nprint(R["alpha"])\n'
            },
            data={"items_v1.jsonl": [{"claim": "x"}]},
        ) as a:
            facts = code_check.schema_facts(a.path)
        self.assertNotIn("'alpha'", facts)

    def test_meta_header_line_does_not_hide_the_real_fields(self):
        """The 68er scar: line 1 is a `_meta` header, the fields start at 2."""
        with AreaFixture(
            PROTOCOL_TWO,
            {"03_evaluate.py": CLEAN_CODE + 'v = row["claim"]\n'},
            data={"items_v1.jsonl": [{"_meta": {"about": "header"}}, {"claim": "x"}]},
        ) as a:
            facts = code_check.schema_facts(a.path)
        self.assertIn("claim", facts)
        self.assertNotIn("'claim' from", facts)

    def test_nested_keys_are_harvested(self):
        """The 68er anchors file keeps its fields inside a `pairs` list."""
        with AreaFixture(
            PROTOCOL_TWO,
            {"03_evaluate.py": CLEAN_CODE + 'v = a["must_contradict"]\n'},
            data={"anchors_v1.jsonl": [{"pairs": [{"must_contradict": True}]}]},
        ) as a:
            facts = code_check.schema_facts(a.path)
        self.assertNotIn("'must_contradict' from", facts)


class TestGateLabels(unittest.TestCase):
    """Gate-label extraction — facts for the agent, not findings."""

    def _labels(self, scripts):
        with AreaFixture(PROTOCOL_TWO, scripts) as a:
            return code_check.gate_labels(a.path)

    def test_string_literal_in_equality(self):
        facts = self._labels(
            {"03_evaluate.py": CLEAN_CODE + 'if answer == "yes": pass\n'}
        )
        self.assertIn("'yes'", facts)
        self.assertIn("answer", facts)

    def test_string_set_in_membership(self):
        facts = self._labels(
            {"03_evaluate.py": CLEAN_CODE + 'if answer in {"a", "b"}: pass\n'}
        )
        self.assertIn("'a'", facts)
        self.assertIn("'b'", facts)
        self.assertIn("answer", facts)

    def test_named_constant_resolved_same_module(self):
        code = CLEAN_CODE + 'VALID = {"yes", "no"}\n' + "if answer in VALID: pass\n"
        facts = self._labels({"03_evaluate.py": code})
        self.assertIn("VALID", facts)
        self.assertIn("[Name, resolved:", facts)
        self.assertIn("'yes'", facts)
        self.assertIn("'no'", facts)

    def test_named_constant_imported(self):
        code = (
            CLEAN_CODE
            + "from labels import VALID_ANSWERS\n"
            + "if answer in VALID_ANSWERS: pass\n"
        )
        facts = self._labels({"03_evaluate.py": code})
        self.assertIn("VALID_ANSWERS", facts)
        self.assertIn("[Name, imported from labels]", facts)

    def test_named_constant_unresolved(self):
        code = CLEAN_CODE + "if answer in MYSTERY: pass\n"
        facts = self._labels({"03_evaluate.py": code})
        self.assertIn("MYSTERY", facts)
        self.assertIn("[Name, unresolved]", facts)

    def test_attribute_constant(self):
        code = CLEAN_CODE + "if answer == LABELS.SUPPORTS: pass\n"
        facts = self._labels({"03_evaluate.py": code})
        self.assertIn("LABELS.SUPPORTS", facts)

    def test_producer_script_not_extracted(self):
        facts = self._labels(
            {"00_prepare.py": 'if x == "yes": pass\n', "03_evaluate.py": CLEAN_CODE}
        )
        self.assertNotIn('"yes"', facts)

    def test_infra_variable_filtered(self):
        facts = self._labels(
            {"03_evaluate.py": CLEAN_CODE + 'if mode == "dry-run": pass\n'}
        )
        self.assertNotIn('"dry-run"', facts)
        self.assertIn("filtered as infrastructure", facts)
        self.assertIn("mode", facts.split("filtered")[1])

    def test_file_extension_literal_filtered(self):
        facts = self._labels(
            {"03_evaluate.py": CLEAN_CODE + 'if ext in {".json", ".csv"}: pass\n'}
        )
        self.assertNotIn('".json"', facts)
        self.assertNotIn('".csv"', facts)

    def test_get_default(self):
        facts = self._labels(
            {"03_evaluate.py": CLEAN_CODE + 'v = mapping.get(answer, "unknown")\n'}
        )
        self.assertIn("'unknown'", facts)

    def test_filter_summary_count(self):
        code = CLEAN_CODE + 'if mode == "a": pass\n' + 'if mode == "b": pass\n'
        facts = self._labels({"03_evaluate.py": code})
        self.assertIn("2 comparison(s) filtered", facts)


class TestBundle(unittest.TestCase):
    def test_bundle_carries_protocol_scripts_and_facts(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            out = a.path / "bundle.md"
            n = code_check.write_bundle(
                a.path, a.path, a.path / "PROTOCOL-fixture.md", out
            )
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 2)
        self.assertIn("Schema facts", text)
        self.assertIn("[C1] trifft", text)
        self.assertIn("c1_pass", text)

    def test_bundle_includes_gate_labels(self):
        with AreaFixture(
            PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE + 'if answer == "yes": pass\n'}
        ) as a:
            out = a.path / "bundle.md"
            code_check.write_bundle(a.path, a.path, a.path / "PROTOCOL-fixture.md", out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("Gate labels", text)
        self.assertIn("'yes'", text)

    def test_bundle_opens_with_severity_legend(self):
        """Both audit agents must grade by the SAME definitions; the
        code-check agent reads only the bundle, so the legend of LAB-015 Preflight
        audit before freezing is quoted from the lab standard — before the facts."""
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            out = a.path / "bundle.md"
            code_check.write_bundle(a.path, a.path, a.path / "PROTOCOL-fixture.md", out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("Severity legend", text)
        self.assertIn(
            rules.paragraph("LAB-015", "**Severity levels**"), text
        )  # verbatim, not a copy
        for grade in ("**BLOCKER**", "**WARNING**", "**NOTE**"):
            self.assertIn(grade, text)
        self.assertLess(text.index("Severity legend"), text.index("Schema facts"))


class TestProtocolChoice(unittest.TestCase):
    """The series rule (LAB-061 Subexperiment-Serien tragen ihre Nummer) puts many protocols in one area. Picking the
    lexicographically first one wordlessly greened the check against s1
    while s13 was the protocol just built (2026-09-26)."""

    def _second(self, area: Path, name="PROTOCOL-s2-later.md"):
        (area / name).write_text(
            "- **Success / failure criterion:** [C9] haelt.\n", encoding="utf-8"
        )
        return area / name

    def _main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = code_check.main([str(a) for a in argv])
        return rc, buf.getvalue()

    def test_several_protocols_refuse_instead_of_picking(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            self._second(a.path)
            rc, out = self._main([a.path])
        self.assertEqual(rc, 2, out)
        self.assertIn("--protocol", out)
        self.assertIn("PROTOCOL-s2-later.md", out)
        self.assertIn("PROTOCOL-fixture.md", out)
        self.assertNotIn("intent-ids:", out)

    def test_named_protocol_is_the_one_checked(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            second = self._second(a.path)
            rc, out = self._main([a.path, "--protocol", second])
        # [C9] is registered in the named protocol and in no script.
        self.assertEqual(rc, 1, out)
        self.assertIn("C9", out)

    def test_single_protocol_still_needs_no_flag(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = self._main([a.path])
        self.assertEqual(rc, 0, out)
        self.assertIn("intent-ids:", out)

    def test_flags_may_come_in_either_order(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            second = self._second(a.path)
            bundle = a.path / "bundle.md"
            rc, out = self._main([a.path, "--bundle", bundle, "--protocol", second])
        self.assertEqual(rc, 1, out)
        self.assertIn("bundle:", out)

    def test_missing_protocol_file_is_an_error_not_a_fallback(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = self._main([a.path, "--protocol", a.path / "nope.md"])
        self.assertEqual(rc, 2, out)
        self.assertIn("no such protocol", out)


if __name__ == "__main__":
    unittest.main()
