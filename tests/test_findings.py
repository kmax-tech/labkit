"""Audit findings as data (2026-10-12): written by labkit-audit, decided by the person, read by preflight."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.formats import findings

BLOCK = "b10c0000000a"  # the promise block every fixture record names
RUN = "2026-01-01T00-00-00_0001"  # the run every analysis fixture record names
SHOWN = "5" * 12  # what every analysis fixture record was shown of RUN
TWO = [
    ("BLOCKER", "BLOCKER · a.py:1 · x · y · LAB-038 What the prompt demands · z"),
    ("WARNING", "WARNING · b.py:2 · x · y · LAB-019 The stamp covers everything · z"),
]


def area_with(
    records: list[tuple[str, list[tuple[str, str]]]], at: Path | None = None
) -> Path:
    area = at or Path(tempfile.mkdtemp()) / "experiments" / "01-x"
    area.mkdir(parents=True, exist_ok=True)
    for i, (mode, rows) in enumerate(records):
        findings.write(
            area,
            mode,
            "opus",
            "abc123def456",
            BLOCK,
            (
                sum(1 for g, _ in rows if g == "BLOCKER"),
                sum(1 for g, _ in rows if g == "WARNING"),
                0,
            ),
            rows,
            run_id=RUN if mode == "analysis" else None,
            shown_sha=SHOWN if mode == "analysis" else None,
            now=1_700_000_000 + 60 * i,
        )
    return area


def set_status(path: Path, n: int, status: str, reason: str = "") -> None:
    """Edit the n-th finding the way the person does: status and reason."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("[[finding]]")
    block = (
        parts[n]
        .replace('status = "open"', f'status = "{status}"')
        .replace('reason = ""', f'reason = "{reason}"')
    )
    parts[n] = block
    path.write_text("[[finding]]".join(parts), encoding="utf-8")


class WriteRead(unittest.TestCase):
    def test_roundtrip_every_finding_starts_open(self):
        area = area_with([("preflight", TWO)])
        files = sorted((area / "audits").glob("*.toml"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith("-preflight.toml"))
        rec = findings.read(files[0])
        self.assertEqual(
            (
                rec.mode,
                rec.model,
                rec.scope_sha,
                rec.block_sha,
                rec.run_id,
                rec.verdict,
            ),
            ("preflight", "opus", "abc123def456", BLOCK, None, (1, 1, 0)),
        )
        self.assertEqual([f.grade for f in rec.findings], ["BLOCKER", "WARNING"])
        self.assertEqual([f.status for f in rec.findings], ["open", "open"])
        self.assertEqual(rec.findings[0].text, TWO[0][1])
        self.assertEqual(len(rec.open), 2)

    def test_quotes_and_unicode_survive(self):
        area = area_with(
            [("analysis", [("NOTE", 'NOTE · x · "quoted" · ä · \\ backslash')])]
        )
        rec = findings.area_records(area)[0]
        self.assertEqual(rec.findings[0].text, 'NOTE · x · "quoted" · ä · \\ backslash')

    def test_a_second_audit_in_the_same_minute_does_not_overwrite(self):
        area = Path(tempfile.mkdtemp())
        a = findings.write(
            area, "preflight", "m", "s", "b", (0, 0, 0), [], now=1_700_000_000
        )
        b = findings.write(
            area, "preflight", "m", "s", "b", (0, 0, 0), [], now=1_700_000_000
        )
        self.assertNotEqual(a, b)
        self.assertEqual(len(findings.area_records(area)), 2)

    def test_audits_writing_at_once_keep_every_record(self):
        """Review 2026-10-20: a free name was looked for, then written to —
        two audits at once took one name and one record was lost."""
        import threading

        area = Path(tempfile.mkdtemp())
        start = threading.Barrier(8)
        paths: list[Path] = []

        def one(i: int) -> None:
            start.wait()
            paths.append(
                findings.write(
                    area,
                    "preflight",
                    "m",
                    f"s{i}",
                    "b",
                    (0, 0, 0),
                    [],
                    now=1_700_000_000,
                )
            )

        threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(paths)), 8)
        shas = {r.scope_sha for r in findings.area_records(area)}
        self.assertEqual(shas, {f"s{i}" for i in range(8)})

    def test_a_taken_name_is_skipped_not_overwritten(self):
        """The twin, without threads: a file already holding the first name
        stays as it was."""
        area = Path(tempfile.mkdtemp())
        first = findings.write(
            area, "preflight", "m", "s", "b", (0, 0, 0), [], now=1_700_000_000
        )
        before = first.read_bytes()
        second = findings.write(
            area, "preflight", "m", "t", "b", (0, 0, 0), [], now=1_700_000_000
        )
        self.assertTrue(second.name.endswith("-preflight-2.toml"))
        self.assertEqual(first.read_bytes(), before)

    def test_wrong_mode_or_grade_refuses_to_write(self):
        area = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            findings.write(area, "clarity", "m", "s", "b", (0, 0, 0), [])
        with self.assertRaises(ValueError):
            findings.write(area, "preflight", "m", "s", "b", (0, 0, 0), [("READ", "x")])

    def test_a_verdict_counting_more_than_the_lines_is_refused(self):
        """Two blockers in the verdict, none readable as a line: written, the
        record read as covered with nothing open (audit 2026-10-15)."""
        area = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as cm:
            findings.write(area, "preflight", "m", "s", "b", (2, 0, 0), [])
        self.assertIn("counts 2 blocker(s)", str(cm.exception))
        self.assertEqual(list(area.glob("audits/*")), [])
        # notes are not held; a warning line under a 1-warning verdict is
        findings.write(area, "preflight", "m", "s", "b", (0, 1, 2), [("WARNING", "w")])


