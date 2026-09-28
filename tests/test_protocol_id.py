"""Tests for the protocol id — identity a run can bind to (Standard 0.16).

Why this exists: nothing in a run said which protocol it belonged to, so in
a series area (`PROTOCOL-s1-*` ... `PROTOCOL-s13-*`) every automatic pairing
of protocol and run was a guess, and `code-check` silently checked s1 while
s13 was the protocol just built (2026-09-26). The id is what a run binds to;
the path only says where it was found.

The gates tested here: the field is due from 0.16 on, the value has one
shape, an id occurs once per repository, and an edit against HEAD is worth a
warning — never a proof, because after the commit the new id IS the state.
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import protocol_check  # noqa: E402

PILOT = """# Experiment protocol: x

- **Standard:** {standard}
{id_line}
- **Question / hypothesis:** does it hold?
- **Success / failure criterion:** [K1] p < .05
- **Stop rule:** [S1] abort above 20% errors
- **Type:** confirmatory
- **Terms:** none
- **Model I/O / prompt:** see below
- **Null condition:** [N1] shuffled labels
- **Raw output:** one real example
- **Frozen before run:** no

```text
prompt
```
"""


def _protocol(dirpath, pid: str | None = "p-0123456789abcdef",
              standard="0.16", name="PROTOCOL-x.md"):
    id_line = f"- **Protocol id:** {pid}" if pid is not None else ""
    p = Path(dirpath) / name
    p.write_text(PILOT.format(standard=standard, id_line=id_line),
                 encoding="utf-8")
    return p


def _check(paths):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = protocol_check.main([str(p) for p in paths])
    return code, buf.getvalue()


class TestFieldIsDueFrom016(unittest.TestCase):

    def test_missing_id_is_a_must_gap_at_016(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d, pid=None)
            _, out = _check([p])
        self.assertIn("MISSING (must): Protocol id", out)

    def test_prose_mentioning_protocol_id_does_not_satisfy_the_field(self):
        """'Protocol id will be added later' must not pass the must-check.

        Before the fix, the regex searched for 'protocol id' anywhere in the
        text; now the structural parser (protocol_id_of) must find a value.
        """
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "PROTOCOL-x.md"
            text = PILOT.format(standard="0.16", id_line="")
            # inject prose that mentions "protocol id" without being the field
            text = text.replace("does it hold?",
                                "does it hold? Protocol id will be added later")
            p.write_text(text, encoding="utf-8")
            _, out = _check([p])
        self.assertIn("MISSING (must): Protocol id", out)

    def test_older_standards_are_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d, pid=None, standard="0.15")
            _, out = _check([p])
        self.assertNotIn("Protocol id", out)

    def test_a_stamped_protocol_reports_nothing_about_its_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d)
            _, out = _check([p])
        self.assertNotIn("Protocol id", out)
        self.assertNotIn("MALFORMED", out)


class TestShape(unittest.TestCase):

    def test_wrong_shape_is_reported(self):
        for bad in ("p-NOTHEX", "p-0123", "0123456789abcdef",
                    "p-0123456789ABCDEF", "<protocol-id>"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                p = _protocol(d, pid=bad)
                code, out = _check([p])
                self.assertIn("MALFORMED protocol id", out)
                self.assertEqual(code, 1)

    def test_sixteen_lowercase_hex_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d, pid="p-9e2341c0390948dc")
            _, out = _check([p])
        self.assertNotIn("MALFORMED", out)


class TestUniqueness(unittest.TestCase):
    """The stamp alone cannot settle uniqueness: a protocol copied as the
    starting point for the next one carries the id along."""

    def test_the_same_id_twice_in_one_repo_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            _protocol(d, name="PROTOCOL-s1-a.md")
            second = _protocol(d, name="PROTOCOL-s2-b.md")
            code, out = _check([second])
        self.assertIn("DUPLICATE protocol id", out)
        self.assertIn("PROTOCOL-s1-a.md", out)
        self.assertEqual(code, 1)

    def test_distinct_ids_side_by_side_are_fine(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            _protocol(d, pid="p-1111111111111111", name="PROTOCOL-s1-a.md")
            second = _protocol(d, pid="p-2222222222222222",
                               name="PROTOCOL-s2-b.md")
            _, out = _check([second])
        self.assertNotIn("DUPLICATE", out)


class TestDivergenceAgainstHead(unittest.TestCase):
    """A warning, never a proof of immutability — after the next commit the
    changed id is the state. It catches the edit in the working tree."""

    def _repo(self, d):
        run = lambda *a: subprocess.run(a, cwd=d, capture_output=True)  # noqa: E731
        run("git", "init", "-q", ".")
        run("git", "config", "user.email", "t@t")
        run("git", "config", "user.name", "t")
        return run

    def test_changed_id_against_head_warns_without_failing(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(d)
            p = _protocol(d, pid="p-1111111111111111")
            run("git", "add", "-A")
            run("git", "commit", "-qm", "init")
            before, _ = _check([p])
            p.write_text(p.read_text(encoding="utf-8").replace(
                "p-1111111111111111", "p-2222222222222222"), encoding="utf-8")
            after, out = _check([p])
        self.assertIn("WARNING: protocol id changed against HEAD", out)
        self.assertIn("p-1111111111111111 -> p-2222222222222222", out)
        # the warning says something, it does not change the verdict
        self.assertEqual(after, before)

    def test_a_new_file_does_not_warn(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._repo(d)
            (Path(d) / "seed.txt").write_text("x", encoding="utf-8")
            run("git", "add", "-A")
            run("git", "commit", "-qm", "init")
            p = _protocol(d)
            _, out = _check([p])
        self.assertNotIn("WARNING: protocol id", out)

    def test_no_git_no_check(self):
        with tempfile.TemporaryDirectory() as d:
            p = _protocol(d)
            _, out = _check([p])
        self.assertNotIn("WARNING: protocol id", out)


if __name__ == "__main__":
    unittest.main()
