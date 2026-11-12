"""labkit-next before the chain: the repo's one area found, an area or a
protocol still missing, the fill line a gap is named with and the fields an
adoption would owe — no lab built. The chain itself, in a stamped lab:
tests/test_next_step.py."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from labkit.gates import next_step
from labkit.tools import next_command


def run_next(area: Path, cwd: Path) -> tuple[int, str, str]:
    """`labkit-next AREA` from CWD: exit code, stdout, stderr."""
    out, err = io.StringIO(), io.StringIO()
    old = Path.cwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = next_command.main([str(area)])
    finally:
        os.chdir(old)
    return rc, out.getvalue(), err.getvalue()


class BareNextFindsTheArea(unittest.TestCase):
    """`labkit-next` without an area speaks of the repo's one area, numbered
    or not (`repo.experiment_areas`); a folder without a protocol, the
    stamp's `experiments/explore/`, is no area."""

    def test_an_unnumbered_area_is_the_one_area(self):
        from labkit.formats import repo

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "experiments" / "explore").mkdir(parents=True)
            area = root / "experiments" / "lines"
            area.mkdir()
            self.assertEqual(repo.experiment_areas(root), [])
            (area / "PROTOCOL-lines.md").write_text("# x\n", encoding="utf-8")
            self.assertEqual(repo.experiment_areas(root), [area])
            (root / "experiments" / "02-other").mkdir()
            self.assertEqual(
                repo.experiment_areas(root), [root / "experiments" / "02-other", area]
            )


class BeforeTheChain(unittest.TestCase):
    def _bare(self, cwd: Path) -> tuple[int, str, str]:
        """`labkit-next` without an area, from CWD."""
        out, err = io.StringIO(), io.StringIO()
        old = Path.cwd()
        os.chdir(cwd)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = next_command.main([])
        finally:
            os.chdir(old)
        return rc, out.getvalue(), err.getvalue()

    def test_without_an_area_and_none_stamped_the_step_creates_one(self):
        """A bare `labkit-next` before any area exists names the stamp
        that creates one, not the usage line."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("no experiment area yet", out)
        self.assertIn("labkit-init exp <name> --kind", out)

    def test_without_an_area_the_one_area_is_taken(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            (Path(d) / "experiments" / "01-x").mkdir(parents=True)
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("labkit-next: experiments/01-x", out)

    def test_without_an_area_and_several_each_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            for name in ("01-x", "02-y"):
                (Path(d) / "experiments" / name).mkdir(parents=True)
            rc, out, err = self._bare(Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("experiments/01-x", err)
        self.assertIn("experiments/02-y", err)

    def test_an_area_without_a_protocol_is_told_to_register(self):
        with tempfile.TemporaryDirectory() as d:
            area = Path(d) / "experiments" / "01-x"
            area.mkdir(parents=True)
            rc, out, err = run_next(area, Path(d))
        self.assertEqual(rc, 0, err)
        self.assertIn("holds no protocol", out)
        self.assertIn("labkit-init exp", out)

    def test_staged_selection_without_a_repository_is_refused(self):
        """An index cannot be selected before the repository exists."""
        with tempfile.TemporaryDirectory() as d:
            area = Path(d) / "experiments" / "01-x"
            area.mkdir(parents=True)
            out, err = io.StringIO(), io.StringIO()
            with (
                contextlib.chdir(d),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                code = next_command.main([str(area), "--staged"])
        self.assertEqual(code, 2)
        self.assertIn("no git repository to read the index", err.getvalue())
        self.assertEqual(out.getvalue(), "")

    def test_a_fill_line_is_named_only_where_one_fill_closes_the_gap(self):
        """A placeholder is filled by protocol-fill; a field absent from the
        text is not (protocol-fill knows no field it cannot see): a † field
        comes with `labkit-init exp … --report`, another absent field is a
        line to write; a freeze key or a contradiction has no single step.
        So `next` never names a fill protocol-fill answers with "no field
        labelled"."""
        area = Path("experiments/01-x")
        line = next_step.fill_line
        self.assertEqual(
            line(area / "P.md", "Unit", absent=False),
            '`protocol-fill experiments/01-x/P.md "Unit=<value>"` fills the first',
        )
        self.assertEqual(
            line(area / "P.md", "[protocol] kind", absent=True),
            '`protocol-fill experiments/01-x/P.md "kind=<compute|fit|apply>"` fills the first',
        )
        absent = line(area / "P.md", "Why this design", absent=True)
        assert absent is not None
        self.assertTrue(
            absent.startswith("`labkit-init exp experiments/01-x --report` appends"),
            absent,
        )
        absent = line(area / "P.md", "Unit", absent=True)
        assert absent is not None
        self.assertIn("write the line `- **Unit:** …`", absent)
        for gap in (
            "[protocol] preflight_audit (frozen = true without the record named)",
            "[protocol] frozen",
        ):
            self.assertIsNone(line(area / "P.md", gap, absent=True), gap)

    def test_the_adoption_names_the_fields_it_would_owe_before_adopt(self):
        """One mouth: `next` asks `check_fields` what the adoption's state
        owes (`adopting`) — a frozen protocol's † result fields — and names
        the fill before `labkit-adopt`, which would refuse the written
        result for them. The twins: filled, or unfrozen, the adoption owes
        nothing more."""
        from protocol_fixture import head

        protocol = Path("experiments/01-x/PROTOCOL-x.md")
        daggered = (
            "- **Conclusion:** the bar was met.\n"
            "- **Question †:** <…>\n- **Did †:** <…>\n- **Expected or surprising †:** <…>\n"
            "- **Rival check †:** <…>\n- **Caps/drops †:** <…>\n- **Analysis audit †:** <…>\n"
        )
        frozen = head(repeat_cost="high", frozen=True, preflight_audit="n/a — test")
        step = next_step._adoption_owes(protocol, frozen + daggered, "r1")
        assert step is not None
        self.assertIn("adopting r1 would owe 6 field(s) still open", step.where)
        self.assertIn(
            '`protocol-fill experiments/01-x/PROTOCOL-x.md "Question †=<value>"`',
            step.next,
        )
        self.assertIn("labkit-adopt refuses", step.held)
        # absent altogether: the † fields come with --report
        step = next_step._adoption_owes(protocol, frozen, "r1")
        assert step is not None
        self.assertIn("`labkit-init exp experiments/01-x --report` appends", step.next)
        filled = frozen + daggered.replace("<…>", "written")
        self.assertIsNone(next_step._adoption_owes(protocol, filled, "r1"))
        self.assertIsNone(
            next_step._adoption_owes(
                protocol, head(repeat_cost="high") + daggered, "r1"
            )
        )

    def test_no_such_area_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = run_next(Path(d) / "nope", Path(d))
        self.assertEqual(rc, 2)
        self.assertIn("labkit-next", err)
