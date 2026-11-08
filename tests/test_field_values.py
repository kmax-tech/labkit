"""One reading of a field's value for every comparison and stamp
(`protocol_check.field_values`): the label by `field_name`, whitespace
folded, a field written twice never read as one of its copies.

Labels are looked up folded, so `Unit (per judged item)` cannot hide a
changed unit; the stamps and the comparisons read the same copies and fold
the Data profile alike."""

import contextlib
import io
import os
import re
import unittest
from pathlib import Path

from labkit.gates import hook_pre_run
from labkit.checks import protocol_report
from labkit.formats import protocol_block, protocol_check, protocol_history
from labkit.formats.area_state import state_of
from labkit.formats.gate import Findings
from labkit.gates import finalize, preflight
from labkit.run import start_check
from labkit.gates import next_step
from protocol_fixture import head
from test_end_to_end import Lab, stamp_count

WAY_OUT = protocol_check.REPEATED_WAY_OUT


def protocol(*lines: str, model: str | None = None) -> str:
    """A low protocol holding LINES as fields; MODEL names a `[model]`
    alias, so the registration stamp binds the Data profile too."""
    return (
        head(repeat_cost="low", model=model)
        + "\n"
        + "".join(f"- {ln}\n" for ln in lines)
    )


def scope_changes(old: str, new: str) -> list[str]:
    return [what for what, _, _ in protocol_history.scope_differences(old, new)]


def registration_changes(old: str, new: str) -> list[str]:
    return [what for what, _, _ in protocol_history.registration_differences(old, new)]


class FieldIdentity(unittest.TestCase):
    def test_a_gloss_does_not_hide_a_changed_unit(self):
        old = protocol("**Unit (per judged item):** seconds")
        new = protocol("**Unit (per judged item):** milliseconds")
        self.assertEqual(scope_changes(old, new), ["Unit"])

    def test_the_label_case_does_not_hide_a_changed_question(self):
        old = protocol("**Question / Hypothesis:** Does A beat B?")
        new = protocol("**Question / Hypothesis:** Does B beat A?")
        self.assertEqual(scope_changes(old, new), ["Question / hypothesis"])

    def test_an_unchanged_glossed_field_is_no_change(self):
        text = protocol("**Unit (per judged item):** seconds")
        self.assertEqual(scope_changes(text, text), [])

    def test_a_gloss_added_to_an_unchanged_field_is_no_change(self):
        old = protocol("**Unit:** seconds")
        new = protocol("**Unit (per judged item):** seconds")
        self.assertEqual(scope_changes(old, new), [])


class WrittenTwice(unittest.TestCase):
    """A field written twice is read as both copies wherever it is read, so
    a change in either is seen by the comparison and the stamp alike; the
    gates refuse it (`repeated_fields`)."""

    OLD = protocol("**Unit:** seconds", "**Unit:** seconds")

    def test_a_change_in_the_first_copy_is_seen_by_the_comparison(self):
        new = protocol("**Unit:** minutes", "**Unit:** seconds")
        self.assertEqual(scope_changes(self.OLD, new), ["Unit"])

    def test_a_change_in_the_second_copy_is_seen_by_the_audit_binding(self):
        new = protocol("**Unit:** seconds", "**Unit:** minutes")
        self.assertNotEqual(
            protocol_check.audited_texts(self.OLD), protocol_check.audited_texts(new)
        )

    def test_a_change_in_the_second_copy_is_seen_by_the_stamp(self):
        old = protocol("**Data profile:** alpha", "**Data profile:** alpha", model="m")
        new = protocol("**Data profile:** alpha", "**Data profile:** beta", model="m")
        self.assertIn("Data profile", protocol_check.registration_stamp(old))
        self.assertNotEqual(
            protocol_check.registration_stamp(old),
            protocol_check.registration_stamp(new),
        )

    def test_counts_in_one_copy_of_data_scope_cut_no_other(self):
        """`scope_value` drops the generated counts to the end of a value;
        applied to the joined copies it would drop the second one."""
        counted = "**Data / scope:** corpus X · counts (prepare run r1): 120 items"
        old = protocol(counted, "**Data / scope:** corpus Y")
        new = protocol(counted, "**Data / scope:** corpus Z")
        self.assertEqual(scope_changes(old, new), ["Data / scope"])

    def test_the_field_report_names_it_apart_from_missing_fields(self):
        report = protocol_check.check_fields(self.OLD)
        (twice,) = report.repeated
        self.assertRegex(
            twice,
            r"^Unit written 2 times \(lines \d+ and \d+\), so which copy is "
            r"registered cannot be told$",
        )
        self.assertFalse([m for m in report.missing_must if "Unit" in m])

    def test_a_versioned_copy_is_the_same_field(self):
        """`Question / hypothesis (v2)` beside the first: a gloss makes no
        other field. The way out keeps the measured version and promises no
        successor protocol: that way has conditions of its own."""
        text = protocol(
            "**Question / hypothesis:** Does A beat B?",
            "**Question / hypothesis (v2):** Does B beat A?",
        )
        ((label, _),) = protocol_check.repeated_fields(text)
        self.assertEqual(label, "Question / hypothesis")
        self.assertIn("the first measurement stood on", WAY_OUT)
        self.assertNotIn("[replaces]", WAY_OUT)

    def test_the_low_registration_lacks_a_single_copy(self):
        missing = protocol_history.registration_missing(self.OLD)
        self.assertTrue(
            any(
                re.fullmatch(
                    r"one copy of Unit \(written 2 times, lines \d+ and \d+\)", m
                )
                for m in missing
            ),
            missing,
        )

    def test_a_bound_field_written_once_is_not_refused(self):
        text = protocol("**Unit:** seconds")
        self.assertEqual(protocol_check.repeated_fields(text), [])
        self.assertFalse(
            [m for m in protocol_history.registration_missing(text) if "copy" in m]
        )


