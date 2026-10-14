"""runs.read_metrics: the one loader for a run's metrics.json (review 2026-10-08)."""

import json
import tempfile
import unittest
from pathlib import Path

from labkit import finalize, promises, runs


class ReadMetrics(unittest.TestCase):
    def _file(self, d: str, content: str) -> Path:
        f = Path(d) / "metrics.json"
        f.write_text(content, encoding="utf-8")
        return f

    def test_an_object_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            got = runs.read_metrics(self._file(d, '{"c1_pass": true}'))
            self.assertEqual(promises.reported_ids(got), {"c1"})

    def test_a_list_a_string_or_null_is_refused(self):
        for content in ('["c1_pass"]', '"c1_pass"', "null"):
            with tempfile.TemporaryDirectory() as d, self.subTest(content=content):
                with self.assertRaises(runs.MetricsError):
                    runs.read_metrics(self._file(d, content))

    def test_broken_json_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(runs.MetricsError):
                runs.read_metrics(self._file(d, "{"))


class CriterionNIsNoBool(unittest.TestCase):
    def test_true_is_not_a_count(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "metrics.json").write_text(json.dumps({"c1_n": True}))
            self.assertEqual(finalize.criterion_n_input_mismatches(run), [])

    def test_an_int_is_still_held_to_the_counts(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "metrics.json").write_text(json.dumps({"c1_n": 12}))
            self.assertTrue(finalize.criterion_n_input_mismatches(run))


class ReadOutputsAndCompletion(unittest.TestCase):
    def test_outputs_as_runlog_writes_them_are_read(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "outputs.json").write_text(
                json.dumps(
                    [
                        {"path": "/x/out.jsonl", "sha256": "ab12", "lines": 12},
                        {
                            "path": "/x/gone.txt",
                            "sha256": None,
                            "lines": None,
                            "note": "absent",
                        },
                    ]
                )
            )
            got = runs.read_outputs(run)
            assert got is not None
            self.assertEqual(
                [(o.path.name, o.lines) for o in got],
                [("out.jsonl", 12), ("gone.txt", None)],
            )

    def test_no_outputs_file_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(runs.read_outputs(Path(d)))

    def test_outputs_of_the_wrong_shape_are_refused(self):
        for content in (
            '{"path": "x"}',
            '[{"lines": 3}]',
            '[{"path": "x", "lines": true}]',
            '[{"path": "x", "rows_from": {"r": "not-an-int"}}]',
            '[{"path": "x", "rows_from": {"r": 2.5}}]',
            '[{"path": "x", "rows_from": {"r": true}}]',
            "[1]",
        ):
            with tempfile.TemporaryDirectory() as d, self.subTest(content=content):
                (Path(d) / "outputs.json").write_text(content)
                with self.assertRaises(runs.ArtefactError):
                    runs.read_outputs(Path(d))

    def test_completion_must_be_an_object(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "completion.json").write_text('{"git": "abc"}')
            self.assertEqual(runs.read_completion(Path(d))["git"], "abc")
            (Path(d) / "completion.json").write_text('["abc"]')
            with self.assertRaises(runs.ArtefactError):
                runs.read_completion(Path(d))


if __name__ == "__main__":
    unittest.main()
