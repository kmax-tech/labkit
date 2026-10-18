"""The stamp check (plan II, I7): a stamped area held to its instrument by
two exact facts — the measure script asks a model exactly when the head
says so, and the stamped contract tests survive by name, unskipped. Every
fresh stamp is silent (the twin); a bent one is named with file and fact."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labkit import claude_hooks, preflight, protocol_block, scaffold, skeletons  # noqa: E402
from labkit import stamp_check  # noqa: E402

NULL_TEST = "test_null_like_registered_lane_stays_silent"


def stamped(**kw) -> tuple[Path, Path]:
    """(repo root, area) of a fresh lab with one area stamped under KW."""
    tmp = tempfile.mkdtemp()
    root = Path(tmp) / "probe"
    with contextlib.redirect_stdout(io.StringIO()):
        scaffold.stamp_lab(root, "probe", ref=None)
        area, _ = scaffold.stamp_area(root, "foo-bar", **kw)
    return root, area


def head_of(area: Path) -> protocol_block.Head:
    return protocol_block.head(
        (area / "PROTOCOL-foo-bar.md").read_text(encoding="utf-8")
    )


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


class FreshStamps(unittest.TestCase):
    def test_every_fresh_stamp_holds_its_instrument(self) -> None:
        for kw in (
            {"cost": "minutes", "model": "haiku"},
            {"cost": "minutes"},
            {"cost": "seconds"},
            {"cost": "seconds", "model": "haiku"},
        ):
            with self.subTest(**kw):
                root, area = stamped(**kw)
                self.assertEqual(
                    stamp_check.stamp_findings(area, head_of(area), root), []
                )

    def test_the_contract_tests_are_the_templates_test_functions(self) -> None:
        for instrument, skeleton in skeletons.SKELETONS.items():
            names = skeletons.contract_tests(instrument)
            stamped_names = re.findall(
                r"^def (test_\w+)\(", skeletons.template(skeleton.test), re.M
            )
            self.assertEqual(list(names), stamped_names, instrument)
            self.assertGreaterEqual(len(names), 3, instrument)

    def test_a_head_without_an_instrument_holds_nothing(self) -> None:
        """protocol-check names the placeholder; there is no instrument to hold to."""
        root, area = stamped(cost="minutes", model="haiku")
        proto = area / "PROTOCOL-foo-bar.md"
        edit(proto, 'instrument = "apply"', 'instrument = "<apply | fit | count>"')
        self.assertEqual(stamp_check.stamp_findings(area, head_of(area), root), [])


class ModelCall(unittest.TestCase):
    def test_a_model_script_without_the_llm_import_is_named(self) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        script = area / "scripts" / "01_measure.py"
        edit(
            script,
            "from labkit import batch, llm, promises, runlog",
            "from labkit import batch, promises, runlog",
        )
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn(
            'instrument = "apply", but the script never imports labkit.llm', finding
        )
        self.assertTrue(finding.startswith("scripts/01_measure.py"))

    def test_a_model_script_that_imports_but_never_asks_is_named(self) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        script = area / "scripts" / "01_measure.py"
        edit(
            script,
            "answers = llm.complete_many(model, [render(j) for j in chunk])",
            "answers = ['x' for j in chunk]",
        )
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn("never calls llm.complete or llm.complete_many", finding)

    def test_a_fit_or_count_script_with_the_llm_import_is_named(self) -> None:
        for kw, instrument in (
            ({"cost": "minutes"}, "fit"),
            ({"cost": "seconds"}, "count"),
        ):
            with self.subTest(instrument=instrument):
                root, area = stamped(**kw)
                script = area / "scripts" / "01_measure.py"
                script.write_text(
                    "from labkit import llm\n" + script.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
                self.assertIn(
                    f'imports labkit.llm, but the head says instrument = "{instrument}"',
                    finding,
                )

    def test_llm_use_reads_every_import_form(self) -> None:
        cases = {
            "from labkit import llm\nllm.complete('a', 'b')\n": (True, True),
            "from labkit import llm as backend\nbackend.complete_many('a', [])\n": (
                True,
                True,
            ),
            "import labkit.llm\nlabkit.llm.complete('a', 'b')\n": (True, True),
            "import labkit.llm as L\nL.complete('a', 'b')\n": (True, True),
            "from labkit.llm import complete as ask\nask('a', 'b')\n": (True, True),
            "from labkit import llm\nllm.provenance('a')\n": (True, False),
            "from labkit import runlog\nrunlog.run('t', {})\n": (False, False),
            "complete('a', 'b')\n": (False, False),
        }
        for source, (imported, called) in cases.items():
            with self.subTest(source=source):
                use = stamp_check.llm_use(source)
                self.assertEqual((use.imported, use.called), (imported, called))

    def test_a_missing_or_unparsable_script_is_named(self) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        script = area / "scripts" / "01_measure.py"
        script.write_text("def (\n", encoding="utf-8")
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn("not valid Python", finding)
        script.unlink()
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn("no scripts/01_measure.py", finding)


class ContractTests(unittest.TestCase):
    def test_a_renamed_or_deleted_contract_test_is_named(self) -> None:
        root, area = stamped(cost="minutes")
        test = root / "tests" / "test_01_foo_bar.py"
        edit(test, f"def {NULL_TEST}(", "def test_something_else(")
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn(f"the stamped contract test `{NULL_TEST}` is gone", finding)
        self.assertTrue(finding.startswith("test_01_foo_bar.py"))

    def test_a_skipped_contract_test_is_named(self) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        test = root / "tests" / "test_01_foo_bar.py"
        edit(
            test,
            f"def {NULL_TEST}(",
            f"@pytest.mark.skip(reason='later')\ndef {NULL_TEST}(",
        )
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn(f"`{NULL_TEST}` is skipped (@pytest.mark.skip)", finding)

    def test_a_split_test_file_keeps_the_contract_together(self) -> None:
        """The contract may be spread over test_<NN>_<name>_<part>.py files."""
        root, area = stamped(cost="seconds")
        test = root / "tests" / "test_01_foo_bar.py"
        text = test.read_text(encoding="utf-8")
        cut = text.index("def test_hidden_entries_do_not_count")
        test.write_text(text[:cut], encoding="utf-8")
        (finding,) = stamp_check.stamp_findings(area, head_of(area), root)
        self.assertIn("test_hidden_entries_do_not_count", finding)
        (root / "tests" / "test_01_foo_bar_more.py").write_text(
            "def test_hidden_entries_do_not_count():\n    assert True\n",
            encoding="utf-8",
        )
        self.assertEqual(stamp_check.stamp_findings(area, head_of(area), root), [])


class Stations(unittest.TestCase):
    def test_preflight_warns_before_the_freeze_and_blocks_after(self) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        edit(
            area / "scripts" / "01_measure.py",
            "from labkit import batch, llm, promises, runlog",
            "from labkit import batch, promises, runlog",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            preflight.preflight_area(area)
        self.assertIn(
            'WARNING: scripts/01_measure.py: instrument = "apply"', buf.getvalue()
        )
        edit(area / "PROTOCOL-foo-bar.md", "frozen = false", "frozen = true")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            preflight.preflight_area(area)
        self.assertIn(
            'BLOCKER: scripts/01_measure.py: instrument = "apply"', buf.getvalue()
        )

    def test_the_command_says_the_stamp_holds_or_what_bent(self) -> None:
        root, area = stamped(cost="minutes")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stamp_check.main([str(area)])
        self.assertEqual(
            (rc, buf.getvalue().strip()),
            (0, "stamp-check: 01-foo-bar: the stamp holds its instrument (fit)"),
        )
        edit(
            root / "tests" / "test_01_foo_bar.py",
            f"def {NULL_TEST}(",
            "def test_other(",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stamp_check.main([str(area)])
        self.assertEqual(rc, 1)
        self.assertIn(
            f"stamp-check: test_01_foo_bar.py: the stamped contract test `{NULL_TEST}` is gone",
            buf.getvalue(),
        )

    def test_the_post_change_hook_runs_it_on_a_script_and_on_the_area_test(
        self,
    ) -> None:
        root, area = stamped(cost="minutes", model="haiku")
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        self.addCleanup(os.environ.pop, "CLAUDE_PROJECT_DIR", None)
        script = area / "scripts" / "01_measure.py"
        edit(
            script,
            "from labkit import batch, llm, promises, runlog",
            "from labkit import batch, promises, runlog",
        )
        test = root / "tests" / "test_01_foo_bar.py"
        edit(test, f"def {NULL_TEST}(", "def test_other(")
        for path in (script, test):
            with self.subTest(path=path.name):
                event = {
                    "tool_name": "Write",
                    "tool_input": {"file_path": str(path)},
                    "cwd": str(root),
                    "session_id": "s-" + os.urandom(4).hex(),
                }
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = claude_hooks.post_change(event)
                self.assertEqual(rc, 0)
                ctx = json.loads(buf.getvalue())["hookSpecificOutput"][
                    "additionalContext"
                ]
                self.assertIn("never imports labkit.llm", ctx)
                self.assertIn(f"`{NULL_TEST}` is gone", ctx)
        self.assertEqual(
            claude_hooks.wants_check(Path("/r/experiments/01-x/scripts/01_measure.py")),
            "stamp",
        )
        self.assertEqual(
            claude_hooks.wants_check(Path("/r/tests/test_01_x.py")), "stamp"
        )
        self.assertIsNone(claude_hooks.wants_check(Path("/r/lib/scoring.py")))


if __name__ == "__main__":
    unittest.main()
