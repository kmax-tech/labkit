"""finalize's named decisions, each testable alone (CODE-006 One function, one thing)."""

import json
import re
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from protocol_fixture import PID, head, run_record  # noqa: E402
from state_fixture import AREA, area_state
from labkit.formats.area_state import state_of
from labkit.gates import finalize
from labkit.checks import run_record_check, readme_check
from labkit.formats import protocol_block, repo
from labkit.formats.gate import (
    BLOCKER,
    GUARANTEED,
    NOT_EXECUTABLE,
    OPEN_RULE,
    TECHNICAL_RULE,
    cited_rule,
    STATIC_EVIDENCE,
    VIOLATED,
    WARNING,
    Findings,
    GateFinding,
)
from labkit.gates.preflight import AreaTests, tell_test_run
from labkit.formats.runs import LLM_CALLS_FILE
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
                json.dumps({"schema_version": 5, "run_kind": "measurement"})
            )
        return protocol

    def _choose(self, protocol: Path) -> tuple[Path | None, Findings]:
        text = protocol.read_text(encoding="utf-8")
        found = Findings(tell=None)
        pid = protocol_block.head(text).id
        state = state_of(protocol.parent)
        return finalize.choose_answering_run(found, protocol, pid, text, state), found

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
            self.assertEqual(warning.rule, OPEN_RULE)

    def test_the_twin_before_adoption_holds_the_newest(self):
        with tempfile.TemporaryDirectory() as d:
            run, found = self._choose(self._area(d, None))
            assert run is not None
            self.assertEqual(run.name, "2026-10-07T10-00-00_aa11")
            self.assertEqual((found.blocked, found.warned), ([], []))

    def test_station_1_tells_the_run_checks_sentences_as_warnings(self):
        """The station forwards the run checks' sentences about the chosen
        run: a model run whose lineage recorded no models_resolved, and its
        single draw, are guaranteed warnings, each with the rule of its
        cause."""
        with tempfile.TemporaryDirectory() as d:
            protocol = self._area(d, None)
            chosen = protocol.parent / "runs" / "2026-10-07T10-00-00_aa11"
            (chosen / "metrics.json").write_text(
                '{"criterion_1_pass": true, "llm_retries": 0}'
            )
            text = protocol.read_text(encoding="utf-8")
            found = Findings(tell=None)
            run = finalize.check_answering_run(
                found,
                protocol.parent,
                protocol,
                text,
                protocol_block.head(text).id,
                state_of(protocol.parent),
            )
        self.assertEqual(run, chosen)
        warned = [f for f in found.found if f.grade == "WARNING"]
        self.assertEqual(len(warned), 2, [f.text for f in found.found])
        self.assertIn("no run in its lineage recorded models_resolved", warned[0].text)
        self.assertIn("is one draw — no spread", warned[1].text)
        self.assertEqual(
            [f.rule for f in warned],
            [run_record_check.LAB_027, run_record_check.LAB_036],
        )

    def test_station_1_forwards_the_arms_lines_as_guaranteed_warnings(self):
        """What the station adds to `arm_findings` (its conditions:
        tests/test_arm_lines.py): nothing — each warning is told as the
        check built it, its rule the cause's. The twin: no warning, none
        told."""
        rule = cited_rule("LAB-027 Model discipline")
        for lines in (["arm b: 3 of 12 rows without a prediction"], []):
            with self.subTest(lines=lines), tempfile.TemporaryDirectory() as d:
                protocol = self._area(d, None)
                text = protocol.read_text(encoding="utf-8")
                found = Findings(tell=None)
                built = [
                    GateFinding(WARNING, line, rule=rule, evidence_kind=GUARANTEED)
                    for line in lines
                ]
                with mock.patch.object(finalize, "arm_findings", return_value=built):
                    finalize.check_answering_run(
                        found,
                        protocol.parent,
                        protocol,
                        text,
                        protocol_block.head(text).id,
                        state_of(protocol.parent),
                    )
                forwarded = [
                    (f.grade, f.evidence_kind, f.rule)
                    for f in found.found
                    if f.text in lines
                ]
                self.assertEqual(
                    forwarded, [("WARNING", GUARANTEED, rule)] * len(lines)
                )

    def test_an_adopted_run_with_no_directory_is_one_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            protocol = self._area(d, "2026-10-07T11-00-00_cc33")
            run, found = self._choose(protocol)
            self.assertIsNone(run)
            (finding,) = found.found
            self.assertIn("no runs/2026-10-07T11-00-00_cc33/", finding.text)
            # the command names the protocol: without it argparse refuses it
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
    that runs: it names the protocol (`--from-run <run>` alone exits 2)."""

    RUN = Path("/x/runs/2026-10-07T10-00-00_aa11")
    PROTOCOL = Path("/x/PROTOCOL-a.md")

    def test_no_declaration_names_labkit_next_and_no_step(self):
        """finalize names no step of its own: the note points to
        `labkit-next AREA`, the one explainer —
        finalize is a station of `next`'s chain, so it cannot print the
        step without calling itself."""
        note = finalize.undeclared_note(head(repeat_cost="low"), self.PROTOCOL)
        assert note is not None
        self.assertIn("no result adopted yet ([result])", note)
        self.assertIn(f"`labkit-next {repo.shown(Path('/x'), Path.cwd())}`", note)
        for command in ("labkit-adopt", "labkit-audit", "protocol-fill"):
            self.assertNotIn(command, note)

    def test_a_declared_run_is_quiet(self):
        text = head(repeat_cost="low", result="2026-10-07T10-00-00_aa11")
        self.assertIsNone(finalize.undeclared_note(text, self.PROTOCOL))

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
        self.assertEqual(gap.rule, TECHNICAL_RULE)
        self.assertEqual(
            finalize.declared_run_gaps(
                head(repeat_cost="low", result="2026-10-07T10-00-00_aa11"), protocol
            ),
            [],
        )


class ModelProvenanceFindings(unittest.TestCase):
    """The station's reading of the model a run's record names: the call
    log first (a blocker, its condition in the rule test), the metrics keys
    after it (a warning)."""

    def _run(
        self,
        d: str,
        metrics: dict,
        models_resolved: dict,
        calls: list[dict] | None = None,
    ) -> Path:
        run = Path(d) / "runs" / "2026-10-08T10-00-00_aaaa"
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "schema_version": 5,
                        "run_kind": "measurement",
                        "models_resolved": models_resolved,
                        "config": {},
                    }
                )
            ),
            encoding="utf-8",
        )
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        if calls is not None:
            (run / LLM_CALLS_FILE).write_text(
                "".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8"
            )
        return run

    @staticmethod
    def _stand_in_hit() -> dict:
        """A call-log line of a replayed answer stored outside any run, as
        the a997 run of the two-stage demo holds it."""
        return {
            "key": "70" * 32,
            "alias": "standin",
            "hit": True,
            "origin": {"run": None, "written": "2026-11-21T10:48:16"},
            "usage": dict.fromkeys(
                ("prompt_tokens", "output_tokens", "cached_tokens", "cost_usd")
            ),
            "uncached": None,
        }

    def test_a_model_run_without_models_resolved_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"criterion_1_pass": True, "llm_retries": 0}, {})
            (gap,) = run_record_check.model_provenance_findings(Path(d), run)
            self.assertEqual(gap.grade, WARNING)
            self.assertIn(
                "called a model, but no run in its lineage recorded models_resolved",
                gap.text,
            )
            self.assertEqual(gap.rule, run_record_check.LAB_027)

    def test_a_model_run_with_models_resolved_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(
                d, {"criterion_1_pass": True, "model_calls": 3}, {"m": {"model": "A"}}
            )
            self.assertEqual(
                run_record_check.model_provenance_findings(Path(d), run), []
            )

    def test_a_run_without_model_calls_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"criterion_1_pass": True, "n_rows": 4}, {})
            self.assertEqual(
                run_record_check.model_provenance_findings(Path(d), run), []
            )

    def test_a_call_log_without_its_alias_in_the_record_blocks(self):
        # the a997 case: no call count in metrics.json, two replayed stand-in
        # answers in the call log, models_resolved empty — finalize said clear
        with tempfile.TemporaryDirectory() as d:
            calls = [self._stand_in_hit(), self._stand_in_hit()]
            run = self._run(d, {"unique_rank_share": 0.6}, {}, calls)
            (gap,) = run_record_check.model_provenance_findings(Path(d), run)
            self.assertEqual((gap.grade, gap.evidence_kind), (BLOCKER, GUARANTEED))
            self.assertIn("alias `standin` (2 stored outside any run)", gap.text)

    def test_the_twin_a_call_log_whose_alias_the_record_names_passes(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(
                d,
                {"unique_rank_share": 0.6, "model_calls": 2},
                {"standin": {"backend": "ollama"}},
                [self._stand_in_hit(), self._stand_in_hit()],
            )
            self.assertEqual(
                run_record_check.model_provenance_findings(Path(d), run), []
            )

    def test_a_run_without_its_config_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"n_rows": 4}, {}, [self._stand_in_hit()])
            (run / "config.json").unlink()
            (gap,) = run_record_check.model_provenance_findings(Path(d), run)
            self.assertEqual((gap.grade, gap.rule), (BLOCKER, TECHNICAL_RULE))
            self.assertIn("has no config.json", gap.text)

    def test_a_call_log_that_does_not_read_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._run(d, {"n_rows": 4}, {}, [{"alias": "standin"}])
            (gap,) = run_record_check.model_provenance_findings(Path(d), run)
            self.assertEqual((gap.grade, gap.rule), (BLOCKER, TECHNICAL_RULE))
            self.assertIn(f"{LLM_CALLS_FILE}:1", gap.text)


class ModelRecordsByRunKind(unittest.TestCase):
    """The call log against the model records, read from run directories,
    for each way a run builds on another: a repeat (`repeat_of`, its own
    record), a derived run (`derived_from`, no record of its own), an
    exploratory step (`[builds_on]` lives in the protocol; its run record
    is a fresh run's), and a hit stored by a run of another area of the lab."""

    BASIS = "2026-11-20T09-00-00_bb22"
    RUN = "2026-11-21T10-00-00_cc33"
    NAMED = {"standin": {"backend": "openai"}}

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.lab = Path(tmp.name)
        (self.lab / "models.toml").write_text("", encoding="utf-8")
        self.area = self.lab / "experiments" / "01-a"

    def _run(
        self,
        run_id: str,
        models_resolved: dict,
        calls: list[dict] | None = None,
        *,
        area: Path | None = None,
        **record: object,
    ) -> Path:
        run = (area or self.area) / "runs" / run_id
        run.mkdir(parents=True)
        (run / "config.json").write_text(
            json.dumps(run_record({"models_resolved": models_resolved, **record})),
            encoding="utf-8",
        )
        (run / "metrics.json").write_text("{}", encoding="utf-8")
        if calls is not None:
            (run / LLM_CALLS_FILE).write_text(
                "".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8"
            )
        return run

    @staticmethod
    def _line(*, hit: bool, origin_run: str | None = None) -> dict:
        return {
            "key": "ab" * 32,
            "alias": "standin",
            "hit": hit,
            "origin": {"run": origin_run, "written": "2026-11-20T09:00:00"}
            if hit
            else None,
            "usage": dict.fromkeys(
                ("prompt_tokens", "output_tokens", "cached_tokens", "cost_usd")
            ),
            "uncached": None,
        }

    def _found(self, run: Path):
        return run_record_check.model_provenance_findings(self.area, run)

    def test_a_repeat_records_its_own_model_and_is_held_to_it(self):
        self._run(self.BASIS, self.NAMED)
        asked = [self._line(hit=False)]
        named = self._run(self.RUN, self.NAMED, asked, repeat_of=self.BASIS, draw=2)
        self.assertEqual(self._found(named), [])
        unnamed = self._run(
            "2026-11-21T11-00-00_dd44", {}, asked, repeat_of=self.BASIS, draw=2
        )
        (f,) = self._found(unnamed)
        self.assertEqual(f.grade, BLOCKER)

    def test_a_derived_run_replaying_its_parent_s_answers_is_held_by_the_parent(self):
        replayed = [self._line(hit=True, origin_run=self.BASIS)]
        self._run(self.BASIS, self.NAMED)
        run = self._run(self.RUN, {}, replayed, derived_from=self.BASIS)
        self.assertEqual(self._found(run), [])

    def test_a_derived_run_whose_parent_names_no_model_blocks(self):
        replayed = [self._line(hit=True, origin_run=self.BASIS)]
        self._run(self.BASIS, {})
        run = self._run(self.RUN, {}, replayed, derived_from=self.BASIS)
        (f,) = self._found(run)
        self.assertEqual(f.grade, BLOCKER)
        self.assertIn(f"stored by run {self.BASIS}", f.text)

    def test_a_derived_run_asking_the_model_is_a_warning_not_a_blocker(self):
        # runlog writes no models_resolved for a derived run: no blocker may
        # demand one; which model answered stays unrecorded and is said
        self._run(self.BASIS, self.NAMED)
        run = self._run(self.RUN, {}, [self._line(hit=False)], derived_from=self.BASIS)
        (f,) = self._found(run)
        self.assertEqual((f.grade, f.evidence_kind), (WARNING, GUARANTEED))

    def test_an_exploratory_step_is_held_like_a_fresh_run(self):
        # a step's basis stands in the protocol's [builds_on]; its run record
        # carries no link and its own models_resolved, as a fresh run's
        self._run(self.BASIS, self.NAMED)
        stored = [self._line(hit=True, origin_run=self.BASIS)]
        self.assertEqual(self._found(self._run(self.RUN, {}, stored)), [])
        asked = self._run("2026-11-21T11-00-00_dd44", {}, [self._line(hit=False)])
        (f,) = self._found(asked)
        self.assertEqual(f.grade, BLOCKER)

    def test_an_answer_stored_by_a_run_of_another_area_is_found_there(self):
        other = self.lab / "experiments" / "02-b"
        self._run(self.BASIS, self.NAMED, area=other)
        stored = [self._line(hit=True, origin_run=self.BASIS)]
        self.assertEqual(self._found(self._run(self.RUN, {}, stored)), [])

    def test_an_answer_whose_storing_run_is_nowhere_blocks(self):
        stored = [self._line(hit=True, origin_run=self.BASIS)]
        (f,) = self._found(self._run(self.RUN, {}, stored))
        self.assertIn(f"no run {self.BASIS} in this area or another area", f.text)


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

    def test_finalize_tells_a_blank_as_static_evidence(self):
        # the pattern also matches an `<…>` written on purpose, so the
        # sentence is an indication, not an exact check
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "README.md").write_text(
                "# x\n\n**The one question.** <one sentence>\n", encoding="utf-8"
            )
            text = head(repeat_cost="low")
            protocol = area / "PROTOCOL-a.md"
            protocol.write_text(text, encoding="utf-8")
            found = Findings(tell=None)
            finalize.check_open_fields(
                found,
                protocol,
                text,
                protocol_block.head(text),
                state_of(protocol.parent),
            )
            (blank,) = [f for f in found.found if "stamped placeholder" in f.text]
            self.assertEqual(blank.evidence_kind, STATIC_EVIDENCE)

    def test_a_placeholder_records_the_field_rule_only_in_a_must_field(self):
        with tempfile.TemporaryDirectory() as d:
            text = (
                head(repeat_cost="high")
                + "- **Unit:** <one file>\n- **Problem in one sentence:** <which>\n"
            )
            protocol = Path(d) / "PROTOCOL-a.md"
            protocol.write_text(text, encoding="utf-8")
            found = Findings(tell=None)
            finalize.check_open_fields(
                found,
                protocol,
                text,
                protocol_block.head(text),
                state_of(protocol.parent),
            )
            rules = {
                f.text.rsplit(": ", 1)[1]: f.rule
                for f in found.found
                if f.text.startswith("PROTOCOL-a.md:")
            }
            self.assertEqual(
                rules,
                {"Unit": finalize.LAB_011, "Problem in one sentence": OPEN_RULE},
            )

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
            self.assertIn("no <!-- labkit:route -->", got[0].text)
            self.assertEqual(got[0].rule, TECHNICAL_RULE)  # the format convention

    def test_a_missing_station_or_wrong_protocol_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE.replace("`labkit-params .`", "`params`"))
            got = readme_check.readme_route(area, "PROTOCOL-b.md")
            self.assertEqual(
                [g.text for g in got],
                [
                    "README.md route: does not name PROTOCOL-b.md",
                    "README.md route: does not name labkit-params",
                ],
            )
            self.assertEqual({g.rule for g in got}, {TECHNICAL_RULE})

    def test_a_script_without_evaluate_rows_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            area = self._area(d, ROUTE, script="def evaluate(rows):\n    return {}\n")
            got = readme_check.readme_route(area, "PROTOCOL-a.md")
            self.assertEqual(
                [g.text for g in got],
                ["README.md route: scripts/01_measure.py defines no evaluate_rows"],
            )
            self.assertEqual(got[0].rule, readme_check.CODE_016)

    def test_a_script_that_does_not_parse_raises_naming_it(self):
        # an unterminated f-string, as a sed edit leaves one: an error naming
        # the script and its line, not a traceback
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
                    found,
                    protocol,
                    text,
                    protocol_block.head(text),
                    state_of(protocol.parent),
                )
                self.assertEqual(len(found.blocked), len(blockers))
                for message, name in zip(found.blocked, blockers):
                    self.assertIn(name, message)
                    self.assertIn("cannot be read as Python", message)
                self.assertFalse([w for w in found.warned if "route" in w])

    def test_no_readme_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(readme_check.readme_route(Path(d), "PROTOCOL-a.md"), [])


