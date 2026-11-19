"""recheck holds a run under the protocol text it started under.

An older run is named for a recheck after its protocol moved on: the
`[kept]` key and the promise block are the ones of the run's own text —
its commit with its uncommitted.patch (`recheck.protocol_as_run_saw`) —,
not the protocol as it reads now. The case: run A kept `score` under a
bar of 0.7; then the protocol names `n_items` as its kept number and
lowers the bar. A's `score` is still compared exactly, a different
`n_items` (descriptive for A) is no failure, and where A's text cannot be
read back that is said — the text as it reads now is never read in its
place. The answering run, rechecked without a name, still holds the
protocol as it reads now to the block it recorded.

The separate check of an older run (`recheck.holds_as_measured`) reads the
rows the run recorded: the file as it stands, or — a later run overwrote
it — the bytes a commit holds with the recorded sha256, in a temporary
directory; with no such bytes left the run is not verifiable, and the
file as it stands is never read in their place.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.checks import recheck
from labkit.formats import promises
from protocol_fixture import C1_BLOCK, PID, head, run_record, started_at
from repo_fixture import git as _git

RUN_A = "2026-11-18T10-00-00_aaaa"
ROWS = [{"id": 1, "ok": True}, {"id": 2, "ok": True}, {"id": 3, "ok": False}]


def evaluate(rows: list[dict]) -> dict:
    """What the area's script computes: the share of rows that hold, its
    verdict against the bar A registered, and the row count."""
    score = sum(r["ok"] for r in rows) / len(rows)
    return {"score": score, "criterion_1_pass": score > 0.5, "n_items": len(rows)}


def protocol(kept: str, block: str = C1_BLOCK) -> str:
    return (
        "- **Inference criterion:** [criterion-1] the criterion holds\n"
        f"- **Recorded results:** score {2 / 3}, 3 items, run {RUN_A}\n\n"
        + head(repeat_cost="low", kind="fit", promises=block, kept=(kept, "1"))
    )


class AnOlderRunUnderItsOwnText(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q")
        self.area = self.repo / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "01_measure.py").write_text("print(1)\n")
        self.protocol = self.area / "PROTOCOL-x.md"
        self.protocol.write_text(protocol("score"), encoding="utf-8")
        self.out = self.area / "output" / "rows.jsonl"
        self.out.parent.mkdir()
        self.out.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the area, as A is measured under it")
        self.run_a = self._run_a()
        # the code step has its own tests (tests/test_run_code.py): this
        # record names no script
        code_step = mock.patch.object(recheck, "require_run_code")
        code_step.start()
        self.addCleanup(code_step.stop)

    def _run_a(self) -> Path:
        """A as runlog leaves it at HEAD: bound, its block recorded, its
        rows registered, its metrics `evaluate`'s."""
        d = self.area / "runs" / RUN_A
        d.mkdir(parents=True)
        block = promises.parse_block(self.protocol.read_text(encoding="utf-8"))
        assert block is not None
        cfg = run_record(
            protocol={"id": PID, "path": self.protocol.name},
            promises=promises.snapshot(block, self.area),
        )
        (d / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        started_at(d, self.repo)
        (d / "completion.json").write_text(json.dumps({"status": "completed"}))
        (d / "metrics.json").write_text(json.dumps(evaluate(ROWS)))
        sha = hashlib.sha256(self.out.read_bytes()).hexdigest()[:16]
        (d / "outputs.json").write_text(
            json.dumps([{"path": str(self.out), "sha256": sha}])
        )
        return d

    def move_on(self, *, block: str = C1_BLOCK) -> None:
        """The protocol after A: `n_items` is its kept number now, BLOCK
        its promises; committed."""
        self.protocol.write_text(protocol("n_items", block), encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the protocol moves on")

    def test_the_kept_key_is_the_one_the_run_started_under(self) -> None:
        self.assertEqual(recheck.kept_keys(self.run_a, self.area), frozenset({"score"}))
        self.move_on()
        self.assertIn('key = "n_items"', self.protocol.read_text(encoding="utf-8"))
        self.assertEqual(recheck.kept_keys(self.run_a, self.area), frozenset({"score"}))

    def test_a_named_run_is_compared_in_its_own_kept_number(self) -> None:
        """After the protocol moved on, A's `score` is still the number
        compared exactly; `n_items`, kept now and descriptive for A, may
        differ. Read as now, both would come out the other way round."""
        self.move_on()

        def other_count(rows: list[dict]) -> dict:
            return {**evaluate(rows), "n_items": 99}

        def other_score(rows: list[dict]) -> dict:
            return {**evaluate(rows), "score": 0.6}

        verdict = recheck.holds(
            self.area, self.out, other_count, self.protocol, run_id=RUN_A
        )
        self.assertEqual(verdict.run_id, RUN_A)
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, other_score, self.protocol, run_id=RUN_A)
        self.assertIn("the kept number ['score']", str(cm.exception))

    def test_a_named_run_holds_under_its_own_block_the_answering_run_to_the_one_now(
        self,
    ) -> None:
        """The bar lowered after A: named, A is rechecked under the block
        it recorded; as the run the protocol answers with, the protocol as
        it reads now is held to that block and refused."""
        self.move_on(block=C1_BLOCK.replace("holds", "holds at a lower bar"))
        recheck.holds(self.area, self.out, evaluate, self.protocol, run_id=RUN_A)
        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, evaluate, self.protocol)
        self.assertIn("the promises changed after the run", str(cm.exception))

    def test_a_text_that_cannot_be_read_back_is_named_never_read_as_now(self) -> None:
        """A's record names a commit this clone does not hold: the refusal
        says so and what brings it back; `n_items` of the text as it reads
        now is not compared in `score`'s place."""
        self.move_on()
        cfg = json.loads((self.run_a / "config.json").read_text())
        cfg["git_full"] = "0" * 40
        (self.run_a / "config.json").write_text(json.dumps(cfg))
        calls: list[int] = []

        def counted(rows: list[dict]) -> dict:
            calls.append(1)
            return evaluate(rows)

        with self.assertRaises(SystemExit) as cm:
            recheck.holds(self.area, self.out, counted, self.protocol, run_id=RUN_A)
        told = str(cm.exception)
        self.assertIn(f"the protocol run {RUN_A} was measured under cannot be", told)
        self.assertIn("a commit this clone does not hold", told)
        self.assertIn("not taken from the protocol as it reads now", told)


