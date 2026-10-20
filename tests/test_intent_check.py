"""Tests for intent-check — registered promises vs. metrics keys.

Fixture material mirrors the real cases of 2026-09-08: a criterion whose
code implements one conjunct of three (62), gate metrics written although
the registration forbids content numbers (63), a fork with no branch (64).
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
from labkit.checks import intent_check  # noqa: E402

PROTOCOL = (
    head()
    + """# 66 — x
- **Success / failure criterion:** [C1] null holds (p > 0,20) AND
  [C2] opened > bare (p < 0,05) AND [C3] both cells agree
- **Admissibility condition:** [A1] at most 2 of 96 rounds unparsed AND
  [A2] placebo in the same run shows its expected value
- **Registered branch:** [B1] on "mixed", report closed - echo
"""
)


class TestIntentCheck(unittest.TestCase):
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
                        "schema_version": 3,
                        "run_kind": "measurement",
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
                    "schema_version": 3,
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

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = intent_check.main(argv)
        return rc, buf.getvalue()

    # -- extraction -------------------------------------------------------
    def test_ids_found_anywhere_in_free_structure(self):
        self.assertEqual(
            intent_check.ids_in_prose(PROTOCOL), {"c1", "c2", "c3", "a1", "a2", "b1"}
        )

    def test_blank_template_registers_no_ids(self):
        """The template's explanatory preamble must not register intent ids.

        Before the fix, the example ids in the preamble text matched the
        regex, so a fresh unfilled protocol registered phantom ids that
        could silently pass if a run happened to write keys like them.
        """
        tmpl = (
            REPO / "labkit" / "templates" / "experiment-protocol.md.template"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            intent_check.ids_in_prose(tmpl),
            set(),
            "the template preamble must not contribute ids",
        )

    def test_reported_intent_ids_match_bare_and_suffixed(self):
        self.assertEqual(
            intent_check.reported_intent_ids(
                {
                    "c1": True,
                    "a1_pass": True,
                    "b1_branch": "a",
                    "auc": 0.7,
                    "n_channels": 24,
                }
            ),
            {"c1", "a1", "b1"},
        )

    def test_f1_score_is_no_intent_id(self):
        """The collision that renamed forks to W: f1_score is a metric name,
        and in an F namespace it would have satisfied a branchless fork."""
        self.assertEqual(
            intent_check.reported_intent_ids({"f1_score": 0.8, "f1": 0.8}), set()
        )

    # -- contract ---------------------------------------------------------
    def test_all_reported_passes(self):
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics(
            {
                "c1_pass": True,
                "c2_pass": False,
                "c3_pass": True,
                "a1_pass": True,
                "a2_pass": True,
                "b1_branch": "none",
            }
        )
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_missing_conjunct_fails(self):
        """The 62 case: criterion_met implemented as one conjunct of three."""
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics(
            {"c2_pass": True, "a1_pass": True, "a2_pass": True, "b1_branch": "none"}
        )
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[C1]", out)
        self.assertIn("[C3]", out)
        self.assertNotIn("[C2]", out)

    def test_unregistered_key_fails(self):
        self.proto.write_text(head() + "# x\n[C1] only.\n", encoding="utf-8")
        self._metrics({"c1": True, "b1_branch": "taken"})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[B1]", out)
        self.assertIn("without a registration", out)

    def test_newest_run_wins(self):
        self.proto.write_text(head() + "# x\n[C1].\n", encoding="utf-8")
        self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"c1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_explicit_metrics_flag(self):
        self.proto.write_text(head() + "# x\n[C1].\n", encoding="utf-8")
        old = self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"c1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto), "--metrics", str(old)])
        self.assertEqual(rc, 1)

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
        promises against — exit 2, not a silent pass (the old "due at
        report time" exit 0 belonged to the directory choice)."""
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 2, out)
        self.assertIn(f"no completed run bound to {PID}", out)
        self.assertIn("no runs in", out)

    # -- usage ------------------------------------------------------------
    def test_missing_protocol_exits_two(self):
        rc, out = self._run([str(self.area / "PROTOCOL-gone.md")])
        self.assertEqual(rc, 2)

    def test_missing_explicit_metrics_exits_two(self):
        self.proto.write_text(head() + "[C1]", encoding="utf-8")
        rc, out = self._run(
            [str(self.proto), "--metrics", str(self.area / "gone.json")]
        )
        self.assertEqual(rc, 2)
        self.assertIn("no such metrics file", out)

    def test_a_refusal_goes_to_stderr_and_leaves_stdout_to_findings(self):
        """A caller reading stdout for findings must not read a refusal as one."""
        self.proto.write_text(head() + "[C1]", encoding="utf-8")
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


class KeysInImportedCode(unittest.TestCase):
    """A registered key written in imported repo code is found (uniagent,
    2026-10-07: every key lives in src/measure/comparison.py, and code-check
    called four promises absent)."""

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
                'def evaluate(rows):\n    return {"c1_pass": True}\n'
            )
            keys = intent_check.code_keys(area)
        self.assertEqual(keys["c1_pass"], ["src/measure/comparison.py:2"])
