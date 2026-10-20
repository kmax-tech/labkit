"""Tests for scope-sha — the audit stamp of lab standard LAB-015 Preflight audit before freezing / LAB-050 Analysis audit before reporting.

Occasion (2026-09-08): the shell one-liner this command replaces produced a
stable-looking stamp that covered no file CONTENT on macOS (BSD xargs has no
`-a`; zsh's noclobber refused the `>` building the list). A stamp that stays
put while an anchor file changes is worse than no stamp — so the properties
that make it a stamp get tested: order independence, content sensitivity,
membership sensitivity, and a hard failure on a missing file.
"""

import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.formats import scope_sha


class Digests(unittest.TestCase):
    """`file_digest` is sha256 of the bytes; `tree_digest` is the one stamp shape."""

    def test_file_digest_is_the_full_sha256(self):
        f = Path(tempfile.mkdtemp()) / "x.bin"
        f.write_bytes(b"abc" * 1_000_000)  # past one read chunk
        self.assertEqual(
            scope_sha.file_digest(f), hashlib.sha256(b"abc" * 1_000_000).hexdigest()
        )

    def test_tree_digest_moves_on_name_content_order_and_trailer(self):
        base = scope_sha.tree_digest([("a", b"1"), ("b", b"2")])
        self.assertEqual(len(base), scope_sha.DIGEST_CHARS)
        self.assertEqual(base, scope_sha.tree_digest([("a", b"1"), ("b", b"2")]))
        self.assertNotEqual(base, scope_sha.tree_digest([("a", b"1"), ("c", b"2")]))
        self.assertNotEqual(base, scope_sha.tree_digest([("a", b"1"), ("b", b"3")]))
        self.assertNotEqual(base, scope_sha.tree_digest([("b", b"2"), ("a", b"1")]))
        self.assertNotEqual(
            base, scope_sha.tree_digest([("a", b"1"), ("b", b"2")], trailer=["pin"])
        )
        self.assertEqual(len(scope_sha.tree_digest([("a", b"1")], chars=None)), 64)

    def test_tree_digest_is_the_spelled_out_shape(self):
        # the shape the stamps were recorded with: name, newline, hex of the
        # content's sha256, newline — a recorded stamp must stay recomputable
        h = hashlib.sha256()
        h.update(b"a\n" + hashlib.sha256(b"1").hexdigest().encode() + b"\n")
        h.update(b"labkit==1\n")
        self.assertEqual(
            scope_sha.tree_digest([("a", b"1")], trailer=["labkit==1"], chars=None),
            h.hexdigest(),
        )


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
            "numpy==2.0.0\nlabkit @ git+file:///l@abc123\n"
        )
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
        self.assertNotEqual(
            before, self._sha(["--area", str(self.area), str(self.anchor)])
        )

    def test_extra_file_moves_the_stamp(self):
        before = self._sha(["--area", str(self.area)])
        self.assertNotEqual(
            before, self._sha(["--area", str(self.area), str(self.anchor)])
        )

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
            "numpy==2.0.0\nlabkit @ git+file:///l@def456\n"
        )
        self.assertNotEqual(
            before, self._sha(["--area", str(self.area), str(self.anchor)])
        )

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
        (self.repo / "tests").mkdir(parents=True)  # layout root without git
        self.area = self.repo / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "01_measure.py").write_text("import anchors\nx = 1\n")
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "anchors.py").write_text("A = 1\n")
        (self.repo / "requirements.txt").write_text("labkit @ git+file:///l@v0.48.1\n")

    def test_spelling_and_cwd_do_not_move_the_stamp(self):
        import os
        from labkit.formats import scope_sha as packaged

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
        from labkit.formats import scope_sha as packaged

        _, files, pin = packaged.area_stamp(self.area)
        self.assertIn("anchors.py", [f.name for f in files])
        self.assertIsNotNone(pin)
        before = packaged.area_stamp(self.area)[0]
        (self.repo / "lib" / "anchors.py").write_text("A = 2\n")
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_audit_preflight_and_cli_agree(self):
        from labkit.gates import audit, preflight
        from labkit.formats import scope_sha as packaged

        sha, files, _ = packaged.area_stamp(self.area)
        self.assertIn(
            f"scope sha {sha}", audit.stamp_facts(audit.Stamp(sha, files), (0, 0, 0))
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            packaged.main(["--area", str(self.area)])
        self.assertIn(f"scope sha {sha}", buf.getvalue())
        from protocol_fixture import head

        (self.area / "PROTOCOL-x.md").write_text("# x\n" + head())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            preflight.preflight_area(self.area)
        self.assertIn(f"  {sha}", buf.getvalue())


class TestDeclaredScopeIsStamped(unittest.TestCase):
    """Review 2026-10-20: `labkit-audit` reads a promise's declared scope in
    full, the stamp covered it only when a script imported it — a declared
    helper audited, then edited, left the old audit valid."""

    def setUp(self):
        from protocol_fixture import head

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / "tests").mkdir()
        self.area = self.repo / "experiments" / "01"
        (self.area / "scripts").mkdir(parents=True)
        (self.area / "scripts" / "m.py").write_text("x = 1\n")
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "deep.py").write_text("D = 1\n")
        (self.area / "helper.py").write_text(
            "import deep\n\ndef score():\n    return 2\n"
        )
        block = (
            '[[promise]]\nid = "C1"\nkey = "c1_pass"\nsentence = "s"\n'
            'scope = ["helper.py:score"]\n'
        )
        (self.area / "PROTOCOL-x.md").write_text("# x\n" + head(promises=block))

    def test_the_audit_reads_nothing_the_stamp_does_not_bind(self):
        from labkit.gates import audit
        from labkit.formats import scope_sha as packaged

        read = {f.resolve() for f in audit.gather(self.area, None).code}
        stamped = {f.resolve() for f in packaged.area_stamp(self.area)[1]}
        self.assertIn((self.area / "helper.py").resolve(), read)
        self.assertLessEqual(read, stamped)

    def test_an_edit_to_a_declared_file_moves_the_stamp(self):
        from labkit.formats import scope_sha as packaged

        before = packaged.area_stamp(self.area)[0]
        (self.area / "helper.py").write_text(
            "import deep\n\ndef score():\n    return 999\n"
        )
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_an_import_of_a_declared_file_moves_the_stamp(self):
        from labkit.formats import scope_sha as packaged

        before = packaged.area_stamp(self.area)[0]
        (self.repo / "lib" / "deep.py").write_text("D = 2\n")
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_a_missing_declared_file_is_named(self):
        from labkit.formats import scope_sha as packaged

        (self.area / "helper.py").unlink()
        with self.assertRaises(FileNotFoundError) as cm:
            packaged.area_stamp(self.area)
        self.assertIn("helper.py", str(cm.exception))

    def test_an_area_without_promises_stamps_as_before(self):
        """The twin: no block, no declared files — the stamp is the scripts'."""
        from protocol_fixture import head
        from labkit.formats import scope_sha as packaged

        (self.area / "PROTOCOL-x.md").write_text("# x\n" + head())
        files = packaged.area_stamp(self.area)[1]
        self.assertEqual([f.name for f in files], ["m.py"])