class DataProfileWhitespace(unittest.TestCase):
    def test_inner_spacing_is_no_change(self):
        old = protocol("**Data profile:** alpha beta", model="m")
        new = protocol("**Data profile:** alpha  beta", model="m")
        self.assertEqual(registration_changes(old, new), [])
        self.assertIn("Data profile", protocol_check.registration_stamp(old))
        self.assertEqual(
            protocol_check.registration_stamp(old),
            protocol_check.registration_stamp(new),
        )

    def test_a_reflow_is_no_change(self):
        """Already equal before the repair (continuation lines join with a
        space): the twin that folding keeps allowed."""
        old = protocol("**Data profile:** alpha beta")
        new = protocol("**Data profile:** alpha\n  beta")
        self.assertEqual(registration_changes(old, new), [])

    def test_a_changed_profile_is_a_change(self):
        old = protocol("**Data profile:** alpha beta")
        new = protocol("**Data profile:** alpha gamma")
        self.assertEqual(registration_changes(old, new), ["Data profile"])

    def test_the_generated_counts_stay_with_data_scope(self):
        """Only Data / scope drops the counts the prepare run writes
        (`protocol_block.COUNTS`); a Data profile that holds the same text
        is compared as written."""
        old_counts = "counts (prepare run r1): 12 items"
        new_counts = "counts (prepare run r2): 13 items"
        old = protocol(
            f"**Data / scope:** corpus X · {old_counts}",
            f"**Data profile:** alpha · {old_counts}",
        )
        new = protocol(
            f"**Data / scope:** corpus X · {new_counts}",
            f"**Data profile:** alpha · {new_counts}",
        )
        self.assertEqual(registration_changes(old, new), ["Data profile"])