class AHeadWithoutAProtocolId(unittest.TestCase):
    """Station 1: a head without a stamped `[protocol] id` binds no run —
    one blocker, and no run is chosen; read from a state built in memory."""

    def test_no_id_is_one_blocker_and_no_run(self):
        found = Findings(tell=None)
        protocol = AREA / "PROTOCOL-x.md"
        run = finalize.choose_answering_run(found, protocol, None, "", area_state())
        self.assertIsNone(run)
        (f,) = found.found
        self.assertTrue(f.text.startswith("no stamped protocol id ([protocol] id)"))
        self.assertIn("labkit-init exp", f.fix or "")
        self.assertEqual(f.rule, cited_rule("LAB-043 Runs go through `runlog`"))

    def test_the_twin_a_stamped_id_goes_on_to_the_choice(self):
        # nothing bound to the id: the choice's own blocker, not this one
        found = Findings(tell=None)
        protocol = AREA / "PROTOCOL-x.md"
        finalize.choose_answering_run(found, protocol, PID, "", area_state())
        self.assertFalse(
            any(f.text.startswith("no stamped protocol id") for f in found.found)
        )


class DataCountsStation(unittest.TestCase):
    """Station 5 forwards `data_counts.counts_gap` (its conditions:
    tests/test_data_counts.py) as one blocker naming the command that writes
    the counts again; read from a state built in memory."""

    PROTOCOL = AREA / "PROTOCOL-x.md"

    def _station(self, scope: str) -> tuple[bool, Findings]:
        found = Findings(tell=None)
        text = f"- **Data / scope:** {scope}\n"
        held = finalize.check_data_counts(found, self.PROTOCOL, text, area_state())
        return held, found

    def test_counts_of_a_run_the_area_lacks_block(self):
        held, found = self._station("data/x.csv · counts (prepare run r9): 4 items")
        self.assertFalse(held)
        (f,) = found.found
        self.assertIn("names prepare run r9, which the area does not have", f.text)
        self.assertIn("--data-counts r9", f.fix or "")
        # a named run the area does not have: the cause's rule, not the station's
        self.assertEqual(f.rule, TECHNICAL_RULE)

    def test_the_twin_a_scope_without_generated_counts_passes(self):
        held, found = self._station("data/x.csv, 4 items")
        self.assertEqual((held, found.found), (True, []))


