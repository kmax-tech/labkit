"""The reference comparison on the real chain (`test_end_to_end.Lab`): the
compute skeleton stamped with a `[reference]`, filled, committed, run,
finalized, audited, adopted, held by the stop hook and the pre-commit —
three areas, one per state. Twin 3: a missed reference is a valid
outcome — nothing holds the adoption, finalize or report-check on it, and
the Recorded results line says `not met` with the distance. Twin 4: a
reference the run cannot compare (the registered key absent from the
run's metrics) blocks finalize, naming the key and the way out, and the
adoption is refused — no "met" is rendered. The twin of both: a met
reference passes the same way and renders `met`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from labkit.formats import protocol_block, reference
from test_end_to_end import Lab, _replace

LINES = (("a.txt", 1), ("b.txt", 2), ("c.txt", 6))  # mean 3.0


def stamp_lines(
    lab: Lab, name: str, ref: protocol_block.Reference
) -> tuple[Path, Path]:
    """The counting skeleton at low repeat cost in LAB under NAME, with REF
    stamped as its `[reference]`, filled for lines per document over
    `data/raw/docs` (planted once). Returns (area, protocol); the caller
    commits."""
    docs = lab.root / "data" / "raw" / "docs"
    if not docs.is_dir():
        docs.mkdir(parents=True)
        for file, lines in LINES:
            (docs / file).write_text("x\n" * lines, encoding="utf-8")
    area, protocol = lab.exp(name, repeat_cost="low", kind="compute", reference=ref)
    _replace(
        area / "scripts" / "01_measure.py",
        [
            (
                'SOURCE = REPO / "data" / "TODO"',
                'SOURCE = REPO / "data" / "raw" / "docs"',
            ),
            ('COUNT_FIELD = "TODO_count"', 'COUNT_FIELD = "lines"'),
            ('METRIC_KEY = "TODO_mean"', 'METRIC_KEY = "lines_mean"'),
            (
                '    raise NotImplementedError("expected_ids(): the ids SOURCE lists")',
                "    return [p.name for p in visible(SOURCE)]",
            ),
            (
                '    raise NotImplementedError("rows(): one dict per id, fail loud on a missing one")',
                '    return [{"id": i, COUNT_FIELD: len((SOURCE / i).read_text(encoding="utf-8").splitlines())} for i in ids]',
            ),
            (
                '    raise NotImplementedError("evaluate_rows(): compute the number(s) from items")',
                "    return {METRIC_KEY: sum(r[COUNT_FIELD] for r in items) / len(ids)}",
            ),
        ],
    )
    lab.fill(
        protocol,
        "type=exploratory",
        "Terms of this protocol=n/a — no coinage",
        "Question / hypothesis=How many lines does a document of data/raw/docs hold on average?",
        "Data / scope=data/raw/docs, 3 documents, read directly",
        "Exclusions / filters=hidden entries and nested directories (visible())",
        "Unit=one document of data/raw/docs",
    )
    return area, protocol


def ref(key: str, value: float, tolerance: float | None, relation: str = "within"):
    return protocol_block.Reference(key, value, tolerance, False, relation, "the task")


class ReferenceOnTheChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.met = stamp_lines(cls.lab, "met", ref("lines_mean", 3.2, 0.5))
        cls.missed = stamp_lines(cls.lab, "missed", ref("lines_mean", 0.62, 0.01))
        cls.absent = stamp_lines(
            cls.lab, "absent", ref("lines_median", 3.0, None, "at_least")
        )
        cls.lab.commit("three computations with a stated value, registered")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def run_area(self, area: Path) -> tuple[str, dict]:
        """`01_measure.py` in AREA: (run id, its metrics.json)."""
        import json

        out = self.lab.script(area, "01_measure.py")
        run_id = self.lab.run_id_of(out)
        metrics = json.loads(
            (area / "runs" / run_id / "metrics.json").read_text(encoding="utf-8")
        )
        return run_id, metrics

    def adopted_line(self, area: Path, protocol: Path, run_id: str) -> str:
        """finalize clean, the analysis record, the adoption, the check, the
        hooks — the whole release; returns the Recorded results line."""
        lab = self.lab
        rc, out = lab.finalize(area)
        self.assertEqual(rc, 0, out)
        lab.record(area, protocol, "analysis", run_id)
        rc, out = lab.adopt(protocol, run_id)
        self.assertEqual(rc, 0, out)
        self.assertIn("finalized, audited, checked", out)
        lab.script(
            area, "02_analyze.py", "--check"
        )  # exits 0: the verdict recomputed and cited
        rc, err = lab.stop_hook()
        self.assertEqual(rc, 0, err)
        lab.git("add", "-A")
        rc, out = lab.pre_commit(protocol, area / "scripts" / "01_measure.py")
        self.assertEqual(rc, 0, out)
        lab.commit(f"{area.name}: the number, adopted")
        text = protocol.read_text(encoding="utf-8")
        (line,) = [
            ln for ln in text.splitlines() if ln.startswith("- **Recorded results:**")
        ]
        return line

    def test_a_met_reference_renders_met(self):
        area, protocol = self.met
        run_id, metrics = self.run_area(area)
        self.assertEqual((metrics["ref_state"], metrics["ref_met"]), ("compared", True))
        line = self.adopted_line(area, protocol, run_id)
        self.assertEqual(
            line,
            f"- **Recorded results:** lines_mean = 3.0; reference 3.2 ± 0.5 (within): "
            f"met, distance {abs(3.0 - 3.2)} (run {run_id})",
        )

    def test_twin_3_a_missed_reference_is_a_valid_outcome(self):
        area, protocol = self.missed
        run_id, metrics = self.run_area(area)
        self.assertEqual(
            (metrics["ref_state"], metrics["ref_met"]), ("compared", False)
        )
        line = self.adopted_line(area, protocol, run_id)
        self.assertEqual(
            line,
            f"- **Recorded results:** lines_mean = 3.0; reference 0.62 ± 0.01 (within): "
            f"not met, distance {abs(3.0 - 0.62)} (run {run_id})",
        )

    def test_twin_4_a_reference_the_run_cannot_compare_blocks(self):
        area, protocol = self.absent
        run_id, metrics = self.run_area(area)
        self.assertEqual(metrics["ref_state"], reference.NOT_COMPARABLE)
        self.assertIsNone(metrics["ref_met"])
        rc, out = self.lab.finalize(area)
        self.assertEqual(rc, 1, out)
        self.assertIn("`lines_median` is absent from metrics.json", out)
        self.assertIn("no verdict can be reported", out)
        self.assertIn("write `lines_median` as a finite number", out)
        self.assertIn("measure anew", out)
        self.lab.record(area, protocol, "analysis", run_id)
        before = protocol.read_text(encoding="utf-8")
        rc, out = self.lab.adopt(protocol, run_id)
        self.assertEqual(rc, 1, out)
        self.assertIn("lines_median", out)
        self.assertEqual(protocol.read_text(encoding="utf-8"), before)
        # the line still holds the stamp's placeholder: no "met" rendered
        line = before.split("- **Recorded results:**")[1].split("\n")[0]
        self.assertIn("<generated", line)
        self.assertNotIn("reference", line)


if __name__ == "__main__":
    unittest.main()
