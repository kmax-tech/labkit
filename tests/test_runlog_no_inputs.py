"""data=runlog.NO_INPUTS: the author's declaration that a run reads no
input file, recorded apart from a data= left out or empty; a reserved key
is no input name; the declaration's shape is held where it is read."""

import tempfile
import unittest
from pathlib import Path

from labkit.formats import runs
from labkit.formats.runs import ArtefactError
from labkit.run import provenance, runlog


class Declaration(unittest.TestCase):
    def test_the_declaration_reads_and_an_empty_table_is_none(self) -> None:
        declared = {runs.NO_INPUTS_KEY: runs.NO_INPUTS_DECLARED}
        self.assertTrue(runs.declares_no_inputs(declared, "config.json"))
        self.assertFalse(runs.declares_no_inputs({}, "config.json"))
        self.assertEqual(runs.data_entries(declared, "config.json"), [])

    def test_a_wrong_value_or_an_input_beside_it_is_refused(self) -> None:
        with self.assertRaisesRegex(ArtefactError, "not 'declared by the author"):
            runs.declares_no_inputs({runs.NO_INPUTS_KEY: True}, "config.json")
        beside = {
            runs.NO_INPUTS_KEY: runs.NO_INPUTS_DECLARED,
            "train": {"path": "a", "sha256": "x", "rows": 1},
        }
        with self.assertRaisesRegex(ArtefactError, "names inputs beside it"):
            runs.declares_no_inputs(beside, "config.json")

    def test_a_reserved_key_is_no_input_name(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.jsonl"
            f.write_text("{}\n", encoding="utf-8")
            for key in runs.RESERVED_DATA_KEYS:
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, "reserves"):
                        provenance.describe_data({key: str(f)}, Path(d))

    def test_the_sentinel_names_itself(self) -> None:
        self.assertEqual(repr(runlog.NO_INPUTS), "runlog.NO_INPUTS")
        self.assertIsInstance(runlog.NO_INPUTS, runlog.NoInputs)


if __name__ == "__main__":
    unittest.main()
