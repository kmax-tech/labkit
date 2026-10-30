"""The ways out of a BLOCKER are one set of decisions in two places: the
list `labkit-audit` prints with every decision list (`ways_out.WAYS_OUT`) and
the stamped AGENTS.md ("When you are stuck"). Held by meaning and command,
not by copied strings: the same causes in both, every command they name a
real one, every flag a flag of it, and the `[replaces]` table they describe
one the head parser reads (K1, docs/notes/2026-10-27-new-registration-contracts.md)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import protocol_block  # noqa: E402
from labkit.gates import audit, ways_out  # noqa: E402
from labkit.tools import protocol_fill, scaffold  # noqa: E402
from protocol_fixture import head  # noqa: E402

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "labkit/templates/AGENTS.md.template"
).read_text(encoding="utf-8")


def stuck_section() -> str:
    start = TEMPLATE.index("## When you are stuck")
    return TEMPLATE[start : TEMPLATE.index("\n## ", start + 1)]


class WaysOut(unittest.TestCase):
    def test_the_template_names_the_same_causes_as_the_printed_list(self):
        named = re.findall(r"^- \*\*([^*]+)\*\* — ", stuck_section(), re.M)
        self.assertEqual(named, [name for name, _ in ways_out.WAYS_OUT])
        for promised in (True, False):
            for full in (True, False):
                printed = "\n".join(ways_out.blocker_routes(promised, full=full))
                for name, _ in ways_out.WAYS_OUT:
                    self.assertIn(f"    {name}: ", printed)

    def test_not_assessable_is_offered_only_where_a_promise_is_registered(self):
        """A computation registers no promise and `--decide` refuses every
        id an effect names (t34, t21 of the pilot, 2026-10-28): its routes
        name what works — limit the claim, fix, defer and hand over."""
        promised = "\n".join(ways_out.blocker_routes(True, full=True))
        self.assertIn("--not-assessable <ID>", promised)
        bare = "\n".join(ways_out.blocker_routes(False, full=True))
        self.assertNotIn("--not-assessable", bare)
        unjudged = next(
            ln for ln in bare.splitlines() if ways_out.UNJUDGED_PROMISE in ln
        )
        for way in ("`limitation`", "Conclusion", "hand over"):
            self.assertIn(way, unjudged)
        # the other routes stay as they are
        self.assertEqual(
            [ln for ln in bare.splitlines() if ways_out.UNJUDGED_PROMISE not in ln],
            [ln for ln in promised.splitlines() if ways_out.UNJUDGED_PROMISE not in ln],
        )

    def test_the_short_form_keeps_cause_next_step_and_where_in_full(self):
        """The decision list prints one line a way out (the cold agent of
        the declared-run case found the full list hard to filter): each
        keeps when it is the cause, the next step, and the list names where
        each stands in full. The auditor's prompt keeps the full text."""
        for promised in (True, False):
            short = ways_out.blocker_routes(promised, full=False)
            self.assertIn(f"    ({ways_out.WAYS_OUT_IN_FULL})", short)
            for line in short[1:-1]:
                self.assertIn(" → ", line)  # the cause, then the next step
                self.assertLess(len(line), 260, line)
            full = "\n".join(ways_out.blocker_routes(promised, full=True))
            self.assertNotIn(ways_out.WAYS_OUT_IN_FULL, full)
        self.assertEqual(
            set(ways_out.WAYS_OUT_SHORT), {n for n, _ in ways_out.WAYS_OUT}
        )

    def test_a_handover_needs_a_named_missing_prerequisite(self):
        """The file-check agent committed past the hook rather than hand
        over; a refusal alone is no reason either — it names its next step."""
        for text in (
            dict(ways_out.WAYS_OUT)["none of these"],
            ways_out.WAYS_OUT_SHORT["none of these"],
            stuck_section(),
        ):
            text = " ".join(text.split())
            self.assertIn("prerequisite", text)
            self.assertIn("--no-verify", text)

    def test_a_miss_comes_before_a_new_registration_and_never_becomes_a_pass(self):
        """The repair case read a missed criterion as an invalid registration."""
        names = [name for name, _ in ways_out.WAYS_OUT]
        self.assertLess(
            names.index("a missed criterion"), names.index("an invalid registration")
        )
        for text in (
            dict(ways_out.WAYS_OUT)["an invalid registration"],
            stuck_section(),
        ):
            text = " ".join(text.split())  # the template wraps its lines
            self.assertIn("never turns an earlier miss into a pass", text)
            self.assertIn('type = "exploratory"', text)

    def test_a_handover_names_the_protocol_not_its_runs(self):
        """A run id in a report reads as its number: the counter-case's
        handover that named the answering run was held."""
        for text in (dict(ways_out.WAYS_OUT)["none of these"], stuck_section()):
            text = " ".join(text.split())
            self.assertIn("the report names the protocol, not its runs", text)
            self.assertIn(
                "no `[result]` table" if "`[result]`" in text else "no [result] table",
                text,
            )

    def test_every_command_named_is_a_real_command_and_flag(self):
        routes = [
            *ways_out.blocker_routes(True, full=True),
            *ways_out.blocker_routes(False, full=True),
            *ways_out.blocker_routes(True, full=False),
            *ways_out.blocker_routes(False, full=False),
        ]
        both = " ".join(("\n".join(routes) + stuck_section()).split())
        self.assertIn("labkit-init exp <new-name> --kind", both)
        init = flags_of(scaffold.main, ["exp", "--help"])
        for flag in re.findall(r"labkit-init exp <new-name> (--[a-z-]+)", both):
            self.assertIn(flag, init)
        decide = flags_of(audit.main, ["--help"])
        report = flags_of(protocol_fill.main, ["--help"])
        # the reading works: flags known to exist are found
        self.assertTrue(
            {"--kind", "--change-kind"} <= init
            and {"--decide", "--not-assessable"} <= decide
        )
        # every flag of every code span, held to the command the span starts
        # with; it read only a flag right after a backtick, so --handover,
        # --why, --tried, --into and --findings went unchecked (audit
        # 2026-10-27, table C)
        known = {"labkit-init": init, "labkit-audit": decide, "protocol-fill": report}
        seen = set()
        for span in re.findall(r"`([^`]*)`", both):
            for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", span):
                if flag == "--no-verify":  # git's, named as what never to use
                    continue
                command = span.split()[0]
                with self.subTest(span=span, flag=flag):
                    self.assertIn(flag, known.get(command, decide | report))
                seen.add(flag)
        self.assertTrue({"--handover", "--tried", "--findings"} <= seen, seen)

    def test_the_replaces_table_described_is_one_the_head_reads(self):
        text = head(
            promises='\n[replaces]\nprotocol = "p-aaaaaaaaaaaaaaaa"\n\n[[replaces.change]]\n'
            'what = "criterion-1 margin"\nfrom = "0.25"\nto = "0.15"\nwhy = "the band was wrong"\n'
        )
        rep = protocol_block.replaces(text)
        assert rep is not None
        self.assertEqual([c.what for c in rep.changes], ["criterion-1 margin"])
        for field in protocol_block.CHANGE_KEYS:
            self.assertIn(field, dict(ways_out.WAYS_OUT)["an invalid registration"])


def flags_of(main, argv: list[str]) -> set[str]:
    """The flags MAIN's parser declares, read while it prints its help."""
    import argparse
    import contextlib
    import io
    from unittest import mock

    seen: set[str] = set()
    real = argparse.ArgumentParser.add_argument

    def spy(self, *names, **kw):
        seen.update(n for n in names if n.startswith("--"))
        return real(self, *names, **kw)

    with (
        mock.patch.object(argparse.ArgumentParser, "add_argument", spy),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        try:
            main(argv)
        except SystemExit:
            pass
    return seen


if __name__ == "__main__":
    unittest.main()
