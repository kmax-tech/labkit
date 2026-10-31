"""The Timebox as a number and the fit skeleton's budget projection (labkit.formats.timebox)."""

import unittest

from labkit.formats import timebox


class ParseSeconds(unittest.TestCase):
    def test_a_duration_first_in_each_unit(self):
        self.assertEqual(timebox.parse_seconds("45 min — then record and ask"), 2700)
        self.assertEqual(timebox.parse_seconds("4h"), 14400)
        self.assertEqual(timebox.parse_seconds("  90 s"), 90)
        self.assertEqual(timebox.parse_seconds("1.5 hours, hard"), 5400)
        self.assertEqual(timebox.parse_seconds("2,5 min"), 150)

    def test_prose_without_a_leading_duration_is_refused_naming_the_grammar(self):
        for value in (
            "a hard budget, such as 4h",
            "until Friday",
            "",
            "0 min",
            "4 fortnights",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError) as cm:
                timebox.parse_seconds(value)
            self.assertIn("Timebox", str(cm.exception))


class SecondsOfProtocol(unittest.TestCase):
    def protocol(self, timebox_value: str | None) -> str:
        field = f"- **Timebox:** {timebox_value}\n" if timebox_value is not None else ""
        return (
            "# P\n\n## Intent (before the run)\n\n- **Question / hypothesis:** q\n"
            + field
            + "- **Unit:** one item\n"
        )

    def test_a_filled_duration_is_read(self):
        seconds, note = timebox.seconds_of(
            self.protocol("45 min — then record and ask")
        )
        self.assertEqual(seconds, 2700)
        self.assertIn("45 min", note)

    def test_a_placeholder_prose_or_missing_field_gives_none_with_the_reason(self):
        for value, reason in (
            (
                "<the duration first, such as `45 min` or `4h`, then what follows: record and ask. "
                "A fit stops before this budget when its first fold projects over it.>",
                "not filled",
            ),
            ("until the review", "names no duration first"),
            (None, "no Timebox field"),
        ):
            with self.subTest(value=value):
                seconds, note = timebox.seconds_of(self.protocol(value))
                self.assertIsNone(seconds)
                self.assertIn(reason, note)
                self.assertIn("no budget projection", note)


class Projection(unittest.TestCase):
    def test_the_whole_run_from_the_first_fold(self):
        # 3 folds of 3 fits, 60 s each fold, plus one final fit (a third of a fold)
        self.assertEqual(timebox.projected_seconds(60, 3, 3, test_fit=True), 200)
        self.assertEqual(timebox.projected_seconds(60, 3, 3, test_fit=False), 180)
        self.assertEqual(
            timebox.projected_seconds(239, 5, 6, test_fit=True), 239 * 5 + 239 / 6
        )

    def test_degenerate_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            timebox.projected_seconds(60, 0, 3, test_fit=False)
        with self.assertRaises(ValueError):
            timebox.projected_seconds(-1, 3, 3, test_fit=False)

    def test_over_budget_names_the_numbers_and_the_way_out_and_fits_stay_silent(self):
        self.assertIsNone(timebox.over_budget(200, 900, 60, 3, 3))
        self.assertIsNone(
            timebox.over_budget(900, 900, 300, 3, 3)
        )  # exactly the budget fits
        msg = timebox.over_budget(1434, 900, 239, 5, 6)
        assert msg is not None
        self.assertIn("239 s", msg)
        self.assertIn("23.9 min", msg)
        self.assertIn("15.0 min", msg)
        self.assertIn("Next:", msg)
        self.assertIn("fewer folds or refits", msg)


if __name__ == "__main__":
    unittest.main()
