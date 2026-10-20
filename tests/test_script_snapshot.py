"""`provenance.snapshot_script`: the copy in the run directory and the
`script_sha` in config.json describe the same bytes.

    .venv/bin/python -m pytest tests/test_script_snapshot.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.formats import scope_sha
from labkit.run import provenance


class SnapshotScript(unittest.TestCase):
    def setUp(self) -> None:
        d = Path(tempfile.mkdtemp())
        self.script = d / "01_measure.py"
        self.script.write_text("N = 1\n", encoding="utf-8")
        self.run_dir = d / "runs" / "r"
        self.run_dir.mkdir(parents=True)
        argv = mock.patch.object(sys, "argv", [str(self.script)])
        argv.start()
        self.addCleanup(argv.stop)

    def _copy(self) -> bytes:
        return (self.run_dir / "script-source.py").read_bytes()

    def test_the_hash_is_the_copys_even_when_the_script_changes_meanwhile(self) -> None:
        """An editor saving between the copy and a second read gave a record
        whose hash matched no stored script."""
        real_write = Path.write_bytes

        def write_then_edit(path: Path, data: bytes) -> int:
            n = real_write(path, data)
            self.script.write_text("N = 2\n", encoding="utf-8")
            return n

        with mock.patch.object(Path, "write_bytes", write_then_edit):
            sha = provenance.snapshot_script(self.run_dir)
        self.assertEqual(self._copy(), b"N = 1\n")
        self.assertEqual(sha, scope_sha.digest(self._copy()))

    def test_an_unchanged_script_records_its_own_hash(self) -> None:
        sha = provenance.snapshot_script(self.run_dir)
        self.assertEqual(sha, provenance.script_sha())
        self.assertEqual(sha, scope_sha.digest(self._copy()))


if __name__ == "__main__":
    unittest.main()
