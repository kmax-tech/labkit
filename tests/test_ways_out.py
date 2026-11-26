"""The ways out of a BLOCKER are one set of decisions in two places: the
list the analysis auditor is shown (`ways_out.WAYS_OUT`) and the agent
guide ("When you are stuck", `labkit-next --guide`; the stamped AGENTS.md
and the decision list name the guide). Held by meaning and command,
not by copied strings: the same causes in both, every command they name a
real one, every flag a flag of it, and the `[replaces]` table they describe
one the head parser reads (K1, docs/notes/2026-10-27-new-registration-contracts.md)."""

from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.checks.audit_binding import gone_run_way  # noqa: E402
from labkit.formats import area_state, commands, protocol_block, repo  # noqa: E402
from labkit.gates import audit, registration_hold, ways_out  # noqa: E402
from labkit.tools import protocol_fill, scaffold  # noqa: E402
from protocol_fixture import head  # noqa: E402

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "labkit/docs/agent-guide.md"
).read_text(encoding="utf-8")


def stuck_section() -> str:
    start = TEMPLATE.index("## When you are stuck")
    return TEMPLATE[start : TEMPLATE.index("\n## ", start + 1)]


class WaysOut(unittest.TestCase):
    def test_the_template_names_the_same_causes_as_the_printed_list(self):
        named = re.findall(r"^- \*\*([^*]+)\*\* — ", stuck_section(), re.M)
        self.assertEqual(named, [name for name, _ in ways_out.WAYS_OUT])
        for promised in (True, False):
            printed = "\n".join(ways_out.blocker_routes(promised))
            for name, _ in ways_out.WAYS_OUT:
                self.assertIn(f"    {name}: ", printed)

    def test_each_way_out_names_the_subject_it_serves_in_both_places(self):
        """A way out bound to a finding's subject says which, in the printed
        list and in the guide, and only a `statement` way offers
        `limitation`, since `--decide` refuses it for an implementation
        finding."""
        guide = {
            m.group(1): m.group(2)
            for m in re.finditer(
                r"^- \*\*([^*]+)\*\* — (.*?)(?=^- \*\*|\Z)",
                stuck_section(),
                re.M | re.S,
            )
        }
        serves = {
            "an implementation error": "`implementation`",
            "an unsettled suspicion": "`undetermined`",
            ways_out.UNJUDGED_PROMISE: "`statement`",
        }
        for name, subject in serves.items():
            with self.subTest(name=name):
                self.assertIn(subject, dict(ways_out.WAYS_OUT)[name])
                self.assertIn(subject, guide[name])
        for promised in (True, False):
            for line in ways_out.blocker_routes(promised):
                if "decide it `limitation`" in line:
                    self.assertIn("`statement`", line)
                    self.assertIn(
                        "`implementation` fault you cannot fix is handed over", line
                    )

    def test_not_assessable_is_offered_only_where_a_promise_is_registered(self):
        """A computation registers no promise and `--decide` refuses every
        id an effect names: its routes name what works — limit the claim, fix, defer and hand over."""
        promised = "\n".join(ways_out.blocker_routes(True))
        self.assertIn("--not-assessable <ID>", promised)
        bare = "\n".join(ways_out.blocker_routes(False))
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

    def test_a_handover_needs_a_named_missing_prerequisite(self):
        """A handover names its missing prerequisite and never commits past
        the hook; a refusal alone is no reason either — it names its next
        step."""
        for text in (dict(ways_out.WAYS_OUT)["none of these"], stuck_section()):
            text = " ".join(text.split())
            self.assertIn("prerequisite", text)
            self.assertIn("--no-verify", text)

    def test_a_miss_comes_before_a_new_registration_and_never_becomes_a_pass(self):
        """A missed criterion is no invalid registration: the miss comes first
        and a new registration never turns it into a pass."""
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
        """A run id in a report reads as its number, so a handover names
        the protocol, not its runs."""
        for text in (dict(ways_out.WAYS_OUT)["none of these"], stuck_section()):
            text = " ".join(text.split())
            self.assertIn("the report names the protocol, not its runs", text)
            self.assertIn(
                "no `[result]` table" if "`[result]`" in text else "no [result] table",
                text,
            )

    def test_every_command_named_is_a_real_command_and_flag(self):
        routes = [*ways_out.blocker_routes(True), *ways_out.blocker_routes(False)]
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
        # with, not only a flag right after a backtick
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


class HandoverIntoTheRegisteredReport(unittest.TestCase):
    """The handover a hold prints for a known protocol writes into the
    report its head registers, not a fixed `REPORT.md` (final review,
    2026-11-16: a head registering RESULTS.md got `--into REPORT.md`, which
    wrote a second report and left the registered one owed)."""

    def protocol(self, report: str | None) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / "CLAUDE.md").write_text("", encoding="utf-8")
        area = root / "experiments" / "01-a"
        area.mkdir(parents=True)
        path = area / "PROTOCOL-a.md"
        path.write_text(f"# A\n\n{head(report=report)}\n", encoding="utf-8")
        return path

    def test_the_handover_names_the_registered_report(self):
        protocol = self.protocol("RESULTS.md")
        for said in (
            ways_out.handover(protocol),
            registration_hold.unread_hold(
                protocol.parent, protocol, "p-aaaa", ["x"]
            ).fix
            or "",
        ):
            into = re.search(r"--into (\S+)`", said)
            assert into is not None, said
            self.assertTrue(into.group(1).endswith("RESULTS.md"), said)

    def test_the_gone_run_way_names_it_for_an_area_spelled_relative(self):
        """The way out of a gone run reads the head from the area state,
        whose texts are keyed by resolved path: an area spelled relative
        to the working directory named `REPORT.md` (review of e6c4b406,
        2026-11-16). Both spellings name the registered report."""
        protocol = self.protocol("RESULTS.md")
        root = protocol.parents[2]
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        with contextlib.chdir(root):
            for spelled in (Path("experiments/01-a"), protocol.parent.resolve()):
                with self.subTest(area=str(spelled)):
                    _, handover = gone_run_way(area_state.state_of(spelled), "r1")
                    self.assertTrue(
                        handover.line.endswith("--into RESULTS.md"), handover.line
                    )

    def test_the_twin_a_head_without_a_report_names_the_default(self):
        self.assertIn("--into REPORT.md`", ways_out.handover(self.protocol(None)))
        self.assertIn("--into REPORT.md`", ways_out.HANDOVER_WAY)


class OneWording(unittest.TestCase):
    """Sentences several gates tell have one builder each."""

    def test_the_repair_of_a_head_names_the_contract_line(self):
        self.assertEqual(
            commands.repair_head_way(None),
            "repair the head as the sentence says (`protocol-check <PROTOCOL> "
            "--contract` shows its fields)",
        )
        named = commands.repair_head_way(Path.cwd() / "PROTOCOL-x.md")
        self.assertIn("`protocol-check PROTOCOL-x.md --contract`", named)

    def test_a_path_beside_a_file_is_relative_to_its_folder(self):
        report = Path("/repo/docs/REPORT.md")
        self.assertEqual(
            repo.path_beside(Path("/repo/docs/exp/PROTOCOL-x.md"), report),
            "exp/PROTOCOL-x.md",
        )
        # the twin: a target outside the report's folder is reached with `..`
        self.assertEqual(
            repo.path_beside(Path("/repo/experiments/01/PROTOCOL-x.md"), report),
            "../experiments/01/PROTOCOL-x.md",
        )


if __name__ == "__main__":
    unittest.main()
