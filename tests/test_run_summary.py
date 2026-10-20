"""runs.run_summary: what a run is, in one record (code-navigation round 11)."""

import json
import tempfile
import unittest
from pathlib import Path

from labkit.formats import runs


def _run(d: Path, name: str, **cfg: object) -> Path:
    run = d / "runs" / name
    run.mkdir(parents=True)
    base = {
        "schema_version": 3,
        "run_kind": "measurement",
        "experiment": "x",
        "script": "01_measure.py",
        "git": "abc1234",
    }
    (run / "config.json").write_text(json.dumps({**base, **cfg}))
    (run / "metrics.json").write_text("{}")
    (run / "completion.json").write_text("{}")
    return run


class Summary(unittest.TestCase):
    def test_a_plain_committed_run(self):
        with tempfile.TemporaryDirectory() as d:
            s = runs.run_summary(
                _run(Path(d), "r1", command=["python", "01_measure.py"])
            )
            self.assertEqual(
                (s.derived_from, s.models, s.git, s.uncommitted_bytes),
                (None, (), "abc1234", 0),
            )
            self.assertEqual(s.command, "python 01_measure.py")
            self.assertEqual(s.state, "completed")
            self.assertEqual(s.run_kind, "measurement")

    def test_the_listing_names_each_runs_kind(self):
        """Preparation, probe and measurement all read "fresh run of the
        script" (review 2026-10-20)."""
        import contextlib
        import io

        from labkit.run import runlog_command

        with tempfile.TemporaryDirectory() as d:
            for name, kind in (
                ("r1", "preparation"),
                ("r2", "probe"),
                ("r3", "measurement"),
            ):
                _run(Path(d), name, run_kind=kind)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                runlog_command._print_finished(Path(d))
        lines = [ln for ln in buf.getvalue().splitlines() if ln.startswith("  r")]
        self.assertEqual(
            [ln.split()[1] for ln in lines], ["preparation", "probe", "measurement"]
        )

    def test_a_derived_dirty_model_run(self):
        with tempfile.TemporaryDirectory() as d:
            run = _run(
                Path(d),
                "r2",
                derived_from="2026-10-01T10-00-00_aaaa",
                git="abc1234+dirty",
                models_resolved={"haiku": {"model": "x"}},
            )
            (run / "uncommitted.patch").write_text("diff --git a b\n")
            s = runs.run_summary(run)
            self.assertEqual(
                (s.derived_from, s.models), ("2026-10-01T10-00-00_aaaa", ("haiku",))
            )
            self.assertTrue(s.git.endswith("+dirty"))
            self.assertGreater(s.uncommitted_bytes, 0)
            self.assertIsNone(s.command)  # recorded only from labkit 0.69

    def test_a_folder_without_config_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                runs.run_summary(Path(d))


if __name__ == "__main__":
    unittest.main()