class Decisions(unittest.TestCase):
    def test_decided_findings_leave_open(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "fixed")
        set_status(path, 2, "deferred", "own task: the reference line")
        rec = findings.read(path)
        self.assertEqual(len(rec.open), 0)
        self.assertEqual([f.text for f in rec.deferred], [TWO[1][1]])
        self.assertEqual(rec.deferred[0].reason, "own task: the reference line")

    def test_a_decided_status_without_reason_is_loud(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "accepted")
        with self.assertRaises(findings.FindingsError) as cm:
            findings.read(path)
        self.assertIn("owes a reason", str(cm.exception))
        self.assertIn(path.name, str(cm.exception))

    def test_counts_outrunning_the_tables_are_loud_on_read(self):
        """The writer refuses `blockers = 2` without a table; a person editing
        the file can write the same — the reader holds the same line, or the
        record reads as covered with nothing open (review 2026-10-18)."""
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("blockers = 1", "blockers = 2"), encoding="utf-8")
        with self.assertRaises(findings.FindingsError) as cm:
            findings.read(path)
        self.assertIn("counts 2 blocker(s) and 1 warning(s)", str(cm.exception))
        self.assertIn("carries 1 BLOCKER and 1 WARNING", str(cm.exception))
        self.assertIn(path.name, str(cm.exception))
        with self.assertRaises(findings.FindingsError):
            findings.audit_coverage(area, "abc123def456", "preflight", BLOCK)
        # a table cut out of the file is the same loss
        head, _, _ = text.partition("\n[[finding]]")
        path.write_text(head + "\n", encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "carries 0 BLOCKER"):
            findings.read(path)
        # notes are not held, on read as on write
        path.write_text(text.replace("notes = 0", "notes = 5"), encoding="utf-8")
        self.assertEqual(findings.read(path).verdict, (1, 1, 5))

    def test_unknown_status_missing_table_and_bad_toml_are_loud(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        set_status(path, 1, "done", "x")
        with self.assertRaisesRegex(findings.FindingsError, "status 'done'"):
            findings.read(path)
        path.write_text(
            '[[finding]]\ngrade = "NOTE"\ntext = "t"\nstatus = "open"\nreason = ""\n'
        )
        with self.assertRaisesRegex(findings.FindingsError, r"no \[audit\] table"):
            findings.read(path)
        path.write_text("not = [toml\n")
        with self.assertRaisesRegex(findings.FindingsError, "not TOML"):
            findings.read(path)
        with self.assertRaises(findings.FindingsError):
            findings.area_records(area)  # the loud file stays loud through the listing


class HandDecisions(unittest.TestCase):
    """The person decides in the file; nothing else writes it. A reason with
    an unescaped quote made the record unreadable (count probe, 2026-10-20),
    so the file says how a reason is written, and the refusal says where it
    went wrong and how to write it."""

    def test_the_file_says_how_a_reason_is_written(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        text = path.read_text(encoding="utf-8")
        self.assertIn("'single quotes' take one line of text without a '", text)
        # both forms the comment names read back
        decided = text.replace(
            'status = "open"\nreason = ""',
            'status = "accepted"\nreason = \'the "inputs" root is fixed\'',
            1,
        ).replace(
            'status = "open"\nreason = ""',
            'status = "dismissed"\nreason = "a \\"quoted\\" word"',
            1,
        )
        path.write_text(decided, encoding="utf-8")
        rec = findings.read(path)
        self.assertEqual(
            [f.reason for f in rec.findings],
            ['the "inputs" root is fixed', 'a "quoted" word'],
        )

    def test_an_unescaped_quote_is_named_with_its_cure(self):
        area = area_with([("preflight", TWO)])
        path = next((area / "audits").glob("*.toml"))
        text = path.read_text(encoding="utf-8").replace(
            'status = "open"\nreason = ""',
            'status = "accepted"\nreason = "the "inputs" root is fixed"',
            1,
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(findings.FindingsError) as cm:
            findings.read(path)
        said = str(cm.exception)
        self.assertIn("not TOML", said)
        self.assertIn("line", said)
        self.assertIn("'single quotes'", said)


class ModelTextReadsBack(unittest.TestCase):
    """The auditor's finding text is the model's: json left DEL and the
    line breaks `str.splitlines` cuts (U+0085, U+2028, U+2029) raw, and the
    record would not have read back (review of the reason fix, 2026-10-20)."""

    def test_every_character_json_leaves_raw_reads_back(self):
        text = "NOTE · a.py:1 · x\x7fy\u2028z\x85w\u2029v · y · LAB-019 r · z"
        area = area_with([("preflight", [("NOTE", text)])])
        path = next((area / "audits").glob("*.toml"))
        self.assertEqual(findings.read(path).findings[0].text, text)


class WriteDecision(unittest.TestCase):
    """The person's decision, given explicitly, stored safely: the tool
    validates it, writes it as TOML and replaces the file whole. It decides
    nothing (count probes 2026-10-20: two hand-written reasons broke the
    file)."""

    def record(self) -> Path:
        area = area_with([("preflight", TWO)])
        return next((area / "audits").glob("*.toml"))

    def test_one_finding_changes_and_nothing_else(self):
        path = self.record()
        before = findings.read(path)
        text_before = path.read_text(encoding="utf-8")
        reason = 'the "inputs" root is fixed \\ checked\nall 12 rows'
        after = findings.write_decision(path, 2, "accepted", reason)
        self.assertEqual(after.findings[1].status, "accepted")
        self.assertEqual(after.findings[1].reason, reason.strip())
        self.assertEqual(after.findings[0], before.findings[0])
        self.assertEqual(
            (after.date, after.mode, after.scope_sha, after.block_sha, after.verdict),
            (
                before.date,
                before.mode,
                before.scope_sha,
                before.block_sha,
                before.verdict,
            ),
        )
        self.assertEqual(findings.read(path), after)
        changed = [
            (a, b)
            for a, b in zip(text_before.splitlines(), path.read_text().splitlines())
            if a != b
        ]
        self.assertEqual(len(changed), 2, changed)  # the status and the reason line
        self.assertEqual(list(path.parent.glob(".*tmp*")), [])

    def test_a_reason_is_owed_and_a_status_is_one_of_the_list(self):
        path = self.record()
        before = path.read_text(encoding="utf-8")
        for status, reason in (("accepted", " "), ("dismissed", ""), ("done", "x")):
            with self.subTest(status=status):
                with self.assertRaises(findings.FindingsError):
                    findings.write_decision(path, 1, status, reason)
        findings.write_decision(path, 1, "fixed", "")  # fixed owes no reason
        self.assertEqual(findings.read(path).findings[0].status, "fixed")
        findings.write_decision(path, 1, "open", "")
        self.assertEqual(findings.read(path).findings[0].status, "open")
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_a_number_outside_the_record_is_named(self):
        path = self.record()
        for n in (0, 3, -1):
            with self.subTest(n=n):
                with self.assertRaisesRegex(findings.FindingsError, "finding 1..2"):
                    findings.write_decision(path, n, "fixed", "")

    def test_a_broken_file_is_refused_and_left_as_it_is(self):
        path = self.record()
        broken = path.read_text(encoding="utf-8").replace(
            'reason = ""', 'reason = "a "b""', 1
        )
        path.write_text(broken, encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "not TOML"):
            findings.write_decision(path, 1, "fixed", "")
        self.assertEqual(path.read_text(encoding="utf-8"), broken)

    def test_a_table_between_findings_does_not_shift_the_count(self):
        """A sub-table after finding 1, then findings 2 and 3: a count that
        restarted at the sub-table reached 1 again at finding 3."""
        three = TWO + [("NOTE", "NOTE · c.py:3 · x · y · LAB-019 r · z")]
        area = area_with([("preflight", three)])
        path = next((area / "audits").glob("*.toml"))
        text = path.read_text(encoding="utf-8")
        i = text.index("\n[[finding]]", text.index("[[finding]]") + 1)
        extra = '\n[finding.extra]\nnote = "x"\n'
        path.write_text(text[:i] + extra + text[i:], encoding="utf-8")
        findings.write_decision(path, 1, "fixed", "")
        rec = findings.read(path)
        self.assertEqual([f.status for f in rec.findings], ["fixed", "open", "open"])

    def test_a_status_line_not_on_one_line_is_refused(self):
        path = self.record()
        text = path.read_text(encoding="utf-8").replace(
            'status = "open"\nreason = ""', 'reason = ""\nstatus = """\nopen"""', 1
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(findings.FindingsError):
            findings.write_decision(path, 1, "fixed", "")
        self.assertEqual(path.read_text(encoding="utf-8"), text)


class DecideCommand(unittest.TestCase):
    """`labkit-audit AREA --decide N STATUS REASON` writes the newest record
    of the area, or the one `--record` names."""

    def run_main(self, argv):
        from labkit.gates import audit

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = audit.main(argv)
            except SystemExit as exc:
                rc = exc.code
        return rc, out.getvalue(), err.getvalue()

    def test_the_newest_record_is_decided_and_named(self):
        area = area_with([("preflight", TWO), ("analysis", TWO)])
        records = sorted((area / "audits").glob("*.toml"), key=findings.written_order)
        rc, out, err = self.run_main(
            [str(area), "--decide", "1", "dismissed", 'not a "bug": the data say so']
        )
        self.assertEqual(rc, 0, err)
        self.assertIn(records[-1].name, out)
        self.assertEqual(findings.read(records[-1]).findings[0].status, "dismissed")
        self.assertEqual(findings.read(records[0]).findings[0].status, "open")
        self.assertIn("1 open", out)

    def test_record_names_another_one_and_a_bad_decision_exits_2(self):
        area = area_with([("preflight", TWO), ("analysis", TWO)])
        first = sorted((area / "audits").glob("*.toml"), key=findings.written_order)[0]
        rc, _, err = self.run_main(
            [str(area), "--decide", "2", "fixed", "", "--record", str(first)]
        )
        self.assertEqual(rc, 0, err)
        self.assertEqual(findings.read(first).findings[1].status, "fixed")
        rc, out, err = self.run_main([str(area), "--decide", "2", "accepted", ""])
        self.assertEqual(rc, 2)
        self.assertIn("owes a reason", err)
        self.assertEqual(out, "")

    def test_decide_and_mode_do_not_go_together_and_one_is_needed(self):
        area = area_with([("preflight", TWO)])
        rc, _, err = self.run_main(
            [str(area), "--mode", "analysis", "--decide", "1", "fixed", ""]
        )
        self.assertEqual(rc, 2)
        rc, _, err = self.run_main([str(area)])
        self.assertEqual(rc, 2)
        self.assertIn("--mode", err)


class Repo(unittest.TestCase):
    def test_deferred_elsewhere_names_the_other_area_only(self):
        root = Path(tempfile.mkdtemp()) / "experiments"
        here = area_with([("preflight", TWO)], at=root / "17-here")
        there = area_with([("preflight", TWO)], at=root / "16-there")
        for area in (here, there):
            set_status(
                next((area / "audits").glob("*.toml")), 2, "deferred", "own task"
            )
        found = findings.deferred_elsewhere(here, root)
        self.assertEqual(
            [(a.name, f.text) for a, _, f in found], [("16-there", TWO[1][1])]
        )
        self.assertEqual(findings.deferred_elsewhere(there, root)[0][0].name, "17-here")
        self.assertEqual(findings.area_records(root / "99-none"), [])


class AuditCoverage(unittest.TestCase):
    """A full run at minutes/hours owes a preflight record of the code as it
    is now, every finding decided (2026-10-14: a stamp no audit had seen)."""

    SHA = "abc123def456"

    def test_a_decided_preflight_record_of_the_stamp_covers_it(self):
        area = area_with([("preflight", TWO)])
        (path,) = sorted((area / findings.DIR).glob("*.toml"))
        set_status(path, 1, "fixed")
        set_status(path, 2, "accepted", "spread is a limit")
        self.assertIsNone(findings.audit_coverage(area, self.SHA, "preflight", BLOCK))

    def test_no_record_another_sha_or_only_an_analysis_record_does_not(self):
        empty = Path(tempfile.mkdtemp()) / "experiments" / "01-x"
        empty.mkdir(parents=True)
        self.assertIn(
            "audited: none",
            findings.audit_coverage(empty, self.SHA, "preflight", BLOCK) or "",
        )
        area = area_with([("preflight", []), ("analysis", [])])
        gap = findings.audit_coverage(area, "0123456789ab", "preflight", BLOCK) or ""
        self.assertIn("no preflight audit saw the area as it is now", gap)
        self.assertIn(f"audited: code {self.SHA}, promises {BLOCK}", gap)
        analysis_only = area_with([("analysis", [])])
        self.assertIn(
            "audited: none",
            findings.audit_coverage(analysis_only, self.SHA, "preflight", BLOCK) or "",
        )

    def test_an_open_finding_of_the_covering_record_is_named(self):
        area = area_with([("preflight", TWO)])
        self.assertIn(
            "2 finding(s)",
            findings.audit_coverage(area, self.SHA, "preflight", BLOCK) or "",
        )


class Binding(unittest.TestCase):
    """A record binds what the auditor read — code, promises and (analysis)
    the run; until 0.97.1 only the code, so a promise rewritten after the
    audit or a later run under the same code kept the record valid (review
    2026-10-18)."""

    SHA = "abc123def456"

    def test_a_changed_promise_block_is_not_covered(self):
        area = area_with([("preflight", [])])
        self.assertIsNone(findings.audit_coverage(area, self.SHA, "preflight", BLOCK))
        gap = findings.audit_coverage(area, self.SHA, "preflight", "0ther0000000") or ""
        self.assertIn("no preflight audit saw the area as it is now", gap)
        self.assertIn(f"code {self.SHA}, promises 0ther0000000; audited: ", gap)

    def test_an_analysis_audit_of_another_run_is_not_covered(self):
        area = area_with([("analysis", [])])
        self.assertIsNone(
            findings.audit_coverage(area, self.SHA, "analysis", BLOCK, RUN, SHOWN)
        )
        gap = (
            findings.audit_coverage(
                area, self.SHA, "analysis", BLOCK, "2026-01-02T00-00-00_0002", SHOWN
            )
            or ""
        )
        self.assertIn(f"run 2026-01-02T00-00-00_0002, shown {SHOWN}; audited: ", gap)
        self.assertIn(f"run {RUN}", gap)

    def test_the_same_run_showing_other_rows_or_metrics_is_not_covered(self):
        """The run id alone could not tell a metrics.json or output rows
        changed after the audit (review 2026-10-20)."""
        area = area_with([("analysis", [])])
        gap = (
            findings.audit_coverage(area, self.SHA, "analysis", BLOCK, RUN, "6" * 12)
            or ""
        )
        self.assertIn(f"run {RUN}, shown {'6' * 12}; audited: ", gap)
        self.assertIn(f"shown {SHOWN}", gap)

    def test_the_run_is_owed_by_analysis_and_refused_by_preflight(self):
        area = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(ValueError, "names the run it read"):
            findings.write(area, "analysis", "m", "s", "b", (0, 0, 0), [])
        with self.assertRaisesRegex(ValueError, "names none"):
            findings.write(area, "preflight", "m", "s", "b", (0, 0, 0), [], run_id=RUN)
        with self.assertRaisesRegex(ValueError, "names what it was shown"):
            findings.write(area, "analysis", "m", "s", "b", (0, 0, 0), [], run_id=RUN)
        with self.assertRaisesRegex(ValueError, "is shown none"):
            findings.write(
                area, "preflight", "m", "s", "b", (0, 0, 0), [], shown_sha=SHOWN
            )
        with self.assertRaisesRegex(ValueError, "held to the answering run"):
            findings.audit_coverage(area, self.SHA, "analysis", BLOCK)
        with self.assertRaisesRegex(ValueError, "held to the answering run"):
            findings.audit_coverage(area, self.SHA, "analysis", BLOCK, RUN)
        with self.assertRaisesRegex(ValueError, "a preflight audit to neither"):
            findings.audit_coverage(area, self.SHA, "preflight", BLOCK, RUN)
        # a record without a run is written as NO_RUN, and read so
        path = findings.write(
            area,
            "analysis",
            "m",
            "s",
            "b",
            (0, 0, 0),
            [],
            run_id=findings.NO_RUN,
            shown_sha=SHOWN,
        )
        self.assertEqual(findings.read(path).run_id, "none")
        self.assertIn(
            "run none",
            findings.audit_coverage(area, "s", "analysis", "b", RUN, SHOWN) or "",
        )

    def test_a_record_missing_its_binding_is_loud(self):
        area = area_with([("preflight", []), ("analysis", [])])
        pre, ana = sorted((area / "audits").glob("*.toml"))
        text = pre.read_text(encoding="utf-8")
        pre.write_text(text.replace(f'block_sha = "{BLOCK}"\n', ""), encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "block_sha is missing"):
            findings.read(pre)
        pre.write_text(text + f'run_id = "{RUN}"\n', encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "reads no run"):
            findings.read(pre)
        pre.write_text(text + f'shown_sha = "{SHOWN}"\n', encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "reads no run"):
            findings.read(pre)
        text = ana.read_text(encoding="utf-8")
        ana.write_text(text.replace(f'run_id = "{RUN}"\n', ""), encoding="utf-8")
        with self.assertRaisesRegex(findings.FindingsError, "run_id is missing"):
            findings.read(ana)
        # an analysis record written before shown_sha existed is no longer read
        ana.write_text(text.replace(f'shown_sha = "{SHOWN}"\n', ""), encoding="utf-8")
        with self.assertRaisesRegex(
            findings.FindingsError, "run the analysis audit again"
        ):
            findings.read(ana)
