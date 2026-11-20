"""A number computed from two output files is rechecked from both, on a
real run: the counting skeleton's script writes, besides its rows (one
per document, its line count), a second row file naming the ids the
number is over — the mean divides by them, so neither file alone gives
it. The run is committed with both files. `recheck.verified_outputs`
holds the run with its real code step: both files pinned, the protocol
as the run saw it, the code it ran. Each counter-case is refused before
a number is compared or by the comparison: the second file gone, the
second file changed after the run, the stored kept number wrong. The
separate check of the run reads a changed second file from the commit
that holds it as recorded.
"""

from __future__ import annotations

import json
import re
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

from labkit.checks import recheck
from labkit.formats import runs
from test_end_to_end import Lab, stamp_count

# an end-to-end scenario file: the full suite before a push runs it, the
# commit hook does not (.githooks/checks)
pytestmark = pytest.mark.slow

#: the second output file, written beside the rows and registered with them
IDS_LINE = (
    'IDS_OUT = AREA / "output" / "lines-ids.jsonl"   '
    "# the ids the number is over, one row each"
)
IDS_WRITE = (
    "        IDS_OUT.write_text(\"\".join(json.dumps({'id': i, '_prov': {'run': run.run_id}}) + "
    '"\\n" for i in ids), encoding="utf-8")\n'
    "        run.output(IDS_OUT)\n"
)


def _two_outputs(measure: Path) -> None:
    """MEASURE, the stamped counting script, rewritten in place to write
    and register IDS_OUT after its rows."""
    text = measure.read_text(encoding="utf-8")
    text, n_const = re.subn(
        r'^(OUT = AREA / "output" / "lines\.jsonl".*)$',
        lambda m: f"{m.group(1)}\n{IDS_LINE}",
        text,
        flags=re.M,
    )
    text, n_write = re.subn(
        r"^        run\.output\(OUT\)\n",
        lambda m: m.group(0) + IDS_WRITE,
        text,
        flags=re.M,
    )
    assert (n_const, n_write) == (1, 1), (n_const, n_write)
    measure.write_text(text, encoding="utf-8")


class TwoOutputFiles(unittest.TestCase):
    """One run, two row files, one number over both."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = Lab()
        cls.area, cls.protocol = stamp_count(cls.lab)
        _two_outputs(cls.area / "scripts" / "01_measure.py")
        cls.lab.commit("the count writes its ids as a second output")
        cls.run_id = cls.lab.run_id_of(cls.lab.script(cls.area, "01_measure.py"))
        cls.lab.commit("the run, its two output files")
        cls.run_dir = runs.run_path(cls.area, cls.run_id)
        cls.counts = cls.area / "output" / "lines.jsonl"
        cls.ids = cls.area / "output" / "lines-ids.jsonl"
        cls.measure: ModuleType = recheck.script_module(cls.area, cls.run_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.close()

    def setUp(self) -> None:
        self.handed: list[set[str]] = []

    def restore(self, path: Path) -> None:
        """PATH as the last commit holds it, once the test ends."""
        self.addCleanup(self.lab.git, "checkout", "--", str(path))

    def recompute(self, rows: Mapping[str, list[dict]]) -> dict:
        """The script's own formula over both files: the counts over the
        ids the second file names."""
        self.handed.append(set(rows))
        ids = [r["id"] for r in rows["ids"]]
        return self.measure.metrics_of(rows["counts"], ids)

    def verified(self) -> dict:
        metrics, _ = recheck.verified_outputs(
            self.run_dir,
            self.area,
            {"counts": self.counts, "ids": self.ids},
            self.recompute,
        )
        return metrics

    def test_the_run_is_recomputed_from_both_files(self) -> None:
        """The twin of every counter-case: both files as recorded, the code
        the run ran, the number the run stored."""
        registered = {o.path.name for o in runs.read_outputs(self.run_dir) or []}
        self.assertEqual(registered, {"lines.jsonl", "lines-ids.jsonl"})
        self.assertEqual(self.verified()["lines_mean"], 3.0)
        self.assertEqual(self.handed, [{"counts", "ids"}])

    def test_the_second_file_gone_is_refused(self) -> None:
        self.restore(self.ids)
        self.ids.unlink()
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn("lines-ids.jsonl is not the file run", str(cm.exception))
        self.assertIn("the file is gone", str(cm.exception))
        self.assertEqual(self.handed, [])

    def test_a_second_file_the_run_did_not_register_is_refused(self) -> None:
        other = self.area / "output" / "other-ids.jsonl"
        other.write_text(self.ids.read_text(encoding="utf-8"), encoding="utf-8")
        self.addCleanup(other.unlink)
        with self.assertRaises(SystemExit) as cm:
            recheck.verified_outputs(
                self.run_dir,
                self.area,
                {"counts": self.counts, "ids": other},
                self.recompute,
            )
        self.assertIn("did not register other-ids.jsonl", str(cm.exception))
        self.assertEqual(self.handed, [])

    def test_the_second_file_changed_after_the_run_is_refused(self) -> None:
        """One id dropped from the second file: the mean over two documents
        would be another number. The pin refuses it before any number is
        compared; the separate check of the run reads the second file from
        the commit that holds it as recorded, and holds."""
        self.restore(self.ids)
        kept = self.ids.read_text(encoding="utf-8").splitlines(keepends=True)
        self.ids.write_text("".join(kept[:-1]), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn("lines-ids.jsonl is not the file run", str(cm.exception))
        self.assertIn("is not the recorded", str(cm.exception))
        self.assertEqual(self.handed, [])
        measured = recheck.holds_as_measured_outputs(
            self.area,
            {"counts": self.counts, "ids": self.ids},
            self.recompute,
            self.run_id,
            self.protocol,
        )
        self.assertEqual(measured.sources["counts"], "the file as it stands")
        self.assertIn(
            "which holds the file as the run recorded it", measured.sources["ids"]
        )
        self.assertEqual(measured.grown, [])

    def test_a_wrong_stored_number_is_refused(self) -> None:
        metrics = runs.metrics_path(self.run_dir)
        self.restore(metrics)
        stored = json.loads(metrics.read_text(encoding="utf-8"))
        metrics.write_text(json.dumps({**stored, "lines_mean": 4.0}), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.verified()
        self.assertIn("the kept number ['lines_mean']", str(cm.exception))
        self.assertEqual(self.handed, [{"counts", "ids"}])


if __name__ == "__main__":
    unittest.main()