class WaysOutUnderAPathWithASpace(unittest.TestCase):
    """Station 5's two ways out name their command through its builder
    (`commands.data_counts_command`, `commands.gate_command`): under an area
    path with a space the printed line reads back as the words it means. The
    twin: a path without a space is printed bare, as before."""

    @staticmethod
    def _printed(fix: str | None) -> list[str]:
        """The words of the last command FIX names between backticks."""
        return shlex.split(re.findall(r"`([^`]*)`", fix or "")[-1])

    def _counts_fix(self, protocol: Path) -> str | None:
        found = Findings(tell=None)
        text = "- **Data / scope:** data/x.csv · counts (prepare run r9): 4 items\n"
        state = area_state(area=protocol.parent)
        self.assertFalse(finalize.check_data_counts(found, protocol, text, state))
        (f,) = found.found
        return f.fix

    def test_the_counts_command_reads_back_as_four_words(self):
        protocol = Path("my lab") / "01 x" / "PROTOCOL-x.md"
        self.assertEqual(
            self._printed(self._counts_fix(protocol)),
            ["protocol-fill", "my lab/01 x/PROTOCOL-x.md", "--data-counts", "r9"],
        )

    def test_the_twin_a_plain_path_is_printed_bare(self):
        fix = self._counts_fix(Path("area") / "PROTOCOL-x.md")
        self.assertIn("`protocol-fill area/PROTOCOL-x.md --data-counts r9`", fix or "")

    def _repeated_fix(self, area: Path) -> str:
        text = head(repeat_cost="low") + "- **Unit:** one\n- **Unit:** two\n"
        found = Findings(tell=None)
        finalize.check_open_fields(
            found,
            area / "PROTOCOL-x.md",
            text,
            protocol_block.head(text),
            area_state(area=area),
        )
        (fix,) = [f.fix for f in found.found if "written 2 times" in f.text]
        return fix or ""

    def test_the_finalize_after_a_repeated_field_reads_back_as_two_words(self):
        fix = self._repeated_fix(Path("my lab") / "01 x")
        self.assertEqual(self._printed(fix), ["finalize", "my lab/01 x"])

    def test_the_twin_a_plain_area_is_printed_bare(self):
        self.assertIn("then `finalize area`", self._repeated_fix(Path("area")))


