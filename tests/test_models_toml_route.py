"""The run and the audit resolve `models.toml` by one function
(`llm.models_toml_from`); the audit's entry names the file it read and
every other one above it, which a script outside the area may read."""

from __future__ import annotations

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from labkit.run import llm


def _models(model: str) -> str:
    return f'[models.m]\nbackend = "openai"\nmodel = "{model}"\n'


class OneRouteToModelsToml(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.area = self.root / "experiments" / "01-x"
        (self.area / "scripts").mkdir(parents=True)
        (self.root / "lib").mkdir()
        (self.root / "models.toml").write_text(_models("root-model"))
        self.enterContext(contextlib.chdir(self.root))

    def run_reads(self, script: Path) -> Path:
        with mock.patch("sys.argv", [str(script)]):
            return llm.find_models_toml()

    def test_a_second_file_in_the_area_is_named_beside_the_one_the_audit_read(
        self,
    ) -> None:
        (self.area / "models.toml").write_text(_models("area-model"))
        # a shared script in lib/ reads the root's file ...
        self.assertEqual(
            self.run_reads(self.root / "lib" / "run.py"), self.root / "models.toml"
        )
        # ... the audit reads the area's, and says so and names the other
        entry = llm.model_entry("m", self.area)
        self.assertIn(f"# from {self.area / 'models.toml'}", entry)
        self.assertIn('model = "area-model"', entry)
        self.assertIn(
            f"another models.toml stands above, at {self.root / 'models.toml'}",
            entry,
        )

    def test_the_twin_one_file_is_read_alike_and_names_no_other(self) -> None:
        for script in (self.area / "scripts" / "m.py", self.root / "lib" / "run.py"):
            with self.subTest(script=script.name):
                self.assertEqual(self.run_reads(script), self.root / "models.toml")
        entry = llm.model_entry("m", self.area)
        self.assertIn(f"# from {self.root / 'models.toml'}", entry)
        self.assertNotIn("another models.toml", entry)


if __name__ == "__main__":
    unittest.main()
