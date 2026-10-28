"""The standard contract: one table of what each tier owes, read by every
consumer — held here to the standard's own statements (LAB-017 The number
of audits follows the cost tier) and to the homes it names (the template's
labels, the shipped templates, the check every skeleton stamps)."""

from __future__ import annotations

import unittest
from pathlib import Path

from labkit.formats import protocol_block, standard_contract as sc
from labkit.tools import scaffold
from labkit.formats.protocol_check import FIELDS


class Lanes(unittest.TestCase):
    def test_low_owes_the_registration_not_the_freeze(self):
        ln = sc.lane("low")
        self.assertEqual(
            (ln.freeze, ln.registration, ln.audits, ln.cut),
            (False, True, ("analysis",), "low"),
        )
        self.assertEqual(
            (ln.probe_allowed, ln.foreground, ln.provenance), (False, True, True)
        )

    def test_minutes_and_hours_owe_the_freeze_with_its_audit(self):
        for cost in ("high",):
            with self.subTest(cost):
                ln = sc.lane(cost)
                self.assertEqual(
                    (ln.repeat_cost, ln.freeze, ln.registration, ln.audits, ln.cut),
                    (cost, True, False, ("preflight", "analysis"), "full"),
                )
                self.assertEqual(
                    (ln.probe_allowed, ln.foreground, ln.provenance),
                    (True, False, False),
                )

    def test_an_unfilled_cost_reads_as_hours(self):
        self.assertEqual(sc.lane(None), sc.lane("high"))
        self.assertEqual(sc.effective_repeat_cost(None), "high")

    def test_a_tier_the_head_cannot_carry_is_refused(self):
        with self.assertRaises(ValueError):
            sc.lane("days")

    def test_the_tiers_are_the_heads(self):
        self.assertEqual((sc.LOW, sc.HIGH), protocol_block.REPEAT_COSTS)


class Registration(unittest.TestCase):
    def test_a_count_registers_its_question_a_bar_its_criterion_and_reference(self):
        """Standard 0.22: the registration follows what the number asserts
        (`kind`), not the model technology — a RandomForest at low repeat cost owed
        nothing but its question (fifth haiku round, t5 and t18)."""
        self.assertEqual(
            sc.registration_fields("compute", False), ("Question / hypothesis",)
        )
        bar = (
            "Question / hypothesis",
            "Success / failure criterion",
            "Admissibility condition",
            "Null condition / anchors",
        )
        self.assertEqual(sc.registration_fields("fit", False), bar)
        self.assertEqual(sc.registration_fields("apply", False), bar)
        self.assertEqual(sc.registration_fields("apply", True), bar + ("Data profile",))
        self.assertEqual(sc.registration_fields("fit", True), bar + ("Data profile",))

    def test_an_unknown_kind_is_refused_not_read_as_a_count(self):
        for bad in ("Count", "estimator", "", "llm"):
            with self.subTest(bad), self.assertRaises(ValueError):
                sc.registration_fields(bad, False)
            with self.subTest(bad), self.assertRaises(ValueError):
                sc.skeleton("low", bad, False)
        self.assertFalse(sc.has_bar("compute"))
        self.assertTrue(sc.has_bar("fit") and sc.has_bar("apply"))

    def test_the_labels_are_the_templates_must_fields_of_the_low_cut(self):
        by_label = {f.label: f for f in FIELDS}
        for label in sc.registration_fields("apply", True):
            with self.subTest(label):
                self.assertIn(label, by_label)
                self.assertEqual(by_label[label].level, "must")
                self.assertIn(by_label[label].low_cut, ("l", "lb", "lm"))


class TheRelease(unittest.TestCase):
    def test_the_description_names_a_probe_only_where_one_precedes_the_run(self):
        for cost in (None, "low", "high"):
            for kind, model in (("compute", False), ("fit", False), ("apply", True)):
                with self.subTest(repeat_cost=cost, kind=kind, model=model):
                    first = sc.describe(cost, kind, model)[0]
                    owed = (
                        sc.skeleton(cost, kind, model).probe
                        and sc.lane(cost).probe_allowed
                    )
                    self.assertEqual("--probe stage before the run" in first, owed)
                    if not owed:
                        self.assertIn("the run is the instrument check", first)

    def test_the_check_command_is_the_areas_analysis_script(self):
        self.assertEqual(
            sc.check_command(Path("/x/01-a")),
            ["/x/01-a/scripts/02_analyze.py", "--check"],
        )