class AnOlderRunFromTheRowsItRecorded(AnOlderRunUnderItsOwnText):
    """A's output is committed, then a later run overwrites the file."""

    LATER = [{"id": 1, "ok": False}, {"id": 2, "ok": False}]

    def overwrite(self, *, commit: bool = True) -> bytes:
        """The output as a later run leaves it; its bytes."""
        self.out.write_text("".join(json.dumps(r) + "\n" for r in self.LATER))
        if commit:
            _git(self.repo, "add", "-A")
            _git(self.repo, "commit", "-qm", "a later run's rows")
        return self.out.read_bytes()

    def check(self, recompute=evaluate) -> recheck.AsMeasured:
        return recheck.holds_as_measured(
            self.area, self.out, recompute, RUN_A, self.protocol
        )

    def test_the_twin_a_file_that_still_stands_is_read_where_it_is(self) -> None:
        held = self.check()
        self.assertEqual(held.source, "the file as it stands")
        self.assertEqual((held.run_id, held.keys_compared), (RUN_A, 3))

    def test_overwritten_rows_are_read_from_the_commit_that_holds_them(self) -> None:
        """The protocol moved on and the file is another run's: A is held
        by its own rows and its own kept key, and the tree is untouched."""
        self.move_on()
        later = self.overwrite()
        seen: list[Path] = []

        def recompute(rows: list[dict]) -> dict:
            seen.append(Path(tempfile.gettempdir()))
            self.assertEqual(rows, ROWS)
            return evaluate(rows)

        held = self.check(recompute)
        self.assertIn("commit ", held.source)
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.out.read_bytes(), later)
        self.assertEqual(_git(self.repo, "status", "--porcelain").strip(), "")

    def test_the_restored_rows_are_compared_not_trusted(self) -> None:
        self.overwrite()
        with self.assertRaises(SystemExit) as cm:
            self.check(lambda rows: {**evaluate(rows), "score": 0.1})
        self.assertNotIsInstance(cm.exception, recheck.NotVerifiable)
        self.assertIn("the kept number ['score']", str(cm.exception))

    def test_rows_no_commit_holds_are_not_verifiable(self) -> None:
        """A's bytes were never committed with the recorded sha256: the
        record names another digest than every version git holds. The
        file as it stands is not read — the recomputation is not called."""
        self.overwrite()
        entry = json.loads((self.run_a / "outputs.json").read_text())
        entry[0]["sha256"] = "0" * 16
        (self.run_a / "outputs.json").write_text(json.dumps(entry))
        calls: list[int] = []

        def counted(rows: list[dict]) -> dict:
            calls.append(1)
            return evaluate(rows)

        with self.assertRaises(recheck.NotVerifiable) as cm:
            self.check(counted)
        told = str(cm.exception)
        self.assertIn("is not verifiable", told)
        self.assertIn("none of the 2 version(s)", told)
        self.assertIn("never read in its place", told)
        self.assertEqual(calls, [])

    def test_the_check_holds_no_note(self) -> None:
        """The protocol cites another run and other numbers by now: the
        separate check of A does not read it."""
        self.protocol.write_text(
            protocol("score").replace(RUN_A, "another run").replace("3 items", "x"),
            encoding="utf-8",
        )
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "the note moved on")
        self.assertEqual(self.check().run_id, RUN_A)


if __name__ == "__main__":
    unittest.main()
