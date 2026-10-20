"""Every fenced block in every Markdown file labkit stamps is closed.

The seconds cut of a count dropped the closing fence of its ```toml block
with the promise tables it removes; every count probe of 2026-10-20 got a
protocol ending inside the block — the fence walker read it to the end, so
no check failed, and the audit raised it in each run."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from labkit.formats import protocol_block
from labkit.tools import scaffold


def open_fences(text: str) -> list[int]:
    """1-based lines of the fences in TEXT that are never closed."""
    lines = text.splitlines()
    return [
        start
        for _, start, end in protocol_block.fence_spans(lines)
        if end >= len(lines)
    ]


class StampedFences(unittest.TestCase):
    def test_the_walker_sees_an_open_fence(self):
        self.assertEqual(open_fences("a\n```toml\nx = 1\n"), [2])
        self.assertEqual(open_fences("a\n```toml\nx = 1\n```\n"), [])

    def test_every_stamped_markdown_file_closes_its_fences(self):
        for cost in (None, "seconds", "minutes", "hours"):
            for model in (False, True):
                with self.subTest(cost=cost, model=model):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp) / "lab"
                        argv = ["exp", "foo", "--repo", str(root)]
                        argv += ["--cost", cost] if cost else []
                        argv += ["--model", "haiku"] if model else []
                        out = io.StringIO()
                        with (
                            contextlib.redirect_stdout(out),
                            contextlib.redirect_stderr(out),
                        ):
                            self.assertEqual(scaffold.main(["lab", str(root)]), 0)
                            self.assertEqual(scaffold.main(argv), 0, out.getvalue())
                        stamped = sorted(root.rglob("*.md"))
                        self.assertTrue(
                            any(p.name.startswith("PROTOCOL-") for p in stamped)
                        )
                        found = {
                            str(p.relative_to(root)): open_fences(
                                p.read_text(encoding="utf-8")
                            )
                            for p in stamped
                        }
                        self.assertEqual(
                            {k: v for k, v in found.items() if v}, {}, "open fences"
                        )


class WithoutPromiseTables(unittest.TestCase):
    """The count's cut removes the tables by the block's structure."""

    def test_tables_and_their_comment_go_the_rest_stays(self):
        from labkit.tools import protocol_cuts

        text = (
            '# P\n\n```toml\n[protocol]\n# the head\nid = "p-1"\n\n'
            '# the promises\n[[promise]]\nid = "C1"\n\n[[promise]]\nid = "A1"\n'
            "```\n\nafter\n"
        )
        new = protocol_cuts.without_promise_tables(text)
        self.assertEqual(
            new, '# P\n\n```toml\n[protocol]\n# the head\nid = "p-1"\n```\n\nafter\n'
        )

    def test_a_protocol_table_after_the_promises_is_kept(self):
        from labkit.tools import protocol_cuts

        text = '```toml\n[[promise]]\nid = "C1"\n\n[protocol]\nid = "p-1"\n```\n'
        new = protocol_cuts.without_promise_tables(text)
        self.assertEqual(new, '```toml\n[protocol]\nid = "p-1"\n```\n')


if __name__ == "__main__":
    unittest.main()
