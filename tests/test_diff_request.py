"""A finding's request for a code diff the audit had no room for: the
`diff:` check read (`findings.diff_request`, `findings.check_of`), the
section of a unified diff it names (`protocol_runs.diff_section`), and
which requests a later audit serves (`followup.diff_requests`). The way
on real commands: `tests/test_protocol_runs.py`, `RequestedDiff`."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from labkit.checks.protocol_runs import diff_lines, diff_section
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
        for check in (f"diff:{OLD}..{NEW}", f"code:{NEW}:lib/w.py:1-9"):
            with self.subTest(check):
                said = findings.check_order(check, "")
                self.assertIn("`fixed` says only: evidence supplied", said)
                self.assertIn("confirms neither the code nor the claim", said)

    def test_a_line_range_of_one_side_of_a_file(self):
        self.assertEqual(
            findings.diff_request(f"diff:{OLD}..{NEW}:lib/w.py:new:120-260"),
            findings.DiffRequest(OLD, NEW, "lib/w.py", "new", (120, 260)),
        )
        self.assertEqual(
            findings.diff_request(f"diff:{OLD}..{NEW}:lib/w.py:old:7-7").lines, (7, 7)
        )
        for bad in ("new:20-10", "mid:1-2", "new:0-3", "new:5"):
            with self.subTest(bad), self.assertRaises(ValueError):
                findings.diff_request(f"diff:{OLD}..{NEW}:lib/w.py:{bad}")

    def test_a_run_s_code_as_it_started_whole_or_a_range(self):
        self.assertEqual(
            findings.code_request(f"code:{NEW}:area/scripts/01_measure.py"),
            findings.CodeRequest(NEW, "area/scripts/01_measure.py", None),
        )
        self.assertEqual(
            findings.code_request(f"code:{NEW}:lib/w.py:5-9").lines, (5, 9)
        )
        for bad in (
            "code:latest:lib/w.py",
            f"code:{NEW}",
            f"code:{NEW}:",
            f"code:{NEW}:/etc/passwd",
            f"code:{NEW}:lib/../../x.py",
            f"code:{NEW}:lib/w.py:9-5",
        ):
            with self.subTest(bad), self.assertRaises(ValueError):
                findings.code_request(bad)
        line = (
            f"BLOCKER · a.py:1 · undetermined · x · y · new class · z · "
            f"check: code:{NEW}:lib/w.py:5-9 — confirms if the weight is 0"
        )
        self.assertEqual(findings.check_of(line)[0], f"code:{NEW}:lib/w.py:5-9")
        with self.assertRaises(ValueError):
            findings.check_of(line.replace(":5-9", ":9-5"))


#: one file's section: lines 1–6 of the old file, 1–7 of the new
FILE = (
    "diff --git a/lib/w.py b/lib/w.py\n--- a/lib/w.py\n+++ b/lib/w.py\n"
    "@@ -1,6 +1,7 @@\n a\n-b\n+B\n c\n d\n+e2\n f\n g\n"
)


class Lines(unittest.TestCase):
    """A line range of one side cut from a file's section, each run of
    lines under a hunk header of its own numbers."""

    def test_the_new_side(self):
        cut = diff_lines(FILE, "new", 4, 5)
        self.assertTrue(cut.startswith("diff --git a/lib/w.py b/lib/w.py\n"))
        self.assertIn("@@ -4,1 +4,2 @@\n d\n+e2\n", cut)
        self.assertNotIn("B", cut)

    def test_the_old_side_keeps_what_replaced_its_lines(self):
        cut = diff_lines(FILE, "old", 2, 2)
        self.assertIn("@@ -2,1 +2,1 @@\n-b\n+B\n", cut)
        self.assertNotIn("e2", cut)

    def test_a_range_past_the_hunks_takes_nothing(self):
        self.assertEqual(diff_lines(FILE, "new", 40, 50), "")


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


DECIDED = replace(ASKING, status="fixed", reason="asked of the follow-up")


def _verdict(
    word: str, *, present: bool = True, of: findings.Finding = DECIDED
) -> findings.FixVerdict:
    """A follow-up's verdict on a.toml#1 as OF was decided."""
    return findings.FixVerdict(
        "a.toml",
        1,
        findings.decision_digest(of),
        word,
        "the requested diff shows it",
        check=ASKING.check,
        check_present=present,
        subject=findings.IMPLEMENTATION if word == "unresolved" else "",
    )


def _followed(*verdicts: findings.FixVerdict, carried=()) -> list[findings.Record]:
    """a.toml with the decided request, b.toml the follow-up with VERDICTS."""
    follow = replace(_record("b.toml", *carried), fix_verdicts=verdicts)
    return [_record("a.toml", DECIDED), follow]


def _asked(records, also=()) -> list[tuple[str, str]]:
    return [(a.check, a.judged) for a in followup.diff_requests(records, also)]


class Served(unittest.TestCase):
    """A request counts from its decision on, until a follow-up judged it
    on the diff it was shown."""

    def test_undecided_it_asks_nothing(self):
        self.assertEqual(_asked([_record("a.toml", ASKING)]), [])

    def test_decided_it_is_served(self):
        self.assertEqual(_asked([_record("a.toml", DECIDED)]), [(ASKING.check, "")])

    def test_carried_open_it_is_still_served(self):
        """Judged not assessable, the carried finding keeps the request."""
        carried = replace(ASKING, carries="a.toml#1")
        records = _followed(_verdict("not_assessable"), carried=(carried,))
        self.assertEqual(_asked(records), [(ASKING.check, "")])

    def test_a_warning_asks_nothing(self):
        warning = replace(ASKING, grade="WARNING", status="fixed", reason="r")
        self.assertEqual(_asked([_record("a.toml", warning)]), [])

    def test_judged_on_the_diff_shown_it_is_served_no_more(self):
        for word in ("resolved", "unresolved"):
            with self.subTest(word):
                (asked,) = _asked(_followed(_verdict(word)))
                self.assertEqual(asked[0], ASKING.check)
                self.assertEqual(asked[1], f"a.toml#1 found `{word}`")

    def test_the_twins_a_verdict_without_the_diff_or_on_another_decision(self):
        unseen = _followed(_verdict("resolved", present=False))
        self.assertEqual(_asked(unseen), [(ASKING.check, "")])
        earlier = replace(DECIDED, reason="an earlier why")
        moved = _followed(_verdict("resolved", of=earlier))
        self.assertEqual(_asked(moved), [(ASKING.check, "")])

    def test_a_verdict_not_yet_recorded_counts_as_one(self):
        """The record about to be written binds the state after its own
        verdicts: the same answer as once it stands."""
        self.assertEqual(
            _asked([_record("a.toml", DECIDED)], (_verdict("resolved"),)),
            _asked(_followed(_verdict("resolved"))),
        )

    def test_the_carried_finding_of_a_judged_request_asks_nothing_again(self):
        member = followup.Member(_record("a.toml", DECIDED), 1, DECIDED)
        carried = followup.carried_finding(member, _verdict("unresolved"), DECIDED)
        self.assertEqual(carried.check, "")
        records = _followed(_verdict("unresolved"), carried=(carried,))
        self.assertEqual(
            _asked(records), [(ASKING.check, "a.toml#1 found `unresolved`")]
        )


if __name__ == "__main__":
    unittest.main()