class AreaTestsTold(unittest.TestCase):
    """What a run of the area's tests found, told by one rendering for
    preflight and finalize (`preflight.tell_test_run`) from the value
    `area_tests` gives — no test is run here."""

    FILE = AREA / "tests" / "test_01_x.py"

    def _told(self, state: str, tail: list[str]) -> Findings:
        found = Findings(tell=None)
        tested = AreaTests("tests/test_01_*.py", [self.FILE], state, tail)
        tell_test_run(found, tested, "evaluate() lost its check", finalize.CODE_003)
        return found

    def test_no_pytest_warns_as_a_check_not_executed(self):
        (f,) = self._told("no-pytest", []).found
        self.assertEqual((f.grade, f.rule), ("WARNING", TECHNICAL_RULE))
        self.assertIn("pytest is not installed", f.text)
        # nothing was tested: the line says so, a failure's does not
        self.assertEqual(f.outcome, NOT_EXECUTABLE)
        self.assertIn("WARNING (check not executable)", f.line)
        (failed,) = self._told("failed", ["1 failed"]).found
        self.assertNotIn("check not executable", failed.line)

    def test_tests_that_did_not_run_block_as_not_executable(self):
        (f,) = self._told("not run", ["ERROR collecting", "1 error in 0.1s"]).found
        self.assertEqual(
            (f.grade, f.outcome, f.rule),
            ("BLOCKER", NOT_EXECUTABLE, TECHNICAL_RULE),
        )
        self.assertIn("test_01_x.py did not run (1 error in 0.1s)", f.text)

    def test_failing_tests_block_naming_the_counts(self):
        (f,) = self._told("failed", ["FAILED test_x", "1 failed in 0.1s"]).found
        self.assertEqual(
            (f.grade, f.outcome, f.rule),
            (
                "BLOCKER",
                VIOLATED,
                finalize.CODE_003,
            ),
        )
        self.assertIn(
            "test_01_x.py failed (1 failed in 0.1s) — evaluate() lost its check", f.text
        )

    def test_the_twin_passing_tests_are_a_note(self):
        self.assertEqual(self._told("ok", []).found, [])


