"""Declared binary artifacts keep byte provenance without weakening text datasets."""

from __future__ import annotations

import contextlib
import io
import json
import pickle
import tempfile
import unittest
from pathlib import Path

from labkit.run import provenance, runlog
from protocol_fixture import head


class BinaryInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.area = Path(self.tmp.name)
        self.weights = self.area / "weights.jsonl"
        self.weights.write_bytes(pickle.dumps({"weight": 2.0}))

    def test_binary_weights_are_hashed_without_text_decoding_or_id_checks(self):
        before = provenance.describe_data(
            {"train": provenance.BinaryInput(self.weights)}, self.area
        )
        self.assertIsNone(before["train"]["rows"])
        self.assertEqual(
            before["train"]["sha256"], provenance.source_digest(self.weights)[:16]
        )
        self.weights.write_bytes(pickle.dumps({"weight": 3.0}))
        after = provenance.describe_data(
            {"train": provenance.BinaryInput(self.weights)}, self.area
        )
        self.assertNotEqual(before["train"]["sha256"], after["train"]["sha256"])

    def test_invalid_utf8_as_an_ordinary_dataset_still_raises(self):
        with self.assertRaises(UnicodeDecodeError):
            provenance.describe_data({"train": self.weights}, self.area)

    def test_text_leakage_is_still_refused_beside_binary_weights(self):
        train, test = self.area / "train.jsonl", self.area / "test.jsonl"
        for dataset in (train, test):
            dataset.write_text('{"id":"same"}\n')
        with self.assertRaisesRegex(RuntimeError, "split leakage"):
            provenance.describe_data(
                {
                    "train": train,
                    "test": test,
                    "model": provenance.BinaryInput(self.weights),
                },
                self.area,
            )

    def test_real_measurement_records_binary_model_and_strict_prepared_dataset(self):
        protocol = self.area / "PROTOCOL-fixed.md"
        protocol.write_text(
            head(kind="compute", repeat_cost="low", promises=None)
            + "\n- **Question / hypothesis:** What does the fixed model return?\n"
        )
        prepared = self.area / "prepared.jsonl"
        prepared.write_text('{"id":"one","features":[1]}\n')
        with contextlib.redirect_stdout(io.StringIO()):
            with runlog.run(
                "fixed",
                config={},
                base_dir=self.area,
                data={
                    "prepared": prepared,
                    "model": provenance.BinaryInput(self.weights),
                },
                run_kind="measurement",
                protocol=protocol.name,
            ) as run:
                run.metrics(value=pickle.loads(self.weights.read_bytes())["weight"])
        config = json.loads((run.dir / "config.json").read_text())
        self.assertIsNone(config["data"]["model"]["rows"])
        self.assertEqual(
            config["data"]["model"]["sha256"],
            provenance.source_digest(self.weights)[:16],
        )
        self.assertEqual(config["data"]["prepared"]["rows"], 1)


if __name__ == "__main__":
    unittest.main()
