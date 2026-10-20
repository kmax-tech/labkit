"""Explicit run purposes: probes inspect an instrument, measurements can be reported."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.formats import runs
from labkit.run import runlog
from protocol_fixture import head


class RunKind(unittest.TestCase):
    def test_only_the_named_kinds_are_accepted(self):
        for kind in ("preparation", "probe", "measurement"):
            self.assertEqual(runs.parse_run_kind(kind), kind)
        for value in (None, True, False, 1, "full", "", [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "run_kind"):
                    runs.parse_run_kind(value)

    def test_invalid_api_kind_leaves_no_run_directory(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            with self.assertRaisesRegex(ValueError, "run_kind"):
                runlog.Run("x", {}, area, run_kind="other")  # type: ignore[arg-type]
            self.assertFalse((area / "runs").exists())

    def test_the_removed_duration_argument_is_not_a_compatibility_path(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            with self.assertRaisesRegex(TypeError, "long"):
                runlog.Run("x", {}, area, long=True)  # type: ignore[call-arg]
            self.assertFalse((area / "runs").exists())

    def test_seconds_refuses_probe_even_with_an_acknowledgement(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(
                head(cost="seconds", promises=None)
                + "\n- **Question / hypothesis:** how many?\n",
                encoding="utf-8",
            )
            with mock.patch.dict("os.environ", {"LABKIT_UNFROZEN": "1"}):
                with self.assertRaisesRegex(SystemExit, "no separate probe stage"):
                    runlog.Run("x", {}, area, run_kind="probe")
            self.assertFalse((area / "runs").exists())
            with contextlib.redirect_stdout(io.StringIO()):
                with runlog.run("x", {}, area, run_kind="measurement") as run:
                    run.metrics(count=1)
            cfg = runs.read_run_config(run.dir)
            self.assertIsNotNone(cfg)
            assert cfg is not None
            self.assertEqual(cfg.schema_version, 3)
            self.assertEqual(cfg.run_kind, "measurement")
            self.assertNotIn("long", cfg.as_record())
            self.assertEqual(runs.unreportable(cfg), [])

    def test_preparation_at_seconds_preserves_provenance_but_cannot_be_reported(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "PROTOCOL-x.md").write_text(
                head(cost="seconds", promises=None), encoding="utf-8"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                with runlog.run("prepare", {}, area, run_kind="preparation") as run:
                    run.metrics(n_items=12)
            cfg = runs.read_run_config(run.dir)
            assert cfg is not None
            self.assertEqual(cfg.run_kind, "preparation")
            self.assertIn("not a measurement", runs.unreportable(cfg)[0])

    def test_current_records_require_a_valid_kind_and_reject_the_old_schema(self):
        for kind in (None, "other", True, "preparation", "probe", "measurement"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                area = Path(d)
                record: dict[str, object] = {"schema_version": 3}
                if kind is not None:
                    record["run_kind"] = kind
                (area / "config.json").write_text(json.dumps(record), encoding="utf-8")
                if kind in ("preparation", "probe", "measurement"):
                    self.assertIsNotNone(runs.read_run_config(area))
                else:
                    with self.assertRaisesRegex(runs.RunConfigError, "run_kind"):
                        runs.read_run_config(area)
        with tempfile.TemporaryDirectory() as d:
            area = Path(d)
            (area / "config.json").write_text(
                json.dumps({"schema_version": 2, "long": True}), encoding="utf-8"
            )
            with self.assertRaisesRegex(runs.RunConfigError, "0.99.0"):
                runs.read_run_config(area)
