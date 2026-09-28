"""Tests for preflight — the read-only gate before freezing.

The individual checks (protocol-check, code-check, scope-sha) have their
own tests. These tests verify that preflight SEQUENCES them correctly and
that the exit code reflects the worst finding.
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import preflight  # noqa: E402

CLEAN_PROTOCOL = """\
# Experiment protocol: x

- **Standard:** 0.16
- **Protocol id:** p-0123456789abcdef
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [K1] p < .05
- **Stop rule:** [S1] abort above 20% errors
- **Type:** confirmatory
- **Terms of art:** none
- **Model I/O / prompt:** see below
- **Null condition:** [N1] shuffled labels
- **Raw output:** one real example
- **Exclusions / filters:** none
- **Frozen before run:** no

```text
prompt
```
"""


def _area(d, protocol_text=CLEAN_PROTOCOL, scripts=True, git=True):
    area = Path(d)
    p = area / "PROTOCOL-x.md"
    p.write_text(protocol_text, encoding="utf-8")
    if scripts:
        (area / "scripts").mkdir(exist_ok=True)
        (area / "scripts" / "01_measure.py").write_text(
            'metrics = {"k1_pass": True, "s1_hit": 0, "n1_pass": True}\n',
            encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", "."], cwd=d, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=d,
                       capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=d,
                       capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=d,
                       capture_output=True)
    return area, p


def _run_preflight(area, protocol=None):
    argv = [str(area)]
    if protocol:
        argv += ["--protocol", str(protocol)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = preflight.main(argv)
    return code, buf.getvalue()


class TestPreflight(unittest.TestCase):

    def test_clean_area_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            code, out = _run_preflight(area)
        self.assertEqual(code, 0, out)
        self.assertIn("0 blocker", out)

    def test_missing_protocol_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = _run_preflight(Path(d))
        self.assertEqual(code, 2, out)
        self.assertIn("no PROTOCOL", out)

    def test_multiple_protocols_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, git=False)
            (area / "PROTOCOL-y.md").write_text(
                CLEAN_PROTOCOL.replace("p-0123456789abcdef",
                                       "p-fedcba9876543210"),
                encoding="utf-8")
            code, out = _run_preflight(area)
        self.assertEqual(code, 2, out)
        self.assertIn("2 protocols", out)

    def test_explicit_protocol_flag(self):
        with tempfile.TemporaryDirectory() as d:
            area, p = _area(d)
            code, out = _run_preflight(area, protocol=p)
        self.assertEqual(code, 0, out)

    def test_protocol_blocker_makes_exit_one(self):
        broken = CLEAN_PROTOCOL.replace(
            "- **Protocol id:** p-0123456789abcdef", "")
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d, protocol_text=broken)
            code, out = _run_preflight(area)
        self.assertEqual(code, 1, out)
        self.assertIn("MISSING (must): Protocol id", out)
        self.assertIn("blocker", out)

    def test_dirty_tree_is_a_warning_not_a_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            area, _ = _area(d)
            (area / "new_file.txt").write_text("x", encoding="utf-8")
            code, out = _run_preflight(area)
        self.assertEqual(code, 0, out)
        self.assertIn("uncommitted changes", out)
        self.assertIn("warning", out.lower())

    def test_help_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = preflight.main(["--help"])
        self.assertEqual(code, 0)

    def test_no_args_exits_two(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = preflight.main([])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
