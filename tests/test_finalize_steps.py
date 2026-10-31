"""finalize's named decisions, each testable alone (CODE-006 One function, one thing)."""

import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import head, run_record  # noqa: E402
from labkit.gates import finalize
from labkit.checks import run_record_check, readme_check
from labkit.formats import protocol_block, repo
from labkit.formats.gate import STATIC_EVIDENCE, Findings
from labkit.formats.scope_sha import SourceError


class Steps(unittest.TestCase):
    def _area(self, d: str, result: str | None) -> Path:
        area = Path(d)
        protocol = area / "PROTOCOL-x.md"
        protocol.write_text(head(repeat_cost="low", result=result), encoding="utf-8")
        pid = protocol_block.head(protocol.read_text(encoding="utf-8")).id
        for name in ("2026-10-07T09-00-00_bb22", "2026-10-07T10-00-00_aa11"):
            run = area / "runs" / name
            run.mkdir(parents=True)
            (run / "config.json").write_text(
                json.dumps(run_record(protocol={"id": pid, "path": "PROTOCOL-x.md"})),
                encoding="utf-8",
            )
            (run / "metrics.json").write_text('{"criterion_1_pass": true}')
            (run / "completion.json").write_text(
                json.dumps({"schema_version": 4, "run_kind": "measurement"})
            )
        return protocol

    def _choose(self, protocol: Path) -> tuple[Path | None, Findings]:
        text = protocol.read_text(encoding="utf-8")
        found = Findings(tell=None)
        pid = protocol_block.head(text).id
        return finalize.choose_answering_run(found, protocol, pid, text), found

    def test_the_adopted_run_is_held_though_another_is_newer_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self._area(d, "2026-10-07T09-00-00_bb22")
            run, found = self._choose(protocol)
            assert run is not None
            self.assertEqual(run.name, "2026-10-07T09-00-00_bb22")
            self.assertEqual(found.blocked, [])
            (warning,) = found.found
            self.assertEqual(warning.evidence_kind, STATIC_EVIDENCE)
            self.assertIn(
                "2026-10-07T10-00-00_aa11: bound to this protocol", warning.text
            )
            self.assertIn("--withdraw", warning.text)

    def test_the_twin_before_adoption_holds_the_newest(self):
        with tempfile.TemporaryDirectory() as d:
            run, found = self._choose(self._area(d, None))
            assert run is not None
            self.assertEqual(run.name, "2026-10-07T10-00-00_aa11")
            self.assertEqual((found.blocked, found.warned), ([], []))

    def test_an_adopted_run_with_no_directory_is_one_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self._area(d, "2026-10-07T11-00-00_cc33")
            run, found = self._choose(protocol)
            self.assertIsNone(run)
            (finding,) = found.found
            self.assertIn("no runs/2026-10-07T11-00-00_cc33/", finding.text)
            # the command names the protocol: without it argparse refused it
            # (audit 2026-10-27, H5)
            fix = finding.fix or ""
            self.assertIn('PROTOCOL-x.md --withdraw --why "<why>"', fix)
            self.assertIn(" <run_id>`", fix)
            self.assertNotIn("--force", fix)

    def test_two_protocols_and_none_named_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-a.md").write_text("x")
            (area / "PROTOCOL-b.md").write_text("x")
            self.assertIsNone(repo.choose_protocol(area, None, "finalize"))
            self.assertEqual(
                repo.choose_protocol(area, area / "PROTOCOL-a.md", "finalize"),
                area / "PROTOCOL-a.md",
            )


class DeclaredRunHint(unittest.TestCase):
    """While no result is declared, finalize notes the command that declares
    the answering run and writes its number — a note, not a warning: it is
    the normal state before adoption, and finalize stays clear. A command
    that runs: it names the protocol (review 2026-10-20: `--from-run <run>`
    alone exits 2)."""

    RUN = Path("/x/runs/2026-10-07T10-00-00_aa11")
    PROTOCOL = Path("/x/PROTOCOL-a.md")

    def test_no_declaration_is_a_hint_with_the_command(self):
        hint = finalize.undeclared_hint(
            head(repeat_cost="low"), self.RUN, self.PROTOCOL
        )
        assert hint is not None
        self.assertIn("no result adopted yet ([result])", hint)
        self.assertIn("labkit-adopt /x 2026-10-07T10-00-00_aa11", hint)

    def test_a_declared_run_is_quiet(self):
        text = head(repeat_cost="low", result="2026-10-07T10-00-00_aa11")
        self.assertIsNone(finalize.undeclared_hint(text, self.RUN, self.PROTOCOL))

    def test_a_typed_id_is_a_blocker(self):
        protocol = Path("/x/PROTOCOL-x.md")
        typed = head(repeat_cost="low").replace(
            'preflight_audit = ""\n',
            'preflight_audit = ""\n\n[result]\nrun = "2026-10-07T10-00-00_final"\n',
        )
        (gap,) = finalize.declared_run_gaps(typed, protocol)
        self.assertIn("no run id runlog writes", gap.text)
        self.assertIn("--withdraw", gap.fix or "")
        self.assertIn("labkit-adopt ", gap.fix or "")
        self.assertEqual(
            finalize.declared_run_gaps(
                head(repeat_cost="low", result="2026-10-07T10-00-00_aa11"), protocol
            ),
            [],
        )


