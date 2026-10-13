"""console.run: a reader that closes the pipe is exit 0 and no traceback."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClosedPipe(unittest.TestCase):
    def test_a_reader_closing_the_pipe_is_not_a_crash(self):
        # 400 kB past the pipe buffer, the reader takes one byte and leaves
        prog = (
            "from labkit import console\n"
            "console.exit_with(lambda argv: (print('x' * 400_000), 0)[1])\n"
        )
        writer = subprocess.Popen(
            [sys.executable, "-c", prog],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert writer.stdout is not None
        writer.stdout.read(1)
        writer.stdout.close()
        _, err = writer.communicate(timeout=30)
        self.assertEqual(writer.returncode, 0, err.decode())
        self.assertNotIn(b"Traceback", err)
        self.assertNotIn(b"BrokenPipe", err)

    def test_the_exit_code_is_main_s(self):
        prog = "from labkit import console\nconsole.exit_with(lambda argv: 3)\n"
        self.assertEqual(
            subprocess.run([sys.executable, "-c", prog], cwd=ROOT).returncode, 3
        )


if __name__ == "__main__":
    unittest.main()
