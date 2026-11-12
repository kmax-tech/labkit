"""The check inventory: which calls count as finding sites, which rules a site
cites, which commands reach it — on synthetic modules, and once on the
package itself with a site known to cite a rule."""

import ast
import tempfile
import textwrap
import unittest
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console, findings, gate
from labkit.tools import check_inventory as inv
from protocol_fixture import protocol_id_of, registration_of


def module(name: str, source: str) -> inv.Module:
    """A parsed synthetic module NAME."""
    src = textwrap.dedent(source)
    path = name.replace(".", "/") + ".py"
    return inv.Module(name, path, ast.parse(src))


CHECKS = module(
    "labkit.checks.demo",
    '''
    """Cites LAB-001 A negative finding is a claim in its docstring only."""
    import warnings

    from labkit.formats.gate import STATIC_EVIDENCE, blocker

    FREEZE_RULE = "LAB-015 Preflight audit before freezing"


    def freeze_gap(name):
        """LAB-050 Analysis audit before reporting, docstring only."""
        return blocker(
            f"{name}: not frozen (LAB-003 No run without an intent paragraph)",
            fix="freeze it",
        )


    def drift(out, n):
        line = f"{n} rows drifted ({FREEZE_RULE})"
        out.warn(line, evidence_kind=STATIC_EVIDENCE)
        warnings.warn("not a gate's warning")


    def start(argv):
        if not argv:
            raise SystemExit(f"runlog: no area given")
        if argv == ["--again"]:
            raise SystemExit(with_way_out(f"runlog: {argv[0]} is a repeat", "name its parent"))
        raise SystemExit(main(argv))


    def tell(f):
        print(f"{f}: WARNING: placeholder left")


    ID_RULE = cited_rule("LAB-004 Identifiers make the intent addressable")


    def recorded(out):
        out.block("open", fix="x", rule=OPEN_RULE)
        out.block("cited", fix="x", rule=cited_rule("LAB-034 Null condition in the same run"))
        out.block("constant", fix="x", rule=ID_RULE)
        held = TECHNICAL_RULE
        out.block("local", fix="x", rule=held)
        out.block("passed", fix="x", rule=out.rule)
        out.block("none", fix="x")
    ''',
)

GATE = module(
    "labkit.gates.demo_gate",
    """
    from labkit.checks import demo


    def cli():
        return demo.freeze_gap("p")
    """,
)


class FindingSites(unittest.TestCase):
    def setUp(self) -> None:
        self.sites = {(s.unit, s.channel): s for s in inv.finding_sites([CHECKS, GATE])}

    def test_a_blocker_cites_the_rule_in_its_message_not_in_the_docstring(self) -> None:
        s = self.sites[("labkit.checks.demo.freeze_gap", "finding")]
        self.assertEqual(
            (s.grade, s.evidence_kind, s.rules), ("BLOCKER", "GUARANTEED", ("LAB-003",))
        )
        self.assertEqual(
            s.wording, "{…}: not frozen (LAB-003 No run without an intent paragraph)"
        )

    def test_a_warning_reads_its_local_message_and_the_module_constant(self) -> None:
        s = self.sites[("labkit.checks.demo.drift", "finding")]
        self.assertEqual(
            (s.grade, s.evidence_kind, s.rules),
            ("WARNING", "STATIC_EVIDENCE", ("LAB-015",)),
        )
        self.assertEqual(s.wording, "{…} rows drifted ({…})")

    def test_the_stdlib_warning_is_no_site(self) -> None:
        drift = [s for s in inv.finding_sites([CHECKS]) if s.unit.endswith(".drift")]
        self.assertEqual(len(drift), 1)

    def test_an_exit_with_a_message_counts_an_exit_code_does_not(self) -> None:
        """A message given directly or through `with_way_out` is a refusal;
        a main's exit code passed through is none."""
        start = [s for s in inv.finding_sites([CHECKS]) if s.unit.endswith(".start")]
        self.assertEqual(
            [(s.channel, s.wording) for s in start],
            [("exit", "runlog: no area given"), ("exit", "runlog: {…} is a repeat")],
        )

    def test_a_printed_warning_line_counts(self) -> None:
        s = self.sites[("labkit.checks.demo.tell", "printed")]
        self.assertEqual((s.grade, s.evidence_kind), ("WARNING", "none"))


