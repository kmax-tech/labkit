"""A directory as a run's data source is frozen like a file, so `finalize`
does not refuse a run that reads one as "source not frozen"."""

import tempfile
import unittest
from pathlib import Path

from labkit.run import provenance


class DirectorySource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / "cases"
        for case, docs in (("a", 2), ("b", 1)):
            (self.src / case).mkdir(parents=True)
            for i in range(docs):
                (self.src / case / f"d{i}").write_text(f"{case}{i}")

    def describe(self) -> dict:
        return provenance.describe_data({"source": self.src}, Path(self.tmp.name))[
            "source"
        ]

    def test_rows_count_visible_files_and_hidden_ones_do_not_count(self):
        (self.src / "a" / ".DS_Store").write_text("x")
        (self.src / ".git").mkdir()
        (self.src / ".git" / "HEAD").write_text("x")
        self.assertEqual(self.describe()["rows"], 3)

    def test_digest_moves_with_content_membership_and_names(self):
        base = self.describe()["sha256"]
        (self.src / "a" / "d0").write_text("changed")
        edited = self.describe()["sha256"]
        self.assertNotEqual(base, edited)
        (self.src / "a" / "d0").rename(self.src / "a" / "d9")
        renamed = self.describe()["sha256"]
        self.assertNotEqual(edited, renamed)
        (self.src / "b" / "d5").write_text("new")
        self.assertNotEqual(renamed, self.describe()["sha256"])

    def test_a_hidden_file_does_not_move_the_digest(self):
        base = self.describe()["sha256"]
        (self.src / "a" / ".DS_Store").write_text("x")
        self.assertEqual(base, self.describe()["sha256"])

    def test_bytecode_does_not_move_the_digest_nor_count(self):
        """A run importing modules shipped in its source writes `.pyc` there;
        counted, its digest would never match the registered one. The twin: a
        real `.py` file still counts."""
        base = self.describe()
        cache = self.src / "a" / "__pycache__"
        cache.mkdir()
        (cache / "rule.cpython-312.pyc").write_bytes(b"\x00bytecode")
        self.assertEqual(self.describe(), base)
        (self.src / "a" / "rule.py").write_text("X = 1\n")
        moved = self.describe()
        self.assertNotEqual(moved["sha256"], base["sha256"])
        self.assertEqual(moved["rows"], base["rows"] + 1)


if __name__ == "__main__":
    unittest.main()
