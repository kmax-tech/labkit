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
        """A failed write leaves no staging file (`.REPORT.md.tmp<pid>`
        beside the report). The twin: a write that succeeds leaves no temp
        file either (above)."""
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


class ExclusiveLock(unittest.TestCase):
    """`exclusive_lock` holds the flock for its block and gives it back."""

    def test_held_inside_the_block_and_free_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".lock"
            with files.exclusive_lock(path):
                # a second open file description cannot take the lock
                self.assertTrue(files.lock_held(path))
            self.assertFalse(files.lock_held(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_released_when_the_block_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".lock"
            with self.assertRaises(RuntimeError):
                with files.exclusive_lock(path):
                    raise RuntimeError("boom")
            self.assertFalse(files.lock_held(path))

    def test_a_second_holder_waits_until_the_first_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".lock"
            order: list[str] = []
            entered = threading.Event()

            def second() -> None:
                entered.set()
                with files.exclusive_lock(path):
                    order.append("second")

            with files.exclusive_lock(path):
                t = threading.Thread(target=second)
                t.start()
                entered.wait()
                t.join(timeout=0.2)
                self.assertTrue(t.is_alive())
                order.append("first")
            t.join(timeout=5)
            self.assertFalse(t.is_alive())
            self.assertEqual(order, ["first", "second"])