class RecordedRule(unittest.TestCase):
    """The rule tables count the assignment a call records as data
    (`FindingSite.assignment`), never an id its message only cites."""

    def test_each_form_of_the_rule_argument_reads_as_its_assignment(self) -> None:
        sites = [s for s in inv.finding_sites([CHECKS]) if s.unit.endswith(".recorded")]
        self.assertEqual(
            [(s.wording, s.assignment) for s in sites],
            [
                ("open", gate.OPEN_ASSIGNMENT),
                ("cited", "LAB-034"),
                ("constant", "LAB-004"),
                ("local", gate.TECHNICAL_CONTRACT),
                ("passed", "variable"),
                ("none", inv.NOT_RECORDED),
            ],
        )

    def test_an_open_cause_is_every_open_rule_no_site_records_itself(self) -> None:
        causes = module(
            "labkit.checks.causes",
            """
            from labkit.formats import gate
            from labkit.formats.gate import OPEN_RULE, TECHNICAL_RULE

            RULES = {"unfrozen": OPEN_RULE}


            def gap(recorded):
                if recorded is None:
                    return ("no block", OPEN_RULE)
                return ("old digest", TECHNICAL_RULE)


            def told(out, exc, why):
                out.block("open site", fix="x", rule=OPEN_RULE)
                held = gate.OPEN_RULE
                out.block("open through a local name", fix="x", rule=held)
                out.block("one arm", fix="x", rule=OPEN_RULE if exc else TECHNICAL_RULE)
                out.block("passed", fix="x", rule=why.rule)
            """,
        )
        self.assertEqual(
            [(c.line, c.unit) for c in inv.open_causes([causes])],
            [
                (5, "labkit.checks.causes"),  # a table at module level
                (10, "labkit.checks.causes.gap"),  # a cause's value
                (18, "labkit.checks.causes.told"),  # one arm of a condition
            ],
        )
        # the twin: the two open sites are sites, not causes
        sites = inv.finding_sites([causes])
        self.assertEqual(
            [s.assignment for s in sites],
            [gate.OPEN_ASSIGNMENT, gate.OPEN_ASSIGNMENT, "variable", "variable"],
        )
        text = inv.render_inventory(sites, [], {}, inv.open_causes([causes]))
        self.assertIn(
            "Open assignments in all: 5 — at the 2 open sites and at 3 causes", text
        )
        self.assertIn("| `labkit/checks/causes.py:10` | `checks.causes.gap` |", text)

    def test_a_rule_only_cited_in_the_message_is_not_recorded(self) -> None:
        (s,) = [
            s for s in inv.finding_sites([CHECKS]) if s.unit.endswith(".freeze_gap")
        ]
        self.assertEqual((s.rules, s.assignment), (("LAB-003",), inv.NOT_RECORDED))


