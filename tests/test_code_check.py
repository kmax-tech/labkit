"""Tests for code-check — the mechanical half of the preflight.

Two duties, and the second is the one that decides whether the tool gets
used: it must FIRE on a real omission, and it must stay SILENT on the shapes
that made the first three calibration rounds unusable (2026-09-10, areas
60-73) — a bare `"s65"` naming a source session, a runtime-built result
dict, a field staged by a later step.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


from labkit.checks import code_check, gate_label_scan, import_check  # noqa: E402

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
    "- **Success / failure criterion:** [criterion-1] trifft und [criterion-2] haelt.\n"
    "- **Admissibility condition:** [quality-check-1] Ausbeute > 90%.\n"
)
CLEAN_CODE = 'm = {"criterion_1_pass": True, "criterion_2_pass": False, "quality_check_1_pass": True}\n'


class TestIntentIdsAgainstCode(unittest.TestCase):
    def test_registered_id_absent_from_code_is_a_blocker(self):
        """[criterion-2] promised, never mentioned — the run reports nothing for it."""
        with AreaFixture(
            PROTOCOL_TWO,
            {
                "03_evaluate.py": 'm = {"criterion_1_pass": 1, "quality_check_1_pass": 1}\n'
            },
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 1)
        self.assertIn("[criterion-2] is registered", out)
        self.assertIn("BLOCKER", out)
        self.assertNotIn("[criterion-1] is registered", out)

    def test_all_ids_present_is_silent(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)
        self.assertNotIn("BLOCKER", out)

    def test_unregistered_metric_key_warns(self):
        """A number gets reported that no registration promised."""
        with AreaFixture(
            PROTOCOL_TWO,
            {"03_evaluate.py": CLEAN_CODE + 'm["quality_check_9_pass"] = 3\n'},
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0)  # a warning is read, not a stop (gate contract)
        self.assertIn("[quality-check-9]", out)
        self.assertIn("WARNING", out)

    def test_bare_id_string_is_not_an_unregistered_promise(self):
        """The 72er scar: source sessions named after the areas they come from.

        `"s65"` without a suffix is a name, not a metric key. Reading it as a
        promise produced three findings and no defect. The S letter is gone;
        the same bare form in today's namespace is `"quality-check-65"`.
        """
        with AreaFixture(
            PROTOCOL_TWO,
            {
                "00_prepare.py": 'SESSIONS = ["quality-check-65", "quality-check-68", "quality-check-69"]\n',
                "03_evaluate.py": CLEAN_CODE,
            },
        ) as a:
            rc, out = a.run()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("quality-check-65", out)

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
            return gate_label_scan.gate_labels(a.path)

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
            n, unreadable = code_check.write_bundle(
                a.path, a.path, a.path / "PROTOCOL-fixture.md", out
            )
            text = out.read_text(encoding="utf-8")
        self.assertEqual((n, unreadable), (2, []))
        self.assertIn("Schema facts", text)
        self.assertIn("[criterion-1] trifft", text)
        self.assertIn("criterion_1_pass", text)

    def test_an_unreadable_file_is_named_not_left_out(self):
        # it was skipped without a word and still counted (audit
        # 2026-10-28, B2)
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            bad = a.path / "scripts" / "04_bytes.py"
            bad.parent.mkdir(exist_ok=True)
            bad.write_bytes(b"\xff\xfe not utf-8")
            out = a.path / "bundle.md"
            n, unreadable = code_check.write_bundle(
                a.path, a.path, a.path / "PROTOCOL-fixture.md", out
            )
            text = out.read_text(encoding="utf-8")
        self.assertEqual(n, 2)  # the protocol and the readable script, as before
        self.assertEqual(unreadable, ["scripts/04_bytes.py"])
        self.assertIn("===== FILE: scripts/04_bytes.py =====\nnot readable:", text)

    def test_bundle_includes_gate_labels(self):
        with AreaFixture(
            PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE + 'if answer == "yes": pass\n'}
        ) as a:
            out = a.path / "bundle.md"
            code_check.write_bundle(a.path, a.path, a.path / "PROTOCOL-fixture.md", out)
            text = out.read_text(encoding="utf-8")
        self.assertIn("Gate labels", text)
        self.assertIn("Gate labels declared ([gate] labels)", text)
        self.assertIn("'yes'", text)

    def test_bundle_opens_with_severity_legend(self):
        """An agent reading the bundle must grade by the SAME definitions as
        the preflight audit; it reads only the bundle, so the legend of LAB-015
        Preflight audit before freezing is quoted from the lab standard — before
        the facts."""
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
    """The series rule (LAB-061 Sub-experiment series carry their number in the name) puts many protocols in one area. Picking the
    lexicographically first one wordlessly greened the check against s1
    while s13 was the protocol just built (2026-09-26)."""

    def _second(self, area: Path, name="PROTOCOL-s2-later.md"):
        (area / name).write_text(
            "- **Success / failure criterion:** [criterion-9] haelt.\n",
            encoding="utf-8",
        )
        return area / name

    def _main(self, argv):
        buf = io.StringIO()  # findings and refusals alike (a refusal is on stderr)
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
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
        # [criterion-9] is registered in the named protocol and in no script.
        self.assertEqual(rc, 1, out)
        self.assertIn("criterion-9", out)

    def test_single_protocol_still_needs_no_flag(self):
        with AreaFixture(PROTOCOL_TWO, {"03_evaluate.py": CLEAN_CODE}) as a:
            rc, out = self._main([a.path])
        self.assertEqual(rc, 0, out)
        self.assertIn("code-check: all clear", out)  # the gate's summary line

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


class TestSummaryLine(unittest.TestCase):
    """What the closing line says is not checked. At low repeat cost it read
    "schema, gate labels, placeholders: not checked — not owed at cost
    seconds" (the tier then called seconds), and an agent took the protocol's open fields for not owed; the
    pre-commit then refused the open promise sentence (judge probe,
    2026-10-20). Only the agent's review is not owed there."""

    def _out(self, cost: str) -> str:
        from protocol_fixture import head

        with AreaFixture(
            head(repeat_cost=cost) + PROTOCOL_TWO, {"m.py": CLEAN_CODE}
        ) as a:
            _, out = a.run()
        return out

    def test_at_low_the_open_fields_are_not_called_not_owed(self):
        out = self._out("low")
        self.assertNotIn("placeholders: not checked", out)
        self.assertIn("schema, gate labels: not checked", out)
        self.assertIn("protocol-fill <PROTOCOL> --list", out)
        # the summary is the gate's, like every gate's, and comes after the
        # note (audit 2026-10-23, C4); with blockers it ends on their list
        note_at, summary_at = (
            out.index("schema, gate labels"),
            out.index("\ncode-check: "),
        )
        self.assertLess(note_at, summary_at, out)

    def test_above_seconds_the_shipped_audit_is_named(self):
        """labkit ships no agent for the bundle (audit 2026-10-27, C12): the
        note names the preflight audit it does ship, and the bundle as one
        for an agent of the lab's own."""
        out = self._out("high")
        self.assertIn("labkit-audit <AREA> --mode preflight", out)
        self.assertIn("labkit ships none", out)
        self.assertNotIn("code-check agent", out)


