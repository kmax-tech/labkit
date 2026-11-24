"""A derived run that declares its answer reading, on the real chain: run A
of the counting skeleton writes its rows; the evaluation is fixed after A
ran; a derived run D re-reads A's rows with `answer_reading` declared, no
model asked. finalize, the area's own `--check`, the adoption and
report-check pass on D, and A's record and rows stay as A left them. Each
change the declaration does not cover holds D: the answer reading, a
prompt, the rows A registered — and the evaluation fix itself, once D
declares nothing (the parent compared whole, as before).

    .venv/bin/python -m pytest tests/test_answer_reading_scenario.py
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest

import pytest

from labkit.formats import standard_contract as sc
from labkit.formats.answer_reading import ANSWER_READING_FILE
from labkit.gates import report_check
from test_end_to_end import Lab, stamp_count

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

READING = 'COUNT_FIELD = "lines"\n\n\ndef count_of(row: dict) -> int:\n    """The count a row holds."""\n    return row[COUNT_FIELD]\n'
PROMPT = "- **Prompt (verbatim, per variant):** Count the lines of each document.\n"
# the stage that derives a run from PARENT's rows; DECLARE: with its answer reading
DERIVE = '''
def derive(parent: str, declare: bool) -> None:
    """A derived run of PARENT: its rows in OUT evaluated again, no row written."""
    ids = expected_ids()
    items = [json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines()]
    frozen = read_inputs()
    with runlog.run("lines", config={k: str(p.relative_to(REPO)) for k, p in frozen.items()},
                    base_dir=AREA, data=frozen, run_kind="measurement", protocol=PROTOCOL.name,
                    derived_from=parent,
                    answer_reading=AREA / "scripts" / "reading.py" if declare else None) as run:
        run.output(OUT)
        metrics = metrics_of(items, ids)
        run.metrics(**metrics)
        print(f"run: {run.run_id}")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] in ("--derive", "--derive-undeclared"):
        derive(sys.argv[2], declare=sys.argv[1] == "--derive")
        return
'''


def _replace(path: Path, old: str, new: str) -> None:
    """PATH with OLD, which it holds once, replaced by NEW."""
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


class DeclaredAnswerReading(unittest.TestCase):
    """A's rows evaluated again by D after an evaluation fix."""

    def setUp(self) -> None:
        self.lab = Lab()
        self.addCleanup(self.lab.close)
        self.area, self.protocol = stamp_count(self.lab)
        self.measure = self.area / "scripts" / "01_measure.py"
        self.reading = self.area / "scripts" / "reading.py"
        self.reading.write_text(READING, encoding="utf-8")
        # the count a row holds is read by the module of its own; the script
        # gains the stage that derives a run
        _replace(
            self.measure,
            "\nimport json\n",
            # the module beside the script, found as the area's tests load it too
            "\nimport json\nimport os\nimport sys\n\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
            "import reading  # noqa: E402\n",
        )
        _replace(
            self.measure,
            "sum(r[COUNT_FIELD] for r in items)",
            "sum(reading.count_of(r) for r in items)",
        )
        _replace(self.measure, "\ndef main() -> None:\n", DERIVE)
        text = self.protocol.read_text(encoding="utf-8")
        anchor = "- **Question / hypothesis:**"
        assert anchor in text
        self.protocol.write_text(
            text.replace(anchor, PROMPT + anchor, 1), encoding="utf-8"
        )
        self.lab.commit("the area reads a row's count in reading.py")
        self.a = self.lab.run_id_of(self.lab.script(self.area, "01_measure.py"))
        self.lab.commit("run A")
        self.a_dir = self.area / "runs" / self.a
        self.out = self.area / "output" / "lines.jsonl"
        self.a_bytes = {
            p: p.read_bytes() for p in (self.a_dir / "config.json", self.out)
        }

    def fix_the_evaluation(self) -> None:
        """The evaluation changed after A ran, the reading not: the mean
        through the standard library, the same number."""
        _replace(
            self.measure,
            "sum(reading.count_of(r) for r in items) / len(ids)",
            "fsum(reading.count_of(r) for r in items) / len(ids)",
        )
        _replace(
            self.measure, "\nimport json\n", "\nimport json\nfrom math import fsum\n"
        )
        self.lab.commit("the evaluation fixed")

    def derive(self, flag: str = "--derive") -> str:
        d = self.lab.run_id_of(
            self.lab.script(self.area, "01_measure.py", flag, self.a)
        )
        self.lab.commit("run D")
        return d

    def report_check(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report_check.protocol_verdict(self.area).exit
        return code, out.getvalue()

    def test_an_evaluation_fix_passes_the_chain_and_leaves_a_as_it_was(self) -> None:
        self.fix_the_evaluation()
        d = self.derive()
        self.assertTrue((self.area / "runs" / d / ANSWER_READING_FILE).is_file())
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"{d} declares its answer reading", out)
        self.assertIn(f"the code of {self.a} is compared in that module", out)
        self.lab.record(self.area, self.protocol, sc.ANALYSIS_AUDIT, d)
        rc, out = self.lab.adopt(self.protocol, d)
        self.assertEqual(rc, 0, out)
        self.lab.commit("D adopted")
        told = self.lab.script(self.area, "02_analyze.py", "--check")
        self.assertIn(f"run {d}", told)
        rc, out = self.report_check()
        self.assertEqual(rc, 0, out)
        # A's record and the rows A registered are as A left them
        for path, data in self.a_bytes.items():
            self.assertEqual(path.read_bytes(), data, path.name)
        # the adopted result names the run D re-read, both code states, and
        # what changed against A: the fix moved no number
        text = self.protocol.read_text(encoding="utf-8")
        self.assertIn(f"re-reads the answers of run {self.a} (commit ", text)
        self.assertIn(
            "its answer reading experiments/01-lines/scripts/reading.py", text
        )
        self.assertIn(f"changed against {self.a}: no number changed", text)

    def test_before_any_derived_run_the_hold_names_the_correction(self) -> None:
        """A concluded, the evaluation fixed, no derived run yet: labkit-next
        holds the changed code, and its way out names measuring anew and
        restoring — and the derived run that declares its answer reading,
        which before only a derived run without the declaration showed."""
        from labkit.gates.next_step import next_step

        self.lab.conclude(self.protocol)
        self.fix_the_evaluation()
        with contextlib.chdir(self.lab.root):
            step = next_step(self.area, self.protocol.resolve())
        self.assertIn("measure anew", step.next)
        self.assertIn(f"derived_from={self.a!r}, answer_reading=MODULE", step.next)

    def test_without_the_declaration_the_parent_is_compared_whole(self) -> None:
        self.fix_the_evaluation()
        d = self.derive("--derive-undeclared")
        self.assertFalse((self.area / "runs" / d / ANSWER_READING_FILE).exists())
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"01_measure.py changed since {self.a} ran it", out)
        self.assertIn("answer_reading=MODULE", out)

    def test_a_change_to_the_answer_reading_holds(self) -> None:
        _replace(
            self.reading, "return row[COUNT_FIELD]", "return int(row[COUNT_FIELD])"
        )
        self.lab.commit("the reading changed")
        self.derive()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"reading.py changed since {self.a} ran", out)

    def test_a_changed_prompt_holds(self) -> None:
        _replace(self.protocol, "Count the lines of each document.", "Count the words.")
        self.lab.commit("the prompt changed")
        self.derive()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn("the prompts field differs", out)

    def test_rows_changed_after_a_ran_hold(self) -> None:
        self.fix_the_evaluation()
        rows = self.out.read_text(encoding="utf-8").splitlines()
        first = json.loads(rows[0])
        rows[0] = json.dumps(first, separators=(",", ":"))  # the same row, other bytes
        self.assertNotEqual(
            rows[0], self.out.read_text(encoding="utf-8").splitlines()[0]
        )
        self.out.write_text("\n".join(rows) + "\n", encoding="utf-8")
        self.lab.commit("the rows rewritten")
        self.derive()
        rc, out = self.lab.finalize(self.area)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"the answers changed after {self.a} ran", out)


if __name__ == "__main__":
    unittest.main()
