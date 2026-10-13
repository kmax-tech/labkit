"""labkit-init: a lab repo and its areas, stamped from the templates that ship with labkit."""

import ast
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from labkit import finalize, rules, scaffold


def quiet(fn, *args, **kw):  # noqa: ANN001, ANN002, ANN003, ANN201 — test helper
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kw)


class Lab(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "probe"
        self.root.mkdir()
        self.log = scaffold.stamp_lab(self.root, "probe", ref=None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_layout(self) -> None:
        for path in (
            "AGENTS.md",
            ".gitignore",
            "requirements.txt",
            "models.toml",
            "pyrightconfig.json",
            ".vscode/settings.json",
            ".vscode/launch.json",
            "tests/test_shared_helpers_come_from_labkit.py",
            "notes/theorie/terms.md",
        ):
            self.assertTrue((self.root / path).is_file(), path)
        glossary = (self.root / "notes" / "theorie" / "terms.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "| Everyday word | Lab term | Code word | Field term (source) |", glossary
        )
        self.assertIn("LAB-084 Double-coinage check", glossary)
        for d in scaffold.LAB_DIRS:
            self.assertTrue((self.root / d).is_dir(), d)
        self.assertEqual(
            (self.root / "CLAUDE.md").resolve(), (self.root / "AGENTS.md").resolve()
        )
        self.assertIn(
            "# AGENTS.md — probe", (self.root / "AGENTS.md").read_text(encoding="utf-8")
        )

    def test_no_copy_of_the_standard_or_of_a_helper(self) -> None:
        self.assertFalse((self.root / "docs" / "arbeitsstandard.md").exists())
        for mod in ("runlog", "llm", "batch"):
            self.assertFalse((self.root / "lib" / f"{mod}.py").exists())

    def test_the_pin_names_the_release_tag_on_github(self) -> None:
        req = (self.root / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(
            req,
            r"(?m)^labkit @ git\+https://github\.com/kmax-tech/labkit\.git@v\d+\.\d+\.\d+$",
        )

    def test_a_ref_overrides_the_tag(self) -> None:
        self.assertTrue(scaffold.labkit_pin("abc1234").endswith("labkit.git@abc1234"))

    def test_rerunning_overwrites_nothing(self) -> None:
        (self.root / "AGENTS.md").write_text("mine\n", encoding="utf-8")
        log = scaffold.stamp_lab(self.root, "probe")
        self.assertEqual(
            (self.root / "AGENTS.md").read_text(encoding="utf-8"), "mine\n"
        )
        self.assertFalse(any(line.startswith("  created") for line in log), log)

    def test_shipped_texts_name_their_rules_and_carry_no_house_path(self) -> None:
        rows = rules.load_registry(rules.REGISTRY)
        for path in sorted(scaffold.TEMPLATES.iterdir()):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(rules.check_refs(path.name, text, rows), [], path.name)
            self.assertIsNone(
                re.search(
                    r"~/work|~/\.claude|/Users/|webis|arbeitsstandard|lib exp", text
                ),
                path.name,
            )


class Exp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "lab"
        self.root.mkdir()
        scaffold.stamp_lab(self.root, "lab")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def area(self) -> Path:
        (area,) = (self.root / "experiments").glob("[0-9]*-foo-bar")
        return area

    def test_an_area_with_protocol_scripts_readme_and_test(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar")
        area = self.area()
        self.assertEqual(area.name, "01-foo-bar")
        for f in (
            "PROTOCOL-foo-bar.md",
            "README.md",
            "scripts/00_prepare.py",
            "scripts/01_measure.py",
            "scripts/02_analyze.py",
            "data/raw/.gitkeep",
            "output/.gitkeep",
        ):
            self.assertTrue((area / f).is_file(), f)
        proto = (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        self.assertRegex(proto, r'(?m)^id = "p-[0-9a-f]{16}"$')
        self.assertNotIn("<!-- s -->", proto)
        test = (self.root / "tests" / "test_01_foo_bar.py").read_text(encoding="utf-8")
        ast.parse(test)
        self.assertIn('"experiments/01-foo-bar"', test)

    def test_the_pilot_part_has_no_report_fields_and_report_adds_them(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar")
        proto = self.area() / "PROTOCOL-foo-bar.md"

        def fields() -> list[str]:
            return re.findall(
                r"(?m)^- \*\*[^*]*†:\*\*", proto.read_text(encoding="utf-8")
            )

        self.assertEqual(fields(), [])
        quiet(scaffold.stamp_area, self.root, "foo-bar", report=True)
        self.assertGreater(len(fields()), 3)

    def test_numbers_count_up_and_a_typed_number_is_dropped(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar")
        quiet(scaffold.stamp_area, self.root, "07-other")
        self.assertTrue((self.root / "experiments" / "02-other").is_dir())

    def test_an_existing_area_refuses_without_report(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar")
        with self.assertRaisesRegex(SystemExit, "already exists"):
            quiet(scaffold.stamp_area, self.root, "foo-bar")

    def test_seconds_stamps_the_cut_and_the_counting_skeleton(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", cost="seconds")
        area = self.area()
        proto = (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        self.assertIn('cost = "seconds"', proto)
        # a count has no bar to clear: no promise tables, no criterion, no admissibility
        self.assertNotIn("[[promise]]", proto)
        self.assertNotIn("Success / failure criterion", proto)
        self.assertNotIn("Admissibility condition", proto)
        # the Summary at seconds is the Result line
        self.assertIn("- **Result:**", proto)
        self.assertNotIn("- **Limits:**", proto)
        self.assertNotIn("- **Next step:**", proto)
        self.assertFalse((area / "scripts" / "00_prepare.py").exists())
        script = (area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        self.assertIn(
            "def evaluate_rows(", script
        )  # the name the README route and finalize expect
        self.assertNotIn("def evaluate(", script)
        readme = (area / "README.md").read_text(encoding="utf-8")
        self.assertIn("evaluate_rows", readme)
        self.assertNotIn("--probe", readme)  # the counting skeleton has no probe
        # a count's README carries no blank: question and contract live in the
        # protocol (cloud draw 11: the placeholder was the one gate line left)
        self.assertEqual(finalize.readme_placeholders(area), [])
        self.assertIn("PROTOCOL-foo-bar.md", readme)
        # the state box names the test file as stamped (underscores, not the slug)
        self.assertIn("tests/test_01_foo_bar.py", readme)
        self.assertTrue((self.root / "tests" / "test_01_foo_bar.py").is_file())
        self.assertIn('"_prov": {"run": run.run_id}', script)  # rows name their run
        self.assertLess(len(proto.splitlines()), 50)  # was 102 lines of guide prose

    def test_seconds_with_a_model_keeps_criterion_promises_and_the_null_lane(
        self,
    ) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", cost="seconds", model="haiku")
        proto = (self.area() / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        for needle in (
            'id = "C1"',
            'id = "A1"',
            'id = "A2"',
            "# constants = {",
            "Success / failure criterion",
            "Admissibility condition",
            "Raw output",
        ):
            self.assertIn(needle, proto, needle)
        self.assertNotRegex(proto, r"(?m)^constants =")

    def test_every_stamped_placeholder_is_one_line(self) -> None:
        stamps = (
            ("full", {}),
            ("quick", {"cost": "seconds"}),
            ("judge", {"cost": "seconds", "model": "haiku"}),
        )
        for name, kw in stamps:
            quiet(scaffold.stamp_area, self.root, name, **kw)
        for proto in (self.root / "experiments").glob("*/PROTOCOL-*.md"):
            text = proto.read_text(encoding="utf-8")
            fence = False
            for line in text.splitlines():
                if line.startswith("```"):
                    fence = not fence
                    continue
                bare = re.sub(
                    r"`[^`]*`", "", line
                )  # `<name>` in a code span is no placeholder
                if fence or "<!--" in line or "<" not in bare:
                    continue
                line = bare
                self.assertTrue(
                    line.rstrip().endswith(">"),
                    f"{proto.name}: a placeholder runs past its line: {line!r}",
                )
            self.assertNotRegex(
                text,
                r"[^\n]\n## ",
                f"{proto.name}: a heading without a blank line before it",
            )

    def test_the_lab_requirements_carry_pytest(self) -> None:
        req = (self.root / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"(?m)^pytest$")

    def test_a_model_alias_fills_the_skeleton(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku")
        self.assertIn(
            "haiku",
            (self.area() / "scripts" / "01_measure.py").read_text(encoding="utf-8"),
        )

    def test_explore_lands_outside_areas_and_moves_in_with_the_area(self) -> None:
        scaffold.stamp_explore(self.root / "experiments", "foo-bar")
        f = self.root / "experiments" / "explore" / "foo-bar.py"
        ast.parse(f.read_text(encoding="utf-8"))
        quiet(scaffold.stamp_area, self.root, "foo-bar")
        self.assertTrue((self.area() / "explore" / "foo-bar.py").is_file())
        self.assertFalse(f.exists())

    def test_a_repo_without_the_lab_layout_is_refused(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        with self.assertRaisesRegex(SystemExit, "labkit-init lab"):
            scaffold.stamp_area(bare, "foo-bar")


class Report(unittest.TestCase):
    """--report answers what a model-free protocol cannot: seed, noise, parser."""

    def stamped(self, model_line: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold.stamp_lab(root, "lab")
            quiet(scaffold.stamp_area, root, "foo-bar")
            (proto,) = root.glob("experiments/*/PROTOCOL-foo-bar.md")
            text = re.sub(
                r"- \*\*Model / tool:\*\* <[^>]*>",
                model_line,
                proto.read_text(encoding="utf-8"),
                count=1,
            )
            proto.write_text(text, encoding="utf-8")
            quiet(scaffold.stamp_area, root, "foo-bar", report=True)
            return proto.read_text(encoding="utf-8")

    def test_no_model_fills_the_three_fields(self) -> None:
        text = self.stamped("- **Model / tool:** none")
        self.assertIn("**Randomness controls †:** n/a — deterministic", text)
        self.assertIn("**Noise ceiling → threshold †:** n/a — deterministic", text)
        self.assertIn("**Parser cases harvested:** n/a — no model", text)

    def test_a_model_leaves_them_open(self) -> None:
        self.assertNotIn("auto-filled", self.stamped("- **Model / tool:** haiku"))


class Cli(unittest.TestCase):
    def test_lab_then_exp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "x"
            self.assertEqual(
                quiet(scaffold.main, ["lab", str(root), "--labkit-ref", "deadbee"]), 0
            )
            self.assertIn(
                "@deadbee", (root / "requirements.txt").read_text(encoding="utf-8")
            )
            self.assertEqual(
                quiet(
                    scaffold.main,
                    ["exp", "foo", "--repo", str(root), "--cost", "seconds"],
                ),
                0,
            )
            self.assertTrue(
                (root / "experiments" / "01-foo" / "PROTOCOL-foo.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()