class TestImportForms(unittest.TestCase):
    """Review 2026-10-07: `from lib import scoring` and `import lib.scoring`
    were read as a module `lib`; lib/scoring.py changed and the stamp stayed
    at the same value. Every allowed form, transitively."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / "tests").mkdir()
        self.area = self.repo / "experiments" / "01"
        (self.area / "scripts").mkdir(parents=True)
        lib = self.repo / "lib"
        lib.mkdir()
        (lib / "scoring.py").write_text("from . import helper\nimport anchors\n")
        (lib / "helper.py").write_text("H = 1\n")
        (lib / "anchors.py").write_text("A = 1\n")
        (lib / "pkg").mkdir()
        (lib / "pkg" / "__init__.py").write_text("")
        (lib / "pkg" / "core.py").write_text("C = 1\n")

    def names(self, source: str) -> list[str]:
        from labkit.formats import scope_sha as packaged

        (self.area / "scripts" / "m.py").write_text(source)
        return [
            f.relative_to(self.repo / "lib").as_posix()
            for f in packaged.imported_repo_helpers(self.area, self.repo)
        ]

    def test_every_allowed_form_reaches_the_module_and_its_imports(self):
        full = ["anchors.py", "helper.py", "scoring.py"]
        for source in (
            "from lib import scoring\n",
            "import lib.scoring\n",
            "from lib.scoring import X\n",
            "import scoring\n",
        ):
            self.assertEqual(self.names(source), full, source)

    def test_a_package_brings_what_python_loads(self):
        """`import pkg` runs pkg/__init__.py only; pkg/core.py comes with
        `import pkg.core` (2026-10-07: taking the whole package charged an
        area with a sibling module it never imported)."""
        self.assertEqual(self.names("import pkg\n"), ["pkg/__init__.py"])
        self.assertEqual(
            self.names("import pkg.core\n"), ["pkg/__init__.py", "pkg/core.py"]
        )
        self.assertEqual(
            self.names("from pkg import core\n"), ["pkg/__init__.py", "pkg/core.py"]
        )

    def test_an_import_through_the_root_brings_its_init(self):
        """`from lib import scoring` runs lib/__init__.py first; `import
        scoring` (lib/ on sys.path) does not."""
        from labkit.formats import scope_sha as packaged

        (self.repo / "lib" / "__init__.py").write_text("N = 2\n")
        self.assertIn("__init__.py", self.names("from lib import scoring\n"))
        self.assertIn("__init__.py", self.names("import lib\n"))
        self.assertNotIn("__init__.py", self.names("import scoring\n"))
        self.names("from lib import scoring\n")
        before = packaged.area_stamp(self.area)[0]
        (self.repo / "lib" / "__init__.py").write_text("N = 300\n")
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_a_sibling_module_is_not_charged(self):
        (self.repo / "lib" / "pkg" / "other.py").write_text("O = 1\n")
        self.assertNotIn("pkg/other.py", self.names("from pkg.core import C\n"))

    def test_src_is_a_root_as_lib_is(self):
        """uniagent computes every registered key in src/measure: with lib/
        alone neither the stamp nor the key search saw it (2026-10-07)."""
        from labkit.formats import scope_sha as packaged

        src = self.repo / "src" / "measure"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "comparison.py").write_text("K = 1\n")
        (src / "positions.py").write_text("P = 1\n")
        (self.area / "scripts" / "m.py").write_text("from measure import comparison\n")
        got = [
            f.relative_to(self.repo).as_posix()
            for f in packaged.imported_repo_helpers(self.area, self.repo)
        ]
        self.assertEqual(got, ["src/measure/__init__.py", "src/measure/comparison.py"])

    def test_a_stdlib_import_is_not_lib(self):
        self.assertEqual(self.names("import json\n"), [])

    def test_a_change_two_imports_deep_moves_the_stamp(self):
        from labkit.formats import scope_sha as packaged

        (self.area / "scripts" / "m.py").write_text("from lib import scoring\n")
        before = packaged.area_stamp(self.area)[0]
        (self.repo / "lib" / "helper.py").write_text("H = 2\n")
        self.assertNotEqual(before, packaged.area_stamp(self.area)[0])

    def test_unparsable_code_is_refused_not_guessed(self):
        from labkit.formats import scope_sha as packaged

        (self.area / "scripts" / "m.py").write_text("def broken(:\n")
        with self.assertRaises(ValueError):
            packaged.area_stamp(self.area)

    def test_the_auditors_scope_is_held_to_the_stamp(self):
        from labkit.gates import audit

        (self.area / "scripts" / "m.py").write_text("import scoring\n")
        report = (
            "verdict: 0 blockers, 0 warnings, 0 notes\nscope:\n"
            "experiments/01/scripts/m.py\nlib/scoring.py\nlib/other.py\n"
        )
        listed = audit.parse(report)["scope"]
        self.assertEqual(
            listed, ["experiments/01/scripts/m.py", "lib/scoring.py", "lib/other.py"]
        )
        gaps = audit.scope_mismatch(self.area, listed, audit.area_stamp(self.area)[1])
        self.assertIn(
            "the auditor read lib/other.py as part of the number, the stamp "
            "does not cover it",
            gaps,
        )
        self.assertTrue(
            any("lib/helper.py, the auditor did not list it" in g for g in gaps)
        )
