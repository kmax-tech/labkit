"""The check inventory: which calls count as finding sites, which rules a site
cites, which commands reach it — on synthetic modules, and once on the
package itself with a site known to cite a rule."""

import ast
import tempfile
import textwrap
import unittest
from pathlib import Path

from labkit import PACKAGE_DIR
from labkit.formats import console, findings
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
        raise SystemExit(main(argv))


    def tell(f):
        print(f"{f}: WARNING: placeholder left")
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
        start = [s for s in inv.finding_sites([CHECKS]) if s.unit.endswith(".start")]
        self.assertEqual(
            [(s.channel, s.wording) for s in start],
            [("exit", "runlog: no area given")],
        )

    def test_a_printed_warning_line_counts(self) -> None:
        s = self.sites[("labkit.checks.demo.tell", "printed")]
        self.assertEqual((s.grade, s.evidence_kind), ("WARNING", "none"))


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
                ],
                sites,
                [CHECKS],
                {"agents/demo.agent.md": "hold LAB-001 A negative finding is a claim"},
            )
        }
        first = uses["LAB-001 A negative finding is a claim"]
        self.assertEqual((first.sites, first.code_modules), ((), ()))
        self.assertEqual(first.shipped_texts, ("agents/demo.agent.md",))
        third = uses["LAB-003 No run without an intent paragraph"]
        self.assertEqual(
            [s.unit for s in third.sites], ["labkit.checks.demo.freeze_gap"]
        )
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
