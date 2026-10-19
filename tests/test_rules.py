"""The lab standard's rules: the shipped standard against its ledger, every living
reference against both, and the checks themselves — each with a twin that must pass."""

import io
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from labkit import rules
from labkit.rules import RuleHead, RuleRow

ROOT = Path(__file__).resolve().parents[1]

#: files a reader takes as current; CHANGELOG.md and docs/usability/ are records
#: and keep the names they were written with, docs/coding-style.md is a vendored copy
LIVING = (
    sorted((ROOT / "labkit").rglob("*.py"))
    + sorted((ROOT / "labkit").rglob("*.md"))
    + sorted((ROOT / "labkit" / "templates").glob("*.template"))
    + [ROOT / "README.md", ROOT / "AGENTS.md"]
    + [p for p in sorted((ROOT / "docs").glob("*.md")) if p.name != "coding-style.md"]
)

ROWS = [
    RuleRow("LAB-001", "§1.A", "A negative finding is a claim", "active"),
    RuleRow("LAB-002", "§1.B", "Own example", "retired"),
    RuleRow("LAB-003", "", "No run without an intent paragraph", "active"),
]
DOC = """# Standard

### LAB-001 · A negative finding is a claim (2026-09-24) *(was §1.A)*

Text of one.

- **LAB-003 · No run without an intent paragraph.** A run binds to a protocol.
  Second line of three.

## Next chapter
"""


class ShippedStandard(unittest.TestCase):
    def test_every_head_matches_the_ledger(self) -> None:
        heads = rules.rule_heads(rules.STANDARD.read_text(encoding="utf-8"))
        self.assertEqual(
            rules.check_registry(rules.load_registry(rules.REGISTRY), heads, ("LAB",)),
            [],
        )

    def test_ledger_holds_every_number_once_in_order(self) -> None:
        numbers = [int(r.id.split("-")[1]) for r in rules.load_registry(rules.REGISTRY)]
        self.assertEqual(numbers, sorted(set(numbers)))
        # the seven numbers that left for the authoring lab's LOCAL ledger (0.82.0)
        self.assertEqual(
            sorted(set(range(1, max(numbers) + 1)) - set(numbers)),
            [2, 70, 73, 78, 80, 81, 99],
        )

    def test_every_living_reference_resolves_and_names_its_rule(self) -> None:
        rows = rules.load_registry(rules.REGISTRY)
        problems = []
        for path in LIVING:
            problems += rules.check_refs(
                str(path.relative_to(ROOT)), path.read_text(encoding="utf-8"), rows
            )
        self.assertEqual(problems, [])

    def test_the_living_files_are_found(self) -> None:
        # a glob that silently matched nothing would make the test above vacuous
        names = {p.name for p in LIVING}
        self.assertTrue(
            {"standard.md", "runlog.py", "experiment-preflight.agent.md", "README.md"}
            <= names
        )

    def test_standard_and_ledger_ship_with_the_package(self) -> None:
        data = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"docs/standard.md"', data)
        self.assertIn('"docs/rules.tsv"', data)


class Heads(unittest.TestCase):
    def test_all_three_head_forms_and_the_alias_mark(self) -> None:
        heads = rules.rule_heads(
            DOC + "**LAB-004 · Bold paragraph rule** *(war §4.5)*, more\n"
        )
        self.assertEqual(
            [(h.id, h.title, h.alias) for h in heads],
            [
                ("LAB-001", "A negative finding is a claim", "§1.A"),
                ("LAB-003", "No run without an intent paragraph", ""),
                ("LAB-004", "Bold paragraph rule", "§4.5"),
            ],
        )

    def test_a_bold_title_may_wrap(self) -> None:
        (h,) = rules.rule_heads(
            "- **LAB-084 · Double-coinage check — first the field, then the\n  lab.** *(was §5.2)* x\n"
        )
        self.assertEqual(
            (h.title, h.alias),
            ("Double-coinage check — first the field, then the lab", "§5.2"),
        )

    def test_heads_in_fenced_code_are_not_rules(self) -> None:
        self.assertEqual(rules.rule_heads("```\n- **LAB-009 · Example.** x\n```\n"), [])


