"""Tests for the `runlog` console command (labkit.run.runlog:cli).

Why this is tested: the working standard's "look, don't ask" rule hands users
this exact command. Its predecessor — `python lib/runlog.py <area>` against a
shim — printed nothing and exited 0 (found 2026-09-06): the shim replaces
sys.modules, so the package's __main__ block never ran. A listing command
whose silent failure is indistinguishable from "no open runs" must prove that
it prints.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the package under test

from protocol_fixture import run_record  # noqa: E402
from labkit.run import runlog_command  # noqa: E402


class TestCli(unittest.TestCase):
    def _run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = runlog_command.main(argv)
        return code, buf.getvalue()

    def test_empty_area_says_so_instead_of_staying_silent(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._run_main([d])
            self.assertEqual(code, 0)
            self.assertIn("no open runs", out)

    def test_a_missing_area_is_refused_not_read_as_idle(self):
        """`runlog <typo>` said "no open runs" with exit 0, and `--wait`
        reported the misspelt area as finished (audit 2026-10-15)."""
        with tempfile.TemporaryDirectory() as d:
            missing = str(Path(d) / "does-not-exist")
            for argv in ([missing], [missing, "--wait"], [missing, "--follow"]):
                with self.subTest(argv=argv):
                    code, out = self._run_main(argv)
                    self.assertEqual(code, 2)
                    self.assertIn("no such area", out)
                    self.assertNotIn("no open runs", out)

    def test_an_open_run_is_listed_with_id_and_state(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "20260906-120000-probe"
            run_dir.mkdir(parents=True)
            (run_dir / "config.json").write_text(
                json.dumps(
                    run_record(
                        {
                            "schema_version": 4,
                            "run_kind": "measurement",
                            "pid": 999_999,
                            "script": "01_measure.py",
                            "config": {"items": "data/prepared/x.jsonl"},
                        }
                    )
                ),
                encoding="utf-8",
            )
            code, out = self._run_main([d])
            self.assertEqual(code, 0)
            self.assertIn("20260906-120000-probe", out)
            self.assertIn("01_measure.py", out)

    def test_help_prints_usage_instead_of_reading_it_as_an_area(self):
        """`runlog --help` once answered "--help: no open runs" — a flag read
        as a directory name. Whoever looks for the flags must find usage."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                runlog_command.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage: runlog", buf.getvalue())

    def test_a_finished_run_is_listed_as_finished_not_open(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "runs" / "20260906-120000-done"
            run_dir.mkdir(parents=True)
            (run_dir / "config.json").write_text(
                json.dumps(run_record()), encoding="utf-8"
            )
            (run_dir / "metrics.json").write_text("{}", encoding="utf-8")
            (run_dir / "completion.json").write_text("{}", encoding="utf-8")
            code, out = self._run_main([d])
            self.assertEqual(code, 0)
            open_part, _, finished_part = out.partition("finished runs")
            self.assertNotIn("20260906-120000-done", open_part)
            self.assertIn("20260906-120000-done", finished_part)
            self.assertIn("not recorded", finished_part)


if __name__ == "__main__":
    unittest.main()