class TheCommandsNameItAsWrittenMoreThanOnce(unittest.TestCase):
    """A bound field written twice is refused as such — not as a missing
    field to fill — by protocol-check, preflight, the run's start check,
    labkit-next and the run hook, each naming REPEATED_WAY_OUT. The twin is
    the committed count protocol as stamp_count fills it, which runs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = stamp_count(cls.lab)
        cls.clean = cls.protocol.read_text(encoding="utf-8")
        unit = re.search(r"^- \*\*Unit[^\n]*$", cls.clean, re.M)
        assert unit is not None
        cls.twice = cls.clean.replace(
            unit.group(0), unit.group(0) + "\n- **unit:** one line of any file", 1
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def setUp(self) -> None:
        self.protocol.write_text(self.twice, encoding="utf-8")
        self.addCleanup(self.protocol.write_text, self.clean, encoding="utf-8")

    def commit_twice(self) -> None:
        """Commit the two copies; the cleanup commits the clean protocol."""
        self.lab.commit("Unit twice")

        def restore() -> None:
            self.protocol.write_text(self.clean, encoding="utf-8")
            self.lab.commit("Unit once again")

        self.addCleanup(restore)

    def test_protocol_check_refuses_it_apart_from_missing_fields(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = protocol_report.main([str(self.protocol)])
        said = out.getvalue()
        self.assertEqual(rc, 1, said)
        self.assertIn("REPEATED (must): Unit written 2 times", said)
        self.assertIn(WAY_OUT, said)
        self.assertNotIn("MISSING (must): Unit", said)
        self.assertNotIn("must fields missing or empty", said)

    def test_preflight_refuses_it_with_the_check_to_run_again(self):
        found = Findings(tell=None)
        text = self.protocol.read_text(encoding="utf-8")
        preflight.check_protocol_fields(
            found,
            self.protocol,
            protocol_check.check_fields(text),
            protocol_block.head(text),
        )
        (line,) = [f.line for f in found.found if "REPEATED" in f.line]
        self.assertIn(WAY_OUT, line)
        self.assertIn("protocol-check", line)

    def test_the_start_check_refuses_it_and_names_the_way_out(self):
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        problems = start_check._freeze_findings(self.area, bound, state_of(self.area))
        self.assertTrue(any("Unit written 2 times" in p for p in problems), problems)
        self.assertFalse(any("not written" in p for p in problems), problems)
        _, way = start_check.measurement_refusal(self.area, self.protocol)
        self.assertIn(WAY_OUT, way)
        self.assertIn("commit the protocol", way)

    def test_a_committed_copy_is_refused_though_the_tree_holds_one(self):
        """The first measurement is held to the commit: two copies at HEAD
        refuse the run although the working tree is already repaired."""
        self.commit_twice()
        self.protocol.write_text(self.clean, encoding="utf-8")
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        problems = start_check._freeze_findings(self.area, bound, state_of(self.area))
        self.assertTrue(
            any("one copy of Unit (written 2 times" in p for p in problems), problems
        )

    def test_copies_in_the_tree_and_at_head_are_named_once(self):
        self.commit_twice()
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        problems = start_check._freeze_findings(self.area, bound, state_of(self.area))
        self.assertEqual(len([p for p in problems if "Unit" in p]), 1, problems)

    def test_finalize_refuses_it_at_the_field_station(self):
        found = Findings(tell=None)
        text = self.protocol.read_text(encoding="utf-8")
        finalize.check_open_fields(
            found, self.protocol, text, protocol_block.head(text)
        )
        (line,) = [f.line for f in found.found if "written 2 times" in f.line]
        self.assertIn(WAY_OUT, line)
        self.assertIn("finalize", line)

    def test_labkit_next_names_it_first(self):
        old = Path.cwd()
        os.chdir(self.lab.root)
        try:
            step = next_step.next_step(self.area, self.protocol.resolve())
        finally:
            os.chdir(old)
        self.assertIn("more than once", step.where)
        self.assertIn(WAY_OUT, step.next)

    def test_the_run_hook_does_not_call_it_written(self):
        line = hook_pre_run._low_registration_line("hook", [self.twice])
        self.assertIn("Unit written 2 times", line)
        self.assertNotIn("registration written", line)

    def test_the_clean_protocol_owes_no_such_step(self):
        self.protocol.write_text(self.clean, encoding="utf-8")
        bound = start_check.protocol_binding(self.area, self.protocol.name)
        problems = start_check._freeze_findings(self.area, bound, state_of(self.area))
        self.assertFalse(any("written 2 times" in p for p in problems), problems)
        found = Findings(tell=None)
        finalize.check_open_fields(
            found, self.protocol, self.clean, protocol_block.head(self.clean)
        )
        self.assertFalse([f for f in found.found if "written" in f.line])
        self.assertEqual(protocol_check.check_fields(self.clean).repeated, [])
        line = hook_pre_run._low_registration_line("hook", [self.clean])
        self.assertIn("registration written", line)


class HighCostWayOut(unittest.TestCase):
    """At high repeat cost deleting a copy changes the registration the
    preflight audit bound: the way out names preflight and the freeze."""

    def test_the_step_names_the_audit_and_the_freeze(self):
        lab = Lab()
        self.addCleanup(lab.close)
        area, proto = lab.exp("hi", repeat_cost="high", kind="compute")
        text = proto.read_text(encoding="utf-8")
        unit = re.search(r"^- \*\*Unit[^\n]*$", text, re.M)
        assert unit is not None
        proto.write_text(
            text.replace(unit.group(0), unit.group(0) + "\n- **Unit:** b", 1),
            encoding="utf-8",
        )
        _, way = start_check.measurement_refusal(area, proto)
        self.assertIn(WAY_OUT, way)
        self.assertIn("preflight", way)
        self.assertIn("protocol-fill <PROTOCOL> --freeze", way)


if __name__ == "__main__":
    unittest.main()
