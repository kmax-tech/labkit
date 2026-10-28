"""labkit-init: a lab repo and its areas, stamped from the templates that ship with labkit."""

import ast
import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

from labkit.checks import readme_check
from labkit.tools import scaffold, protocol_cuts
from labkit.formats import (
    console,
    promises,
    protocol_block,
    protocol_check,
    rules,
    standard_contract,
)
from protocol_fixture import head  # noqa: E402


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
            with self.assertRaises(console.Refused) as cm:
                scaffold.labkit_pin()
            self.assertIn("0.0.1", str(cm.exception))
            self.assertIn(str(source), str(cm.exception))
            scaffold.importlib.metadata.version = lambda name: source
            self.assertTrue(scaffold.labkit_pin().endswith(f"@v{source}"))
        finally:
            scaffold.importlib.metadata.version = real

    def test_lab_from_a_checkout_off_the_pin_is_refused(self) -> None:
        """Stamped from main under a v0.103.0 pin, AGENTS.md named `--kind`,
        which that labkit lacks (2026-10-27). This suite runs from the
        checkout, so `check_lab_pin` compares."""
        self.assertIsNotNone(scaffold.source_version())
        root = self.root / "lab"
        off = mock.patch.object(
            scaffold, "lab_templates_off_ref", return_value=["AGENTS.md.template"]
        )
        with off, self.assertRaisesRegex(console.Refused, "AGENTS.md.template"):
            quiet(scaffold.main, ["lab", str(root)])
        self.assertFalse(root.exists())
        unknown = mock.patch.object(
            scaffold,
            "lab_templates_off_ref",
            side_effect=RuntimeError("v0.0.1 is no commit"),
        )
        with unknown, self.assertRaisesRegex(console.Refused, "cannot tell"):
            quiet(scaffold.main, ["lab", str(root)])
        self.assertFalse(root.exists())
        same = mock.patch.object(scaffold, "lab_templates_off_ref", return_value=[])
        with same:
            self.assertEqual(quiet(scaffold.main, ["lab", str(root)]), 0)
        self.assertTrue((root / "AGENTS.md").is_file())

    def test_lab_from_an_installed_release_compares_nothing(self) -> None:
        root = self.root / "lab"
        with (
            mock.patch.object(scaffold, "source_version", return_value=None),
            mock.patch.object(
                scaffold, "lab_templates_off_ref", side_effect=AssertionError
            ),
        ):
            self.assertEqual(quiet(scaffold.main, ["lab", str(root)]), 0)
        self.assertTrue((root / "AGENTS.md").is_file())

    def test_the_stamped_repo_tests_pass_against_this_labkit(self) -> None:
        """The lab repo's own guard test compares the helpers' module names
        with their package path; it is run here, not only read, so a stamped
        repo starts green (docs/notes/2026-10-19-layer-packages.md)."""
        tests = self.root / "tests"
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(tests)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Ran 3 tests", r.stderr)

    def test_rerunning_overwrites_nothing(self) -> None:
        (self.root / "AGENTS.md").write_text("mine\n", encoding="utf-8")
        log = scaffold.stamp_lab(self.root, "probe")
        self.assertEqual(
            (self.root / "AGENTS.md").read_text(encoding="utf-8"), "mine\n"
        )
        self.assertFalse(any(line.startswith("  created") for line in log), log)

    def test_shipped_texts_name_their_rules_and_carry_no_house_path(self) -> None:
        rows = rules.load_ledger(rules.LEDGER)
        for path in sorted(scaffold.TEMPLATES.iterdir()):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(rules.check_refs(path.name, text, rows), [], path.name)
            self.assertIsNone(
                re.search(
                    r"~/work|~/\.claude|/Users/|webis|arbeitsstandard|lib exp", text
                ),
                path.name,
            )


GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.org"]


