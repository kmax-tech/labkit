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


class TestOneStampEverywhere(unittest.TestCase):
    """Review 2026-10-07: scope-sha, preflight and labkit-audit gave four
    different stamps for one unchanged area — the path spelling, the working
    directory and whether lib/ and the pin counted all differed. One home
    now: `area_stamp`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "lab"
        (self.repo / "tests").mkdir(parents=True)          # layout root without git
        self.area = self.repo / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "01_measure.py").write_text("import anchors\nx = 1\n")
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "anchors.py").write_text("A = 1\n")
        (self.repo / "requirements.txt").write_text("labkit @ git+file:///l@v0.48.1\n")

    def test_spelling_and_cwd_do_not_move_the_stamp(self):
        import os
        from labkit import scope_sha as packaged
        absolute = packaged.area_stamp(self.area)[0]
        cwd = os.getcwd()
        try:
            os.chdir(self.repo)
            relative = packaged.area_stamp(Path("experiments/01-x"))[0]
            os.chdir(self.area)
            here = packaged.area_stamp(Path("."))[0]
        finally:
            os.chdir(cwd)
        self.assertEqual(absolute, relative)
        self.assertEqual(absolute, here)

    def test_imported_lib_and_pin_are_in_scope(self):
        from labkit import scope_sha as packaged
        _, files, pin = packaged.area_stamp(self.area)
        self.assertIn("anchors.py", [f.name for f in files])
        self.assertIsNotNone(pin)
        before = packaged.area_stamp(self.area)[0]
        (self.repo / "lib" / "anchors.py").write_text("A = 2\n")
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_audit_preflight_and_cli_agree(self):
        from labkit import audit, preflight
        from labkit import scope_sha as packaged
        sha = packaged.area_stamp(self.area)[0]
        self.assertIn(f"scope sha {sha}", audit.stamp_facts(self.area, (0, 0, 0)))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packaged.main(["--area", str(self.area)])
        self.assertIn(f"scope sha {sha}", buf.getvalue())
        from protocol_fixture import head
        (self.area / "PROTOCOL-x.md").write_text("# x\n" + head())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            preflight.run(self.area)
        self.assertIn(f"  {sha}", buf.getvalue())
