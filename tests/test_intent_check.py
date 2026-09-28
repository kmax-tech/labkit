"""Tests for intent-check — registered promises vs. metrics keys.

Fixture material mirrors the real cases of 2026-09-08: a criterion whose
code implements one conjunct of three (62), gate metrics written although
the registration forbids content numbers (63), a fork with no branch (64).
The metrics structures are shaped like real runs/*/metrics.json files.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "intent_check", REPO / "labkit" / "intent_check.py")
assert spec is not None and spec.loader is not None
intent_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intent_check)

PROTOCOL = """# 66 — x
- **Success / failure criterion:** [K1] null holds (p > 0,20) AND
  [K2] opened > bare (p < 0,05) AND [K3] both cells agree
- **Stop rule:** [S1] > 2 of 96 rounds unparsed -> parser is the finding
- **Registered fork:** [W1] on "mixed", report closed - echo
- **Null condition:** [N1] placebo in the same run
"""


class TestIntentCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name)
        self.proto = self.area / "PROTOCOL-x.md"
        self.addCleanup(self.tmp.cleanup)

    def _metrics(self, data, run="2026-09-09T10-00-00_ab12"):
        d = self.area / "runs" / run
        d.mkdir(parents=True, exist_ok=True)
        (d / "metrics.json").write_text(json.dumps(data), encoding="utf-8")
        return d / "metrics.json"

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = intent_check.main(argv)
        return rc, buf.getvalue()

    # -- extraction -------------------------------------------------------
    def test_ids_found_anywhere_in_free_structure(self):
        self.assertEqual(intent_check.registered_ids(PROTOCOL),
                         {"k1", "k2", "k3", "s1", "w1", "n1"})

    def test_blank_template_registers_no_ids(self):
        """The template's explanatory preamble must not register intent ids.

        Before the fix, [K1]/[S1]/[W1]/[N1] in the preamble text matched
        the regex, so a fresh unfilled protocol registered four phantom ids
        that could silently pass if a run happened to write k1/s1/w1/n1.
        """
        tmpl = (REPO / "labkit" / "experiment-protocol.md.template").read_text(
            encoding="utf-8")
        self.assertEqual(intent_check.registered_ids(tmpl), set(),
                         "the template preamble must not contribute ids")

    def test_reported_intent_ids_match_bare_and_suffixed(self):
        self.assertEqual(
            intent_check.reported_intent_ids({"k1": True, "s1_hit": 0, "w1_branch": "a",
                                     "auc": 0.7, "n_channels": 24}),
            {"k1", "s1", "w1"})

    def test_f1_score_is_no_intent_id(self):
        """The collision that renamed forks to W: f1_score is a metric name,
        and in an F namespace it would have satisfied a branchless fork."""
        self.assertEqual(intent_check.reported_intent_ids({"f1_score": 0.8, "f1": 0.8}),
                         set())

    # -- contract ---------------------------------------------------------
    def test_all_reported_passes(self):
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics({"k1_pass": True, "k2_pass": False, "k3_pass": True,
                       "s1_hit": 0, "w1_branch": "none", "n1_pass": True})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_missing_conjunct_fails(self):
        """The 62 case: criterion_met implemented as one conjunct of three."""
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        self._metrics({"k2_pass": True, "s1_hit": 0, "w1_branch": "none",
                       "n1_pass": True})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[K1]", out)
        self.assertIn("[K3]", out)
        self.assertNotIn("[K2]", out)

    def test_unregistered_key_fails(self):
        self.proto.write_text("# x\n[K1] only.\n", encoding="utf-8")
        self._metrics({"k1": True, "w1_branch": "taken"})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 1)
        self.assertIn("[W1]", out)
        self.assertIn("without a registration", out)

    def test_newest_run_wins(self):
        self.proto.write_text("# x\n[K1].\n", encoding="utf-8")
        self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"k1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0, out)

    def test_explicit_metrics_flag(self):
        self.proto.write_text("# x\n[K1].\n", encoding="utf-8")
        old = self._metrics({}, run="2026-09-09T09-00-00_old1")
        self._metrics({"k1": 1}, run="2026-09-09T11-00-00_new2")
        rc, out = self._run([str(self.proto), "--metrics", str(old)])
        self.assertEqual(rc, 1)

    # -- opt-in by presence ----------------------------------------------
    def test_no_ids_is_no_failure(self):
        """Everything written before the ids existed keeps its verdict."""
        self.proto.write_text("# old protocol, no ids\n", encoding="utf-8")
        self._metrics({"criterion_pass": False})
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0)
        self.assertIn("no intent ids", out)

    def test_ids_but_no_run_yet_is_no_failure(self):
        self.proto.write_text(PROTOCOL, encoding="utf-8")
        rc, out = self._run([str(self.proto)])
        self.assertEqual(rc, 0)
        self.assertIn("due at report time", out)

    # -- usage ------------------------------------------------------------
    def test_missing_protocol_exits_two(self):
        rc, out = self._run([str(self.area / "PROTOCOL-gone.md")])
        self.assertEqual(rc, 2)

    def test_missing_explicit_metrics_exits_two(self):
        self.proto.write_text("[K1]", encoding="utf-8")
        rc, out = self._run([str(self.proto), "--metrics",
                             str(self.area / "gone.json")])
        self.assertEqual(rc, 2)

    def test_help_exits_zero(self):
        rc, out = self._run(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("usage: intent-check", out)
