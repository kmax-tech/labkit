"""The standard contract: one table of what each tier owes, read by every
consumer — held here to the standard's own statements (LAB-017 The number
of audits follows the cost tier) and to the homes it names (the template's
labels, the shipped templates, the check every skeleton stamps)."""

from __future__ import annotations

import unittest
from pathlib import Path

from labkit import protocol_block, scaffold, standard_contract as sc
from labkit.protocol_check import FIELDS


class Lanes(unittest.TestCase):
    def test_seconds_owes_the_registration_not_the_freeze(self):
        ln = sc.lane("seconds")
        self.assertEqual(
            (ln.freeze, ln.registration, ln.audits, ln.cut),
            (False, True, ("analysis",), "seconds"),
        )
        self.assertTrue(ln.every_run_full and ln.foreground and ln.provenance)

    def test_minutes_and_hours_owe_the_freeze_with_its_audit(self):
        for cost in ("minutes", "hours"):
            with self.subTest(cost):
                ln = sc.lane(cost)
                self.assertEqual(
                    (ln.tier, ln.freeze, ln.registration, ln.audits, ln.cut),
                    (cost, True, False, ("preflight", "analysis"), "full"),
                )
                self.assertFalse(ln.every_run_full or ln.foreground or ln.provenance)

    def test_an_unfilled_cost_reads_as_hours(self):
        self.assertEqual(sc.lane(None), sc.lane("hours"))
        self.assertEqual(sc.tier(None), "hours")

    def test_a_tier_the_head_cannot_carry_is_refused(self):
        with self.assertRaises(ValueError):
            sc.lane("days")

    def test_the_tiers_are_the_heads(self):
        self.assertEqual((sc.SECONDS, sc.MINUTES, sc.HOURS), protocol_block.COST_TIERS)


class Registration(unittest.TestCase):
    def test_a_count_registers_its_question_a_model_also_the_bar(self):
        self.assertEqual(sc.registration_fields(False), ("Question / hypothesis",))
        self.assertEqual(
            sc.registration_fields(True),
            (
                "Question / hypothesis",
                "Success / failure criterion",
                "Admissibility condition",
            ),
        )

    def test_the_labels_are_the_templates_must_fields_of_the_seconds_cut(self):
        by_label = {f.label: f for f in FIELDS}
        for label in sc.registration_fields(True):
            with self.subTest(label):
                self.assertIn(label, by_label)
                self.assertEqual(by_label[label].level, "must")
                self.assertIn(by_label[label].seconds, ("s", "sm"))


class TheRelease(unittest.TestCase):
    def test_the_description_names_a_probe_only_where_one_precedes_the_run(self):
        for cost in (None, "seconds", "minutes", "hours"):
            for model in (True, False):
                with self.subTest(cost=cost, model=model):
                    first = sc.describe(cost, model)[0]
                    owed = (
                        sc.skeleton(cost, model).probe
                        and not sc.lane(cost).every_run_full
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
        self.assertIs(sc.skeleton("seconds", False), sc.COUNT)
        self.assertIs(sc.skeleton("minutes", False), sc.ESTIMATOR)
        self.assertIs(sc.skeleton(None, False), sc.ESTIMATOR)
        for cost in ("seconds", "minutes", "hours", None):
            self.assertIs(sc.skeleton(cost, True), sc.MODEL)

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
            [sk.instrument for sk in sc.SKELETONS if not sk.probe], ["count"]
        )


class Described(unittest.TestCase):
    def test_every_tier_names_its_check_and_what_comes_before_the_run(self):
        for cost, model in ((None, False), ("seconds", False), ("seconds", True)):
            with self.subTest(cost=cost, model=model):
                text = "\n".join(sc.describe(cost, model))
                self.assertIn("scripts/02_analyze.py --check", text)
                self.assertIn(
                    "registration written" if cost == "seconds" else "frozen = true",
                    text,
                )
        self.assertIn(
            "Success / failure criterion", "\n".join(sc.describe("seconds", True))
        )
        self.assertNotIn("Success / failure", "\n".join(sc.describe("seconds", False)))


if __name__ == "__main__":
    unittest.main()