if __name__ == "__main__":
    unittest.main()


class TestStampCoverage(unittest.TestCase):
    """1d: code the stamp cannot follow is a WARNING naming the line; stamped imports stay silent."""

    def _repo(self, script: str) -> tuple[Path, Path]:
        repo = Path(tempfile.mkdtemp())
        (repo / ".git").mkdir()
        (repo / "lib").mkdir()
        (repo / "lib" / "scoring.py").write_text("X = 1\n", encoding="utf-8")
        (repo / "tools").mkdir()
        (repo / "tools" / "helper.py").write_text("Y = 2\n", encoding="utf-8")
        area = repo / "experiments" / "01-x"
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "helpers.py").write_text("Z = 3\n", encoding="utf-8")
        (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
        return repo, area

    def test_stamped_imports_and_the_templates_sys_path_line_are_silent(self):
        repo, area = self._repo(
            "import sys\nfrom pathlib import Path\nREPO = Path('.')\n"
            "sys.path.insert(0, str(REPO / 'lib'))\nsys.path.insert(0, str(REPO / 'src'))\n"
            "import json\nfrom lib import scoring\nimport helpers\nfrom labkit.run import runlog\n"
        )
        self.assertEqual(import_check.stamp_coverage_findings(area, repo), [])

    def test_sys_path_edits_and_dynamic_loaders_warn_with_the_line(self):
        repo, area = self._repo(
            "import sys, importlib\n"
            "sys.path.insert(0, str(REPO / 'experiments' / '14-other' / 'scripts'))\n"
            "sys.path += [somewhere]\n"
            "m = importlib.import_module('measure_14')\n"
            "exec(open('z').read())\n"
        )
        found = [f.line for f in import_check.stamp_coverage_findings(area, repo)]
        self.assertEqual(len(found), 5, found)
        self.assertTrue(
            all(
                # static evidence says so in the line (audit 2026-10-23, C5)
                f.startswith(
                    "WARNING · static evidence · experiments/01-x/scripts/01_measure.py:"
                )
                for f in found
            )
        )
        self.assertIn(":2 · `sys.path` gains 14-other, experiments, scripts", found[0])
        self.assertIn(":2 · names area `14-other`", found[1])
        self.assertIn(":3 · `sys.path` gains a computed path", found[2])
        self.assertIn(":4 · `import_module(…)`", found[3])
        self.assertIn(":5 · `exec(…)`", found[4])
        self.assertTrue(
            all(
                "LAB-019 The stamp covers everything that determines the number" in f
                for f in found
            )
        )

    def test_a_path_string_into_another_area_warns_the_own_area_does_not(self):
        repo, area = self._repo(
            "from lib import scoring\n"
            "A14 = REPO / 'experiments/14-hotel-und-fremde-buchung/scripts/01_measure.py'\n"
            "OWN = REPO / 'experiments/01-x/scripts/01_measure.py'\n"
        )
        found = [f.line for f in import_check.stamp_coverage_findings(area, repo)]
        self.assertEqual(len(found), 1, found)
        self.assertIn(":2 · names area `14-hotel-und-fremde-buchung`", found[0])

    def test_a_loader_in_a_shared_helper_is_not_charged_to_every_area(self):
        repo, area = self._repo(
            "from lib import scoring\nP = REPO / 'experiments' / '01-x' / 'scripts'\n"
        )
        (repo / "lib" / "scoring.py").write_text(
            "import importlib.util\ndef load(p):\n    return importlib.util.spec_from_file_location('m', p)\n",
            encoding="utf-8",
        )
        self.assertEqual(
            import_check.stamp_coverage_findings(area, repo), []
        )  # own area name: silent

    def test_loading_a_file_the_stamp_covers_is_silent_a_computed_one_is_not(self):
        """The stamped 02_analyze.py loads its own 01_measure.py by
        `AREA / "scripts" / "01_measure.py"`: every fresh area with a model
        started with a WARNING from labkit's own skeleton (cold Sonnet,
        2026-10-14). The twin: a path the reader cannot resolve, or a file
        outside the area's stamp, stays a finding."""
        repo, area = self._repo("from lib import scoring\n")
        (area / "scripts" / "02_analyze.py").write_text(
            "import importlib.util\n"
            "_spec = importlib.util.spec_from_file_location('m', AREA / 'scripts' / '01_measure.py')\n"
            "_other = importlib.util.spec_from_file_location('n', AREA / 'data' / 'gen.py')\n"
            "_any = importlib.util.spec_from_file_location('o', somewhere)\n",
            encoding="utf-8",
        )
        found = [f.line for f in import_check.stamp_coverage_findings(area, repo)]
        self.assertEqual(len(found), 2, found)
        self.assertIn("02_analyze.py:3 · `spec_from_file_location(…)`", found[0])
        self.assertIn("02_analyze.py:4 · `spec_from_file_location(…)`", found[1])

    def test_an_import_outside_lib_and_src_warns(self):
        repo, area = self._repo("from tools import helper\nimport experiments\n")
        found = [f.line for f in import_check.stamp_coverage_findings(area, repo)]
        self.assertEqual(len(found), 2, found)
        self.assertIn("`tools` resolves to tools, outside lib/ and src/", found[0])
        self.assertIn("`experiments` resolves to experiments", found[1])

    def test_the_command_counts_it_as_a_warning_and_exits_0(self):
        """A warning is static evidence to read, not a stop: exit 0, as the
        gate contract says (until 0.97.1 code-check exited 1 here, and a
        calling script took evidence for a blocker — audit 2026-10-18)."""
        repo, area = self._repo("import sys\nsys.path.append(str(REPO / 'tools'))\n")
        (area / "PROTOCOL-x.md").write_text(
            "- **Protocol id:** p-0123456789abcdef\n", encoding="utf-8"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = code_check.main([str(area)])
        self.assertEqual(rc, 0)
        self.assertIn("`sys.path` gains tools", buf.getvalue())
        self.assertIn("1 warning(s)", buf.getvalue())
