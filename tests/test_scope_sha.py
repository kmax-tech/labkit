"""Tests for scope-sha — the audit stamp of Arbeitsstandard §2.A12 / §2.D11.

Occasion (2026-09-08): the shell one-liner this command replaces produced a
stable-looking stamp that covered no file CONTENT on macOS (BSD xargs has no
`-a`; zsh's noclobber refused the `>` building the list). A stamp that stays
put while an anchor file changes is worse than no stamp — so the properties
that make it a stamp get tested: order independence, content sensitivity,
membership sensitivity, and a hard failure on a missing file.
"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scope_sha", REPO / "labkit" / "scope_sha.py")
assert spec is not None and spec.loader is not None
scope_sha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope_sha)


class TestScopeSha(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.area = Path(self.tmp.name) / "65-area"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "analysis").mkdir()
        (self.area / "scripts" / "01_measure.py").write_text("x = 1\n")
        (self.area / "analysis" / "note.py").write_text("y = 2\n")
        self.lib = Path(self.tmp.name) / "lib"
        self.lib.mkdir()
        self.anchor = self.lib / "bt.py"
        self.anchor.write_text("ANCHORS = [-3.4]\n")
        (Path(self.tmp.name) / "requirements.lock").write_text(
            "numpy==2.0.0\nlabkit @ git+file:///l@abc123\n")
        self.addCleanup(self.tmp.cleanup)

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = scope_sha.main(argv)
        return rc, buf.getvalue()

    def _sha(self, argv):
        rc, out = self._run(argv)
        self.assertEqual(rc, 0, out)
        line = [ln for ln in out.splitlines() if ln.startswith("scope sha ")]
        self.assertEqual(len(line), 1, out)
        return line[0].split()[-1]

    def test_same_input_same_stamp(self):
        a = self._sha(["--area", str(self.area), str(self.anchor)])
        b = self._sha(["--area", str(self.area), str(self.anchor)])
        self.assertEqual(a, b)
        self.assertEqual(len(a), scope_sha.DIGEST_CHARS)

    def test_content_change_moves_the_stamp(self):
        """The failure of the shell version: an edited anchor left it untouched."""
        before = self._sha(["--area", str(self.area), str(self.anchor)])
        self.anchor.write_text("ANCHORS = [-3.9]\n")
        self.assertNotEqual(before, self._sha(["--area", str(self.area), str(self.anchor)]))

    def test_extra_file_moves_the_stamp(self):
        before = self._sha(["--area", str(self.area)])
        self.assertNotEqual(before, self._sha(["--area", str(self.area), str(self.anchor)]))

    def test_argument_order_does_not_matter(self):
        second = self.lib / "stats.py"
        second.write_text("def auc(): pass\n")
        a = self._sha(["--area", str(self.area), str(self.anchor), str(second)])
        b = self._sha(["--area", str(self.area), str(second), str(self.anchor)])
        self.assertEqual(a, b)

    def test_duplicate_naming_does_not_matter(self):
        a = self._sha(["--area", str(self.area), str(self.anchor)])
        b = self._sha(["--area", str(self.area), str(self.anchor), str(self.anchor)])
        self.assertEqual(a, b)

    def test_missing_file_fails_loudly(self):
        rc, out = self._run(["--area", str(self.area), str(self.lib / "gone.py")])
        self.assertEqual(rc, 2)
        self.assertIn("missing", out)

    def test_pin_is_part_of_the_stamp(self):
        before = self._sha(["--area", str(self.area), str(self.anchor)])
        (Path(self.tmp.name) / "requirements.lock").write_text(
            "numpy==2.0.0\nlabkit @ git+file:///l@def456\n")
        self.assertNotEqual(before, self._sha(["--area", str(self.area), str(self.anchor)]))

    def test_pin_line_and_files_are_listed(self):
        rc, out = self._run(["--area", str(self.area), str(self.anchor)])
        self.assertEqual(rc, 0)
        self.assertIn("01_measure.py", out)
        self.assertIn("note.py", out)
        self.assertIn("bt.py", out)
        self.assertIn("labkit @", out)

    def test_no_pin_flag_drops_the_pin(self):
        with_pin = self._sha(["--area", str(self.area), str(self.anchor)])
        without = self._sha(["--area", str(self.area), "--no-pin", str(self.anchor)])
        self.assertNotEqual(with_pin, without)

    def test_empty_area_fails(self):
        empty = Path(self.tmp.name) / "nothing"
        empty.mkdir()
        rc, out = self._run(["--area", str(empty)])
        self.assertEqual(rc, 2)
        self.assertIn("no scope files", out)

    def test_help_exits_zero(self):
        rc, out = self._run(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("usage: scope-sha", out)
