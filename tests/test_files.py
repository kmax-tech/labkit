"""files.write_atomic: a file is written whole or not at all."""

import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path

from labkit.formats import files


class WriteAtomic(unittest.TestCase):
    def test_the_file_is_whole_and_no_temp_file_stays(self):
        d = Path(tempfile.mkdtemp())
        target = d / "lease.json"
        files.write_atomic(target, "one")
        files.write_atomic(target, "two")
        self.assertEqual(target.read_text(), "two")
        self.assertEqual([p.name for p in d.iterdir()], ["lease.json"])

    def test_a_reader_never_sees_a_partial_file(self):
        d = Path(tempfile.mkdtemp())
        target = d / "state.json"
        body_a, body_b = "a" * 200_000, "b" * 200_000
        files.write_atomic(target, body_a)
        seen: set[int] = set()
        stop = threading.Event()

        def read() -> None:
            while not stop.is_set():
                seen.add(len(target.read_text()))

        t = threading.Thread(target=read)
        t.start()
        for _ in range(50):
            files.write_atomic(target, body_b)
            files.write_atomic(target, body_a)
        stop.set()
        t.join()
        self.assertEqual(seen, {200_000})
        self.assertFalse([p for p in d.iterdir() if f".tmp{os.getpid()}" in p.name])

    def test_a_failed_write_leaves_the_old_file_and_no_temp_file(self):
        """The staging file stayed behind a failed write (`.REPORT.md.tmp<pid>`
        beside the report, phase 1.4). The twin: a write that succeeds
        leaves no temp file either (above)."""
        d = Path(tempfile.mkdtemp())
        target = d / "PROTOCOL-x.md"
        files.write_atomic(target, "kept")

        def dies(tmp: Path) -> None:
            tmp.write_text("half", encoding="utf-8")
            raise OSError("No space left on device")

        with self.assertRaises(OSError):
            files._replace(target, dies)
        self.assertEqual(target.read_text(), "kept")
        self.assertEqual([p.name for p in d.iterdir()], ["PROTOCOL-x.md"])

    def test_an_existing_file_keeps_its_mode_and_a_read_only_one_is_refused(self):
        d = Path(tempfile.mkdtemp())
        script = d / "01_measure.py"
        files.write_atomic(script, "one")
        script.chmod(0o755)
        files.write_atomic(script, "two")
        self.assertEqual(stat.S_IMODE(script.stat().st_mode), 0o755)
        script.chmod(0o444)
        with self.assertRaises(PermissionError):
            files.write_atomic(script, "three")
        self.assertEqual(script.read_text(), "two")
        self.assertEqual([p.name for p in d.iterdir()], ["01_measure.py"])


if __name__ == "__main__":
    unittest.main()