class Registry(unittest.TestCase):
    def test_matching_document_passes(self) -> None:
        self.assertEqual(
            rules.check_registry(ROWS, rules.rule_heads(DOC), ("LAB",)), []
        )

    def test_title_drift_is_caught(self) -> None:
        heads = rules.rule_heads(
            DOC.replace("A negative finding is a claim", "A negative finding")
        )
        self.assertTrue(
            any("head says" in p for p in rules.check_registry(ROWS, heads, ("LAB",)))
        )

    def test_active_rule_without_head_is_caught(self) -> None:
        heads = [h for h in rules.rule_heads(DOC) if h.id != "LAB-003"]
        self.assertEqual(
            rules.check_registry(ROWS, heads, ("LAB",)),
            ["LAB-003: active in the ledger but no rule head states it"],
        )

    def test_a_retired_rule_stated_in_the_document_is_caught(self) -> None:
        heads = [*rules.rule_heads(DOC), RuleHead("LAB-002", "Own example", "§1.B", 40)]
        self.assertEqual(
            rules.check_registry(ROWS, heads, ("LAB",)),
            ["line 40: LAB-002 is retired in the ledger, yet stated here"],
        )

    def test_ids_of_another_prefix_are_not_held_to_this_document(self) -> None:
        rows = [*ROWS, RuleRow("LOCAL-001", "", "A house rule", "active")]
        self.assertEqual(
            rules.check_registry(rows, rules.rule_heads(DOC), ("LAB",)), []
        )

    def test_bad_status_and_duplicate_id(self) -> None:
        rows = [
            *ROWS,
            RuleRow("LAB-003", "", "Twice", "active"),
            RuleRow("LAB-005", "", "x", "gone"),
        ]
        problems = rules.check_registry(rows, rules.rule_heads(DOC), ("LAB",))
        self.assertIn("LAB-003: id given twice in the ledger", problems)
        self.assertTrue(any("LAB-005: status 'gone'" in p for p in problems))


class Ledger(unittest.TestCase):
    def test_growth_by_the_next_number_passes(self) -> None:
        self.assertEqual(
            rules.check_ledger(ROWS, [*ROWS, RuleRow("LAB-004", "", "New", "active")]),
            [],
        )

    def test_retiring_and_moving_pass(self) -> None:
        after = [ROWS[0], ROWS[1], ROWS[2]._replace(status="moved:house")]
        self.assertEqual(rules.check_ledger(ROWS, after), [])

    def test_removing_a_row_is_caught(self) -> None:
        self.assertEqual(
            rules.check_ledger(ROWS, ROWS[:2]),
            ["LAB-003: removed from the ledger — retire it, never delete"],
        )

    def test_rewriting_an_alias_is_caught(self) -> None:
        after = [ROWS[0]._replace(alias="§9.Z"), *ROWS[1:]]
        self.assertEqual(
            rules.check_ledger(ROWS, after), ["LAB-001: alias changed '§1.A' → '§9.Z'"]
        )

    def test_reviving_a_retired_id_is_caught(self) -> None:
        before = [*ROWS, RuleRow("LAB-004", "", "Old", "retired")]
        after = [*ROWS, RuleRow("LAB-004", "", "Old", "active")]
        self.assertTrue(
            rules.check_ledger(before, after)[0].startswith("LAB-004: was retired")
        )