class ARegistrationReleaseThatCannotBeChecked(unittest.TestCase):
    """Station 2: when whether a correction in place releases a field
    cannot be told (an `AuditError` of the follow-up's coverage), that is
    one blocker naming why — never an unreleased change whose way back
    would undo the correction. Composition: the comparison is stubbed."""

    def _held(self, inner) -> list:
        from unittest import mock

        from labkit.formats.area_state import Measured
        from labkit.gates import registration_hold
        from state_fixture import area_evidence

        with mock.patch.object(registration_hold, "_scope_held", inner):
            return registration_hold.scope_changes(
                AREA,
                AREA / "PROTOCOL-x.md",
                PID,
                AREA / "runs" / "r1",
                None,
                Measured(AREA, PID, (), (), (), ()),
                area_state(),
                area_evidence(),
            )

    def test_an_audit_error_is_one_blocker_with_its_way_out(self):
        from labkit.checks.audit_binding import AuditError

        def fails(*_a, **_k):
            raise AuditError("the follow-up's record does not read", fix="restore it")

        (f,) = self._held(fails)
        self.assertIn("cannot be checked: the follow-up's record does not read", f.text)
        self.assertEqual((f.fix, f.rule), ("restore it", TECHNICAL_RULE))

    def test_the_twin_a_comparison_that_runs_is_its_own_answer(self):
        self.assertEqual(self._held(lambda *_a, **_k: []), [])


