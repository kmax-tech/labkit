"""files.write_atomic: a file is written whole or not at all."""

import os
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


if __name__ == "__main__":
    unittest.main()