class CheckOutcome(unittest.TestCase):
    """The outcome column (`site_outcome`): a constant the call states, a
    value computed at run time, else what `gate.derived_outcome` gives for
    the evidence kind and the rule assignment the scan read."""

    OUTCOMES = module(
        "labkit.checks.outcomes",
        """
        from labkit.formats.gate import (
            GUARANTEED, NOT_EXECUTABLE, OPEN_RULE, STATIC_EVIDENCE, TECHNICAL_RULE,
            cited_rule, outcome_of_failed_read,
        )


        def told(out, exc, why, kind):
            out.block("rule", fix="x", rule=cited_rule("LAB-034 Null condition in the same run"))
            out.block("contract", fix="x", rule=TECHNICAL_RULE)
            out.block("open", fix="x", rule=OPEN_RULE)
            out.block("no assignment", fix="x")
            out.warn("hint", evidence_kind=STATIC_EVIDENCE, rule=TECHNICAL_RULE)
            out.warn("hint, rule passed in", evidence_kind=STATIC_EVIDENCE, rule=why.rule)
            out.block("unrun", fix="x", stated_outcome=NOT_EXECUTABLE, rule=OPEN_RULE)
            out.block("read", fix="x", stated_outcome=outcome_of_failed_read(exc), rule=TECHNICAL_RULE)
            out.block("stated nothing", fix="x", stated_outcome=None, rule=TECHNICAL_RULE)
            out.block("rule passed in", fix="x", rule=why.rule)
            out.warn("kind passed in", evidence_kind=kind, rule=TECHNICAL_RULE)
            raise SystemExit("refused")
        """,
    )

    def test_each_site_reads_as_its_outcome(self) -> None:
        sites = sorted(inv.finding_sites([self.OUTCOMES]), key=lambda s: s.line)
        self.assertEqual(
            [(s.wording, s.outcome) for s in sites],
            [
                ("rule", gate.VIOLATED),
                ("contract", gate.VIOLATED),
                ("open", gate.DEVIATION),
                ("no assignment", inv.REFUSED),
                ("hint", gate.SUSPECTED),
                ("hint, rule passed in", gate.SUSPECTED),
                ("unrun", gate.NOT_EXECUTABLE),
                ("read", inv.COMPUTED),
                ("stated nothing", gate.VIOLATED),
                ("rule passed in", "variable"),
                ("kind passed in", "variable"),
                ("refused", "none"),
            ],
        )

    def test_the_table_and_the_count_line_tell_it(self) -> None:
        text = inv.render_inventory(inv.finding_sites([self.OUTCOMES]), [], {}, [])
        self.assertIn(
            "Check outcome of the 11 gate findings (`GateFinding.outcome`): "
            "3 violated, 1 deviation, 2 suspected, 1 not executable, 1 computed, "
            "2 variable, 1 refused",
            text,
        )
        self.assertIn("| Rule (data) | Check outcome | Cited in the text |", text)
        row = next(line for line in text.splitlines() if line.endswith("| unrun |"))
        self.assertIn("| open assignment | not executable |", row)

    def test_the_package_has_every_kind_of_outcome(self) -> None:
        """A known positive on the real source, and the sum: every gate
        finding has an outcome, an exit and a printed line none."""
        sites = inv.finding_sites(inv.read_modules(PACKAGE_DIR))
        found = {s.outcome for s in sites if s.channel == "finding"}
        self.assertEqual(found, {*gate.OUTCOMES, inv.COMPUTED, "variable"})
        self.assertEqual({s.outcome for s in sites if s.channel != "finding"}, {"none"})
        (read,) = [
            s for s in sites if s.unit == "labkit.checks.code_scan.unreadable_source"
        ]
        self.assertEqual(read.outcome, inv.COMPUTED)


class Reach(unittest.TestCase):
    def test_a_command_reaches_a_check_through_a_module_alias(self) -> None:
        graph = inv.call_graph([CHECKS, GATE])
        reach = inv.reaching_commands(
            graph, {"demo-gate": "labkit.gates.demo_gate.cli"}
        )
        self.assertEqual(reach["labkit.checks.demo.freeze_gap"], {"demo-gate"})
        self.assertNotIn("labkit.checks.demo.drift", reach)

    def test_entry_points_read_the_console_scripts(self) -> None:
        pyproject = '[project.scripts]\nfinalize = "labkit.gates.finalize:cli"\n'
        self.assertEqual(
            inv.entry_points(pyproject), {"finalize": "labkit.gates.finalize.cli"}
        )


