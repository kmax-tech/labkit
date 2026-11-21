"""`protocol_then.protocol_path_at`: in a commit, the protocol carrying an
id is found among the files a repo-wide scan reads, never in a copy."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from repo_fixture import git

from labkit.formats.protocol_then import protocol_path_at


def _protocol(pid: str, note: str) -> str:
    return f'# x\n\n```toml\n[protocol]\nid = "{pid}"\n```\n\n{note}\n'


class ProtocolPathAt(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.area = self.root / "experiments" / "01-x"
        self.area.mkdir(parents=True)
        git(self.root, "init", "-q")
        (self.area / "PROTOCOL-x.md").write_text(_protocol("p-1", "registered"))

    def commit(self) -> str:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "c")
        return git(self.root, "rev-parse", "HEAD")

    def test_a_copy_with_the_same_id_is_not_the_protocol(self) -> None:
        for copy in ("PROTOCOL-a.txt", "PROTOCOL-before.md.bak"):
            (self.area / copy).write_text(_protocol("p-1", "an old copy"))
        (self.area / "runs" / "r1").mkdir(parents=True)
        (self.area / "runs" / "r1" / "PROTOCOL-a.md").write_text(
            _protocol("p-1", "a run's copy")
        )
        found = protocol_path_at(self.root, self.commit(), "p-1")
        self.assertEqual(found, self.area / "PROTOCOL-x.md")

    def test_the_twin_a_protocol_under_another_name_is_found(self) -> None:
        (self.area / "PROTOCOL-x.md").rename(self.area / "PROTOCOL-a.md")
        found = protocol_path_at(self.root, self.commit(), "p-1")
        self.assertEqual(found, self.area / "PROTOCOL-a.md")


if __name__ == "__main__":
    unittest.main()
