"""A protocol is a regular file, in the tree and in the index.

The stop read a symbolic link's target in the tree and the commit read
the link's stored name in the index, so the two judged different text
(`report_hold.repo_sources` followed it, `repo.state_text` does not).
labkit refuses a protocol link with a sentence naming it, valid or
broken, in each state by that state alone; a regular protocol reads in
both. Audit 2026-10-27 (second), left open, settled the same day.

    .venv/bin/python -m pytest tests/test_protocol_links.py
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labkit.formats import repo  # noqa: E402
from labkit.checks.protocol_report import check_files, template_lines  # noqa: E402
from labkit.checks.protocol_report import find_template  # noqa: E402
from labkit.gates import report_check, report_hold  # noqa: E402
from protocol_fixture import head  # noqa: E402

REFUSED = "a protocol must be a regular file, not a symbolic link"


class ProtocolLinks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.git("init", "-q")
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        self.protocol = self.area / "PROTOCOL-x.md"
        self.target = self.root / "notes" / "PROTOCOL-real.md"
        self.target.parent.mkdir()
        self.target.write_text(head(repeat_cost="low"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True)

    def regular(self) -> None:
        if self.protocol.is_symlink():
            self.protocol.unlink()
        self.protocol.write_text(head(repeat_cost="low"))

    def link(self, target: Path) -> None:
        if self.protocol.exists() or self.protocol.is_symlink():
            self.protocol.unlink()
        self.protocol.symlink_to(target)

    def held(self, *, staged: bool) -> tuple[bool, int, str]:
        """(refused by repo_sources, hold_declared's exit, its output)."""
        sources = report_hold.repo_sources(self.root, staged=staged)
        refused = REFUSED in sources.unreadable.get(self.protocol, "")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = report_check.hold_declared(self.protocol, self.root, staged=staged)
        return refused, rc, out.getvalue()

    def test_a_regular_protocol_reads_in_tree_and_index(self):
        self.regular()
        self.git("add", "-A")
        for staged in (False, True):
            with self.subTest(staged=staged):
                sources = report_hold.repo_sources(self.root, staged=staged)
                self.assertIn(self.protocol, sources.texts)
                self.assertNotIn(self.protocol, sources.unreadable)
                self.assertEqual(self.held(staged=staged)[1], 0)
        self.assertEqual(repo.the_protocol(self.area, None), self.protocol)

    def test_a_link_valid_or_broken_is_refused_in_tree_and_index(self):
        for target in (self.target, self.root / "missing.md"):
            self.link(target)
            self.git("add", "-A")
            for staged in (False, True):
                with self.subTest(target=target.name, staged=staged):
                    refused, rc, out = self.held(staged=staged)
                    self.assertTrue(refused)
                    self.assertEqual(rc, 2, out)
                    self.assertIn(REFUSED, out)
                    self.assertIn(str(self.protocol), out)
            with self.assertRaisesRegex(repo.ProtocolChoiceError, REFUSED):
                repo.the_protocol(self.area, None)
            with self.assertRaisesRegex(repo.ProtocolChoiceError, REFUSED):
                repo.the_protocol(self.area, self.protocol)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                tmpl = template_lines(find_template(None))
                self.assertTrue(check_files([self.protocol], tmpl))
            self.assertIn(REFUSED, out.getvalue())

    def test_an_unreadable_protocol_is_a_refusal_not_a_traceback(self):
        # the tree read caught OSError before it moved to repo.state_text
        # (audit 2026-10-27, third, K2)
        self.regular()
        self.protocol.chmod(0)
        try:
            _, rc, out = self.held(staged=False)
        finally:
            self.protocol.chmod(0o644)
        self.assertEqual(rc, 2, out)
        self.assertIn(str(self.protocol), out)

    def test_each_state_is_judged_by_itself(self):
        # a link staged, a regular file in the tree: the commit refuses
        self.link(self.target)
        self.git("add", "-A")
        self.regular()
        self.assertFalse(self.held(staged=False)[0])
        self.assertTrue(self.held(staged=True)[0])
        # a regular file staged, a link in the tree: the stop refuses
        self.git("add", "-A")
        self.link(self.target)
        self.assertTrue(self.held(staged=False)[0])
        self.assertFalse(self.held(staged=True)[0])


if __name__ == "__main__":
    unittest.main()
