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

    def test_stale_editable_metadata_refuse_the_pin(self) -> None:
        """The first re-stamp after the 0.88.7 release pinned v0.88.5: the
        editable install's metadata kept its last `pip install -e` while the
        templates came from the source (2026-10-13). This suite runs from the
        checkout, so source_version() is the pyproject's."""
        source = scaffold.source_version()
        self.assertIsNotNone(source)
        real = scaffold.importlib.metadata.version
        scaffold.importlib.metadata.version = lambda name: "0.0.1"
        try:
            with self.assertRaises(SystemExit) as cm:
                scaffold.labkit_pin()
            self.assertIn("0.0.1", str(cm.exception))
            self.assertIn(str(source), str(cm.exception))
            scaffold.importlib.metadata.version = lambda name: source
            self.assertTrue(scaffold.labkit_pin().endswith(f"@v{source}"))
        finally:
            scaffold.importlib.metadata.version = real

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

    def test_the_stamped_prepare_step_runs_under_the_promise_block(self) -> None:
        """runlog refuses any run under the block whose config lacks a
        registered constant, the prepare step too; the stamped 00_prepare.py
        passed none, so the first step of every area with a model refused
        (cold Sonnet, judge at minutes, 2026-10-14)."""
        import subprocess
        import sys

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku")
        raw = self.root / "data" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "claims.jsonl").write_text(
            '{"id": "c01", "text": "Rain causes floods.", "gold": "causal"}\n',
            encoding="utf-8",
        )
        script = self.area() / "scripts" / "00_prepare.py"
        script.write_text(
            script.read_text(encoding="utf-8")
            .replace('REPO / "data" / "TODO"', 'REPO / "data" / "raw" / "claims.jsonl"')
            .replace('"TODO_v1.jsonl"', '"claims_v1.jsonl"'),
            encoding="utf-8",
        )
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 items ->", r.stdout)

    def test_the_stamped_criterion_holds_a_lane_exactly_at_null_plus_margin(
        self,
    ) -> None:
        """[C1] compared floats: 5/12 + 0.25 is 0.6666666666666667, 8/12 is
        0.6666666666666666, so a lane exactly at null + margin failed (the
        preflight audit of a cold Sonnet probe, 2026-10-14). The twin: one
        item below the bar still fails."""
        import importlib.util
        import sys

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku")
        path = self.area() / "scripts" / "01_measure.py"
        spec = importlib.util.spec_from_file_location("stamped_measure", path)
        assert spec is not None and spec.loader is not None
        measure = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = measure  # a dataclass resolves its module by name
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(measure)
        measure.ANSWERS.update({"Yes": "pos", "No": "neg"})
        self.assertEqual(measure.CONFIG.margin, 0.25)

        def lane(name: str, correct: int) -> list[dict]:
            return [
                {"lane": name, "gold": "pos", "answer": "Yes" if i < correct else "No"}
                for i in range(12)
            ]

        at_bar = measure.evaluate_rows(lane("registered", 8) + lane("null", 5))
        self.assertTrue(at_bar["a2_pass"])  # 5/12 is chance ± one item
        self.assertIs(at_bar["c1_pass"], True)
        below = measure.evaluate_rows(lane("registered", 7) + lane("null", 5))
        self.assertIs(below["c1_pass"], False)
        # every item is in the denominator: two empty answers are not correct
        empty = lane("registered", 10)
        for row in empty[10:]:
            row["answer"] = ""
        two_empty = measure.evaluate_rows(empty + lane("null", 6))
        self.assertEqual(
            (two_empty["a1_empty"], two_empty["c1_accuracy"]), (2, 10 / 12)
        )

    def test_init_exp_from_inside_the_area_finds_the_lab(self) -> None:
        """Run from an area directory, labkit-init called the area "not a lab
        repo" (cloud judge probe, 2026-10-14); it finds the lab above, as git
        finds its repo."""
        import os

        quiet(scaffold.stamp_area, self.root, "foo-bar")
        area = self.area()
        self.assertEqual(scaffold.lab_root(area / "scripts"), self.root.resolve())
        cwd = os.getcwd()
        try:
            os.chdir(area)
            self.assertEqual(quiet(scaffold.main, ["exp", "foo-bar", "--report"]), 0)
        finally:
            os.chdir(cwd)
        proto = (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        self.assertIn("Deviations after freeze", proto)  # the report fields arrived
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        self.assertEqual(scaffold.lab_root(outside), outside.resolve())

    def test_a_freshly_stamped_head_cannot_be_frozen_as_stamped(self) -> None:
        """The stamp's promise sentences are `<…>`; setting frozen = true
        without writing them is a must gap, not a registration."""
        from labkit import protocol_check

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku")
        text = (self.area() / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        frozen = text.replace("frozen = false", "frozen = true", 1)
        gaps = protocol_check.check_fields(frozen).missing_must
        self.assertTrue(
            any("C1, A1, A2 still carries the stamp's" in g for g in gaps), gaps
        )

    def test_the_stamped_measure_refuses_rows_of_another_prompt(self) -> None:
        """Resume by id alone kept the old prompt's answers under a new one
        (cloud judge probe, 2026-10-14). The stamped measure() hands its
        instrument to the Store: rows of another prompt stop it before any
        call; rows of its own resume."""
        import importlib.util
        import sys
        from unittest import mock

        from labkit import batch

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku")
        path = self.area() / "scripts" / "01_measure.py"
        spec = importlib.util.spec_from_file_location("stamped_measure_2", path)
        assert spec is not None and spec.loader is not None
        measure = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = measure
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(measure)
        out = Path(self.tmp.name) / "rows.jsonl"
        old = {**measure.instrument(measure.CONFIG), "prompt_sha": "000000000000"}
        with batch.Store(out, instrument=old) as store:
            store.append({"id": "registered:a", "answer": "Yes"})
        jobs = [{"id": "registered:a"}, {"id": "registered:b"}]
        with mock.patch.object(measure.llm, "complete_many") as calls:
            with self.assertRaises(batch.InstrumentError):
                quiet(measure.measure, measure.CONFIG, jobs, out)
            calls.assert_not_called()
        out.unlink()
        own = measure.instrument(measure.CONFIG)
        with batch.Store(out, instrument=own) as store:
            store.append({"id": "registered:a", "answer": "Yes"})
        with (
            mock.patch.object(
                measure.llm, "complete_many", return_value=["No"]
            ) as calls,
            mock.patch.object(measure, "render", return_value="p"),
        ):
            quiet(measure.measure, measure.CONFIG, jobs, out)
        self.assertEqual(calls.call_count, 1)  # only registered:b was asked

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