class LabTemplatesOffRef(unittest.TestCase):
    """`lab_templates_off_ref` against a labkit-like checkout tagged v1.0.0."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.templates = self.repo / "labkit" / "templates"
        self.templates.mkdir(parents=True)
        for name in scaffold.LAB_TEMPLATES:
            (self.templates / name).write_text(f"{name}\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "release")
        self.git("tag", "v1.0.0")

    def git(self, *args: str) -> str:
        r = subprocess.run(
            ["git", *GIT_ID, *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()

    def test_the_templates_as_tagged_pass(self) -> None:
        self.assertEqual(scaffold.lab_templates_off_ref(self.repo, "v1.0.0"), [])

    def test_a_template_changed_since_the_ref_is_named(self) -> None:
        (self.templates / "AGENTS.md.template").write_text("--kind\n", encoding="utf-8")
        off = ["AGENTS.md.template"]
        self.assertEqual(scaffold.lab_templates_off_ref(self.repo, "v1.0.0"), off)
        self.git("commit", "-q", "-am", "main moves on")
        self.assertEqual(scaffold.lab_templates_off_ref(self.repo, "v1.0.0"), off)
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(scaffold.lab_templates_off_ref(self.repo, head), [])

    def test_a_template_the_ref_lacks_is_named(self) -> None:
        name = scaffold.LAB_TEMPLATES[-1]
        self.git("rm", "-q", "--cached", f"labkit/templates/{name}")
        self.git("commit", "-q", "-m", "untrack one template")
        self.git("tag", "v1.0.1")
        self.assertEqual(scaffold.lab_templates_off_ref(self.repo, "v1.0.1"), [name])

    def test_a_ref_the_checkout_lacks_cannot_be_compared(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "v9.9.9 is no commit"):
            scaffold.lab_templates_off_ref(self.repo, "v9.9.9")

    def test_a_directory_without_git_cannot_be_compared(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "no git checkout"):
                scaffold.lab_templates_off_ref(Path(d), "v1.0.0")


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

    def test_a_bar_names_its_stamped_ids_and_a_count_names_none(self) -> None:
        """A fit or an apply stamps `[C1]`, `[A1]`, `[A2]` before the fields
        that state them — the ids its block declares, nothing added; the
        fields stay open. A computation is stamped without those fields and without
        promise tables at every tier, so its prose names no id."""
        cases = (
            ("low", "fit", None),
            ("high", "fit", None),
            ("high", "apply", "haiku"),
            ("high", "compute", None),
            ("low", "compute", None),
        )
        for cost, kind, model in cases:
            with self.subTest(repeat_cost=cost, kind=kind):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                root = Path(tmp.name) / "lab"
                root.mkdir()
                scaffold.stamp_lab(root, "lab")
                quiet(
                    scaffold.stamp_area,
                    root,
                    "x",
                    repeat_cost=cost,
                    kind=kind,
                    model=model,
                )
                (proto,) = (root / "experiments").glob("*-x/PROTOCOL-x.md")
                text = proto.read_text(encoding="utf-8")
                if kind == "compute":
                    # standard 0.22: no bar field and no promise table at any tier
                    self.assertEqual(promises.ids_in_prose(text), set())
                    self.assertIsNone(promises.parse_block(text))
                    labels = {f.label for f in protocol_check.fields(text)}
                    self.assertFalse(labels & set(protocol_cuts.PROMISE_FIELDS), cost)
                    continue
                block = promises.parse_block(text)
                assert block is not None
                self.assertEqual(
                    {i.upper() for i in promises.ids_in_prose(text)},
                    {p.id for p in block.promises},
                )
                by_label = {f.label: f for f in protocol_check.fields(text)}
                for label, pid in protocol_cuts.PROMISE_FIELDS.items():
                    self.assertTrue(by_label[label].value.startswith(f"[{pid}] <"))
                    self.assertTrue(by_label[label].placeholder, label)

    def test_an_area_with_protocol_scripts_readme_and_test(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
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
        self.assertNotRegex(proto, r"<!-- l[bm]? -->")
        test = (self.root / "tests" / "test_01_foo_bar.py").read_text(encoding="utf-8")
        ast.parse(test)
        self.assertIn('"experiments/01-foo-bar"', test)

    def test_the_pilot_part_has_no_report_fields_and_report_adds_them(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
        proto = self.area() / "PROTOCOL-foo-bar.md"

        def fields() -> list[str]:
            return re.findall(
                r"(?m)^- \*\*[^*]*†:\*\*", proto.read_text(encoding="utf-8")
            )

        self.assertEqual(fields(), [])
        quiet(scaffold.stamp_area, self.root, "foo-bar", report=True, kind="fit")
        self.assertGreater(len(fields()), 3)
        # the cut marks are the template's, never a written protocol's (the
        # --report path kept 12-16 of them after the l-rename, review 2026-10-25)
        self.assertNotRegex(proto.read_text(encoding="utf-8"), r"<!-- l[bm]? -->")

    def test_numbers_count_up_and_a_typed_number_is_dropped(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
        quiet(scaffold.stamp_area, self.root, "07-other", kind="fit")
        self.assertTrue((self.root / "experiments" / "02-other").is_dir())

    def test_an_existing_area_refuses_without_report(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
        with self.assertRaisesRegex(console.Refused, "already exists"):
            quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")

    def _two_areas_of_one_name(self) -> Path:
        """`experiments/` with `01-x` (high fit) and its copy `02-x`, and
        `03-y` (low computation) beside a hand-made `y` — two areas for each
        name, as a copy or a rename by hand leaves them."""
        quiet(scaffold.stamp_area, self.root, "x", "high", kind="fit")
        quiet(scaffold.stamp_area, self.root, "other", kind="fit")
        quiet(scaffold.stamp_area, self.root, "y", "low", kind="compute")
        exp = self.root / "experiments"
        shutil.copytree(exp / "01-x", exp / "02-x")
        shutil.copytree(exp / "03-y", exp / "y")
        return exp

    def _snapshot(self) -> dict[Path, bytes]:
        return {p: p.read_bytes() for p in sorted(self.root.rglob("*")) if p.is_file()}

    def test_a_name_two_areas_carry_is_refused_naming_both(self) -> None:
        """`--report` and `--change-kind` took the first area of the slug in
        directory order, without a word (audit 2026-10-27, doubled homes:
        the copy `02-x` was promoted); a new area's refusal named one of
        them. Each refuses naming both and the command that picks one,
        nothing changed; an area without a number is told to take one."""
        self._two_areas_of_one_name()
        before = self._snapshot()
        for call, said in (
            (
                lambda: scaffold.stamp_area(self.root, "x", report=True),
                "01-x, 02-x — name the one you mean by its number "
                "(`labkit-init exp 01-x …`)",
            ),
            (
                lambda: scaffold.change_kind(self.root, "y", "fit"),
                "03-y, y — name the one you mean by its number (`labkit-init "
                "exp 03-y …`); y has no number to be named by",
            ),
            (
                lambda: scaffold.stamp_area(self.root, "x", kind="fit"),
                "already exists: 01-x, 02-x under",
            ),
        ):
            with self.subTest(said=said):
                with self.assertRaises(console.Refused) as caught:
                    quiet(call)
                self.assertIn(said, caught.exception.why)
                self.assertEqual(self._snapshot(), before)
        with self.assertRaises(console.Refused) as caught:
            quiet(scaffold.stamp_area, self.root, "x", kind="fit")
        self.assertIn("`labkit-init exp 01-x --report`", caught.exception.why)

    def test_a_typed_number_no_area_carries_is_refused(self) -> None:
        """`exp 02-x --change-kind` beside `01-x` alone restamped `01-x`:
        the number typed was dropped for an existing area too (cold review
        of this change). For `--report` and `--change-kind` it names the
        area or is refused naming the areas of that name; a new area still
        drops it (`test_numbers_count_up_and_a_typed_number_is_dropped`)."""
        self._two_areas_of_one_name()
        before = self._snapshot()
        for call, said in (
            (
                lambda: scaffold.stamp_area(self.root, "05-other", report=True),
                "no area 05-other under",
            ),
            (
                lambda: scaffold.change_kind(self.root, "09-y", "fit"),
                "no area 09-y under",
            ),
        ):
            with self.subTest(said=said):
                with self.assertRaises(console.Refused) as caught:
                    quiet(call)
                self.assertIn(said, caught.exception.why)
                self.assertEqual(self._snapshot(), before)
        with self.assertRaises(console.Refused) as caught:
            quiet(scaffold.stamp_area, self.root, "05-other", report=True)
        self.assertIn(
            "'other' names 02-other; name the one you mean by its number "
            "(`labkit-init exp 02-other …`)",
            caught.exception.why,
        )

    def test_the_twin_the_numbered_name_picks_one_of_them(self) -> None:
        exp = self._two_areas_of_one_name()
        first = (exp / "01-x" / "PROTOCOL-x.md").read_bytes()
        report_field = r"(?m)^- \*\*[^*]*†:\*\*"
        for name in ("02-x", "02-X", "02-x/"):
            with self.subTest(name=name):
                area, _ = quiet(scaffold.stamp_area, self.root, name, report=True)
                self.assertEqual(area, exp / "02-x")
                self.assertRegex(
                    (exp / "02-x" / "PROTOCOL-x.md").read_text(encoding="utf-8"),
                    report_field,
                )
                self.assertEqual((exp / "01-x" / "PROTOCOL-x.md").read_bytes(), first)
        area, _ = quiet(scaffold.stamp_area, self.root, "02-other", report=True)
        self.assertEqual(area, exp / "02-other")
        area, _ = quiet(scaffold.change_kind, self.root, "03-y", "fit")
        self.assertEqual(area, exp / "03-y")
        head = protocol_block.head(
            (exp / "03-y" / "PROTOCOL-y.md").read_text(encoding="utf-8")
        )
        self.assertEqual(head.kind, "fit")

    def test_low_stamps_the_cut_and_the_counting_skeleton(self) -> None:
        quiet(
            scaffold.stamp_area, self.root, "foo-bar", repeat_cost="low", kind="compute"
        )
        area = self.area()
        proto = (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        self.assertIn('repeat_cost = "low"', proto)
        self.assertIn('kind = "compute"', proto)
        # a computation has no bar to clear: no promise tables, no criterion, no admissibility
        self.assertNotIn("[[promise]]", proto)
        self.assertNotIn("Success / failure criterion", proto)
        self.assertNotIn("Admissibility condition", proto)
        # the Summary at low repeat cost is the Result line
        self.assertIn("- **Conclusion:**", proto)
        self.assertNotIn("- **Limits:**", proto)
        self.assertNotIn("- **Next step:**", proto)
        self.assertFalse((area / "scripts" / "00_prepare.py").exists())
        # the one public recheck of every skeleton: the compute skeleton's 02_analyze.py
        # imports evaluate_rows from 01_measure.py and carries the --check
        # (until 0.99.0 the check sat inside 01_measure.py, and report-check
        # asked for a file the skeleton never stamped, audit 2026-10-19)
        analyze = (area / "scripts" / "02_analyze.py").read_text(encoding="utf-8")
        self.assertIn('"--check"', analyze)
        self.assertIn("measure.evaluate_rows(rows, ids)", analyze)
        self.assertIn('AREA / "scripts" / "01_measure.py"', analyze)
        script = (area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        # one home for the check: the compute skeleton's 01_measure.py only measures
        self.assertNotIn('add_argument("--check"', script)
        self.assertNotIn("recheck.holds", script)
        self.assertIn(
            "def evaluate_rows(", script
        )  # the name the README route and finalize expect
        self.assertNotIn("def evaluate(", script)
        readme = (area / "README.md").read_text(encoding="utf-8")
        self.assertIn("evaluate_rows", readme)
        self.assertNotIn("--probe", readme)  # the counting skeleton has no probe
        # a computation's README carries no blank: question and contract live in the
        # protocol (cloud draw 11: the placeholder was the one gate line left)
        self.assertEqual(readme_check.readme_placeholders(area), [])
        self.assertIn("PROTOCOL-foo-bar.md", readme)
        # the state box names the test file as stamped (underscores, not the slug)
        self.assertIn("tests/test_01_foo_bar.py", readme)
        self.assertTrue((self.root / "tests" / "test_01_foo_bar.py").is_file())
        self.assertIn('"_prov": {"run": run.run_id}', script)  # rows name their run
        self.assertLess(len(proto.splitlines()), 50)  # was 102 lines of guide prose

    def test_low_with_a_model_keeps_criterion_promises_and_the_null_lane(
        self,
    ) -> None:
        quiet(
            scaffold.stamp_area,
            self.root,
            "foo-bar",
            repeat_cost="low",
            model="haiku",
            kind="apply",
        )
        proto = (self.area() / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        for needle in (
            'id = "C1"',
            'id = "A1"',
            'id = "A2"',
            "constants = { margin = 0.25 }",
            "constants = { max_empty = 2 }",
            "constants = { null_band_items = 1 }",
            "Success / failure criterion",
            "Admissibility condition",
            "Raw output",
        ):
            self.assertIn(needle, proto, needle)
        # the stamped skeleton reads those constants: its config builds
        # (a commented hint made every first run a TypeError, 2026-10-15)
        import importlib.util
        import sys

        path = self.area() / "scripts" / "01_measure.py"
        spec = importlib.util.spec_from_file_location("stamped_seconds_measure", path)
        assert spec is not None and spec.loader is not None
        measure = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = measure
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(measure)
        self.assertEqual(measure.CONFIG.margin, 0.25)

    def test_the_stamped_prepare_step_runs_under_the_promise_block(self) -> None:
        """runlog refuses any run under the block whose config lacks a
        registered constant, the prepare step too; the stamped 00_prepare.py
        passed none, so the first step of every area with a model refused
        (cold Sonnet, judge at high, 2026-10-14)."""
        import subprocess
        import sys

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
        raw = self.root / "data" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "claims.jsonl").write_text(
            '{"id": "c01", "text": "Rain causes floods.", "gold": "causal"}\n',
            encoding="utf-8",
        )
        script = self.area() / "scripts" / "00_prepare.py"
        stamped = script.read_text(encoding="utf-8")
        pointed = stamped.replace(
            'REPO / "data" / "TODO"', 'REPO / "data" / "raw" / "claims.jsonl"'
        ).replace('"TODO_v1.jsonl"', '"claims_v1.jsonl"')
        script.write_text(pointed, encoding="utf-8")
        run = lambda: subprocess.run(  # noqa: E731
            [sys.executable, str(script)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # the legend still stamped `TODO: …` is refused before the file is written
        r = run()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("about still reads 'TODO:", r.stderr)
        self.assertFalse(
            (self.area() / "data" / "prepared" / "claims_v1.jsonl").exists()
        )
        # the author fills the two legend lines, as the stamp asks
        legend = pointed.replace(
            'ABOUT = "TODO: one sentence — what one row is and what this dataset is for."',
            'ABOUT = "one claim per row, judged causal or not"',
        ).replace(
            '"gold": "TODO: every gold value spelled out, e.g. causal | not_causal"',
            '"gold": "causal | not_causal"',
        )
        self.assertNotIn('"TODO:', legend)  # the knob comment may keep its TODO
        script.write_text(legend, encoding="utf-8")
        r = run()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 items ->", r.stdout)
        # the run binds the raw file it read (audit 2026-10-21: none recorded)
        import json

        # the refused attempt left its record too; the written run is the newest
        record = max((self.area() / "runs").glob("*/config.json"))
        data = json.loads(record.read_text(encoding="utf-8"))["data"]
        self.assertIn("source", data)  # beside runlog's own leakage_check
        self.assertEqual(
            data["source"]["path"], "data/raw/claims.jsonl"
        )  # repo-relative
        from labkit.run.provenance import RECORD_SHA_CHARS

        self.assertEqual(len(data["source"]["sha256"]), RECORD_SHA_CHARS)
        self.assertEqual(data["source"]["rows"], 1)

    def test_the_stamped_criterion_holds_a_lane_exactly_at_null_plus_margin(
        self,
    ) -> None:
        """[C1] compared floats: 5/12 + 0.25 is 0.6666666666666667, 8/12 is
        0.6666666666666666, so a lane exactly at null + margin failed (the
        preflight audit of a cold Sonnet probe, 2026-10-14). The twin: one
        item below the bar still fails."""
        import importlib.util
        import sys

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
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

    def test_the_next_steps_are_the_lane_with_its_gates(self) -> None:
        """The printed steps at high repeat cost skipped the preflight, both
        audits and the adoption while the stamped AGENTS.md named them; an
        agent following the console met the refusal at the run's start
        (review 2026-10-19). The steps read the contract: every gate the
        lane owes stands in order, numbered without a gap."""
        rel = Path("experiments/01-foo")
        for cost, kind, model in (("high", "fit", False), ("high", "apply", True)):
            text = scaffold.next_steps(rel, "foo", "01", cost, kind, model)
            order = [
                "code-check experiments/01-foo",
                "preflight experiments/01-foo",
                "labkit-audit experiments/01-foo --mode preflight",
                "`frozen = true`",
                "git add + commit, THEN",
                "runlog start experiments/01-foo",
                "finalize experiments/01-foo",
                "labkit-audit experiments/01-foo --mode analysis",
                "protocol-fill experiments/01-foo/PROTOCOL-foo.md --from-run",
            ]
            positions = [text.index(step) for step in order]
            self.assertEqual(positions, sorted(positions), text)
            numbers = [int(m) for m in re.findall(r"^  (\d+)\. ", text, re.M)]
            self.assertEqual(numbers, list(range(1, len(numbers) + 1)), text)
        low = scaffold.next_steps(rel, "foo", "01", "low", "compute", False)
        for not_owed in ("preflight", "frozen = true", "runlog start", "--probe"):
            self.assertNotIn(not_owed, low, low)
        for owed in ("code-check", "finalize", "--mode analysis", "--from-run"):
            self.assertIn(owed, low, low)

    def test_the_next_steps_name_only_what_the_skeleton_has(self) -> None:
        """A high computation was told to fill `00_prepare.py` and run
        `--show 3` and `--probe 4`, which its skeleton lacks, and no area
        with a model but without the prompt skeleton heard of the data
        profile it owes (audit 2026-10-27, C2 and C4). The steps name a
        script only when the skeleton stamps it, a probe only when the lane
        allows one, the data profile whenever a model is named; the detached
        command names its script from the repo root, where `runlog start`
        runs it (C3)."""
        rel = Path("experiments/01-foo")
        for kind in ("compute", "fit", "apply"):
            for cost in ("low", "high"):
                for model in (False, True):
                    text = scaffold.next_steps(rel, "foo", "01", cost, kind, model)
                    sk = standard_contract.skeleton(cost, kind, model)
                    stamped = {dest for _, dest in sk.scripts}
                    for name in re.findall(r"scripts/(\d\d_\w+\.py)", text):
                        self.assertIn(name, stamped, text)
                    owes_probe = sk.probe and standard_contract.lane(cost).probe_allowed
                    self.assertEqual("--probe" in text, owes_probe, text)
                    if sk is standard_contract.COMPUTE:
                        self.assertNotIn("--show", text)
                    self.assertEqual("data profile" in text, model, text)
                    if not standard_contract.lane(cost).foreground:
                        self.assertIn(
                            "runlog start experiments/01-foo -- .venv/bin/python "
                            "experiments/01-foo/scripts/01_measure.py",
                            text,
                        )

    def test_a_computation_is_told_to_check_its_kind_first(self) -> None:
        """An agent told to train a random forest stamped `--kind compute` and
        read "no criterion" (docs/notes/2026-10-26-kind-choice.md). A
        computation's steps open with the kind questions and the restamp as
        a fit; a counting area keeps its cut without a criterion. A fit's
        steps carry no such detour and name its bar."""
        rel = Path("experiments/01-foo")
        for cost in ("low", "high"):
            compute = scaffold.next_steps(rel, "foo", "01", cost, "compute", False)
            first = re.search(r"^  1\. (.*)$", compute, re.M)
            assert first is not None, compute
            self.assertIn("Check the kind", first.group(1))
            self.assertIn("labkit-init exp foo --kind fit --change-kind", compute)
            self.assertNotIn("rm -r", compute)
            self.assertIn("also when the deliverable is predictions", compute)
            fit = scaffold.next_steps(rel, "foo", "01", cost, "fit", False)
            self.assertNotIn("Check the kind", fit)
            self.assertNotIn("--kind fit", fit)
        low = scaffold.next_steps(rel, "foo", "01", "low", "compute", False)
        self.assertIn("no criterion", low)
        self.assertIn(
            "criterion", scaffold.next_steps(rel, "foo", "01", "low", "fit", False)
        )
        quiet(scaffold.stamp_area, self.root, "count-docs", "low", kind="compute")
        proto = next(self.root.glob("experiments/*-count-docs/PROTOCOL-*.md"))
        self.assertEqual(protocol_block.head(proto.read_text()).kind, "compute")

    def _compute_area_with_work(self) -> tuple[Path, Path, str]:
        """(area, protocol, its id): `foo-bar` stamped as a computation at
        low cost after an explore file, its Question written."""
        from labkit.tools import protocol_fill

        quiet(scaffold.main, ["exp", "foo-bar", "--explore", "--repo", str(self.root)])
        quiet(scaffold.stamp_area, self.root, "foo-bar", "low", kind="compute")
        area = self.area()
        proto = area / "PROTOCOL-foo-bar.md"
        text = proto.read_text(encoding="utf-8")
        label = next(
            f.label
            for f in protocol_check.fields(text)
            if f.name.startswith("question")
        )
        proto.write_text(
            protocol_fill.fill(text, label, "how well does a forest predict K?"),
            encoding="utf-8",
        )
        pid = protocol_block.head(text).id
        assert pid is not None
        return area, proto, pid

    def test_a_kind_changed_before_the_run_keeps_the_work(self) -> None:
        """The next steps once said `rm -r` the area and stamp it anew: the
        explore file moved into the area went with it, and the computation's
        test under tests/ survived and was skipped by the new stamp — a fit
        script beside a test expecting COUNT_FIELD (review 2026-10-26).
        `--change-kind` keeps the explore file and the written Question,
        keeps the id, and stamps the fit's scripts and test whole."""
        area, proto, pid = self._compute_area_with_work()
        explore = area / "explore" / "foo-bar.py"
        self.assertTrue(explore.is_file())
        kept = explore.read_text(encoding="utf-8")
        rc = quiet(
            scaffold.main,
            [
                "exp",
                "foo-bar",
                "--kind",
                "fit",
                "--change-kind",
                "--repo",
                str(self.root),
            ],
        )
        self.assertEqual(rc, 0)
        self.assertEqual(explore.read_text(encoding="utf-8"), kept)
        text = proto.read_text(encoding="utf-8")
        head = protocol_block.head(text)
        self.assertEqual((head.kind, head.id, head.repeat_cost), ("fit", pid, "low"))
        self.assertIn("how well does a forest predict K?", text)
        nn = area.name.split("-")[0]
        fit = scaffold.script_stamps(
            self.root,
            area,
            nn,
            "foo-bar",
            standard_contract.skeleton("low", "fit", False),
            False,
        )
        for path, stamped in fit.items():
            self.assertEqual(path.read_text(encoding="utf-8"), stamped, path)
        (test,) = (self.root / "tests").glob("test_*foo_bar*.py")
        self.assertNotIn("COUNT_FIELD", test.read_text(encoding="utf-8"))
        compute = scaffold.script_stamps(
            self.root,
            area,
            nn,
            "foo-bar",
            standard_contract.skeleton("low", "compute", False),
            False,
        )
        for gone in set(compute) - set(fit):
            self.assertFalse(gone.exists(), gone)

    def test_a_kind_change_refuses_to_lose_work_and_changes_nothing(self) -> None:
        """An edited stamp, or a run, holds the change; the area stays
        byte for byte as it was."""
        area, _, _ = self._compute_area_with_work()
        script = area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# mine\n")

        def snapshot() -> dict[Path, bytes]:
            return {
                p: p.read_bytes()
                for p in sorted(self.root.rglob("*"))
                if p.is_file() and ".git" not in p.parts
            }

        before = snapshot()
        with self.assertRaises(console.Refused) as caught:
            scaffold.change_kind(self.root, "foo-bar", "fit")
        self.assertIn(
            "01_measure.py: edited since the compute stamp", str(caught.exception)
        )
        self.assertEqual(snapshot(), before)
        (area / "runs" / "2026-10-26T10-00-00_abcd").mkdir(parents=True)
        before = snapshot()
        with self.assertRaises(console.Refused) as caught:
            scaffold.change_kind(self.root, "foo-bar", "fit")
        self.assertIn("has measured", str(caught.exception))
        self.assertIn("a new registration", str(caught.exception))
        self.assertEqual(snapshot(), before)

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
        )

    def _stamped_by_an_earlier_labkit(
        self,
        kind: str,
        tmpl: str,
        old: str,
        new: str,
        meanwhile: Callable[[Path], None] | None = None,
    ) -> Path:
        """`foo-bar` stamped as KIND at low cost by an earlier labkit — the
        template TMPL then read OLD where it reads NEW now — and committed
        under that labkit's pin; then MEANWHILE (given the area: the work
        done under that pin, nothing by default); then the pin raised and
        committed. Returns the area."""
        real = scaffold.template

        def earlier(name: str) -> str:
            text = real(name)
            if name != tmpl:
                return text
            self.assertEqual(text.count(new), 1, new)
            return text.replace(new, old)

        with mock.patch.object(scaffold, "template", earlier):
            quiet(scaffold.stamp_area, self.root, "foo-bar", "low", kind=kind)
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("commit", "-qm", "stamp under the earlier pin")
        if meanwhile is not None:
            meanwhile(self.area())
        req = self.root / "requirements.txt"
        raised = re.sub(r"labkit\.git@\S+", "labkit.git@v99.0.0", req.read_text())
        self.assertNotEqual(raised, req.read_text())
        req.write_text(raised, encoding="utf-8")
        self._git("commit", "-qam", "raise the pin")
        return self.area()

    def test_a_template_upgrade_is_no_edit_of_the_stamp(self) -> None:
        """ "Edited since the stamp" compared the area with the INSTALLED
        labkit's templates: after a pin raise an unedited stamp read as the
        user's edit, and `--change-kind` held for nothing (audit 2026-10-27,
        C13). Unchanged since the commit that added it, under another pin,
        it is the earlier labkit's stamp: replaced, the commit named. The
        twin: an edit since that commit still holds."""
        measure = dict(
            (dest, tmpl) for tmpl, dest in standard_contract.COMPUTE.scripts
        )["01_measure.py"]
        area = self._stamped_by_an_earlier_labkit(
            "compute",
            measure,
            "#!/usr/bin/env python3\n# an earlier labkit's line\n",
            "#!/usr/bin/env python3\n",
        )
        script = area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# mine\n")
        with self.assertRaises(console.Refused) as caught:
            scaffold.change_kind(self.root, "foo-bar", "fit")
        self.assertIn(
            "01_measure.py: edited since the compute stamp", str(caught.exception)
        )
        self._git("checkout", "--", str(script))
        _, report = scaffold.change_kind(self.root, "foo-bar", "fit")
        self.assertRegex(
            report, r"replaced\s+\S*01_measure\.py \(the stamp of an earlier pin, "
        )
        self.assertEqual(
            protocol_block.head(
                (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
            ).kind,
            "fit",
        )

    def test_a_template_upgrade_is_no_edit_of_the_promise_block(self) -> None:
        """The promise block, as the stamp files: the earlier labkit's block
        unchanged since its commit is replaced; written since, it holds."""
        area = self._stamped_by_an_earlier_labkit(
            "fit",
            scaffold.PROTOCOL_TEMPLATE.name,
            "constants = { margin = 0.2 }",
            "constants = { margin = 0.25 }",
        )
        proto = area / "PROTOCOL-foo-bar.md"
        committed = proto.read_text(encoding="utf-8")
        proto.write_text(committed.replace("margin = 0.2 ", "margin = 0.3 "))
        with self.assertRaises(console.Refused) as caught:
            scaffold.change_kind(self.root, "foo-bar", "compute")
        self.assertIn("the promise block differs", str(caught.exception))
        proto.write_text(committed, encoding="utf-8")
        _, report = scaffold.change_kind(self.root, "foo-bar", "compute")
        self.assertIn("the promise block of an earlier pin", report)

    def _measure_template(self) -> str:
        return dict((dest, tmpl) for tmpl, dest in standard_contract.COMPUTE.scripts)[
            "01_measure.py"
        ]

    def test_an_edit_is_no_earlier_stamp_after_a_rename_a_re_add_or_a_shallow_clone(
        self,
    ) -> None:
        """The commit that "added" the file was taken as the stamp: a rename
        after an edit, a delete and re-add with one's own text, and a
        shallow clone's only commit each made an edit read as the earlier
        labkit's stamp, and `--change-kind` replaced it (cold review
        2026-10-27). The first addition is followed through renames; a
        re-add or a shallow clone is no evidence. The twin: a rename
        without an edit is still the earlier stamp."""
        old = "#!/usr/bin/env python3\n# an earlier labkit's line\n"
        new = "#!/usr/bin/env python3\n"

        def stamped(meanwhile: Callable[[Path], None]) -> Path:
            return self._stamped_by_an_earlier_labkit(
                "compute", self._measure_template(), old, new, meanwhile
            )

        def held(root: Path) -> None:
            with self.assertRaises(console.Refused) as caught:
                scaffold.change_kind(root, "foo-bar", "fit")
            self.assertIn(
                "01_measure.py: edited since the compute stamp", str(caught.exception)
            )

        def edit(area: Path) -> None:
            script = area / "scripts" / "01_measure.py"
            script.write_text(script.read_text(encoding="utf-8") + "# mine\n")
            self._git("commit", "-qam", "my edit")

        def renumber(area: Path) -> None:
            self._git("mv", str(area), str(area.with_name("02-foo-bar")))
            self._git("commit", "-qm", "renumber")

        def re_add(area: Path) -> None:
            script = area / "scripts" / "01_measure.py"
            mine = script.read_text(encoding="utf-8") + "# mine\n"
            self._git("rm", "-q", str(script))
            self._git("commit", "-qm", "drop")
            script.write_text(mine, encoding="utf-8")
            self._git("add", str(script))
            self._git("commit", "-qm", "mine")

        def edit_then_renumber(area: Path) -> None:
            edit(area)
            renumber(area)

        with self.subTest("renamed after an edit"):
            stamped(edit_then_renumber)
            held(self.root)
        with self.subTest("deleted and added again"):
            self.setUp()
            stamped(re_add)
            held(self.root)
        with self.subTest("a shallow clone"):
            self.setUp()
            clone = self.root.with_name("clone")

            def shallow(area: Path) -> None:
                edit(area)
                self._git(
                    "clone", "-q", "--depth", "1", f"file://{self.root}", str(clone)
                )

            stamped(shallow)
            req = clone / "requirements.txt"  # the pin raised in the clone, too
            req.write_text(
                (self.root / "requirements.txt").read_text(), encoding="utf-8"
            )
            held(clone)
        with self.subTest("renamed without an edit: the earlier stamp"):
            self.setUp()
            stamped(renumber)
            _, report = scaffold.change_kind(self.root, "foo-bar", "fit")
            self.assertRegex(
                report, r"replaced\s+\S*01_measure\.py \(the stamp of an earlier pin, "
            )

    def test_an_uncommitted_stamp_file_is_named_as_such(self) -> None:
        """A stamp file git never saw differs from today's stamp: no evidence
        whose text it is, and the refusal says that instead of "edited". The
        twin: committed, an edit is named an edit (above)."""
        area, _, _ = self._compute_area_with_work()
        self._git("init", "-q")
        script = area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# mine\n")
        with self.assertRaises(console.Refused) as caught:
            scaffold.change_kind(self.root, "foo-bar", "fit")
        self.assertIn(
            "01_measure.py: differs from the compute stamp and was never committed",
            str(caught.exception),
        )

    def test_an_edit_committed_with_the_stamp_still_holds(self) -> None:
        """Without a pin raise this labkit's templates are the ones the area
        was stamped from: a difference committed with the stamp is an edit
        and holds, as before — also when a lock file appears later, which
        names no other labkit than the pin it had."""
        area, _, _ = self._compute_area_with_work()
        script = area / "scripts" / "01_measure.py"
        script.write_text(script.read_text(encoding="utf-8") + "# mine\n")
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("commit", "-qm", "stamp with an edit")
        for step in ("stamped", "commented", "locked"):
            if step == "commented":  # a note beside the pin pins no other labkit
                req = self.root / "requirements.txt"
                req.write_text(
                    re.sub(
                        r"(labkit\.git@\S+)", r"\1  # the lab's pin", req.read_text()
                    ),
                    encoding="utf-8",
                )
                self._git("commit", "-qam", "note the pin")
            if step == "locked":
                (self.root / "requirements.lock").write_text(
                    "labkit @ git+https://github.com/kmax-tech/labkit.git@0123abc\n",
                    encoding="utf-8",
                )
                self._git("add", "requirements.lock")
                self._git("commit", "-qm", "lock")
            with self.subTest(step=step), self.assertRaises(console.Refused) as caught:
                scaffold.change_kind(self.root, "foo-bar", "fit")
            self.assertIn(
                "01_measure.py: edited since the compute stamp", str(caught.exception)
            )

    def test_explore_refuses_the_flags_of_an_area_stamp(self) -> None:
        """`--explore` dropped `--kind`, `--repeat-cost`, `--model` and
        `--report` without a word: the person believed them stamped. Each is
        refused with nothing written; the twin, `--explore` alone, stamps
        (below)."""
        argv = ["exp", "foo-bar", "--repo", str(self.root), "--explore"]
        explore = self.root / "experiments" / "explore" / "foo-bar.py"
        for extra in (
            ["--kind", "fit"],
            ["--repeat-cost", "low"],
            ["--model"],
            ["--report"],
        ):
            with self.subTest(extra=extra):
                err = io.StringIO()
                with (
                    contextlib.redirect_stderr(err),
                    self.assertRaises(SystemExit) as caught,
                ):
                    quiet(scaffold.main, [*argv, *extra])
                self.assertEqual(caught.exception.code, 2)
                self.assertIn("--explore stamps only", err.getvalue())
                self.assertFalse(explore.exists())

    def test_change_kind_with_explore_is_refused_before_anything_is_written(
        self,
    ) -> None:
        """`--explore` returned before the `--change-kind` guard: the pair
        stamped the explore file and exited 0 (audit 2026-10-27, C13). It is
        refused with nothing written; the twin, `--explore` alone, stamps."""
        argv = ["exp", "foo-bar", "--repo", str(self.root)]
        explore = self.root / "experiments" / "explore" / "foo-bar.py"
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            quiet(scaffold.main, [*argv, "--explore", "--change-kind", "--kind", "fit"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--change-kind takes only --kind", err.getvalue())
        self.assertFalse(explore.exists())
        self.assertEqual(quiet(scaffold.main, [*argv, "--explore"]), 0)
        self.assertTrue(explore.is_file())

    def _dying_midway(self, part: str):  # noqa: ANN202 — a patch context
        """`Path.write_text` that truncates a file whose name holds PART,
        writes half of the text and fails as a full disk does — the write
        of an existing file dying midway."""
        real = Path.write_text

        def write_text(path: Path, data: str, *a, **kw) -> int:  # noqa: ANN002, ANN003
            if part in path.name:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(data[: len(data) // 2])
                raise OSError(28, "No space left on device (simulated)")
            return real(path, data, *a, **kw)

        return mock.patch.object(Path, "write_text", write_text)

    def _rewrites(self) -> dict[str, tuple[Path, Callable[[], object]]]:
        """{flag: (protocol, the call rewriting it)} — `--report` on a high
        area `other`, `--change-kind` on the computation `foo-bar`."""
        _, proto, _ = self._compute_area_with_work()
        quiet(scaffold.stamp_area, self.root, "other", "high", kind="fit")
        (high,) = (self.root / "experiments").glob("*-other")
        return {
            "--report": (
                high / "PROTOCOL-other.md",
                lambda: scaffold.stamp_area(self.root, "other", report=True),
            ),
            "--change-kind": (
                proto,
                lambda: scaffold.change_kind(self.root, "foo-bar", "fit"),
            ),
        }

    def test_a_write_that_dies_midway_leaves_the_protocol_whole(self) -> None:
        """`--report` and `--change-kind` rewrote the protocol in place
        (`Path.write_text`): a write that died midway left it truncated
        (audit 2026-10-27, doubled homes: protocols written non-atomically).
        Both write through `files.write_atomic`, which keeps the old file's
        mode."""
        for flag, (protocol, call) in self._rewrites().items():
            with self.subTest(flag=flag):
                before = protocol.read_text(encoding="utf-8")
                with self._dying_midway("PROTOCOL-"), self.assertRaises(OSError):
                    quiet(call)
                self.assertEqual(protocol.read_text(encoding="utf-8"), before)

    def test_the_twin_a_whole_rewrite_leaves_no_staging_file(self) -> None:
        for flag, (protocol, call) in self._rewrites().items():
            with self.subTest(flag=flag):
                before = protocol.read_text(encoding="utf-8")
                quiet(call)
                self.assertNotEqual(protocol.read_text(encoding="utf-8"), before)
                self.assertEqual(
                    [p for p in protocol.parent.rglob(".*") if ".tmp" in p.name], []
                )

    def test_a_kind_change_that_dies_midway_leaves_the_script_whole(self) -> None:
        """The stamp files `--change-kind` replaces go through
        `files.write_atomic` too: the script it was writing stays as it was."""
        area, _, _ = self._compute_area_with_work()
        script = area / "scripts" / "01_measure.py"
        before = script.read_text(encoding="utf-8")
        with self._dying_midway("01_measure"), self.assertRaises(OSError):
            quiet(scaffold.change_kind, self.root, "foo-bar", "fit")
        self.assertEqual(script.read_text(encoding="utf-8"), before)

    def test_a_kind_change_that_fails_at_the_protocol_changes_nothing(self) -> None:
        """The scripts were written before the protocol: a protocol write that
        died left the scripts of the new kind beside the old protocol, and a
        second `--change-kind` was refused as "edited since the stamp"
        (phase-1 leftover). Every file is staged first (`files.write_all`):
        the area stays as it was, and the change runs again."""
        area, _, _ = self._compute_area_with_work()

        def snapshot() -> dict[str, str]:
            return {
                str(p.relative_to(area)): p.read_text(encoding="utf-8")
                for p in sorted(area.rglob("*"))
                if p.is_file()
            }

        before = snapshot()
        with self._dying_midway("PROTOCOL-"), self.assertRaises(OSError):
            quiet(scaffold.change_kind, self.root, "foo-bar", "fit")
        self.assertEqual(snapshot(), before)
        quiet(scaffold.change_kind, self.root, "foo-bar", "fit")
        self.assertNotEqual(snapshot(), before)

    def test_the_kind_refusal_asks_the_questions(self) -> None:
        """Without `--kind` the refusal prints the same questions as the
        help, training first."""
        with self.assertRaises(console.Refused) as caught:
            scaffold.asked_kind(None)
        self.assertIn(scaffold.KIND_QUESTIONS, str(caught.exception))

    def test_init_exp_from_inside_the_area_finds_the_lab(self) -> None:
        """Run from an area directory, labkit-init called the area "not a lab
        repo" (cloud judge probe, 2026-10-14); it finds the lab above, as git
        finds its repo."""
        import os

        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
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
        self.assertIsNone(scaffold.lab_root(outside))  # repo.lab_root: none above

    def test_a_freshly_stamped_head_cannot_be_frozen_as_stamped(self) -> None:
        """The stamp's promise sentences are `<…>`; setting frozen = true
        without writing them is a must gap, not a registration."""
        from labkit.formats import protocol_check

        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
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

        from labkit.run import batch

        import models_fixture

        models_fixture.serve(
            self, (self.root / "models.toml").read_text(encoding="utf-8")
        )
        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
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
        jobs = [
            {"id": f"registered:{x}", "lane": "registered", "text": x} for x in "ab"
        ]
        with mock.patch.object(measure.lanes.llm, "complete_many") as calls:
            with self.assertRaises(batch.InstrumentError):
                quiet(measure.measure, measure.CONFIG, jobs, out)
            calls.assert_not_called()
        out.unlink()
        own = measure.instrument(measure.CONFIG)
        with batch.Store(out, instrument=own) as store:
            store.append({"id": "registered:a", "answer": "Yes"})
        with mock.patch.object(
            measure.lanes.llm, "complete_many", return_value=["No"]
        ) as calls:
            quiet(measure.measure, measure.CONFIG, jobs, out)
        self.assertEqual(calls.call_count, 1)  # only registered:b was asked

    def test_the_probe_names_the_area_test_file_and_its_case_list(self) -> None:
        """The probe printed `tests/test_<NN>_<name>.py PARSER_CASES`: the
        placeholder unreplaced in the scripts, and a list the test computes
        rather than holds (cloud judge probe, 2026-10-14)."""
        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
        script = (self.area() / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        # the area names its test; `lanes` prints "paste into <it> PROBE_CASES"
        self.assertIn('probe_cases_in="tests/test_01_foo_bar.py"', script)
        self.assertNotIn("<NN>", script)
        self.assertTrue((self.root / "tests" / "test_01_foo_bar.py").is_file())

    def test_every_stamped_placeholder_is_one_line(self) -> None:
        stamps = (
            ("full", {}),
            ("quick", {"repeat_cost": "low"}),
            ("judge", {"repeat_cost": "low", "model": "haiku"}),
        )
        for name, kw in stamps:
            quiet(scaffold.stamp_area, self.root, name, **kw, kind="fit")
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

    def test_minutes_without_a_model_stamps_the_estimator_skeleton(self) -> None:
        """2026-10-17: nine of nine pilot attempts were classical ML and got the
        prompt skeleton. Without `--model` at high repeat cost the instrument is
        an estimator: no prompt, no parser, a permuted-label null lane, the
        promise constants in its words, and the model-shaped fields answered."""
        from labkit.formats import promises, protocol_check

        quiet(scaffold.stamp_area, self.root, "foo-bar", repeat_cost="high", kind="fit")
        area = self.area()
        script = (area / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        self.assertIn("def make_estimator", script)
        self.assertNotIn("PROMPT", script)
        test = (self.root / "tests" / "test_01_foo_bar.py").read_text(encoding="utf-8")
        self.assertIn("measure_01_foo_bar", test)
        self.assertIn("chance_of", test)
        proto = (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
        self.assertIn("**Model / tool:** n/a — no model call", proto)
        model_line = next(ln for ln in proto.splitlines() if "**Model / tool:**" in ln)
        self.assertNotIn("<", model_line)  # an n/a with a `<…>` tail read as filled
        # not owed without a model, so not stamped at all (audit 2026-10-27,
        # third, I9): an "n/a" answered a field nobody asks for
        self.assertNotIn("**Prompt (verbatim, per variant):**", proto)
        self.assertNotIn("```text", proto)  # the prompt's example block is gone
        self.assertNotIn("**Parser cases harvested:**", proto)  # no model text to parse
        self.assertFalse(protocol_check.model_named(proto))
        block = promises.parse_block(proto)
        assert block is not None
        consts = promises.all_constants(block)
        self.assertEqual(consts, {"margin": 0.25, "max_empty": 0, "null_band": 0.1})
        self.assertNotIn("null_band_items", proto)
        self.assertIn("permuted-label lane", proto)
        # protocol-check reads the stamp as a clean pilot with placeholders only
        self.assertEqual(
            protocol_cuts.estimator_placeholders.__name__, "estimator_placeholders"
        )

    def test_the_stamped_estimator_formula_holds_the_contract(self) -> None:
        """The stamped `evaluate_rows` runs without any estimator library:
        perfect against chance fires [C1] exactly at the bar (fractions), a
        lane without gold is refused, the test lane is counted, never scored."""
        import importlib.util
        import sys
        from dataclasses import replace

        quiet(scaffold.stamp_area, self.root, "foo-bar", repeat_cost="high", kind="fit")
        path = self.area() / "scripts" / "01_measure.py"
        spec = importlib.util.spec_from_file_location("stamped_estimator", path)
        assert spec is not None and spec.loader is not None
        measure = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = measure
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(measure)
        self.assertEqual(
            (measure.CONFIG.margin, measure.CONFIG.max_empty, measure.CONFIG.null_band),
            (0.25, 0, 0.1),
        )

        def lane(name: str, correct: int, gold_none: bool = False) -> list[dict]:
            golds = ["pos"] * 6 + ["neg"] * 6
            return [
                {
                    "id": f"{name}:{i}",
                    "lane": name,
                    "item": str(i),
                    "fold": 0,
                    "pred": g if i < correct else ("neg" if g == "pos" else "pos"),
                    "gold": None if gold_none and i == 0 else g,
                }
                for i, g in enumerate(golds)
            ]

        test_rows = [
            {
                "id": "test:a",
                "lane": "test",
                "item": "a",
                "fold": None,
                "pred": "pos",
                "gold": None,
            }
        ]
        m = measure.evaluate_rows(lane("registered", 12) + lane("null", 6) + test_rows)
        self.assertEqual(
            (m["c1_pass"], m["a2_pass"], m["n_test"], m["a2_chance"]),
            (True, True, 1, 0.5),
        )
        # the scored items per gold; the test lane's item has none and is no class
        self.assertEqual(m["scored_class_counts"], {"neg": 6, "pos": 6})
        regression = replace(measure.CONFIG, score="r2")
        numeric = [
            {**r, "pred": 1.0, "gold": float(i % 3)}
            for i, r in enumerate(lane("registered", 12) + lane("null", 6))
        ]
        self.assertNotIn(
            "scored_class_counts", measure.evaluate_rows(numeric, regression)
        )
        wide = replace(measure.CONFIG, null_band=0.25)
        at_bar = measure.evaluate_rows(lane("registered", 8) + lane("null", 5), wide)
        self.assertIs(at_bar["c1_pass"], True)  # 8/12 >= 5/12 + 1/4 exactly
        with self.assertRaisesRegex(ValueError, "without gold"):
            measure.evaluate_rows(
                lane("registered", 12, gold_none=True) + lane("null", 6)
            )
        with self.assertRaises(NotImplementedError):
            measure.make_estimator(0)

    def test_the_stamped_estimator_test_passes_as_stamped(self) -> None:
        """The area's test (`test-estimator.py.template`) runs green on the
        fresh stamp: the resolution check needs no estimator library."""
        import subprocess
        import sys

        quiet(scaffold.stamp_area, self.root, "foo-bar", repeat_cost="high", kind="fit")
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                str(self.root / "tests" / "test_01_foo_bar.py"),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("10 passed", r.stdout)

    def test_the_stamp_declares_the_model_in_the_head(self) -> None:
        """Phase 4 (2026-10-21): `--model <alias>` writes `[model] alias`, a bare
        `--model` its placeholder, no flag no table; the prose field asks for
        the instrument's sentence, not the alias."""
        quiet(
            scaffold.stamp_area,
            self.root,
            "with-alias",
            repeat_cost="low",
            kind="apply",
            model="haiku",
        )
        text = next(self.root.glob("experiments/*with-alias/PROTOCOL-*.md")).read_text()
        m = protocol_block.model(text)
        assert m is not None
        self.assertEqual((m.alias, m.arms), ("haiku", {}))
        self.assertNotIn("Arm `before`", text)
        quiet(
            scaffold.stamp_area,
            self.root,
            "bare-flag",
            repeat_cost="low",
            model=True,
            kind="apply",
        )
        text = next(self.root.glob("experiments/*bare-flag/PROTOCOL-*.md")).read_text()
        m = protocol_block.model(text)
        assert m is not None
        self.assertIsNone(m.alias)
        quiet(
            scaffold.stamp_area,
            self.root,
            "no-model",
            repeat_cost="low",
            kind="compute",
        )
        text = next(self.root.glob("experiments/*no-model/PROTOCOL-*.md")).read_text()
        self.assertIsNone(protocol_block.model(text))

    def test_a_bare_model_flag_keeps_the_prompt_skeleton(self) -> None:
        """`--model` without an alias still means a model in the loop."""
        quiet(scaffold.stamp_area, self.root, "foo-bar", model=True, kind="apply")
        script = (self.area() / "scripts" / "01_measure.py").read_text(encoding="utf-8")
        self.assertIn("PROMPT", script)
        self.assertIn('MODEL = "TODO-alias"', script)

    def test_a_model_alias_fills_the_skeleton(self) -> None:
        quiet(scaffold.stamp_area, self.root, "foo-bar", model="haiku", kind="apply")
        self.assertIn(
            "haiku",
            (self.area() / "scripts" / "01_measure.py").read_text(encoding="utf-8"),
        )

    def test_explore_lands_outside_areas_and_moves_in_with_the_area(self) -> None:
        scaffold.stamp_explore(self.root / "experiments", "foo-bar")
        f = self.root / "experiments" / "explore" / "foo-bar.py"
        ast.parse(f.read_text(encoding="utf-8"))
        quiet(scaffold.stamp_area, self.root, "foo-bar", kind="fit")
        self.assertTrue((self.area() / "explore" / "foo-bar.py").is_file())
        self.assertFalse(f.exists())

    def test_the_step_after_explore_is_a_command_that_runs(self) -> None:
        """After `--explore` the printed next step was `labkit-init exp
        foo-bar`, which is refused without `--kind` (audit 2026-10-27, B4).
        It prints one complete command per kind with the questions that
        choose; each runs from the lab and takes the explore file along."""
        import os
        import shlex

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scaffold.main(["exp", "foo-bar", "--explore", "--repo", str(self.root)])
        printed = re.findall(r"^\s*(labkit-init exp .*)$", out.getvalue(), re.M)
        self.assertEqual(
            printed,
            [
                f"labkit-init exp foo-bar --kind {k} --repeat-cost low"
                for k in protocol_block.KINDS
            ],
        )
        self.assertIn(scaffold.KIND_QUESTIONS, out.getvalue())
        explore = self.root / "experiments" / "explore" / "foo-bar.py"
        # the explore file's own text names the step with its kind too
        self.assertEqual(
            re.findall(r"labkit-init exp foo-bar(?! --kind)", explore.read_text()), []
        )
        for cmd in printed:
            with self.subTest(cmd=cmd):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "lab"
                    scaffold.stamp_lab(root, "lab")
                    (root / "experiments" / "explore").mkdir()
                    (root / "experiments" / "explore" / "foo-bar.py").write_text(
                        explore.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                    cwd = os.getcwd()
                    try:
                        os.chdir(root)
                        rc = quiet(scaffold.main, shlex.split(cmd)[1:])
                    finally:
                        os.chdir(cwd)
                    self.assertEqual(rc, 0)
                    (area,) = (root / "experiments").glob("[0-9]*-foo-bar")
                    self.assertTrue((area / "explore" / "foo-bar.py").is_file())

    def test_a_repo_without_the_lab_layout_is_refused(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        with self.assertRaisesRegex(console.Refused, "labkit-init lab"):
            scaffold.stamp_area(bare, "foo-bar")


class AreaNumbers(unittest.TestCase):
    """A new area's number is one above every number the repository holds —
    this tree, `_archiv/`, every branch, every other worktree — and
    `labkit-init numbers` holds one number per area (labkit-paper,
    2026-10-27: two branches of one repo each had their next area at 12)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "lab"
        self.root.mkdir()
        scaffold.stamp_lab(self.root, "lab")
        self.exp = self.root / "experiments"
        self._git("init", "-q", "-b", "main")
        self._git("add", "-A")
        self._git("commit", "-qm", "lab")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _git(self, *args: str, cwd: Path | None = None) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=cwd or self.root,
            check=True,
            capture_output=True,
        )

    def _areas(self, *names: str) -> None:
        for name in names:
            (self.exp / name).mkdir(parents=True)
            (self.exp / name / "README.md").write_text("x\n", encoding="utf-8")

    def test_paths_name_living_and_archived_areas(self) -> None:
        paths = [
            "01-a/README.md",
            "_archiv/02-b/data/raw/.gitkeep",
            "explore/x.py",
            ".gitkeep",
            "_archiv/.gitkeep",
            "03-c",  # a file, no area
        ]
        self.assertEqual(scaffold.area_dirs_in(paths), {"01-a", "_archiv/02-b"})

    def test_the_next_number_is_one_above_every_place(self) -> None:
        nxt = scaffold.next_experiment_number
        self.assertEqual(nxt(set(), {}), "01")
        self.assertEqual(nxt({"01-a", "_archiv/05-e"}, {}), "06")
        self.assertEqual(nxt({"11-a"}, {"branch side": {"12-b", "13-c"}}), "14")
        self.assertEqual(nxt({"11-a"}, {"branch old": {"03-c"}}), "12")
        self.assertEqual(nxt(set(), {"branch side": {"99-z"}}), "100")

    def test_a_number_another_branch_took_is_not_handed_out(self) -> None:
        self._git("checkout", "-qb", "side")
        quiet(scaffold.stamp_area, self.root, "on-side", kind="fit")
        self._git("add", "-A")
        self._git("commit", "-qm", "side")
        self._git("checkout", "-q", "main")
        self.assertFalse((self.exp / "01-on-side").exists())
        area, report = quiet(scaffold.stamp_area, self.root, "on-main", kind="fit")
        self.assertEqual(area.name, "02-on-main")
        self.assertIn("number taken   01-on-side on branch side", report)

    def test_an_area_in_another_worktree_counts_before_its_commit(self) -> None:
        other = Path(self.tmp.name) / "other"
        self._git("worktree", "add", "-q", "-b", "other", str(other))
        quiet(scaffold.stamp_area, other, "there", kind="fit")  # not committed
        area, report = quiet(scaffold.stamp_area, self.root, "here", kind="fit")
        self.assertEqual(area.name, "02-here")
        self.assertIn("01-there on worktree ", report)

    def test_without_other_places_the_numbers_leave_no_gap(self) -> None:
        """The twin: one branch, one worktree — the numbers count up as before."""
        quiet(scaffold.stamp_area, self.root, "first", kind="fit")
        area, report = quiet(scaffold.stamp_area, self.root, "second", kind="fit")
        self.assertEqual(area.name, "02-second")
        self.assertNotIn("number taken", report)

    def test_two_areas_of_one_number_are_named_in_the_tree_and_the_index(self) -> None:
        self._areas("12-a", "12-b")
        code, report = scaffold.number_check(self.root, staged=False)
        self.assertEqual(code, 1)
        self.assertIn(
            "number 12 is carried by 2 areas in the working tree: "
            "experiments/12-a, experiments/12-b",
            report,
        )
        self.assertIn("move the other area to the next free number, 13", report)
        # nothing staged yet: the index holds neither area
        self.assertEqual(scaffold.number_check(self.root, staged=True)[0], 0)
        self._git("add", "experiments")
        code, report = scaffold.number_check(self.root, staged=True)
        self.assertEqual(code, 1)
        self.assertIn("in the index: experiments/12-a, experiments/12-b", report)

    def test_an_archived_area_keeps_its_number(self) -> None:
        self._areas("12-a", "_archiv/12-b")
        code, report = scaffold.number_check(self.root, staged=False)
        self.assertEqual(code, 1)
        self.assertIn("experiments/12-a, experiments/_archiv/12-b", report)

    def test_one_number_per_area_passes(self) -> None:
        self._areas("12-a", "_archiv/13-b")
        self._git("checkout", "-qb", "side")
        self._areas("15-c")
        self._git("add", "experiments/15-c")
        self._git("commit", "-qm", "side")
        self._git("checkout", "-q", "main")
        self.assertEqual(
            scaffold.number_check(self.root, staged=False),
            (
                0,
                "labkit-init numbers: 2 area(s) in the working tree, each with a "
                "number of its own; next free number 16",
            ),
        )

    def test_staged_outside_a_repository_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scaffold.stamp_lab(Path(tmp), "lab")
            with self.assertRaisesRegex(console.Refused, "no index to read"):
                scaffold.number_check(Path(tmp), staged=True)
            self.assertEqual(scaffold.number_check(Path(tmp), staged=False)[0], 0)


class Report(unittest.TestCase):
    """--report answers what a model-free protocol cannot: seed, noise, parser."""

    def stamped(self, model: bool | str) -> str:
        """An area stamped with MODEL (the head's `[model]`, phase 4), then promoted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold.stamp_lab(root, "lab")
            quiet(scaffold.stamp_area, root, "foo-bar", model=model, kind="apply")
            (proto,) = root.glob("experiments/*/PROTOCOL-foo-bar.md")
            quiet(scaffold.stamp_area, root, "foo-bar", report=True, kind="fit")
            return proto.read_text(encoding="utf-8")

    def test_no_model_fills_the_parser_field_and_leaves_randomness_owed(self) -> None:
        """2026-10-17: a seeded estimator owes its randomness fields; --report
        no longer writes "no seed, spread 0" into them (Sonnet v2 t5)."""
        text = self.stamped(False)
        self.assertNotIn("**Parser cases harvested:**", text)  # no model text to parse
        self.assertNotIn("n/a — deterministic", text)
        self.assertRegex(text, r"\*\*Randomness controls †:\*\* <")
        self.assertRegex(text, r"\*\*Noise ceiling → threshold †:\*\* <")

    def test_a_model_leaves_them_open(self) -> None:
        self.assertNotIn("auto-filled", self.stamped("haiku"))


class NextStepFields(unittest.TestCase):
    """The first next step names what every kind fills (terms, question,
    unit, data, exclusions — AGENTS.md's "every kind"), at both costs, and
    the title says repeat_cost, not "lane" (audit 2026-10-27, third, I12).
    A kind with a bar names its [[promise]] constants as the agent's to set,
    the low cut names 00_prepare.py where the skeleton has one, and the
    adoption step puts the Conclusion first and the task's output file
    after it (Haiku start reading, 2026-10-28)."""

    def steps(self, cost: str, kind: str, model: bool) -> str:
        return scaffold.next_steps(
            Path("experiments/01-x"), "x", "01", cost, kind, model
        )

    def test_every_kind_names_terms_question_unit_data_exclusions(self):
        for cost in ("low", "high"):
            for kind in ("compute", "fit", "apply"):
                for model in (False, True):
                    with self.subTest(cost=cost, kind=kind, model=model):
                        out = self.steps(cost, kind, model)
                        self.assertIn("terms, question, unit, data, exclusions", out)
                        self.assertNotIn("lane high", out)
                        self.assertNotIn("into the protocol's raw output", out)
                        self.assertIn("the Conclusion, then `protocol-fill", out)
                        self.assertIn(
                            "output file is written from that run only after", out
                        )

    def test_a_bar_names_its_constants_a_computation_none(self):
        for cost in ("low", "high"):
            for model in (False, True):
                with self.subTest(cost=cost, model=model):
                    self.assertNotIn(
                        "[[promise]] constants", self.steps(cost, "compute", model)
                    )
                    for kind in ("fit", "apply"):
                        self.assertIn(
                            "[[promise]] constants", self.steps(cost, kind, model)
                        )

    def test_the_low_cut_names_the_prepare_script_where_the_skeleton_has_one(self):
        self.assertNotIn("00_prepare.py", self.steps("low", "compute", False))
        for kind in ("fit", "apply"):
            for model in (False, True):
                with self.subTest(kind=kind, model=model):
                    self.assertIn(
                        "scripts/00_prepare.py", self.steps("low", kind, model)
                    )


class OwedCut(unittest.TestCase):
    """The full form stamps only the fields its kind and model owe — the
    rule the checker applies (`protocol_check.not_owed`); a high
    computation without a model was stamped a data profile, a prompt and
    instrument checks (audit 2026-10-27, third, I9)."""

    def test_a_high_computation_is_stamped_without_model_and_criterion_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            scaffold.stamp_lab(root, "lab")
            compute = scaffold.protocol_stamp(root, "c", "high", "compute", False, True)
            apply_model = scaffold.protocol_stamp(
                root, "a", "high", "apply", "haiku", True
            )
        for label in ("Data profile", "Prompt (verbatim", "Model I/O", "Instrument check",
                      "Resolution check", "Noise ceiling", "Render check", "Parser cases",
                      "Raw output"):  # fmt: skip
            with self.subTest(label=label):
                self.assertNotIn(f"**{label}", compute)
                self.assertIn(f"**{label}", apply_model)
        self.assertIn("**Question / hypothesis:**", compute)

    def test_raw_output_asks_for_the_runs_rows_not_the_probes(self):
        # the estimator stamp asked for rows "as --probe prints them" in a
        # field written after the run (audit 2026-10-27, third, I11)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            scaffold.stamp_lab(root, "lab")
            fit_model = scaffold.protocol_stamp(root, "f", "high", "fit", "haiku", True)
            fit = scaffold.protocol_stamp(root, "g", "high", "fit", False, True)
        (line,) = [ln for ln in fit_model.splitlines() if "**Raw output" in ln]
        self.assertIn("read from the run's kept output", line)
        self.assertNotIn("--probe", line)
        self.assertNotIn("**Raw output", fit)

    def test_a_fit_with_a_model_is_not_stamped_no_model_call(self):
        # the estimator stamp wrote "n/a — no model call" beside `[model]
        # alias` (audit 2026-10-27, third, I12)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            scaffold.stamp_lab(root, "lab")
            for cost in ("low", "high"):
                with self.subTest(cost=cost):
                    stamped = scaffold.protocol_stamp(
                        root, "f", cost, "fit", "haiku", False
                    )
                    self.assertIn('alias = "haiku"', stamped)
                    self.assertNotIn("no model call", stamped)
                    plain = scaffold.protocol_stamp(
                        root, "g", cost, "fit", False, False
                    )
                    self.assertIn("no model call", plain)


class Cli(unittest.TestCase):
    def test_lab_then_exp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "x"
            # deadbee is no commit: the comparison with the pin has its own tests
            with mock.patch.object(scaffold, "lab_templates_off_ref", return_value=[]):
                self.assertEqual(
                    quiet(scaffold.main, ["lab", str(root), "--labkit-ref", "deadbee"]),
                    0,
                )
            self.assertIn(
                "@deadbee", (root / "requirements.txt").read_text(encoding="utf-8")
            )
            self.assertEqual(
                quiet(
                    scaffold.main,
                    [
                        "exp",
                        "foo",
                        "--repo",
                        str(root),
                        "--repeat-cost",
                        "low",
                        "--kind",
                        "compute",
                    ],
                ),
                0,
            )
            self.assertTrue(
                (root / "experiments" / "01-foo" / "PROTOCOL-foo.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()


class ModelNamed(unittest.TestCase):
    """`--report` asks `protocol_check.model_named`, since phase 4 the head's
    `[model]` table: prose that says "—", "none" or names an alias decides
    nothing (until 0.100.0 a regex over the Model / tool line did, and a `—`
    or a `†` label read as "a model", audit 2026-10-15)."""

    PARSER = "- **Parser cases harvested:** <cases>\n"

    def test_without_a_model_table_the_parser_field_is_filled(self):
        for value in ("—", "none", "gpt-oss"):
            text = (
                head(repeat_cost="high")
                + f"- **Model / tool †:** {value}\n"
                + self.PARSER
            )
            filled, n = protocol_cuts.auto_fill_deterministic(text)
            self.assertEqual(n, 1, value)
            self.assertIn("n/a — no model", filled)

    def test_a_model_table_leaves_it_open(self):
        text = (
            head(repeat_cost="high", model="gpt-oss")
            + "- **Model / tool:** none\n"
            + self.PARSER
        )
        self.assertEqual(protocol_cuts.auto_fill_deterministic(text), (text, 0))
