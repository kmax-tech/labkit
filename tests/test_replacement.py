"""K1 (docs/notes/2026-10-27-new-registration-contracts.md): a protocol that
declares `[replaces]` answers a new, post-hoc question, and the declaration
binds it — every change of the registration against its predecessor
declared, `type = "exploratory"`, the predecessor's open BLOCKERs decided,
its verdict rendered first. The repair case (2026-10-27): a second area
lowered the criterion's margin 0.25 → 0.15 and declared nothing; a report
that switched its citations from the old area to the new one is a hint,
never a block (independent questions stay free).
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import result_render  # noqa: E402
from labkit.formats import findings, protocol_block, protocol_history  # noqa: E402
from labkit.gates import finalize, report_check, report_hold  # noqa: E402
from protocol_fixture import completed_run, head, registration_of, started_at  # noqa: E402

A_ID, B_ID = "p-aaaaaaaaaaaaaaaa", "p-bbbbbbbbbbbbbbbb"
A_RUN, B_RUN = "2026-10-27T09-00-00_aaaa", "2026-10-27T10-00-00_bbbb"
BODY = "- **Question / hypothesis:** does it hold?\n- **Data profile:** 944 compounds\n"


def block(
    margin: float, sentence: str = "out-of-fold R² beats the null by margin"
) -> str:
    return (
        f'[[promise]]\nid = "criterion-1"\nkey = "criterion_1_pass"\nsentence = "{sentence}"\n'
        f'scope = ["scripts/01_measure.py"]\nconstants = {{ margin = {margin} }}\n\n'
        '[[promise]]\nid = "quality-check-1"\nkey = "quality_check_1_pass"\nsentence = "every item predicted"\n'
        'scope = ["scripts/01_measure.py"]\n'
    )


def replaces(pid: str, *changes: tuple[str, str, str]) -> str:
    rows = "".join(
        f'\n[[replaces.change]]\nwhat = "{w}"\nfrom = "{f}"\nto = "{t}"\nwhy = "the band was wrong"\n'
        for w, f, t in changes
    )
    return f'\n[replaces]\nprotocol = "{pid}"\n{rows}'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class Parse(unittest.TestCase):
    def test_a_replaces_table_reads_and_a_malformed_one_is_named(self):
        text = head(
            promises=block(0.25)
            + replaces(A_ID, ("criterion-1 margin", "0.25", "0.15"))
        )
        rep = protocol_block.replaces(text)
        assert rep is not None
        self.assertEqual(rep.protocol, A_ID)
        self.assertEqual(
            [(c.what, c.from_, c.to) for c in rep.changes],
            [("criterion-1 margin", "0.25", "0.15")],
        )
        self.assertIsNone(protocol_block.replaces(head(promises=block(0.25))))
        for bad, said in (
            (replaces("p-1"), "the id of the protocol"),
            (
                replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")).replace(
                    "the band was wrong", " "
                ),
                "`why` is empty",
            ),
            ('\n[replaces]\nprotocol = "' + A_ID + '"\nwho = "x"\n', "unknown field"),
        ):
            with (
                self.subTest(said=said),
                self.assertRaisesRegex(protocol_block.BlockError, said),
            ):
                protocol_block.replaces(head(promises=block(0.25) + bad))


class Differences(unittest.TestCase):
    def test_every_difference_of_the_registration_is_named(self):
        old = head(promises=block(0.25)) + BODY
        new = head(
            promises=block(0.15, "R² beats the null"), kind="fit"
        ) + BODY.replace("944", "232")
        self.assertEqual(
            protocol_history.registration_differences(old, new),
            [
                ("kind", "compute", "fit"),
                (
                    "criterion-1 sentence",
                    "out-of-fold R² beats the null by margin",
                    "R² beats the null",
                ),
                ("criterion-1 margin", "0.25", "0.15"),
                ("Data profile", "944 compounds", "232 compounds"),
            ],
        )
        self.assertEqual(protocol_history.registration_differences(old, old), [])


class _Areas(unittest.TestCase):
    """Two areas in one repository: A registered and measured, B replacing it."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        _git(self.root, "init", "-q")
        self.a = self.root / "experiments" / "01-a"
        self.b = self.root / "experiments" / "02-b"
        self.a_metrics = {
            "criterion_1_pass": False,
            "quality_check_1_pass": True,
            "criterion_1_score": 0.7,
        }
        self._area(self.a, A_ID, block(0.25), A_RUN, self.a_metrics)

    def _area(
        self, area: Path, pid: str, promises: str, run: str, metrics: dict, **kw
    ) -> Path:
        (area / "scripts").mkdir(parents=True, exist_ok=True)
        (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
        proto = area / "PROTOCOL-x.md"
        proto.write_text(
            head(id=pid, result=run, promises=promises, **kw) + BODY, encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", f"register {area.name}")
        started_at(completed_run(area, run, pid=pid, metrics=metrics), self.root)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", f"run {area.name}")
        return proto

    def _b(self, extra: str, **kw) -> Path:
        return self._area(
            self.b,
            B_ID,
            block(0.15) + extra,
            B_RUN,
            {"criterion_1_pass": True, "quality_check_1_pass": True},
            **kw,
        )

    def gaps(self) -> list[str]:
        ctx = report_check.checked(self.b, self.b / "PROTOCOL-x.md")
        return [g.line for g in report_check.replacement_gaps(ctx)]


class Gate(_Areas):
    def test_an_undeclared_change_is_held_with_the_lines_that_declare_it(self):
        """The repair case's margin, lowered in the new area and not declared."""
        self._b(replaces(A_ID))
        (gap,) = self.gaps()
        self.assertIn("changed against PROTOCOL-x.md", gap)
        self.assertIn("not declared: criterion-1 margin 0.25 → 0.15", gap)
        self.assertIn(
            '[[replaces.change]] what = "criterion-1 margin", from = "0.25", to = "0.15"',
            gap,
        )

    def test_report_check_runs_the_replacement_station(self):
        self._b(replaces(A_ID))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report_check.main([str(self.b)])
        self.assertEqual(code, 1)
        self.assertIn("not declared: criterion-1 margin 0.25 → 0.15", out.getvalue())

    def test_the_twin_every_change_declared_passes(self):
        self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        self.assertEqual(self.gaps(), [])

    def test_a_declared_change_that_is_none_is_held(self):
        self._b(
            replaces(
                A_ID,
                ("criterion-1 margin", "0.25", "0.15"),
                ("quality-check-1 sentence", "x", "y"),
            )
        )
        (gap,) = self.gaps()
        self.assertIn(
            "declares a change the registrations do not show: quality-check-1 sentence x → y",
            gap,
        )

    def test_a_replacement_is_exploratory(self):
        self._b(
            replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")), type="confirmatory"
        )
        (gap,) = self.gaps()
        self.assertIn('type = "exploratory"', gap)

    def test_itself_an_unknown_predecessor_and_a_circle_are_named(self):
        for extra, said in (
            (replaces(B_ID), "its own id"),
            (replaces("p-cccccccccccccccc"), "names no protocol of this repo"),
        ):
            with self.subTest(said=said):
                self._b(extra)
                (gap,) = self.gaps()
                self.assertIn(said, gap)
        # A names B, B names A: a circle
        a = self.a / "PROTOCOL-x.md"
        a.write_text(
            a.read_text().replace("```\n", replaces(B_ID) + "```\n", 1)
            if False
            else a.read_text()
        )
        text = a.read_text(encoding="utf-8")
        a.write_text(
            text.replace("[[promise]]", replaces(B_ID).strip() + "\n\n[[promise]]", 1)
        )
        self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        self.assertTrue(any("in a circle" in g for g in self.gaps()), self.gaps())

    def test_the_predecessors_open_blocker_is_decided_first(self):
        record = findings.write(
            self.a,
            "analysis",
            "opus",
            "0" * 12,
            "1" * 12,
            (1, 0, 0),
            [
                (
                    "BLOCKER",
                    "BLOCKER · scripts/01_measure.py:1 · the target leaks · x · LAB-019 r · z",
                )
            ],
            run_id=A_RUN,
            shown_sha="2" * 12,
            registration=registration_of(self.a),
        )
        self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        (gap,) = self.gaps()
        self.assertIn("its predecessor's BLOCKER is still open", gap)
        self.assertIn(f'--decide 1 deferred "replaced by {B_ID}: <why>"', gap)
        findings.write_decision(
            record, 1, "deferred", f"replaced by {B_ID}: the leak is its question"
        )
        self.assertEqual(self.gaps(), [])

    def test_the_predecessors_verdict_is_rendered_first(self):
        proto = self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        text = proto.read_text(encoding="utf-8")
        line = result_render.rendering(
            self.b, text, self.b / "runs" / B_RUN
        ).recorded_results
        self.assertTrue(
            line.startswith(
                f"replaces {A_ID} (01-a/PROTOCOL-x.md): criterion-1 missed; quality-check-1 met · this question: criterion-1 met; quality-check-1 met"
            ),
            line,
        )
        plain = result_render.rendering(
            self.a, (self.a / "PROTOCOL-x.md").read_text(), self.a / "runs" / A_RUN
        )
        self.assertTrue(
            plain.recorded_results.startswith(
                "criterion-1 missed; quality-check-1 met · recorded: criterion_1_score = 0.7"
            )
        )


class ConflictingRegistrations(_Areas):
    """K3's registration that cannot be told, and its way out through K1:
    two first measurements at one commit, the second with the margin raised
    in the tree (its `uncommitted.patch` keeps the change). A replacement
    declares its changes against each, read back as each run saw it."""

    A2_RUN = "2026-10-27T09-30-00_cccc"

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        _git(self.root, "init", "-q")
        self.a = self.root / "experiments" / "01-a"
        self.b = self.root / "experiments" / "02-b"
        (self.a / "scripts").mkdir(parents=True)
        (self.a / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
        proto = self.a / "PROTOCOL-x.md"
        proto.write_text(head(id=A_ID, promises=block(0.25)) + BODY, encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "register 01-a")
        metrics = {"criterion_1_pass": True, "quality_check_1_pass": True}
        started_at(completed_run(self.a, A_RUN, pid=A_ID, metrics=metrics), self.root)
        proto.write_text(
            head(id=A_ID, result=self.A2_RUN, promises=block(0.3)) + BODY,
            encoding="utf-8",
        )  # not committed: the second run at the same commit saw another block
        second = completed_run(self.a, self.A2_RUN, pid=A_ID, metrics=metrics)
        started_at(second, self.root)
        (second / "uncommitted.patch").write_text(
            _git(self.root, "diff", "HEAD") + "\n", encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "the margin raised, runs")

    def test_k3_holds_the_predecessor(self):
        ctx = report_check.checked(self.a, self.a / "PROTOCOL-x.md")
        (finding,) = finalize.registration_changes(
            ctx.area, ctx.protocol, ctx.head.id, ctx.run
        )
        self.assertEqual(finding.grade, report_check.BLOCKER)
        self.assertIn("recorded different registrations", finding.line)

    def test_a_change_owed_against_one_of_them_is_held_naming_that_run(self):
        self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        (gap,) = self.gaps()
        self.assertIn(f"as its first measurement {self.A2_RUN} saw it", gap)
        self.assertIn("with its uncommitted.patch", gap)
        self.assertIn("not declared: criterion-1 margin 0.3 → 0.15", gap)

    def test_the_twin_declared_against_each_passes(self):
        self._b(
            replaces(
                A_ID,
                ("criterion-1 margin", "0.25", "0.15"),
                ("criterion-1 margin", "0.3", "0.15"),
            )
        )
        self.assertEqual(self.gaps(), [])

    def test_a_registration_that_cannot_be_read_back_hands_over(self):
        (self.a / "runs" / self.A2_RUN / "uncommitted.patch").unlink()
        self._b(
            replaces(
                A_ID,
                ("criterion-1 margin", "0.25", "0.15"),
                ("criterion-1 margin", "0.3", "0.15"),
            )
        )
        (gap,) = self.gaps()
        self.assertIn(f"its first measurement {self.A2_RUN} recorded block", gap)
        self.assertIn("cannot be read back", gap)
        self.assertIn(
            "until they can, hand over: `labkit-audit <area> --findings`", gap
        )
        self.assertIn("the handover leaves no [result] table", gap)
        self.assertNotIn("fetch", gap)

    def test_the_predecessor_renders_no_verdict(self):
        proto = self._b(
            replaces(
                A_ID,
                ("criterion-1 margin", "0.25", "0.15"),
                ("criterion-1 margin", "0.3", "0.15"),
            )
        )
        line = result_render.rendering(
            self.b, proto.read_text(encoding="utf-8"), self.b / "runs" / B_RUN
        ).recorded_results
        self.assertTrue(
            line.startswith(
                f"replaces {A_ID} (01-a/PROTOCOL-x.md): no verdict — its first "
                f"measurements recorded different registrations · this question: "
            ),
            line,
        )


class MovedPredecessor(_Areas):
    """The repair case's laundering: the predecessor's bar moved after its
    first measurement (K3 holds it), and a replacement must not carry the
    moved verdict as the earlier one."""

    def test_a_verdict_under_a_moved_bar_is_not_rendered_first(self):
        proto = self.a / "PROTOCOL-x.md"
        later = "2026-10-27T09-30-00_cccc"
        proto.write_text(
            head(id=A_ID, result=later, promises=block(0.1)) + BODY, encoding="utf-8"
        )
        _git(self.root, "commit", "-qam", "the margin lowered after the first run")
        started_at(
            completed_run(
                self.a,
                later,
                pid=A_ID,
                metrics={"criterion_1_pass": True, "quality_check_1_pass": True},
            ),
            self.root,
        )
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "run again")
        proto_b = self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        line = result_render.rendering(
            self.b, proto_b.read_text(encoding="utf-8"), self.b / "runs" / B_RUN
        ).recorded_results
        self.assertTrue(
            line.startswith(
                f"replaces {A_ID} (01-a/PROTOCOL-x.md): no verdict — its "
                f"registration changed after the first measurement {A_RUN}"
            ),
            line,
        )


class Hint(_Areas):
    """The report switch is a hint, never a block."""

    def _report(self, *runs: str) -> Path:
        report = self.root / "REPORT.md"
        report.write_text(
            "# Report\n\n" + "".join(f"run {r}\n" for r in runs), encoding="utf-8"
        )
        return report

    def hints(self, report: Path) -> list[str]:
        sources = report_hold.repo_sources(self.root, staged=False)
        return report_hold.replacement_hints(
            report,
            "REPORT.md",
            report.read_text(encoding="utf-8"),
            self.root.resolve(),
            sources,
        )

    def test_a_report_moved_to_an_undeclared_successor_is_a_hint(self):
        report = self._report(A_RUN)
        _git(self.root, "add", "REPORT.md")
        _git(self.root, "commit", "-qm", "report A")
        self._b("")
        self._report(B_RUN)
        (hint,) = self.hints(report)
        self.assertIn("declares no [replaces] of it", hint)
        self.assertIn(f'[replaces] protocol = "{A_ID}"', hint)

    def test_the_twins_a_declared_successor_and_independent_questions_give_none(self):
        report = self._report(A_RUN)
        _git(self.root, "add", "REPORT.md")
        _git(self.root, "commit", "-qm", "report A")
        self._b(replaces(A_ID, ("criterion-1 margin", "0.25", "0.15")))
        self._report(B_RUN)
        self.assertEqual(self.hints(report), [])
        self._report(A_RUN, B_RUN)  # both questions answered: nothing dropped
        self.assertEqual(self.hints(report), [])


if __name__ == "__main__":
    unittest.main()
