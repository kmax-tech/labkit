"""The stop hook and the pre-commit hold an area the session touched to its
audit records: a BLOCKER nobody decided sends the agent back, and refuses
the commit (`claude-hook undecided`).

Third haiku round on labkit 0.99.0 (labkit-paper area 09, t5): the agent
ran the preflight audit, read its four BLOCKERs, left every finding `open`,
measured with long=False and reported. report-check would have refused the
number, but no gate the agent has to call is a gate; the stop and the
commit are the two it cannot choose. Twins: a decided BLOCKER, an open
WARNING, an area the session did not touch — all silent.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import claude_hooks, findings  # noqa: E402
from protocol_fixture import head  # noqa: E402
from test_claude_hooks import _git, _run  # noqa: E402

BLOCKER = ("BLOCKER", "BLOCKER · scripts/01_measure.py:3 · the target leaks")
WARNING = ("WARNING", "WARNING · scripts/01_measure.py:9 · the seed is not recorded")


class Undecided(unittest.TestCase):
    def setUp(self):
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.area = self.root / "experiments" / "01-x"
        self.other = self.root / "experiments" / "02-y"
        for area in (self.area, self.other):
            (area / "scripts").mkdir(parents=True)
            (area / "PROTOCOL-x.md").write_text(head(), encoding="utf-8")
            (area / "scripts" / "01_measure.py").write_text("x = 1\n")
        _git(self.root, "init", "-q", ".")
        _git(self.root, "config", "user.email", "t@t")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "init")

    def _record(self, area: Path, rows) -> Path:
        return findings.write(
            area,
            "preflight",
            "opus",
            "0123456789ab",
            "b10c0000000a",
            (
                sum(g == "BLOCKER" for g, _ in rows),
                sum(g == "WARNING" for g, _ in rows),
                0,
            ),
            rows,
        )

    def _touch(self, area: Path) -> Path:
        p = area / "scripts" / "01_measure.py"
        p.write_text("x = 2\n", encoding="utf-8")
        return p

    def _stop(self, active: bool = False) -> tuple[int, str, str]:
        return _run(
            claude_hooks.stop,
            {"session_id": "s1", "cwd": str(self.root), "stop_hook_active": active},
        )

    def test_an_open_blocker_in_a_touched_area_sends_the_agent_back(self):
        path = self._record(self.area, [BLOCKER])  # audits/ is itself a change
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("BLOCKER(s) nobody decided", err)
        self.assertIn(
            f"experiments/01-x: {path.name}: BLOCKER · scripts/01_measure.py:3", err
        )
        self.assertIn("cannot be reported", err)

    def test_the_committed_record_blocks_once_the_area_is_touched_again(self):
        self._record(self.area, [BLOCKER])
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "audit")
        rc, _, _ = self._stop()
        self.assertEqual(rc, 0)  # nothing of this area changed in the session
        self._touch(self.area)
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("the target leaks", err)

    def test_a_decided_blocker_and_an_open_warning_let_it_stop(self):
        path = self._record(self.area, [BLOCKER, WARNING])
        text = path.read_text(encoding="utf-8")
        first, rest = text.split("[[finding]]", 1)
        blocker_tbl, warning_tbl = rest.split("[[finding]]")
        decided = blocker_tbl.replace('status = "open"', 'status = "accepted"').replace(
            'reason = ""', 'reason = "the leak is the measured quantity"'
        )
        path.write_text(first + "[[finding]]" + decided + "[[finding]]" + warning_tbl)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_an_untouched_area_does_not_block(self):
        self._record(self.other, [BLOCKER])
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "audit elsewhere")
        self._touch(self.area)
        rc, _, err = self._stop()
        self.assertEqual(rc, 0, err)

    def test_sent_back_once_already_may_stop(self):
        self._record(self.area, [BLOCKER])
        rc, _, _ = self._stop(active=True)
        self.assertEqual(rc, 0)

    def test_an_unreadable_record_is_loud(self):
        (self.area / findings.DIR).mkdir()
        (self.area / findings.DIR / "x-preflight.toml").write_text("no = [toml\n")
        rc, _, err = self._stop()
        self.assertEqual(rc, 2)
        self.assertIn("not TOML", err)

    def test_the_pre_commit_command_holds_the_staged_paths(self):
        path = self._record(self.area, [BLOCKER])
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = claude_hooks.main(
                    ["undecided", "experiments/01-x/scripts/01_measure.py"]
                )
            self.assertEqual(rc, 1)
            self.assertIn(path.name, out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    claude_hooks.main(
                        ["undecided", "experiments/02-y/scripts/01_measure.py"]
                    ),
                    0,
                )
                self.assertEqual(claude_hooks.main(["undecided", "README.md"]), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(claude_hooks.main(["undecided"]), 2)
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_the_stamped_pre_commit_runs_it(self):
        from labkit import install_hooks

        self.assertIn("claude-hook undecided $staged", install_hooks.pre_commit())


if __name__ == "__main__":
    unittest.main()