class RuleUses(unittest.TestCase):
    def test_each_rule_names_its_sites_other_code_and_shipped_texts(self) -> None:
        sites = inv.finding_sites([CHECKS])
        uses = {
            u.rule: u
            for u in inv.rule_uses(
                [
                    ("LAB-001", "A negative finding is a claim"),
                    ("LAB-003", "No run without an intent paragraph"),
                    ("LAB-015", "Preflight audit before freezing"),
                    ("LAB-004", "Identifiers make the intent addressable"),
                ],
                sites,
                [CHECKS],
                {"agents/demo.agent.md": "hold LAB-001 A negative finding is a claim"},
            )
        }
        first = uses["LAB-001 A negative finding is a claim"]
        self.assertEqual((first.sites, first.code_modules), ((), ()))
        self.assertEqual(first.shipped_texts, ("agents/demo.agent.md",))
        # a site counts for the rule it records as data, not one its message cites
        third = uses["LAB-003 No run without an intent paragraph"]
        self.assertEqual(third.sites, ())
        recorded = uses["LAB-004 Identifiers make the intent addressable"]
        self.assertEqual([s.wording for s in recorded.sites], ["constant"])
        # the constant stands outside every site's call: other code
        freeze = uses["LAB-015 Preflight audit before freezing"]
        self.assertEqual(freeze.code_modules, ("labkit.checks.demo",))


class ThePackage(unittest.TestCase):
    """A known positive on the real source: report-check's registration
    blocker cites its rule and report-check reaches it."""

    def test_the_registration_blocker_is_found_and_reached(self) -> None:
        text = inv.inventory(PACKAGE_DIR)
        row = next(
            line
            for line in text.splitlines()
            if "`gates.report_check._registration_at`" in line
            and "recorded no commit" in line
        )
        self.assertIn("| LAB-003 |", row)
        self.assertIn("report-check", row)

    def test_out_writes_the_file_and_a_wrong_line_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "checks.md"
            self.assertEqual(inv.main(["--out", str(out)]), 0)
            self.assertTrue(
                out.read_text(encoding="utf-8").startswith("# Check inventory")
            )
        with self.assertRaises(console.Refused):
            inv.main(["--bogus"])


class AuditRules(unittest.TestCase):
    """`--records`: the audit findings of a lab repo per rule, and every
    `new class` finding listed for review."""

    def test_findings_are_counted_by_rule_and_new_classes_listed(self) -> None:
        experiments = Path(tempfile.mkdtemp()) / "experiments"
        area = experiments / "01-x"
        area.mkdir(parents=True)
        rows = [
            (
                "BLOCKER",
                "BLOCKER · a.py:1 · implementation · x · y · LAB-038 What the prompt demands · z",
            ),
            (
                "WARNING",
                "WARNING · b.py:2 · statement · a claim wider than the run · y · new class · z",
            ),
        ]
        findings.write(
            area,
            "preflight",
            "opus",
            "abc123def456",
            "b10c0000000a",
            (1, 1, 0),
            rows,
            registration=registration_of(area),
            protocol_id=protocol_id_of(area),
        )
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "checks.md"
            inv.main(["--records", str(experiments), "--out", str(out)])
            text = out.read_text(encoding="utf-8")
        self.assertIn("2 findings in 1 audit records, 1 of them `new class`", text)
        self.assertIn("| LAB-038 | 1 |", text)
        self.assertRegex(
            text,
            r"\| `01-x/audits/[^`]+-preflight\.toml#2` \| WARNING \| statement \| open \| WARNING · b\.py:2",
        )

    def test_a_missing_folder_and_a_doubled_option_are_refused(self) -> None:
        for argv in (["--records", "/no/such/folder"], ["--out", "a", "--out", "b"]):
            with self.subTest(argv=argv):
                with self.assertRaises(console.Refused):
                    inv.main(argv)


if __name__ == "__main__":
    unittest.main()
