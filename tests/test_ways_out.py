"""The ways out of a BLOCKER are one set of decisions in two places: the
list `labkit-audit` prints with every decision list (`audit.WAYS_OUT`) and
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
from labkit.gates import audit  # noqa: E402
from labkit.tools import scaffold  # noqa: E402
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
        self.assertEqual(named, [name for name, _ in audit.WAYS_OUT])
        printed = "\n".join(audit.BLOCKER_ROUTES)
        for name, _ in audit.WAYS_OUT:
            self.assertIn(f"    {name}: ", printed)

    def test_a_miss_comes_before_a_new_registration_and_never_becomes_a_pass(self):
        """The repair case read a missed criterion as an invalid registration."""
        names = [name for name, _ in audit.WAYS_OUT]
        self.assertLess(
            names.index("a missed criterion"), names.index("an invalid registration")
        )
        for text in (dict(audit.WAYS_OUT)["an invalid registration"], stuck_section()):
            text = " ".join(text.split())  # the template wraps its lines
            self.assertIn("never turns an earlier miss into a pass", text)
            self.assertIn('type = "exploratory"', text)

    def test_every_command_named_is_a_real_command_and_flag(self):
        both = " ".join(("\n".join(audit.BLOCKER_ROUTES) + stuck_section()).split())
        self.assertIn("labkit-init exp <new-name> --kind", both)
        init = flags_of(scaffold.main, ["exp", "--help"])
        for flag in re.findall(r"labkit-init exp <new-name> (--[a-z-]+)", both):
            self.assertIn(flag, init)
        decide = flags_of(audit.main, ["--help"])
        # the reading works: flags known to exist are found
        self.assertTrue(
            {"--kind", "--change-kind"} <= init and {"--decide", "--effect"} <= decide
        )
        for flag in re.findall(r"`(--[a-z-]+)", both):
            if flag != "--no-verify":  # git's, named as what never to use
                self.assertIn(flag, decide)

    def test_the_replaces_table_described_is_one_the_head_reads(self):
        text = head(
            promises='\n[replaces]\nprotocol = "p-aaaaaaaaaaaaaaaa"\n\n[[replaces.change]]\n'
            'what = "C1 margin"\nfrom = "0.25"\nto = "0.15"\nwhy = "the band was wrong"\n'
        )
        rep = protocol_block.replaces(text)
        assert rep is not None
        self.assertEqual([c.what for c in rep.changes], ["C1 margin"])
        for field in protocol_block.CHANGE_KEYS:
            self.assertIn(field, dict(audit.WAYS_OUT)["an invalid registration"])


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
