"""A finding's request for a code diff the audit had no room for: the
`diff:` check read (`findings.diff_request`, `findings.check_of`), the
section of a unified diff it names (`protocol_runs.diff_section`), and
which requests a later audit serves (`followup.diff_requests`). The way
on real commands: `tests/test_protocol_runs.py`, `RequestedDiff`."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from labkit.checks.protocol_runs import diff_section
from labkit.formats import findings, followup

OLD = "2026-11-17T10-00-00_aa11"
NEW = "2026-11-17T11-00-00_bb22"

DIFF = (
    "diff --git a/area/scripts/01_measure.py b/area/scripts/01_measure.py\n"
    "--- a/area/scripts/01_measure.py\n+++ b/area/scripts/01_measure.py\n"
    "@@ -1 +1 @@\n-keep\n+drop\n"
    "diff --git a/lib/weights.py b/lib/weights.py\n"
    "--- a/lib/weights.py\n+++ b/lib/weights.py\n@@ -1 +1 @@\n-1\n+2\n"
)


class Read(unittest.TestCase):
    def test_the_whole_diff_and_a_section(self):
        self.assertEqual(
            findings.diff_request(f"diff:{OLD}..{NEW}"),
            findings.DiffRequest(OLD, NEW, None),
        )
        self.assertEqual(
            findings.diff_request(f"diff:{OLD}..{NEW}:lib/weights.py").path,
            "lib/weights.py",
        )

    def test_a_request_no_follow_up_could_serve_is_refused(self):
        for bad in (
            f"diff:{OLD}",
            f"diff:{OLD}..final",
            f"diff:{OLD}..{NEW}:",
            f"diff:{OLD}..{NEW}:/etc/passwd",
            f"diff:{OLD}..{NEW}:lib/../../x.py",
        ):
            with self.subTest(bad), self.assertRaises(ValueError):
                findings.diff_request(bad)

    def test_the_finding_line_carries_it_as_its_check(self):
        line = (
            f"BLOCKER · a.py:1 · undetermined · x · y · new class · z · "
            f"check: diff:{OLD}..{NEW}:lib — confirms if a filter stands there"
        )
        self.assertEqual(
            findings.check_of(line),
            (f"diff:{OLD}..{NEW}:lib", "confirms if a filter stands there"),
        )
        with self.assertRaises(ValueError):
            findings.check_of(line.replace(NEW, "latest"))

    def test_its_fixed_is_named_as_evidence_supplied_only(self):
        """The one wording of the decision list, the decide output and the
        follow-up's holds: `fixed` on a request says the evidence is
        supplied, never that code or claim is confirmed."""
        said = findings.check_order(f"diff:{OLD}..{NEW}", "")
        self.assertIn("`fixed` says only: evidence supplied", said)
        self.assertIn("confirms neither the code nor the claim", said)


class Section(unittest.TestCase):
    def test_a_file_or_a_folder_takes_its_sections_only(self):
        self.assertEqual(
            diff_section(DIFF, "lib/weights.py"), DIFF[DIFF.index("diff --git a/lib") :]
        )
        self.assertEqual(diff_section(DIFF, "lib/"), diff_section(DIFF, "lib"))
        self.assertIn("+drop", diff_section(DIFF, "area/scripts"))
        self.assertNotIn("weights", diff_section(DIFF, "area/scripts"))

    def test_a_path_that_does_not_differ_takes_nothing(self):
        self.assertEqual(diff_section(DIFF, "area/scripts/02_analyze.py"), "")
        self.assertEqual(diff_section(DIFF, "li"), "")  # a prefix is no folder


def _record(name: str, *found: findings.Finding) -> findings.Record:
    return findings.Record(
        Path(name),
        "2026-11-17",
        "analysis",
        "m",
        "s",
        "b",
        (),
        OLD,
        "x",
        (1, 0, 0),
        found,
        "p-0123456789abcdef",
    )


ASKING = findings.Finding(
    "BLOCKER",
    "the cut diff may hide a filter",
    "open",
    "",
    check=f"diff:{OLD}..{NEW}",
    subject=findings.UNDETERMINED,
)


class Served(unittest.TestCase):
    """A request counts from its decision on and while its chain's head keeps it."""

    def test_undecided_it_asks_nothing(self):
        self.assertEqual(followup.diff_requests([_record("a.toml", ASKING)]), [])

    def test_decided_it_is_served(self):
        decided = replace(ASKING, status="fixed", reason="asked of the follow-up")
        self.assertEqual(
            followup.diff_requests([_record("a.toml", decided)]), [ASKING.check]
        )

    def test_carried_open_it_is_still_served(self):
        decided = replace(ASKING, status="fixed", reason="asked of the follow-up")
        carried = replace(ASKING, carries="a.toml#1", subject=findings.IMPLEMENTATION)
        records = [_record("a.toml", decided), _record("b.toml", carried)]
        self.assertEqual(followup.diff_requests(records), [ASKING.check])

    def test_a_warning_asks_nothing(self):
        warning = replace(ASKING, grade="WARNING", status="fixed", reason="r")
        self.assertEqual(followup.diff_requests([_record("a.toml", warning)]), [])


if __name__ == "__main__":
    unittest.main()
