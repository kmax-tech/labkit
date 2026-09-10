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
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, REPO / "labkit" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


intent_check = _load("intent_check")
import sys
sys.modules["labkit.intent_check"] = intent_check
code_check = _load("code_check")


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
                    "\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = code_check.main([str(self.path)])
        return rc, buf.getvalue()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()


PROTOCOL_TWO = "Kriterium: [K1] trifft und [K2] haelt.\nAbbruch: [S1] bei p>.05."
CLEAN_CODE = 'm = {"k1_pass": True, "k2_pass": False, "s1_hit": 0}\n'


class TestIntentIdsAgainstCode(unittest.TestCase):

    def test_registered_id_absent_from_code_is_a_blocker(self):
        """[K2] promised, never mentioned — the run reports nothing for it."""
        with AreaFixture(PROTOCOL_TWO,
                         {"03_evaluate.py": 'm = {"k1_pass": 1, "s1_hit": 0}\n'}
                         ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 1)
        self.assertIn("[K2] is registered", out)
        self.assertIn("BLOCKER", out)
        self.assertNotIn("[K1] is registered", out)

    def test_all_ids_present_is_silent(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)
        self.assertNotIn("BLOCKER", out)

    def test_unregistered_metric_key_warns(self):
        """A number gets reported that no registration promised."""
        with AreaFixture(PROTOCOL_TWO,
                         {"03_evaluate.py": CLEAN_CODE
                          + 'm["s9_hit"] = 3\n'}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 1)
        self.assertIn("[S9]", out)
        self.assertIn("WARNING", out)

    def test_bare_id_string_is_not_an_unregistered_promise(self):
        """The 72er scar: source sessions named after the areas they come from.

        `"s65"` without a suffix is a name, not a metric key. Reading it as a
        promise produced three findings and no defect.
        """
        with AreaFixture(PROTOCOL_TWO,
                         {"00_prepare.py": 'SESSIONS = ["s65", "s68", "s69"]\n',
                          "03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("S65", out)

    def test_protocol_without_ids_is_not_audited(self):
        with AreaFixture("Kein Intent-Kennzeichen hier.",
                         {"03_evaluate.py": "x = 1\n"}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)


class TestSchemaFacts(unittest.TestCase):
    """The field table states facts; it never claims a finding of its own."""

    def test_unexplained_read_is_listed_not_accused(self):
        with AreaFixture(
                PROTOCOL_TWO,
                {"00_prepare.py": 'row = {"claim": "x"}\n',
                 "03_evaluate.py": CLEAN_CODE + 'v = row["verdict"]\n'},
                data={"items_v1.jsonl": [{"claim": "x", "id": 1}]}) as a:
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
                {"03_evaluate.py": CLEAN_CODE
                 + 'R = {}\nR["alpha"] = 1\nprint(R["alpha"])\n'},
                data={"items_v1.jsonl": [{"claim": "x"}]}) as a:
            facts = code_check.schema_facts(a.path)
        self.assertNotIn("'alpha'", facts)

    def test_meta_header_line_does_not_hide_the_real_fields(self):
        """The 68er scar: line 1 is a `_meta` header, the fields start at 2."""
        with AreaFixture(
                PROTOCOL_TWO,
                {"03_evaluate.py": CLEAN_CODE + 'v = row["claim"]\n'},
                data={"items_v1.jsonl": [{"_meta": {"about": "header"}},
                                         {"claim": "x"}]}) as a:
            facts = code_check.schema_facts(a.path)
        self.assertIn("claim", facts)
        self.assertNotIn("'claim' from", facts)

    def test_nested_keys_are_harvested(self):
        """The 68er anchors file keeps its fields inside a `pairs` list."""
        with AreaFixture(
                PROTOCOL_TWO,
                {"03_evaluate.py": CLEAN_CODE + 'v = a["must_contradict"]\n'},
                data={"anchors_v1.jsonl": [
                    {"pairs": [{"must_contradict": True}]}]}) as a:
            facts = code_check.schema_facts(a.path)
        self.assertNotIn("'must_contradict' from", facts)


class TestBundle(unittest.TestCase):

    def test_bundle_carries_protocol_scripts_and_facts(self):
        with AreaFixture(PROTOCOL_TWO,
                         {"03_evaluate.py": CLEAN_CODE}) as a:
            out = a.path / "bundle.md"
            n = code_check.write_bundle(a.path, a.path,
                                        a.path / "PROTOCOL-fixture.md", out)
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 2)
        self.assertIn("Schema facts", text)
        self.assertIn("[K1] trifft", text)
        self.assertIn("k1_pass", text)


if __name__ == "__main__":
    unittest.main()