class Refs(unittest.TestCase):
    def test_a_named_reference_passes(self) -> None:
        self.assertEqual(
            rules.check_refs(
                "f", "see LAB-003 No run without an intent paragraph.", ROWS
            ),
            [],
        )

    def test_first_two_words_are_enough(self) -> None:
        self.assertEqual(rules.check_refs("f", "(LAB-001 A negative)", ROWS), [])

    def test_a_bare_id_is_caught(self) -> None:
        self.assertEqual(
            rules.check_refs("f", "see LAB-003.", ROWS),
            ["f:1: LAB-003 without its name — write 'LAB-003 No run without an…'"],
        )

    def test_unknown_and_retired_ids_are_caught(self) -> None:
        problems = rules.check_refs(
            "f", "LAB-099 Whatever and LAB-002 Own example", ROWS
        )
        self.assertEqual(
            problems,
            [
                "f:1: LAB-099 is not in the ledger",
                "f:1: LAB-002 is retired, not active",
            ],
        )

    def test_a_retired_id_passes_when_allowed(self) -> None:
        self.assertEqual(
            rules.check_refs(
                "f", "LAB-002 Own example, retired", ROWS, ("active", "retired")
            ),
            [],
        )

    def test_ids_in_inline_code_and_heads_are_not_citations(self) -> None:
        self.assertEqual(
            rules.check_refs("f", "run `labkit.rules show LAB-003`\n" + DOC, ROWS), []
        )

    def test_an_id_as_a_string_literal_is_an_argument(self) -> None:
        self.assertEqual(rules.check_refs("f", 'rule_text("LAB-003")', ROWS), [])
        # twin: a citation inside a longer string still needs its name
        self.assertEqual(
            len(rules.check_refs("f", 'msg = "see LAB-003 for why"', ROWS)), 1
        )

    def test_a_moved_id_is_left_to_the_ledger_it_moved_to(self) -> None:
        rows = [*ROWS, RuleRow("LAB-004", "", "Alter Name", "moved:labkit")]
        self.assertEqual(rules.check_refs("f", "LAB-004 New English name", rows), [])
        # twin: the same id while active here is held to its name
        active = [*ROWS, RuleRow("LAB-004", "", "Alter Name", "active")]
        self.assertEqual(
            len(rules.check_refs("f", "LAB-004 New English name", active)), 1
        )

    def test_a_prefix_the_ledger_does_not_keep_is_left_alone(self) -> None:
        self.assertEqual(rules.check_refs("f", "CODE-008 Run the linter", ROWS), [])

    def test_a_marked_legacy_example_passes(self) -> None:
        self.assertEqual(
            rules.check_refs(
                "f", "order §2.A2 before §2.A10  (rule-ref: legacy-example)", ROWS
            ),
            [],
        )

    def test_old_ids_only_inside_the_alias_mark(self) -> None:
        self.assertEqual(rules.check_refs("f", "the rule *(was §1.A)* says", ROWS), [])
        self.assertEqual(
            rules.check_refs("f", "as §1.A says", ROWS),
            ["f:1: old id §1.A → LAB-001 A negative finding is a claim"],
        )


class Show(unittest.TestCase):
    def test_the_block_from_head_to_next_head(self) -> None:
        text = rules.rule_text("LAB-003", DOC, ROWS)
        self.assertTrue(
            text.startswith("- **LAB-003 · No run without an intent paragraph.**")
        )
        self.assertIn("Second line of three.", text)
        self.assertNotIn("Next chapter", text)

    def test_a_retired_rule_says_so(self) -> None:
        with self.assertRaisesRegex(LookupError, "LAB-002: retired"):
            rules.rule_text("LAB-002", DOC, ROWS)

    def test_an_unknown_id_raises(self) -> None:
        with self.assertRaises(KeyError):
            rules.rule_text("LAB-777", DOC, ROWS)

    def test_the_shipped_standard_answers_every_active_id(self) -> None:
        for row in rules.load_registry(rules.REGISTRY):
            if row.status == "active":
                self.assertIn(f"{row.id} · ", rules.rule_text(row.id))


class Cli(unittest.TestCase):
    def run_main(self, *argv: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = rules.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_check_passes_on_the_shipped_standard(self) -> None:
        code, out = self.run_main("check")
        self.assertEqual(
            (code, out.strip().splitlines()[-1]),
            (0, "rules: standard.md against rules.tsv: 0 problem(s)"),
        )

    def test_show_an_unknown_id_exits_1(self) -> None:
        code, out = self.run_main("show", "LAB-002")  # a number that left for LOCAL
        self.assertEqual(
            (code, out.strip()), (1, "LAB-002: no such rule in the ledger")
        )

    def test_refs_exits_1_on_a_bare_id(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "note.md"
            f.write_text("see LAB-015.\n", encoding="utf-8")
            code, out = self.run_main("refs", str(f))
        self.assertEqual(code, 1)
        self.assertTrue(re.search(r"LAB-015 without its name", out))


if __name__ == "__main__":
    unittest.main()
