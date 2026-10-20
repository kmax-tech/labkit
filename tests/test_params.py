"""`labkit-params`: the table of a run's values — what each row claims, and
what the view refuses to claim (2026-10-08).

    .venv/bin/python -m pytest tests/test_params.py
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import PID, head

from labkit.tools import params

C1 = """[[promise]]
id = "C1"
key = "c1_pass"
sentence = "accuracy >= min_acc"
scope = ["scripts/01_measure.py"]
constants = { min_acc = 0.7 }
"""
SCRIPT = "min_acc = 0.7\nMODEL = 'm'\n\n\ndef evaluate_rows(rows):\n    return {}\n"


def _area(tmp: str, script: str = SCRIPT) -> Path:
    area = Path(tmp)
    (area / "PROTOCOL-x.md").write_text(
        head(id=PID, promises=C1) + "\n- **Question:** q\n", encoding="utf-8"
    )
    (area / "scripts").mkdir()
    (area / "scripts" / "01_measure.py").write_text(script, encoding="utf-8")
    (area / "runs").mkdir()
    return area


def _run(
    area: Path,
    name: str,
    config: dict,
    *,
    models_resolved: dict | None = None,
    derived_from: str | None = None,
    pid: str = PID,
) -> Path:
    d = area / "runs" / name
    d.mkdir()
    (d / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "run_kind": "measurement",
                "script": "01_measure.py",
                "pid": 1,
                "protocol": {"id": pid, "path": "PROTOCOL-x.md"},
                "derived_from": derived_from,
                "models_resolved": models_resolved or {},
                "config": config,
            }
        ),
        encoding="utf-8",
    )
    (d / "metrics.json").write_text('{"c1_pass": true}', encoding="utf-8")
    (d / "completion.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "run_kind": "measurement",
                "finished": "x",
                "git": "g",
                "git_full": "g",
                "note": "",
            }
        ),
        encoding="utf-8",
    )
    return d


MODEL_A = {"m": {"alias": "m", "model": "A", "endpoint": "http://a"}}


def _by_name(rows: list[params.ParamRow]) -> dict[str, params.ParamRow]:
    return {r.name: r for r in rows}


class Table(unittest.TestCase):
    def test_twin_every_row_guaranteed_nothing_unrecorded(self) -> None:
        """A fresh run that recorded the registered constant and its model:
        no static-evidence row, no missing constant."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.7, "model": "m"},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            self.assertEqual({r.tier for r in rows.values()}, {params.GUARANTEED})
            self.assertEqual(rows["min_acc"].in_run, "0.7")
            self.assertEqual(rows["min_acc"].home, "PROTOCOL-x.md [C1] constants")
            self.assertEqual(rows["model m"].value, "m → A @ http://a")
            self.assertEqual(rows["model m"].in_run, "recorded")
            self.assertNotIn(
                "MODEL", rows
            )  # recorded as `model`: not an unrecorded constant

    def test_a_model_spec_under_a_foreign_key_is_evidence(self) -> None:
        """uniagent 14–17 recorded the resolved model as `judge`: the run has
        it, labkit does not hold it — the row says so instead of "recorded"."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {
                    "min_acc": 0.7,
                    "judge": {"alias": "m", "model": "A", "endpoint": "http://a"},
                },
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            self.assertEqual(rows["judge"].tier, params.EVIDENCE)
            self.assertIn("runlog does not read", rows["judge"].meaning)
            self.assertIn("not recorded in models_resolved", rows["model"].meaning)

    def test_an_unrecorded_module_constant_is_evidence_not_proof(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, SCRIPT + "SOME_CONSTANT = 3\n")
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.7},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            row = rows["SOME_CONSTANT"]
            self.assertEqual(
                (row.tier, row.in_run, row.home),
                (params.EVIDENCE, "—", "scripts/01_measure.py:7"),
            )
            self.assertIn("not claimed", row.meaning)

    def test_a_registered_constant_the_record_lacks_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"margin": 0.1},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            self.assertEqual(
                rows["min_acc"].in_run,
                "— (not recorded; scripts/01_measure.py:1 holds min_acc = 0.7)",
            )
            self.assertIn("absent", rows["min_acc"].tier)
            self.assertIn(params.EVIDENCE, rows["min_acc"].tier)

    def test_an_upper_case_copy_stands_in_the_registered_row(self) -> None:
        """Cold reader 2026-10-09: the script copied `min_acc` as `MIN_ACC`;
        the registered row said only "not recorded" and the copy stood as a
        row of its own."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, SCRIPT.replace("min_acc = 0.7", "MIN_ACC = 0.7"))
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"margin": 0.1},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            self.assertEqual(
                rows["min_acc"].in_run,
                "— (not recorded; scripts/01_measure.py:1 holds MIN_ACC = 0.7)",
            )
            self.assertNotIn("MIN_ACC", rows)

    def test_a_differing_constant_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.5},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", run))
            self.assertEqual(rows["min_acc"].in_run, "0.5  ≠ DIFFERS")
            self.assertEqual(rows["min_acc"].tier, params.GUARANTEED)

    def test_a_derived_run_names_the_ancestor_that_recorded_the_model(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            parent = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.7},
                models_resolved=MODEL_A,
            )
            _run(
                area,
                "2026-10-02T10-00-00_bbbb",
                {"min_acc": 0.7},
                derived_from=parent.name,
            )
            child = _run(
                area,
                "2026-10-03T10-00-00_cccc",
                {"min_acc": 0.7},
                derived_from="2026-10-02T10-00-00_bbbb",
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", child))
            self.assertEqual(rows["model m"].in_run, f"inherited from {parent.name}")
            self.assertEqual(
                rows["model m"].home,
                f"models_resolved of {parent.name}, inherited through 2026-10-03T10-00-00_cccc → 2026-10-02T10-00-00_bbbb",
            )

    def test_a_lineage_without_any_model_record_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            parent = _run(area, "2026-10-01T10-00-00_aaaa", {"min_acc": 0.7})
            child = _run(
                area,
                "2026-10-02T10-00-00_bbbb",
                {"min_acc": 0.7},
                derived_from=parent.name,
            )
            rows = _by_name(params.params_table(area, area / "PROTOCOL-x.md", child))
            self.assertIn(
                "not recorded in models_resolved along lineage", rows["model"].meaning
            )
            self.assertIn(
                "2026-10-02T10-00-00_bbbb → 2026-10-01T10-00-00_aaaa",
                rows["model"].meaning,
            )
            self.assertEqual(rows["model"].tier, params.GUARANTEED)


def _main(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = params.main(argv)
    return code, buf.getvalue()


class CommandLine(unittest.TestCase):
    def test_the_first_line_names_run_and_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.7},
                models_resolved=MODEL_A,
            )
            code, out = _main([str(area)])
            self.assertEqual(code, 0, out)
            first = out.splitlines()[0]
            self.assertIn("PROTOCOL-x.md", first)
            self.assertIn("run 2026-10-01T10-00-00_aaaa", first)
            self.assertIn(f"answers for {PID}", first)
            self.assertIn("min_acc", out)

    def test_a_named_run_is_read_as_named(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            old = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"min_acc": 0.7},
                models_resolved=MODEL_A,
            )
            _run(
                area,
                "2026-10-02T10-00-00_bbbb",
                {"min_acc": 0.7},
                models_resolved=MODEL_A,
            )
            code, out = _main([str(area), "--run", old.name])
            self.assertEqual(code, 0, out)
            self.assertIn(f"run {old.name} (named with --run)", out.splitlines()[0])

    def test_no_bound_run_is_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d)
            _run(area, "2026-10-01T10-00-00_aaaa", {"min_acc": 0.7}, pid="p-other")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = params.main([str(area)])
            self.assertEqual(code, 2)
            self.assertEqual(out.getvalue(), "")  # a refusal, not a table
            self.assertIn("no completed run bound to", err.getvalue())
            self.assertIn("bound to p-other", err.getvalue())


if __name__ == "__main__":
    unittest.main()
