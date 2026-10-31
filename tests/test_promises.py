"""Tests for the promise block (2026-10-06): promises as data, the guaranteed tier.

The chain: promise (id, key, constants, declared scope) → run (records the
block's digest and a scope hash per promise) → report (intent-check holds
the metrics and the recorded block against the protocol; recheck refuses a
recomputation over a changed scope).

The scope fixture is the counterexample from the thread note
`scope-hash-aussage`: `compute_score` writes the number and calls
`filter_items`. A hash over the writing function alone does NOT see an edit
to `filter_items` — the test pins that limit down, so nobody mistakes the
stamp for "all the code the number depends on". Declaring `filter_items`
makes the edit visible; that is the whole claim.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit.checks import intent_check, recheck  # noqa: E402
from labkit.run import runlog  # noqa: E402
from labkit.formats import promises  # noqa: E402
from protocol_fixture import head  # noqa: E402

MEASURE = """\
def filter_items(rows):
    return [r for r in rows if r["answer"] is not None]


def compute_score(rows):
    kept = filter_items(rows)
    return sum(r["answer"] == r["gold"] for r in kept) / len(kept)


def unrelated():
    return 1
"""


def block(*entries: str) -> str:
    return "```toml\n" + "\n".join(entries) + "```\n"


C1 = """[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
sentence = "accuracy >= min_acc"
scope = ["scripts/01_measure.py:compute_score"]
constants = { min_acc = 0.7 }
"""
A1 = """[[promise]]
id = "quality-check-1"
key = "quality_check_1_anchor_ok"
sentence = "the anchor items come out at 1.0, else no verdict"
scope = ["scripts/01_measure.py"]
"""

B1 = """[[promise]]
id = "branch-1"
key = "branch_1_outcome"
sentence = "criterion-1 met → generalises: used on the next cohort; quality-check-1 not met → noisy: no verdict, the parser is repaired first; otherwise → no-verdict: reported descriptively"
scope = ["scripts/01_measure.py"]
"""
OUTCOMES = (
    "criterion-1 met and quality-check-1 met → generalises: used on the next cohort; "
    "quality-check-1 not met → noisy: no verdict, the parser is repaired first; "
    "otherwise → no-verdict: reported descriptively, no further analysis"
)


def parsed(text: str) -> promises.PromiseTables:
    """parse_block for a text that must carry a block."""
    b = promises.parse_block(text)
    assert b is not None, "fixture has no promise block"
    return b


def protocol_text(
    *entries: str,
    prose: str = "Criterion [criterion-1]; admissibility [quality-check-1].\n",
) -> str:
    """A protocol whose one ```toml block holds the head and `entries`."""
    return head(promises="\n".join(entries)) + "\n" + prose


class Parse(unittest.TestCase):
    def test_no_block_is_none(self):
        self.assertIsNone(promises.parse_block("criterion [K1] only in prose\n"))

    def test_block_without_promise_tables_declares_none(self):
        self.assertIsNone(
            promises.parse_block('```toml\n[protocol]\nstandard = "0.23"\n```\n')
        )

    def test_unknown_top_level_table(self):
        self.assertRejects(
            "```toml\n[tool]\nx = 1\n```\n", "only [protocol] and [[promise]]"
        )

    def test_entries_kinds_constants(self):
        b = parsed(protocol_text(C1, A1))
        self.assertEqual([p.id for p in b.promises], ["criterion-1", "quality-check-1"])
        self.assertEqual(b.by_id()["criterion-1"].kind, "criterion")
        self.assertEqual(b.by_id()["quality-check-1"].kind, "quality-check")
        self.assertEqual(b.by_id()["criterion-1"].constants, {"min_acc": 0.7})
        self.assertEqual(b.by_id()["quality-check-1"].constants, {})

    def test_digest_follows_the_block_not_the_prose(self):
        a = parsed(protocol_text(C1))
        b = parsed(protocol_text(C1, prose="other prose [criterion-1]\n"))
        c = parsed(protocol_text(C1.replace("0.7", "0.8")))
        self.assertEqual(a.sha, b.sha)
        self.assertNotEqual(a.sha, c.sha)

    def test_digest_ignores_the_head(self):
        """Freezing or stamping the audit edits the head, not a promise:
        a run must not read that as "promises changed after the run"."""
        a = parsed(protocol_text(C1))
        b = parsed(
            head(
                frozen=True,
                preflight_audit="2026-10-07 · ab12 · 0 findings",
                promises=C1,
            )
        )
        self.assertEqual(a.sha, b.sha)

    def assertRejects(self, text: str, fragment: str):
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_block(text)
        self.assertIn(fragment, str(cm.exception))

    def test_two_blocks(self):
        self.assertRejects(block(C1) + block(A1), "exactly one")

    def test_invalid_toml(self):
        self.assertRejects(block('[[promise]]\nid = "criterion-1\n'), "not valid TOML")

    def test_earlier_letter_in_block(self):
        self.assertRejects(
            block(C1.replace('"criterion-1"', '"K1"')),
            "is not criterion-<n>, quality-check-<n> or branch-<n>",
        )

    def test_the_letters_of_0_103_are_refused_naming_the_version(self):
        """A protocol in the C/A/B letters is not read: refused with the
        version that reads it, never checked as if it registered nothing.
        The twin: the kind-word id parses (every test above)."""
        self.assertRejects(
            block(
                C1.replace('"criterion-1"', '"C1"').replace(
                    '"criterion_1_pass"', '"c1_pass"'
                )
            ),
            "labkit 0.103.0 (C/A/B)",
        )
        self.assertEqual(
            promises.earlier_ids("[C1] and [A2] and [criterion-1]"), ["A2", "C1"]
        )

    def test_key_outside_namespace(self):
        self.assertRejects(
            block(C1.replace('"criterion_1_pass"', '"criterion_2_pass"')),
            "outside the id's namespace",
        )
        self.assertRejects(
            block(C1.replace('"criterion_1_pass"', '"criterion_10_pass"')),
            "outside the id's namespace",
        )

    def test_duplicate_id(self):
        self.assertRejects(block(C1, C1), "duplicate id")

    def test_missing_and_empty_fields(self):
        self.assertRejects(
            block(C1.replace('sentence = "accuracy >= min_acc"\n', "")),
            "missing `sentence`",
        )
        self.assertRejects(
            block(C1.replace('["scripts/01_measure.py:compute_score"]', "[]")),
            "non-empty list",
        )

    def test_non_scalar_constant_and_unknown_field(self):
        self.assertRejects(
            block(C1.replace("min_acc = 0.7", "min_acc = [0.7]")), "only scalars"
        )
        self.assertRejects(block(C1 + "threshold = 0.7\n"), "unknown field")


class Alphabet(unittest.TestCase):
    def test_metric_names_are_not_ids(self):
        metrics = {"f1_score": 1, "p1": 1, "q1": 1, "r1_recall": 1, "h1": 1}
        self.assertEqual(promises.reported_ids(metrics), set())

    def test_only_kind_word_keys_are_ids(self):
        metrics = {
            "criterion_1_pass": 1,
            "quality_check_2": 1,
            "branch_1_outcome": "x",
            "c1_pass": 1,
            "k1_pass": 1,
            "n1": 1,
        }
        self.assertEqual(
            promises.reported_ids(metrics),
            {"criterion-1", "quality-check-2", "branch-1"},
        )

    def test_one_alphabet_everywhere(self):
        self.assertIs(intent_check.ID_KEY, promises.ID_KEY)
        self.assertIs(intent_check.ID_IN_PROTOCOL, promises.ID_IN_PROTOCOL)
        self.assertIs(recheck.INTENT_KEY, promises.INTENT_KEY)

    def test_prose_mismatch_both_directions(self):
        b = parsed(block(C1))
        self.assertEqual(
            promises.prose_mismatch("[criterion-1] and [quality-check-2] and [K1]", b),
            (["quality-check-2"], []),
        )
        self.assertEqual(promises.prose_mismatch("only [K1]", b), ([], ["criterion-1"]))


class ScopeHash(unittest.TestCase):
    """The four rows of the table in `scope-hash-aussage`."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        (self.area / "scripts").mkdir()
        self.script = self.area / "scripts" / "01_measure.py"
        self.script.write_text(MEASURE, encoding="utf-8")

    def sha(self, *scope: str) -> str:
        return promises.declared_scope_sha(self.area, scope)

    def edit(self, old: str, new: str):
        text = self.script.read_text(encoding="utf-8")
        assert old in text
        self.script.write_text(text.replace(old, new), encoding="utf-8")

    FILTER_EDIT = ('if r["answer"] is not None', 'if r["answer"]')

    def test_writer_only_does_not_see_the_helper_edit(self):
        before = self.sha("scripts/01_measure.py:compute_score")
        self.edit(*self.FILTER_EDIT)
        self.assertEqual(before, self.sha("scripts/01_measure.py:compute_score"))

    def test_declared_helper_sees_the_edit(self):
        scope = (
            "scripts/01_measure.py:compute_score",
            "scripts/01_measure.py:filter_items",
        )
        before = self.sha(*scope)
        self.edit(*self.FILTER_EDIT)
        self.assertNotEqual(before, self.sha(*scope))

    def test_function_scope_ignores_neighbour_edits(self):
        before = self.sha("scripts/01_measure.py:compute_score")
        self.edit("return 1", "return 2")
        self.assertEqual(before, self.sha("scripts/01_measure.py:compute_score"))

    def test_file_scope_sees_every_edit(self):
        before = self.sha("scripts/01_measure.py")
        self.edit("return 1", "return 2")
        self.assertNotEqual(before, self.sha("scripts/01_measure.py"))

    def test_scope_spelling_is_part_of_the_stamp(self):
        self.assertNotEqual(
            self.sha("scripts/01_measure.py:compute_score"),
            self.sha(
                "scripts/01_measure.py:compute_score", "scripts/01_measure.py:unrelated"
            ),
        )

    def test_missing_function_or_file_is_an_error(self):
        with self.assertRaises(promises.PromiseError):
            self.sha("scripts/01_measure.py:gone")
        with self.assertRaises(promises.PromiseError):
            self.sha("scripts/02_analyze.py")


class Chain(unittest.TestCase):
    """protocol block → runlog snapshot → intent-check → recheck."""

    def setUp(self):
        self.area = Path(tempfile.mkdtemp())
        (self.area / "scripts").mkdir()
        (self.area / "scripts" / "01_measure.py").write_text(MEASURE, encoding="utf-8")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(protocol_text(C1, A1), encoding="utf-8")
        os.environ.pop("LABKIT_UNFROZEN", None)
        os.environ.pop("CLAUDECODE", None)

    def start(self) -> runlog.Run:
        with contextlib.redirect_stdout(io.StringIO()):
            return runlog.Run("t", {"min_acc": 0.7}, self.area, run_kind="probe")

    def complete(self, run: runlog.Run, metrics: dict) -> Path:
        (run.dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (run.dir / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 4,
                    "run_kind": "measurement",
                    "finished": "x",
                    "git": "g",
                    "git_full": "g",
                    "note": "",
                }
            ),
            encoding="utf-8",
        )
        return run.dir

    def check(self) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = intent_check.main([str(self.protocol)])
        return rc, buf.getvalue()

    GOOD = {"criterion_1_pass": True, "quality_check_1_anchor_ok": True}

    def test_run_records_block_and_scope_per_promise(self):
        run = self.start()
        rec = json.loads((run.dir / "config.json").read_text())["promises"]
        self.assertEqual(rec["block_sha"], promises.load(self.protocol).sha)
        self.assertEqual(set(rec["ids"]), {"criterion-1", "quality-check-1"})
        self.assertEqual(rec["ids"]["criterion-1"]["constants"], {"min_acc": 0.7})
        self.assertEqual(
            rec["ids"]["criterion-1"]["declared_scope_sha"],
            promises.declared_scope_sha(
                self.area, ("scripts/01_measure.py:compute_score",)
            ),
        )

    def test_protocol_without_block_records_none(self):
        self.protocol.write_text(
            protocol_text(prose="no promise here\n"), encoding="utf-8"
        )
        run = self.start()
        self.assertIsNone(json.loads((run.dir / "config.json").read_text())["promises"])

    def test_dangling_scope_is_refused_before_mkdir(self):
        self.protocol.write_text(
            protocol_text(C1.replace("compute_score", "gone"), A1), encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as cm:
            self.start()
        self.assertIn("promise block", str(cm.exception))
        self.assertFalse((self.area / "runs").exists())

    def test_constants_are_read_from_the_protocol(self):
        self.assertEqual(
            promises.constants(self.protocol, "criterion-1"), {"min_acc": 0.7}
        )
        with self.assertRaises(promises.PromiseError):
            promises.constants(self.protocol, "criterion-9")

    def test_intent_check_green_on_the_bound_block(self):
        self.complete(self.start(), self.GOOD)
        rc, out = self.check()
        self.assertEqual(rc, 0, out)
        self.assertIn("is the one the run recorded", out)

    def test_block_changed_after_the_run(self):
        self.complete(self.start(), self.GOOD)
        self.protocol.write_text(
            protocol_text(C1.replace("0.7", "0.6"), A1), encoding="utf-8"
        )
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("promises changed after the run", out)

    def test_run_config_contradicting_a_constant_is_refused_before_mkdir(self):
        """Durchstich 2026-10-06: the script kept min_f1 = 0.5 against 0.6.
        Since 0.71 the run never starts; the record can only carry the
        registered value."""
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                runlog.Run("t", {"min_acc": 0.5}, self.area, run_kind="probe")
        self.assertIn(
            "min_acc = 0.7 is registered, the config says 0.5", str(cm.exception)
        )
        self.assertFalse((self.area / "runs").exists())

    def test_a_record_contradicting_a_constant_is_still_a_finding(self):
        """An old or hand-edited record (runlog 0.70 let it through): intent-check names it."""
        run = self.start()
        cfg_path = run.dir / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["config"]["min_acc"] = 0.5
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        self.complete(run, self.GOOD)
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("declares min_acc = 0.7, the run used min_acc = 0.5", out)

    def test_a_record_lacking_a_constant_is_a_finding(self):
        run = self.start()
        cfg_path = run.dir / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        del cfg["config"]["min_acc"]
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        self.complete(run, self.GOOD)
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("recorded no constant of that name", out)
        self.assertIn("0.70.0", out)

    def test_run_config_agreeing_with_a_constant_is_silent(self):
        with contextlib.redirect_stdout(io.StringIO()):
            run = runlog.Run("t", {"min_acc": 0.7}, self.area, run_kind="probe")
        self.complete(run, self.GOOD)
        rc, out = self.check()
        self.assertEqual(rc, 0, out)

    def with_branch(self) -> None:
        self.protocol.write_text(
            protocol_text(
                C1,
                A1,
                B1,
                prose="Criterion [criterion-1]; quality check [quality-check-1]; "
                "branch [branch-1].\n",
            ),
            encoding="utf-8",
        )

    def test_a_registered_reading_passes(self):
        """The twin: a registered name passes, whichever outcome it names."""
        self.with_branch()
        for outcome in ("generalises", "no-verdict"):
            with self.subTest(outcome=outcome):
                if (self.area / "runs").exists():
                    shutil.rmtree(self.area / "runs")
                self.complete(self.start(), {**self.GOOD, "branch_1_outcome": outcome})
                rc, out = self.check()
                self.assertEqual(rc, 0, out)

    def test_an_unregistered_outcome_is_a_blocker_naming_the_outcomes(self):
        """Free text recorded as the branch's value: no outcome holds it."""
        self.with_branch()
        self.complete(
            self.start(),
            {**self.GOOD, "branch_1_outcome": "generalises if criterion-1 met"},
        )
        rc, out = self.check()
        self.assertEqual(rc, 1, out)
        self.assertIn(
            "[branch-1] records branch_1_outcome = "
            "'generalises if criterion-1 met', which is none of its outcomes' "
            "names. Next: record one of generalises, noisy, no-verdict",
            out,
        )

    def test_unregistered_outcomes_is_pure_and_type_strict(self):
        block = parsed(protocol_text(C1, B1))
        for value in (True, None, 1, ["noisy"], "Noisy"):
            with self.subTest(value=value):
                (finding,) = intent_check.unregistered_outcomes(
                    block, {"branch_1_outcome": value}, "r1"
                )
                self.assertEqual(finding.grade, "BLOCKER")
                self.assertEqual(finding.evidence_kind, "guaranteed")
                self.assertIn("generalises, noisy, no-verdict", finding.fix or "")
        self.assertEqual(
            intent_check.unregistered_outcomes(
                block, {"branch_1_outcome": "noisy"}, "r1"
            ),
            [],
        )
        # an unreported key is check_block_against_run's finding, not this one
        self.assertEqual(intent_check.unregistered_outcomes(block, {}, "r1"), [])

    def test_declared_key_must_be_reported_exactly(self):
        self.complete(
            self.start(), {"criterion_1_debug": 1, "quality_check_1_anchor_ok": True}
        )
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("declares key 'criterion_1_pass'", out)

    def test_prose_and_block_must_name_the_same_ids(self):
        self.protocol.write_text(
            protocol_text(C1, A1, prose="only [criterion-1] and [branch-1]\n"),
            encoding="utf-8",
        )
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn(
            "[branch-1] appears in the text but not in the promise block", out
        )
        self.assertIn("[quality-check-1] is in the promise block but never named", out)

    def test_recheck_refuses_a_changed_block(self):
        """Durchstich 2026-10-06: the threshold lowered after the run left
        the verdict unchanged, and recheck held the note anyway."""
        run = self.complete(self.start(), self.GOOD)
        recheck.block_unchanged(run, self.area)  # unchanged: passes
        self.protocol.write_text(
            protocol_text(C1.replace("0.7", "0.5"), A1), encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.block_unchanged(run, self.area)
        self.assertIn("promises changed after the run", str(cm.exception))

    def test_drift_helpers_without_a_block(self):
        self.assertEqual(promises.scope_drift(None, self.area), [])
        self.assertIsNone(promises.block_drift(None, None))
        rec = {"block_sha": "abc", "ids": {}}
        self.assertIn("now carries none", promises.block_drift(rec, None) or "")

    def test_finalize_blocks_a_changed_scope(self):
        """Durchstich 2026-10-06: a scope edited after the run went through
        finalize; only recheck saw it."""
        from labkit.gates import finalize

        self.complete(self.start(), self.GOOD)

        def station() -> str:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                finalize.main([str(self.area)])
            out = buf.getvalue()
            return out[
                out.index("── the run's code and declared scopes ──") : out.index(
                    "── open fields"
                )
            ]

        self.assertIn("2 declared scope(s) unchanged", station())
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text().replace('== r["gold"]', '!= r["gold"]'), encoding="utf-8"
        )
        out = station()
        self.assertIn("BLOCKER: declared scope changed", out)
        self.assertIn("[criterion-1]", out)

    def test_recheck_refuses_a_changed_scope(self):
        run = self.complete(self.start(), self.GOOD)
        recheck.scopes_unchanged(run, self.area)  # unchanged: passes
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text().replace('== r["gold"]', '!= r["gold"]'), encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.scopes_unchanged(run, self.area)
        self.assertIn("[criterion-1]", str(cm.exception))
        self.assertIn("[quality-check-1]", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class Decorators(unittest.TestCase):
    def test_a_changed_decorator_moves_the_declared_scope(self):
        """Review 2026-10-07: decorators were excluded, so `@cache` → `@retry`
        left the stamp alone while the behaviour changed."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "m.py").write_text("@cache\ndef evaluate(r):\n    return r\n")
            before = promises.declared_scope_sha(base, ("m.py:evaluate",))
            (base / "m.py").write_text("@retry\ndef evaluate(r):\n    return r\n")
            self.assertNotEqual(
                before, promises.declared_scope_sha(base, ("m.py:evaluate",))
            )


class Redefinition(unittest.TestCase):
    """Review 2026-10-20: `file:score` hashed the first of two `def score`;
    Python runs the second, so its result went 2 → 999 under an unmoved
    stamp. A name bound twice at the top level is refused."""

    def stamp(self, source: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text(source)
            return promises.declared_scope_sha(Path(d), ("m.py:score",))

    def test_a_second_def_is_refused(self):
        with self.assertRaises(promises.PromiseError) as cm:
            self.stamp("def score():\n    return 2\n\ndef score():\n    return 999\n")
        self.assertIn("lines 1, 4", str(cm.exception))

    def test_a_rebinding_assignment_or_import_is_refused(self):
        for tail in ("score = lambda: 999\n", "from other import score\n"):
            with self.assertRaises(promises.PromiseError, msg=tail):
                self.stamp("def score():\n    return 2\n" + tail)

    def test_one_definition_and_other_names_pass(self):
        """The twin: neighbours, imports and assignments of other names do not block."""
        self.stamp(
            "import json\nx = 1\n\ndef score():\n    return 2\n\ndef other():\n    pass\n"
        )


class Constants(unittest.TestCase):
    """A constant is named like its config key, has one home, and is held
    type-strictly (0.71.0)."""

    def assertRejects(self, text: str, fragment: str):
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_block(text)
        self.assertIn(fragment, str(cm.exception))

    def test_uppercase_name_is_refused(self):
        self.assertRejects(
            protocol_text(C1.replace("min_acc = 0.7", "MIN_ACC = 0.7")),
            "constant 'MIN_ACC' — a constant is named like the config key",
        )

    def test_a_name_in_two_promises_is_refused(self):
        a1 = A1.replace(
            'scope = ["scripts/01_measure.py"]',
            'scope = ["scripts/01_measure.py"]\nconstants = { min_acc = 0.7 }',
        )
        self.assertRejects(
            protocol_text(C1, a1),
            "constant min_acc already stands in [[promise]] criterion-1",
        )

    def test_a_name_twice_in_one_table_is_toml_s_refusal(self):
        twice = C1.replace(
            "constants = { min_acc = 0.7 }",
            "constants = { min_acc = 0.7, min_acc = 0.8 }",
        )
        self.assertRejects(protocol_text(twice), "not valid TOML")

    def test_all_constants_unites_the_promises(self):
        a1 = A1.replace(
            'scope = ["scripts/01_measure.py"]',
            'scope = ["scripts/01_measure.py"]\nconstants = { max_empty = 2 }',
        )
        self.assertEqual(
            promises.all_constants(parsed(protocol_text(C1, a1))),
            {"min_acc": 0.7, "max_empty": 2},
        )

    def test_constant_records_are_type_strict(self):
        block = parsed(protocol_text(C1.replace("min_acc = 0.7", "min_acc = 1")))
        states = {
            repr(v): promises.constant_records(block, {"min_acc": v})[0].state
            for v in (1, 1.0, True)
        }
        self.assertEqual(
            states, {"1": "equal", "1.0": "different", "True": "different"}
        )
        self.assertEqual(promises.constant_records(block, {})[0].state, "missing")

    def test_a_stamp_placeholder_sentence_is_a_table_not_yet_written(self):
        """Three `<…>` sentences were frozen, hashed into the run's block
        digest and passed every gate (cloud judge probe, 2026-10-14). The
        twin: the written sentence passes; an unfrozen pilot may carry one."""
        stamped = parsed(
            protocol_text(C1).replace(
                'sentence = "accuracy >= min_acc"',
                'sentence = "<the criterion in one sentence>"',
            )
        )
        self.assertEqual(promises.placeholder_sentences(stamped), ["criterion-1"])
        for frozen, full_run in ((True, False), (False, True)):
            with self.subTest(frozen=frozen, full_run=full_run):
                owed = (
                    promises.promise_tables_owed(
                        stamped, frozen=frozen, full_run=full_run
                    )
                    or ""
                )
                self.assertIn(
                    "[[promise]] criterion-1 still carries the stamp's `<…>` sentence",
                    owed,
                )
        self.assertIsNone(
            promises.promise_tables_owed(stamped, frozen=False, full_run=False)
        )
        written = parsed(protocol_text(C1))
        self.assertEqual(promises.placeholder_sentences(written), [])
        self.assertIsNone(
            promises.promise_tables_owed(written, frozen=True, full_run=True)
        )

    def test_block_owed_when_frozen_or_a_full_run_without_tables(self):
        self.assertIsNone(
            promises.promise_tables_owed(None, frozen=False, full_run=False)
        )
        self.assertIsNone(
            promises.promise_tables_owed(
                parsed(protocol_text(C1)), frozen=True, full_run=True
            )
        )
        self.assertIn(
            "frozen = true, but",
            promises.promise_tables_owed(None, frozen=True, full_run=False) or "",
        )
        self.assertIn(
            "a full run is held to the registration, but",
            promises.promise_tables_owed(None, frozen=False, full_run=True) or "",
        )
        # a computation registers nothing, frozen too: the high-cost freeze
        # asked for the tables its own stamp removes (review 2026-10-27, 1)
        for frozen, full_run in ((True, False), (True, True), (False, True)):
            with self.subTest(frozen=frozen, full_run=full_run):
                self.assertIsNone(
                    promises.promise_tables_owed(
                        None, frozen=frozen, full_run=full_run, registers=False
                    )
                )


class Outcomes(unittest.TestCase):
    """A branch's sentence lists its outcomes, `<condition> → <outcome>:
    <consequence>`; `parse_outcomes` reads them or refuses them by name."""

    def assertRefused(self, sentence: str, fragment: str, *, shows_form: bool = True):
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_outcomes(sentence)
        self.assertIn(fragment, str(cm.exception))
        if shows_form:
            self.assertIn(promises.OUTCOMES_FORM, str(cm.exception))

    def test_the_form_reads_outcome_by_outcome(self):
        self.assertEqual(
            promises.parse_outcomes(OUTCOMES),
            (
                promises.BranchOutcome(
                    "criterion-1 met and quality-check-1 met",
                    "generalises",
                    "used on the next cohort",
                ),
                promises.BranchOutcome(
                    "quality-check-1 not met",
                    "noisy",
                    "no verdict, the parser is repaired first",
                ),
                promises.BranchOutcome(
                    "otherwise",
                    "no-verdict",
                    "reported descriptively, no further analysis",
                ),
            ),
        )
        # two outcomes without `otherwise`, digits in a name, tight spacing
        self.assertEqual(
            [
                o.name
                for o in promises.parse_outcomes(
                    "n >= 50→full:all reported;n < 50 → coverage-2: coverage only"
                )
            ],
            ["full", "coverage-2"],
        )

    def test_an_outcome_without_its_consequence_is_refused(self):
        """An outcome without a consequence registers a label, not what the
        result permits; the twin above carries one each."""
        self.assertRefused(
            "a → yes; b → no: stop", "outcome 1 'a → yes' names no consequence"
        )
        self.assertRefused("a → yes:; b → no: stop", "names no consequence")

    def test_a_semicolon_inside_a_consequence_is_named(self):
        self.assertRefused(
            "a → yes: report it; then stop; b → no: nothing",
            "a consequence holds none — write it with commas",
        )

    def test_a_sentence_without_an_arrow_is_refused(self):
        """The free text of 0.103.0: nothing held the recorded value to it."""
        self.assertRefused(
            "generalises if criterion-1 met; noisy if quality-check-1 not met",
            "outcome 1 'generalises if criterion-1 met' holds 0 `→`, not one",
        )

    def test_the_ascii_arrow_is_refused_by_name(self):
        self.assertRefused("a -> yes: x; b → no: y", "(the arrow is `→`, not `->`)")

    def test_two_arrows_in_one_arm_are_refused(self):
        self.assertRefused("a → b → c: x; d → e: y", "holds 2 `→`, not one")

    def test_an_empty_arm_is_refused(self):
        self.assertRefused("a → yes: x; ; b → no: y", "outcome 2 is empty")
        self.assertRefused("a → yes: x; b → no: y;", "outcome 3 is empty")

    def test_an_empty_condition_is_refused(self):
        self.assertRefused(
            "→ yes: x; b → no: y", "outcome 1 '→ yes: x' has no condition"
        )

    def test_a_reading_that_is_not_a_slug_is_refused(self):
        for outcome in ("Yes", "no verdict", "-no", "", "réussi"):
            with self.subTest(outcome=outcome):
                self.assertRefused(
                    f"a → {outcome}: x; b → other: y",
                    "is not lowercase letters, digits and hyphens",
                )

    def test_a_reading_twice_is_refused(self):
        self.assertRefused(
            "a → yes: x; b → yes: y",
            "name 'yes' stands in an earlier outcome too",
            shows_form=False,
        )

    def test_one_arm_is_refused(self):
        self.assertRefused("a → yes: x", "one outcome — a branch chooses")

    def test_otherwise_before_the_last_arm_is_refused(self):
        self.assertRefused(
            "otherwise → yes: x; b → no: y", "is `otherwise` but not the last outcome"
        )

    def test_parse_block_refuses_a_free_text_interpretation_by_id(self):
        free = B1.replace(
            "criterion-1 met → generalises: used on the next cohort; quality-check-1 not met → noisy: no verdict, the parser is repaired first; otherwise → no-verdict: reported descriptively",
            "generalises if criterion-1 met, noisy otherwise",
        )
        with self.assertRaises(promises.PromiseError) as cm:
            promises.parse_block(protocol_text(C1, free))
        self.assertIn("[[promise]] branch-1: `sentence`: outcome 1", str(cm.exception))
        self.assertIn(promises.OUTCOMES_FORM, str(cm.exception))

    def test_parse_block_reads_the_arms_and_leaves_other_kinds_free(self):
        b = parsed(protocol_text(C1, A1, B1))
        self.assertEqual(
            b.by_id()["branch-1"].outcome_names(),
            ("generalises", "noisy", "no-verdict"),
        )
        # a criterion's sentence is no outcome form, and none is asked of it
        self.assertEqual(b.by_id()["criterion-1"].outcomes, ())
        self.assertEqual(b.by_id()["quality-check-1"].outcome_names(), ())

    def test_a_stamp_placeholder_interpretation_parses_without_arms(self):
        """An unfrozen pilot may carry the stamp's `<…>`; `promise_tables_owed`
        holds it once frozen or a full run."""
        stamped = B1.replace(
            "criterion-1 met → generalises: used on the next cohort; quality-check-1 not met → noisy: no verdict, the parser is repaired first; otherwise → no-verdict: reported descriptively",
            "<the outcomes of the outcome>",
        )
        b = parsed(protocol_text(C1, stamped))
        self.assertEqual(b.by_id()["branch-1"].outcomes, ())
        self.assertEqual(promises.placeholder_sentences(b), ["branch-1"])


class KeyKind(unittest.TestCase):
    """`promises.key_kind` is the one way to ask a key's letter."""

    def test_kinds_and_outsiders(self):
        self.assertEqual(promises.key_kind("criterion_1_pass"), "criterion")
        self.assertEqual(promises.key_kind("quality_check_2"), "quality-check")
        self.assertEqual(promises.key_kind("branch_10_outcome"), "branch")
        self.assertIsNone(promises.key_kind("c1_pass"))
        self.assertIsNone(promises.key_kind("quality-check-2"))
        for key in ("f1", "p1_x", "criterion_pass", "ac1_pass", "k1_pass"):
            self.assertIsNone(promises.key_kind(key), key)


class SnapshotChanges(unittest.TestCase):
    """What differs between two recorded registrations (K3): named per id;
    the declared-scope digest — the code — is no change of the registration."""

    def snap(self, sha: str, **ids: dict) -> dict:
        return {"block_sha": sha, "ids": ids}

    def test_each_change_of_the_registration_is_named(self):
        a2 = {
            "key": "quality_check_2_pass",
            "constants": {"null_band": 0.1},
            "scope": ["s.py"],
            "declared_scope_sha": "x",
        }
        was = self.snap(
            "aaa",
            **{
                "quality-check-2": a2,
                "quality-check-3": {
                    "key": "quality_check_3_pass",
                    "constants": {},
                    "scope": ["s.py"],
                },
            },
        )
        now = self.snap(
            "bbb",
            **{
                "quality-check-2": {
                    **a2,
                    "constants": {"null_band": 0.15},
                    "scope": ["s.py", "t.py"],
                },
                "criterion-2": {
                    "key": "criterion_2_pass",
                    "constants": {},
                    "scope": [],
                },
            },
        )
        self.assertEqual(
            promises.snapshot_changes(was, now),
            [
                "[criterion-2] added",
                "[quality-check-3] dropped",
                "[quality-check-2] null_band 0.1 → 0.15",
                "[quality-check-2] scope ['s.py'] → ['s.py', 't.py']",
            ],
        )

    def test_the_same_block_and_a_repaired_code_name_nothing(self):
        a2 = {
            "key": "quality_check_2_pass",
            "constants": {"null_band": 0.1},
            "scope": ["s.py"],
            "declared_scope_sha": "x",
        }
        self.assertEqual(
            promises.snapshot_changes(self.snap("aaa", A2=a2), self.snap("aaa", A2=a2)),
            [],
        )
        moved = {
            **a2,
            "declared_scope_sha": "y",
        }  # the block digest would not move either
        self.assertEqual(
            promises.snapshot_changes(
                self.snap("aaa", A2=a2), self.snap("aaa", A2=moved)
            ),
            [],
        )

    def test_a_block_that_differs_in_nothing_kept_differs_in_a_sentence(self):
        a2 = {"key": "quality_check_2_pass", "constants": {}, "scope": ["s.py"]}
        self.assertEqual(
            promises.snapshot_changes(self.snap("aaa", A2=a2), self.snap("bbb", A2=a2)),
            ["a promise's sentence"],
        )