class Skeletons(unittest.TestCase):
    def test_which_skeleton_an_area_gets(self):
        """By the kind, at every tier: a fit at low repeat cost got the count's
        skeleton until 0.104 (fifth haiku round)."""
        for cost in ("low", "high", None):
            with self.subTest(repeat_cost=cost):
                self.assertIs(sc.skeleton(cost, "compute", False), sc.COMPUTE)
                self.assertIs(sc.skeleton(cost, "fit", False), sc.ESTIMATOR)
                self.assertIs(sc.skeleton(cost, "fit", True), sc.ESTIMATOR)
                self.assertIs(sc.skeleton(cost, "apply", True), sc.MODEL)
                self.assertIs(sc.skeleton(cost, "apply", False), sc.ESTIMATOR)

    def test_every_skeleton_stamps_the_check_from_a_shipped_template(self):
        for sk in sc.SKELETONS:
            with self.subTest(sk.instrument):
                dests = [dest for _, dest in sk.scripts]
                self.assertIn(sc.CHECK_SCRIPT.name, dests)
                self.assertEqual(len(dests), len(set(dests)))
                for tmpl, _ in sk.scripts:
                    self.assertTrue((scaffold.TEMPLATES / tmpl).is_file(), tmpl)
                self.assertTrue((scaffold.TEMPLATES / sk.test).is_file(), sk.test)

    def test_only_the_count_has_no_probe_stage(self):
        self.assertEqual(
            [sk.instrument for sk in sc.SKELETONS if not sk.probe], ["compute"]
        )

    def test_every_flag_of_a_run_opening_stamp_is_a_run_or_a_no_run_stage(self):
        """NO_RUN_FLAGS is the one list of the stamps' stages that open no
        run; the hook knew three of five, and `00_prepare.py --audit`, which
        the producer documents as no write, was gated like a run start
        (labkit-paper area 15, round 2, D7). A flag a run-opening stamp adds
        must be put in one of the two lists here."""
        import re

        from labkit.gates import claude_hooks
        from labkit.run import lanes

        run_flags = {"--seed", "--repeat-of", "--model"}  # each starts a run
        defines = re.compile(r"add_argument\(\s*\"(--[\w-]+)\"")
        sources = [Path(lanes.__file__)] + [
            p
            for p in sorted(scaffold.TEMPLATES.glob("*.py.template"))
            if claude_hooks.OPENS_RUN.search(p.read_text(encoding="utf-8"))
        ]
        seen: set[str] = set()
        for path in sources:
            flags = set(defines.findall(path.read_text(encoding="utf-8")))
            self.assertEqual(flags - run_flags - set(sc.NO_RUN_FLAGS), set(), path)
            seen |= flags
        self.assertEqual(set(sc.NO_RUN_FLAGS) - seen, set())
        self.assertEqual(run_flags - seen, set())


class Described(unittest.TestCase):
    def test_every_tier_names_its_check_and_what_comes_before_the_run(self):
        for cost, kind, model in (
            (None, "fit", False),
            ("low", "compute", False),
            ("low", "apply", True),
        ):
            with self.subTest(repeat_cost=cost, kind=kind, model=model):
                text = "\n".join(sc.describe(cost, kind, model))
                self.assertIn("scripts/02_analyze.py --check", text)
                self.assertIn(
                    "registration written" if cost == "low" else "frozen = true",
                    text,
                )
        self.assertIn(
            "Success / failure criterion",
            "\n".join(sc.describe("low", "apply", True)),
        )
        self.assertIn(
            "Success / failure criterion",
            "\n".join(sc.describe("low", "fit", False)),
        )
        self.assertNotIn(
            "Success / failure", "\n".join(sc.describe("low", "compute", False))
        )

    def test_the_before_run_line_says_which_gate_holds_which_list(self):
        # runlog checks the registration fields, the pre-commit hook every
        # must field (Haiku start reading 2026-10-28: 3 of 3 asked)
        for kind in ("compute", "fit", "apply"):
            with self.subTest(kind=kind):
                text = "\n".join(sc.describe("low", kind, False))
                self.assertIn("runlog checks these; the pre-commit hook holds", text)


if __name__ == "__main__":
    unittest.main()
