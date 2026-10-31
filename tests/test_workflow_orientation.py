"""The callable workflow guidance agrees on stages and offers failed-audit recovery."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from protocol_fixture import head  # noqa: E402

from labkit.formats import attempts, findings, protocol_check, repo, standard_contract
from labkit.formats import failed_attempts
from labkit.checks import protocol_report
from labkit.gates import audit, finalize
from labkit.tools import scaffold


class WorkflowOrientation(unittest.TestCase):
    def test_the_area_route_includes_analysis_before_adoption(self):
        for sk in standard_contract.SKELETONS:
            with self.subTest(instrument=sk.instrument):
                text = scaffold.area_readme("01", "example", sk, True)
                route = text.split("**The gates, in order.**", 1)[1].split(
                    "## State", 1
                )[0]
                stages = (
                    "`finalize`",
                    "--mode analysis",
                    "decide",
                    "Conclusion",
                    "labkit-adopt",
                )
                positions = [route.index(stage) for stage in stages]
                self.assertEqual(positions, sorted(positions), route)

    def test_the_step_after_a_run_goes_through_the_audit(self):
        # every skeleton printed only the adoption, which then refused for
        # the missing audit (audit 2026-10-27, third, I3)
        protocol = Path("experiments/01-x/PROTOCOL-x.md").resolve()
        line = repo.next_after_run(protocol, "2026-10-27T10-00-00_ab12")
        stages = ("finalize", "--mode analysis", "decide", "Conclusion", "labkit-adopt")
        positions = [line.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions), line)
        for template in (
            "measure-quick-script.py.template",
            "measure-estimator-script.py.template",
        ):
            text = (
                Path(scaffold.__file__).parents[1] / "templates" / template
            ).read_text()
            with self.subTest(template=template):
                self.assertIn("next_after_run(PROTOCOL, run.run_id)", text)
                self.assertNotIn("adopt_command(PROTOCOL, run.run_id)", text)

    def test_every_line_to_the_adoption_names_the_report_fields_first(self):
        """The adoption runs protocol-check, which refuses a frozen protocol
        without the report fields owed once a result is declared: the step
        stands before the adoption, from one home (`repo.report_fields_step`),
        in the run's next line, finalize's hint and labkit-init's closing
        steps. The twin: the step names the contract line that lists them."""
        protocol = Path("experiments/01-x/PROTOCOL-x.md").resolve()
        run = "2026-10-27T10-00-00_ab12"
        step = repo.report_fields_step(protocol)
        self.assertIn("write the Conclusion and the report fields", step)
        self.assertIn(f"`{repo.contract_command(protocol)}`", step)
        self.assertIn("--contract", repo.contract_command(protocol))
        self.assertIn("once frozen and adopted", step)
        hint = finalize.undeclared_hint(
            head(repeat_cost="low"), protocol.parent / "runs" / run, protocol
        )
        assert hint is not None
        closing = scaffold.next_steps(
            Path("experiments/01-x"), "x", "01", "high", "compute", False
        )
        for name, line in (
            ("next_after_run", repo.next_after_run(protocol, run)),
            ("undeclared_hint", hint),
            ("next_steps", closing),
        ):
            with self.subTest(line=name):
                self.assertIn(step, line)
                self.assertLess(line.index(step), line.index("labkit-adopt"))

    def test_the_area_route_names_the_area_from_the_root(self):
        # `runlog .` from the root, as AGENTS.md asks, read the repo as an
        # area (audit 2026-10-27, third, I10)
        text = scaffold.area_readme("01", "example", standard_contract.COMPUTE, False)
        self.assertIn("`runlog experiments/01-example`", text)
        self.assertIn("`labkit-params experiments/01-example`", text)
        self.assertNotIn("`runlog .`", text)

    def test_model_raw_output_is_listed_after_the_run_in_the_contract(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            protocol_report.print_contract()
        summary = out.getvalue().splitlines()[0]
        before, after = summary.split("; after the run: ", 1)
        self.assertNotIn("Raw output", before)
        self.assertIn("Raw output", after)
        self.assertIn("with a model", after)

    def test_a_failed_first_audit_names_the_no_model_handover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold.stamp_lab(root, "orientation")
            area, _ = scaffold.stamp_area(
                root, "example", repeat_cost="low", kind="compute"
            )
            failed = failed_attempts.write_failed(
                area,
                "analysis",
                "auditor",
                "abc",
                "none",
                60,
                "service unavailable",
                "labkit-audit example --mode analysis",
                cause="unavailable",
            )
            out = io.StringIO()
            with (
                mock.patch.object(
                    audit.llm, "complete", side_effect=AssertionError("no model call")
                ),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(out),
            ):
                rc = audit.main([str(area), "--findings"])
            self.assertEqual(rc, 2, out.getvalue())
            self.assertIn(failed.name, out.getvalue())
            self.assertIn("service unavailable", out.getvalue())
            self.assertIn("--handover", out.getvalue())
            self.assertNotIn("--decide", out.getvalue())

    def test_a_preflight_record_does_not_hide_a_failed_analysis_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold.stamp_lab(root, "orientation")
            area, _ = scaffold.stamp_area(
                root, "example", repeat_cost="high", kind="compute"
            )
            registration = protocol_check.registration_stamp(
                (area / "PROTOCOL-example.md").read_text(encoding="utf-8")
            )
            findings.write(
                area,
                "preflight",
                "auditor",
                "abc",
                "none",
                (0, 0, 0),
                [],
                registration=registration,
            )
            # the failed call and the later audit as labkit-audit makes them:
            # each an attempt of the journal, ended with its file
            tried = attempts.begin(
                area,
                "analysis",
                "auditor",
                "abc",
                block_sha="none",
                protocol="PROTOCOL-example.md",
            )
            failed = failed_attempts.write_failed(
                area,
                "analysis",
                "auditor",
                "abc",
                "none",
                60,
                "service unavailable",
                "labkit-audit example --mode analysis",
                cause="unavailable",
            )
            tried.end("failed", file=failed.name)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = audit.main([str(area), "--findings"])
            self.assertEqual(rc, 2, out.getvalue())
            self.assertIn(failed.name, out.getvalue())
            self.assertIn("--handover", out.getvalue())
            later = attempts.begin(
                area,
                "analysis",
                "auditor",
                "abc",
                block_sha="none",
                protocol="PROTOCOL-example.md",
            )
            covering = findings.write(
                area,
                "analysis",
                "auditor",
                "abc",
                "none",
                (0, 0, 0),
                [],
                registration=registration,
                run_id=findings.NO_RUN,
                shown_sha="none",
            )
            later.end("record", file=covering.name)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = audit.main([str(area), "--findings"])
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn(f"audit call superseded: {failed.name}", out.getvalue())
            self.assertNotIn("audit did not complete", out.getvalue())
            self.assertNotIn("--handover", out.getvalue())


if __name__ == "__main__":
    unittest.main()
