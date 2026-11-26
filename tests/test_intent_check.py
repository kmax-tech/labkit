"""Tests for intent-check — registered promises vs. metrics keys.

Fixture material mirrors three real cases, numbered as the tests cite
them: a criterion whose code implements one conjunct of three (62), gate
metrics written although the registration forbids content numbers (63), a
fork with no branch (64).
The metrics structures are shaped like real runs/*/metrics.json files.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record, PID, head

REPO = Path(__file__).resolve().parent.parent
from labkit.formats.runs import RUN_SCHEMA  # noqa: E402
from labkit.checks import intent_check  # noqa: E402
from labkit.formats import promises  # noqa: E402
from command_fixture import run_main  # noqa: E402

PROTOCOL = (
    head()
    + """# 66 — x
- **Inference criterion:** [criterion-1] null holds (p > 0,20) AND
  [criterion-2] opened > bare (p < 0,05) AND [criterion-3] both cells agree
- **Quality check:** [quality-check-1] at most 2 of 96 rounds unparsed AND
  [quality-check-2] placebo in the same run shows its expected value
- **Registered branch:** [branch-1] on "mixed", report closed - echo
"""
)


class _AreaWithRun(unittest.TestCase):
    """An empty area and the writer of a completed run bound to PID."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)
        self.proto = self.area / "PROTOCOL-x.md"
        self.addCleanup(self.tmp.cleanup)

    def _metrics(self, data, run="2026-09-09T10-00-00_ab12"):
        """A completed run bound to PID, reporting `data`."""
        d = self.area / "runs" / run
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(
            json.dumps(
                run_record(
                    {
                        "script": "01_measure.py",
                        "pid": 1,
                        "protocol": {"id": PID, "path": "PROTOCOL-x.md"},
                    }
                )
            ),
            encoding="utf-8",
        )
        (d / "metrics.json").write_text(json.dumps(data), encoding="utf-8")
        (d / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": RUN_SCHEMA,
                    "run_kind": "measurement",
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
        return d / "metrics.json"


class TestIntentCheck(_AreaWithRun):
    def _run(self, argv):
        return run_main(intent_check.main, argv)

    # -- extraction -------------------------------------------------------
    def test_ids_found_anywhere_in_free_structure(self):
        self.assertEqual(
            promises.ids_in_prose(PROTOCOL),
            {
                "criterion-1",
                "criterion-2",
                "criterion-3",
                "quality-check-1",
                "quality-check-2",
                "branch-1",
            },
        )

    def test_blank_template_registers_no_ids(self):
        """The template's explanatory preamble must not register intent ids.

        The example ids in the preamble text would otherwise register
        phantom ids in a fresh unfilled protocol, which could silently pass
        if a run happened to write keys like them.
        """
        tmpl = (
            REPO / "labkit" / "templates" / "experiment-protocol.md.template"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            promises.ids_in_prose(tmpl),
            set(),
            "the template preamble must not contribute ids",
        )

    def test_reported_intent_ids_match_bare_and_suffixed(self):
        self.assertEqual(
            promises.reported_ids(
                {
                    "criterion_1": True,
                    "quality_check_1_pass": True,
                    "branch_1_outcome": "a",
                    "auc": 0.7,
                    "n_channels": 24,
                }
            ),
            {"criterion-1", "quality-check-1", "branch-1"},
        )

    def test_f1_score_is_no_intent_id(self):
        """Forks are W, not F: f1_score is a metric name, and in an F
        namespace it would satisfy a branchless fork."""
        self.assertEqual(promises.reported_ids({"f1_score": 0.8, "f1": 0.8}), set())

    # -- contract ---------------------------------------------------------
    def test_all_reported_passes(self):
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics(
            {
                "criterion_1_pass": True,
                "criterion_2_pass": False,
                "criterion_3_pass": True,
                "quality_check_1_pass": True,
                "quality_check_2_pass": True,
                "branch_1_outcome": "none",
            }
        )
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_missing_conjunct_fails(self):
        """The 62 case: criterion_met implemented as one conjunct of three."""
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics(
            {
                "criterion_2_pass": True,
                "quality_check_1_pass": True,
                "quality_check_2_pass": True,
                "branch_1_outcome": "none",
            }
        )
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[criterion-1]", out)
        self.assertIn("[criterion-3]", out)
        self.assertNotIn("[criterion-2]", out)

    def test_unregistered_key_fails(self):
        self.proto.write_text(head() + "# x\n[criterion-1] only.\n", encoding="utf-8")
        self._metrics({"criterion_1": True, "branch_1_outcome": "taken"})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[branch-1]", out)
        self.assertIn("without a registration", out)

    def test_newest_run_wins(self):
        self.proto.write_text(head() + "# x\n[criterion-1].\n", encoding="utf-8")
        self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"criterion_1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_explicit_metrics_flag(self):
        self.proto.write_text(head() + "# x\n[criterion-1].\n", encoding="utf-8")
        old = self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"criterion_1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto), "--metrics", str(old)])
        self.assertEqual(rc, 1)

    def test_a_word_after_the_metrics_file_is_refused(self):
        """`--metrics FILE extra` is refused, not checked with `extra`
        dropped; the same line without it is checked (the twin above)."""
        self.proto.write_text(head() + "# x\n[criterion-1].\n", encoding="utf-8")
        old = self._metrics({}, run="2026-09-09T09-00-00_old1")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = intent_check.main([str(self.proto), "--metrics", str(old), "extra"])
        self.assertEqual((rc, out.getvalue()), (2, ""))
        self.assertEqual(err.getvalue(), "intent-check: unexpected argument 'extra'\n")

    # -- opt-in by presence ----------------------------------------------
    def test_no_ids_is_no_failure(self):
        """A protocol that promises nothing passes with a note."""
        self.proto.write_text(head() + "# protocol, no ids\n", encoding="utf-8")
        self._metrics({"criterion_pass": False})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0)
        self.assertIn("no intent ids", out)

    def test_ids_but_no_run_yet_exits_two(self):
        """With a bound protocol, no completed run means nothing to hold the
        promises against — exit 2, not a silent pass."""
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 2, out)
        self.assertIn(f"no completed run bound to {PID}", out)
        self.assertIn("no runs in", out)
        self.assertIn(intent_check.METRICS_HINT, out)  # its own command line

    def test_finalize_is_not_offered_a_flag_it_lacks(self):
        # finalize calls hold() and has no --metrics: the hint is the
        # command line's, not hold()'s
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        with self.assertRaises(intent_check.NoRunChosen) as caught:
            intent_check.hold(self.proto, None)
        self.assertNotIn("--metrics", caught.exception.why)

    # -- usage ------------------------------------------------------------
    def test_missing_protocol_exits_two(self):
        rc, out = self._run([str(self.area / "PROTOCOL-gone.md")])
        self.assertEqual(rc, 2)

    def test_missing_explicit_metrics_exits_two(self):
        self.proto.write_text(head() + "[criterion-1]", encoding="utf-8")
        rc, out = self._run(
            [str(self.proto), "--metrics", str(self.area / "gone.json")]
        )
        self.assertEqual(rc, 2)
        self.assertIn("no such metrics file", out)

    def test_a_refusal_goes_to_stderr_and_leaves_stdout_to_findings(self):
        """A caller reading stdout for findings must not read a refusal as one."""
        self.proto.write_text(head() + "[criterion-1]", encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = intent_check.main(
                [str(self.proto), "--metrics", str(self.area / "gone.json")]
            )
        self.assertEqual(rc, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(
            err.getvalue(),
            f"intent-check: no such metrics file: {self.area / 'gone.json'}\n",
        )

    def test_help_exits_zero(self):
        rc, out = self._run(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("usage: intent-check", out)


class SourceHeldToItsOwnText(_AreaWithRun):
    """`origin_intent_findings`: an origin run held to the protocol as it saw it,
    not to the protocol as it reads now."""

    FULL = {
        "criterion_1_pass": True,
        "criterion_2_pass": True,
        "criterion_3_pass": True,
        "quality_check_1_pass": True,
        "quality_check_2_pass": True,
        "branch_1_outcome": "mixed",
    }

    def held(self, metrics: dict, text: str = PROTOCOL) -> list[str]:
        mpath = self._metrics(metrics)
        return [
            f.line
            for f in intent_check.origin_intent_findings(mpath.parent, text, self.area)
        ]

    def test_a_source_reporting_every_promise_of_its_text_is_clean(self):
        self.assertEqual(self.held(self.FULL), [])

    def test_a_promise_of_its_text_the_source_does_not_report_blocks(self):
        without = {k: v for k, v in self.FULL.items() if k != "criterion_3_pass"}
        (line,) = self.held(without)
        self.assertIn(
            "origin run 2026-09-09T10-00-00_ab12, held to the protocol as it saw "
            "it: its protocol then: [criterion-3] registered",
            line,
        )
        self.assertIn("measure the origin anew under its protocol", line)
        self.assertNotIn("fix the code and measure again", line)

    def test_an_id_the_protocol_registered_later_is_not_asked_of_the_source(self):
        """The twin: the same metrics against the text as it reads now, one
        id further, block; against the run's own text they do not."""
        now = PROTOCOL + "- **Later:** [criterion-4] added for the next run\n"
        self.assertEqual(len(self.held(self.FULL, now)), 1)
        self.assertEqual(self.held(self.FULL, PROTOCOL), [])

    def test_a_text_that_registers_no_id_owes_nothing(self):
        self.assertEqual(self.held({"n": 3}, head() + "# 66 — a count\n"), [])

    def test_a_promise_block_of_its_text_that_does_not_read_blocks(self):
        """Before any comparison: the block of the text the run saw has a
        promise without its key, so nothing can be held against the run.
        The twin: the same promise with its key reads, and that blocker is
        gone."""
        prose = PROTOCOL.removeprefix(head())
        run = self._metrics(self.FULL).parent
        without_key = '[[promise]]\nid = "criterion-1"\n'
        reads = (
            without_key
            + 'key = "criterion_1_pass"\nsentence = "null holds"\n'
            + 'scope = ["scripts/01_measure.py"]\n'
        )
        twin = intent_check.origin_intent_findings(
            run, head(promises=reads) + prose, self.area
        )
        self.assertFalse([f.text for f in twin if "promise block: " in f.text])
        (found,) = intent_check.origin_intent_findings(
            run, head(promises=without_key) + prose, self.area
        )
        self.assertEqual(found.grade, "BLOCKER")
        self.assertTrue(
            found.text.startswith(
                "origin run 2026-09-09T10-00-00_ab12, held to the protocol as it "
                "saw it: promise block: "
            ),
            found.text,
        )
        self.assertIn("measure the origin anew under its protocol", found.fix or "")

    def test_a_source_whose_metrics_do_not_read_blocks(self):
        mpath = self._metrics(self.FULL)
        mpath.write_text("[", encoding="utf-8")
        (found,) = intent_check.origin_intent_findings(
            mpath.parent, PROTOCOL, self.area
        )
        self.assertIn("held to the protocol as it saw it", found.text)
        self.assertEqual(found.grade, "BLOCKER")


class KeysInImportedCode(unittest.TestCase):
    """A registered key written in imported repo code is found: every key
    may live in a module the script imports."""

    def test_a_key_in_src_counts_for_the_area(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "tests").mkdir()
            area = repo / "experiments" / "01-x"
            (area / "scripts").mkdir(parents=True)
            (area / "scripts" / "m.py").write_text("from measure import comparison\n")
            (repo / "src" / "measure").mkdir(parents=True)
            (repo / "src" / "measure" / "__init__.py").write_text("")
            (repo / "src" / "measure" / "comparison.py").write_text(
                'def evaluate(rows):\n    return {"criterion_1_pass": True}\n'
            )
            keys = intent_check.code_keys(area)
        self.assertEqual(keys["criterion_1_pass"], ["src/measure/comparison.py:2"])


class OneAnswerToRegistersPromises(unittest.TestCase):
    """The audit of 2026-11-08, round 2, R2: a [[promise]] table the prose
    does not name still registers its id — every telling of the answering
    run holds a probe run alike."""

    def test_a_table_alone_registers_and_a_protocol_without_ids_does_not(self):
        table_only = (
            '# P\n\n```toml\n[[promise]]\nid = "criterion-1"\n'
            'sentence = "the f1 holds"\nkeys = ["f1"]\n```\n'
        )
        self.assertFalse(promises.prose_names_ids(table_only))
        self.assertTrue(promises.registers_promises(table_only))
        self.assertFalse(promises.registers_promises("# P\n\nno ids here\n"))