class ModelProvenanceGap(unittest.TestCase):
    def _run(self, d: str, metrics: dict, models_resolved: dict) -> Path:
        run = Path(d) / "runs" / "2026-10-08T10-00-00_aaaa"
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 4,
                        "run_kind": "measurement",
                        "models_resolved": models_resolved,
                        "config": {},
                    }
                )
            ),
            encoding="utf-8",
        )
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        return run

    def test_a_model_run_without_models_resolved_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"criterion_1_pass": True, "llm_retries": 0}, {})
            gap = run_record_check.model_provenance_gap(run) or ""
            self.assertIn(
                "called a model, but no run in its lineage recorded models_resolved",
                gap,
            )

    def test_a_model_run_with_models_resolved_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(
                d, {"criterion_1_pass": True, "model_calls": 3}, {"m": {"model": "A"}}
            )
            self.assertIsNone(run_record_check.model_provenance_gap(run))

    def test_a_run_without_model_calls_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"criterion_1_pass": True, "n_rows": 4}, {})
            self.assertIsNone(run_record_check.model_provenance_gap(run))


class ReadmePlaceholders(unittest.TestCase):
    def test_a_stamped_blank_is_named_and_a_filled_readme_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "README.md").write_text(
                "# x\n\n**Die eine Frage.** <ein Satz — dieselbe Frage wie im\n"
                "PROTOCOL-Intent; braucht sie ein und, sind es zwei>\n\nok <3\n"
            )
            got = readme_check.readme_placeholders(area)
            self.assertEqual(len(got), 1)
            self.assertIn("README.md:3", got[0])  # a blank that wraps lines
            (area / "README.md").write_text("# x\n\n**Die eine Frage.** Zählt es?\n")
            self.assertEqual(readme_check.readme_placeholders(area), [])

    def test_no_readme_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(readme_check.readme_placeholders(Path(d)), [])

    def test_angle_brackets_inside_code_spans_are_examples_not_blanks(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "README.md").write_text(
                "**The one question.** the files under `<inputs>/<case_id>/`.\n\n"
                "```\n<inputs>/<case_id>/document-1.txt\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(readme_check.readme_placeholders(area), [])
            (area / "README.md").write_text(
                "**The one question.** <one sentence — the question>\n",
                encoding="utf-8",
            )
            self.assertEqual(
                len(readme_check.readme_placeholders(area)), 1
            )  # the twin: a real blank


ROUTE = (
    "<!-- labkit:route -->\n**Nachvollziehen.**\n"
    "- Vertrag und berichtete Antwort: `PROTOCOL-a.md`\n"
    "- Läufe und Herkunft: `runlog .`\n"
    "- Wirksame Werte: `labkit-params .`\n"
    "- Entscheidung der Kennungen: `scripts/01_measure.py:evaluate_rows`\n"
    "- Unveränderlicher Beleg: `config.json` des gewählten Laufs unter `runs/`\n"
    "<!-- /labkit:route -->\n"
)


class ReadmeRoute(unittest.TestCase):
    def _area(
        self,
        d: str,
        readme: str,
        script: str = "def evaluate_rows(rows):\n    return {}\n",
    ) -> Path:
        area = Path(d)
        (area / "README.md").write_text(readme, encoding="utf-8")
        (area / "scripts").mkdir()
        (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
        return area

    def test_the_stamped_route_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, "# x\n\n" + ROUTE)
            self.assertEqual(readme_check.readme_route(area, "PROTOCOL-a.md"), [])
            # the markers are HTML comments, not stamped blanks
            self.assertEqual(readme_check.readme_placeholders(area), [])

    def test_no_block_is_one_warning(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, "# x\n\nDie Zahlen entstehen in comparison.py.\n")
            got = readme_check.readme_route(area, "PROTOCOL-a.md")
            self.assertEqual(len(got), 1)
            self.assertIn("no <!-- labkit:route -->", got[0])

    def test_a_missing_station_or_wrong_protocol_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE.replace("`labkit-params .`", "`params`"))
            self.assertEqual(
                readme_check.readme_route(area, "PROTOCOL-b.md"),
                [
                    "README.md route: does not name PROTOCOL-b.md",
                    "README.md route: does not name labkit-params",
                ],
            )

    def test_a_script_without_evaluate_rows_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE, script="def evaluate(rows):\n    return {}\n")
            self.assertEqual(
                readme_check.readme_route(area, "PROTOCOL-a.md"),
                ["README.md route: scripts/01_measure.py defines no evaluate_rows"],
            )

    def test_a_script_that_does_not_parse_raises_naming_it(self):
        # a sed edit left an unterminated f-string (Qwen pilot): a traceback
        # out of finalize, not a finding
        broken = 'def evaluate_rows(rows):\n    return f"{rows\n'
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE, script=broken)
            with self.assertRaises(SourceError) as caught:
                readme_check.readme_route(area, "PROTOCOL-a.md")
            self.assertIn("01_measure.py", str(caught.exception))
            self.assertIn("line 2", str(caught.exception))

    def test_finalize_takes_a_script_that_does_not_parse_as_one_blocker(self):
        broken = 'def evaluate_rows(rows):\n    return f"{rows\n'
        for script, blockers in (
            ("def evaluate_rows(rows):\n    return {}\n", []),
            (broken, ["01_measure.py"]),
        ):
            with self.subTest(blockers=blockers), tempfile.TemporaryDirectory() as d:
                area = self._area(d, ROUTE, script=script)
                text = head(repeat_cost="low")
                protocol = area / "PROTOCOL-a.md"
                protocol.write_text(text, encoding="utf-8")
                found = Findings(tell=None)
                finalize.check_open_fields(
                    found, protocol, text, protocol_block.head(text)
                )
                self.assertEqual(len(found.blocked), len(blockers))
                for message, name in zip(found.blocked, blockers):
                    self.assertIn(name, message)
                    self.assertIn("cannot be read as Python", message)
                self.assertFalse([w for w in found.warned if "route" in w])

    def test_no_readme_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(readme_check.readme_route(Path(d), "PROTOCOL-a.md"), [])


if __name__ == "__main__":
    unittest.main()
