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
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import intent_check, promises, recheck, runlog  # noqa: E402
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
id = "C1"
key = "c1_pass"
sentence = "accuracy >= min_acc"
scope = ["scripts/01_measure.py:compute_score"]
constants = { min_acc = 0.7 }
"""
A1 = """[[promise]]
id = "A1"
key = "a1_anchor_ok"
sentence = "the anchor items come out at 1.0, else no verdict"
scope = ["scripts/01_measure.py"]
"""


def parsed(text: str) -> promises.PromiseBlock:
    """parse_block for a text that must carry a block."""
    b = promises.parse_block(text)
    assert b is not None, "fixture has no promise block"
    return b


def protocol_text(
    *entries: str, prose: str = "Criterion [C1]; admissibility [A1].\n"
) -> str:
    """A protocol whose one ```toml block holds the head and `entries`."""
    return head(promises="\n".join(entries)) + "\n" + prose


class Parse(unittest.TestCase):
    def test_no_block_is_none(self):
        self.assertIsNone(promises.parse_block("criterion [K1] only in prose\n"))

    def test_block_without_promise_tables_declares_none(self):
        self.assertIsNone(
            promises.parse_block('```toml\n[protocol]\nstandard = "0.18"\n```\n')
        )

    def test_unknown_top_level_table(self):
        self.assertRejects(
            "```toml\n[tool]\nx = 1\n```\n", "only [protocol] and [[promise]]"
        )

    def test_entries_kinds_constants(self):
        b = parsed(protocol_text(C1, A1))
        self.assertEqual([p.id for p in b.promises], ["C1", "A1"])
        self.assertEqual(b.by_id()["C1"].kind, "criterion")
        self.assertEqual(b.by_id()["A1"].kind, "admissibility")
        self.assertEqual(b.by_id()["C1"].constants, {"min_acc": 0.7})
        self.assertEqual(b.by_id()["A1"].constants, {})

    def test_digest_follows_the_block_not_the_prose(self):
        a = parsed(protocol_text(C1))
        b = parsed(protocol_text(C1, prose="other prose [C1]\n"))
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
        self.assertRejects(block('[[promise]]\nid = "C1\n'), "not valid TOML")

    def test_earlier_letter_in_block(self):
        self.assertRejects(
            block(C1.replace('"C1"', '"K1"')), "is not C<n>, A<n> or B<n>"
        )

    def test_key_outside_namespace(self):
        self.assertRejects(
            block(C1.replace('"c1_pass"', '"c2_pass"')), "outside the id's namespace"
        )
        self.assertRejects(
            block(C1.replace('"c1_pass"', '"c10_pass"')), "outside the id's namespace"
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

    def test_only_c_a_b_keys_are_ids(self):
        metrics = {"c1_pass": 1, "a2": 1, "b1_branch": "x", "k1_pass": 1, "n1": 1}
        self.assertEqual(promises.reported_ids(metrics), {"c1", "a2", "b1"})

    def test_one_alphabet_everywhere(self):
        self.assertIs(intent_check.ID_KEY, promises.ID_KEY)
        self.assertIs(intent_check.ID_IN_PROTOCOL, promises.ID_IN_PROTOCOL)
        self.assertIs(recheck.INTENT_KEY, promises.INTENT_KEY)

    def test_prose_mismatch_both_directions(self):
        b = parsed(block(C1))
        self.assertEqual(
            promises.prose_mismatch("[C1] and [A2] and [K1]", b), (["A2"], [])
        )
        self.assertEqual(promises.prose_mismatch("only [K1]", b), ([], ["C1"]))


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
            return runlog.Run("t", {"min_acc": 0.7}, self.area, long=False)

    def complete(self, run: runlog.Run, metrics: dict) -> Path:
        (run.dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (run.dir / "completion.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
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

    GOOD = {"c1_pass": True, "a1_anchor_ok": True}

    def test_run_records_block_and_scope_per_promise(self):
        run = self.start()
        rec = json.loads((run.dir / "config.json").read_text())["promises"]
        self.assertEqual(rec["block_sha"], promises.load(self.protocol).sha)
        self.assertEqual(set(rec["ids"]), {"C1", "A1"})
        self.assertEqual(rec["ids"]["C1"]["constants"], {"min_acc": 0.7})
        self.assertEqual(
            rec["ids"]["C1"]["declared_scope_sha"],
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
        self.assertEqual(promises.constants(self.protocol, "C1"), {"min_acc": 0.7})
        with self.assertRaises(promises.PromiseError):
            promises.constants(self.protocol, "C9")

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
                runlog.Run("t", {"min_acc": 0.5}, self.area, long=False)
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
            run = runlog.Run("t", {"min_acc": 0.7}, self.area, long=False)
        self.complete(run, self.GOOD)
        rc, out = self.check()
        self.assertEqual(rc, 0, out)

    def test_declared_key_must_be_reported_exactly(self):
        self.complete(self.start(), {"c1_debug": 1, "a1_anchor_ok": True})
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("declares key 'c1_pass'", out)

    def test_prose_and_block_must_name_the_same_ids(self):
        self.protocol.write_text(
            protocol_text(C1, A1, prose="only [C1] and [B1]\n"), encoding="utf-8"
        )
        rc, out = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("[B1] appears in the text but not in the promise block", out)
        self.assertIn("[A1] is in the promise block but never named", out)

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
        from labkit import finalize

        self.complete(self.start(), self.GOOD)

        def station() -> str:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                finalize.main([str(self.area)])
            out = buf.getvalue()
            return out[out.index("── declared scopes ──") : out.index("── open fields")]

        self.assertIn("2 declared scope(s) unchanged", station())
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text().replace('== r["gold"]', '!= r["gold"]'), encoding="utf-8"
        )
        out = station()
        self.assertIn("BLOCKER: declared scope changed", out)
        self.assertIn("[C1]", out)

    def test_recheck_refuses_a_changed_scope(self):
        run = self.complete(self.start(), self.GOOD)
        recheck.scopes_unchanged(run, self.area)  # unchanged: passes
        script = self.area / "scripts" / "01_measure.py"
        script.write_text(
            script.read_text().replace('== r["gold"]', '!= r["gold"]'), encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as cm:
            recheck.scopes_unchanged(run, self.area)
        self.assertIn("[C1]", str(cm.exception))
        self.assertIn("[A1]", str(cm.exception))


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
            protocol_text(C1, a1), "constant min_acc already stands in [[promise]] C1"
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

    def test_block_owed_only_when_frozen_without_tables(self):
        self.assertIsNone(promises.block_owed(False, None))
        self.assertIsNone(promises.block_owed(True, parsed(protocol_text(C1))))
        self.assertIn(
            "frozen = true, but the protocol declares no [[promise]]",
            promises.block_owed(True, None) or "",
        )