class AnUnlistedHistoryComesBeforeTheOtherHolds(unittest.TestCase):
    """Station 2 (`registration_station.station_changes`): a history git
    could not list is the one finding, before the hold on a start file
    that is found nowhere — that check did not run on the commits' files.
    The twin, a history that was listed, leaves the other hold its turn.
    Composition: the state is written down, no repository is read for it."""

    WORDS = "what git holds under area/runs/ cannot be listed: fatal: bad object"
    MISSING = "2026-10-07T10-00-00_ab12"

    def _station(self, history_unread: str) -> list[GateFinding]:
        from labkit.formats.area_state import Measured
        from labkit.formats.protocol_history import Workflow
        from labkit.gates import registration_station
        from state_fixture import area_evidence

        measured = Measured(AREA, PID, (), (), (), (), missing_starts=(self.MISSING,))
        state = area_state(history_unread=history_unread, measured={PID: measured})
        flow, holds = registration_station.station_changes(
            AREA,
            AREA / "PROTOCOL-x.md",
            PID,
            AREA / "runs" / "r1",
            state,
            area_evidence(),
        )
        # either hold leaves the first measurement untold: no workflow is read
        self.assertIs(flow, Workflow.UNDECIDED)
        return holds

    def test_an_unlisted_history_is_the_one_blocker(self):
        from labkit.formats.gate import BLOCKER
        from labkit.gates.registration_hold import UNREAD_HISTORY

        (hold,) = self._station(self.WORDS)
        self.assertEqual(
            (hold.grade, hold.outcome, hold.known_as),
            (BLOCKER, NOT_EXECUTABLE, UNREAD_HISTORY),
        )
        self.assertIn(self.WORDS, hold.text)
        self.assertNotIn("a start file was written", hold.text)

    def test_the_twin_a_listed_history_leaves_the_next_hold_its_turn(self):
        (hold,) = self._station("")
        self.assertIsNone(hold.known_as)
        self.assertIn(f"a start file was written for run {self.MISSING}", hold.text)


