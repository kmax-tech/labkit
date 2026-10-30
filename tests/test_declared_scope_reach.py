"""`scope_sha.areas_touched` over declared scope: a file a promise names in
its `scope` determines the number as an imported helper does, so its change
touches the area even when no code of the area imports it.

    .venv/bin/python -m pytest tests/test_declared_scope_reach.py
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from labkit.formats.scope_sha import areas_touched
from protocol_fixture import head


def _block(*scope: str) -> str:
    entries = ", ".join(f'"{s}"' for s in scope)
    return (
        '[[promise]]\nid = "criterion-1"\nkey = "criterion_1_pass"\n'
        f'sentence = "the criterion holds"\nscope = [{entries}]\n'
    )


class DeclaredScope(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        (self.root / "lib").mkdir()
        # read at run time, never imported
        self.rubric = self.root / "lib" / "rubric.md"
        self.rubric.write_text("score 1 when ...\n", encoding="utf-8")
        self.labels = self.root / "data" / "labels.py"  # outside every LOCAL_ROOT
        self.labels.parent.mkdir()
        self.labels.write_text("GOLD = {}\n", encoding="utf-8")
        self.a = self._area(
            "01-a",
            _block(
                "scripts/01_measure.py", "../../lib/rubric.md", "../../data/labels.py"
            ),
        )
        self.b = self._area("02-b", _block("scripts/01_measure.py"))

    def _area(self, name: str, block: str) -> Path:
        area = self.root / "experiments" / name
        (area / "scripts").mkdir(parents=True)
        (area / "scripts" / "01_measure.py").write_text("x = 1\n", encoding="utf-8")
        (area / "PROTOCOL-x.md").write_text(head(promises=block), encoding="utf-8")
        return area

    def test_a_declared_file_touches_the_area_that_declares_it(self) -> None:
        self.assertEqual(areas_touched([self.rubric], self.root), [self.a])
        self.assertEqual(areas_touched([self.labels], self.root), [self.a])
        self.rubric.unlink()  # a deleted declared file is still one the number rests on
        self.assertEqual(areas_touched([self.rubric], self.root), [self.a])

    def test_a_file_nobody_declares_or_imports_touches_no_area(self) -> None:
        stray = self.root / "lib" / "notes.md"
        stray.write_text("x\n", encoding="utf-8")
        self.assertEqual(areas_touched([stray], self.root), [])

    def test_a_damaged_block_touches_its_own_area_and_no_other(self) -> None:
        """Whether area c declares the file cannot be told, so it counts as
        touched; a and b answer as before, and nothing raises."""
        c = self.root / "experiments" / "03-c"
        c.mkdir()
        (c / "PROTOCOL-x.md").write_text(
            head(promises='[[promise]]\nid = "criterion-1"\n'), encoding="utf-8"
        )
        self.assertEqual(sorted(areas_touched([self.rubric], self.root)), [self.a, c])
        stray = self.root / "lib" / "notes.md"
        self.assertEqual(areas_touched([stray], self.root), [c])


if __name__ == "__main__":
    unittest.main()