class CriterionNStation(unittest.TestCase):
    """finalize's criterion-n station reads a run's inputs and outputs only
    when its metrics.json holds a denominator; a record that does not read
    then blocks (the condition itself: `tests/test_rules_run_record_check.py`)."""

    def _run(self, d: str, metrics: dict) -> Path:
        run = Path(d) / "runs" / "r1"
        run.mkdir(parents=True)
        (run / "config.json").write_text(json.dumps(run_record()), encoding="utf-8")
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (run / "outputs.json").write_text("{not json", encoding="utf-8")
        return run

    def test_a_denominator_over_a_record_that_does_not_read_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            found = Findings(tell=None)
            finalize.check_criterion_n(found, self._run(d, {"criterion_1_n": 12}))
            (f,) = found.found
            self.assertIn("the record of r1 does not read", f.text)
            self.assertEqual(f.rule, TECHNICAL_RULE)

    def test_the_twin_without_a_denominator_the_record_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            found = Findings(tell=None)
            finalize.check_criterion_n(found, self._run(d, {"criterion_1_pass": True}))
            self.assertEqual(found.found, [])


class NullLaneStation(unittest.TestCase):
    """finalize's null-lane station (station 9) hands on what the kept rows
    show: the warning of an unmoved null lane reaches the findings (the
    condition itself: `tests/test_rules_run_record_check.py`). The reader of
    the run's outputs is given."""

    def _found(self, null_pred) -> Findings:
        from labkit.formats.runs import KeptRows, OutputEntry

        gold = [0, 1, 0, 1]
        rows: list[dict[str, object]] = [
            {"lane": lane, "item": str(i), "pred": pred(g), "gold": g}
            for lane, pred in (("registered", lambda g: g), ("null", null_pred))
            for i, g in enumerate(gold)
        ]
        kept = [KeptRows(OutputEntry(Path("out/rows.jsonl"), None, len(rows)), rows)]
        found = Findings(tell=None)
        with mock.patch.object(finalize, "kept_jsonl_rows", return_value=kept):
            finalize.check_null_lane(found, AREA / "runs" / "r1")
        return found

    def test_an_unmoved_null_lane_reaches_the_findings_as_a_warning(self):
        (f,) = self._found(lambda g: g).found
        self.assertEqual((f.grade, f.evidence_kind), ("WARNING", STATIC_EVIDENCE))
        self.assertIn("the null lane's answer and gold equal", f.text)

    def test_the_twin_a_moved_null_lane_leaves_no_finding(self):
        self.assertEqual(self._found(lambda g: 0).found, [])


if __name__ == "__main__":
    unittest.main()
