"""`labkit-params`: the table of a run's values — what each row claims, and
what the view refuses to claim.

    .venv/bin/python -m pytest tests/test_params.py
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from protocol_fixture import run_record, PID, head

from labkit.formats.runs import RUN_SCHEMA
from labkit.formats import gate, promises
from labkit.tools import params
from command_fixture import run_main

C1 = """[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
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
    # as runlog writes them: the promise snapshot of the protocol and a copy
    # of the script, both as they stand when the run starts
    text = (area / "PROTOCOL-x.md").read_text(encoding="utf-8")
    block = promises.parse_block(text)
    snap = promises.snapshot(block, area) if block is not None else None
    (d / "script-source.py").write_bytes(
        (area / "scripts" / "01_measure.py").read_bytes()
    )
    (d / "config.json").write_text(
        json.dumps(
            run_record(
                {
                    "schema_version": RUN_SCHEMA,
                    "run_kind": "measurement",
                    "script": "01_measure.py",
                    "pid": 1,
                    "protocol": {"id": pid, "path": "PROTOCOL-x.md"},
                    "derived_from": derived_from,
                    "models_resolved": models_resolved or {},
                    "config": config,
                    "promises": snap,
                }
            )
        ),
        encoding="utf-8",
    )
    (d / "metrics.json").write_text('{"criterion_1_pass": true}', encoding="utf-8")
    (d / "completion.json").write_text(
        json.dumps(
            {
                "schema_version": RUN_SCHEMA,
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
            rows = _by_name(params.params_table(run))
            self.assertEqual(
                {r.evidence_kind for r in rows.values()}, {gate.GUARANTEED}
            )
            self.assertEqual(rows["min_acc"].in_run, "0.7")
            self.assertEqual(
                rows["min_acc"].home,
                f"{run.name}/config.json: promises [criterion-1] constants",
            )
            self.assertEqual(rows["model m"].value, "m → A @ http://a")
            self.assertEqual(rows["model m"].in_run, "recorded")
            self.assertNotIn(
                "MODEL", rows
            )  # recorded as `model`: not an unrecorded constant

    def test_a_model_spec_under_a_foreign_key_is_evidence(self) -> None:
        """A run that recorded the resolved model as `judge` has it, labkit
        does not hold it — the row says so instead of "recorded"."""
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
            rows = _by_name(params.params_table(run))
            self.assertEqual(rows["judge"].evidence_kind, gate.STATIC_EVIDENCE)
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
            rows = _by_name(params.params_table(run))
            row = rows["SOME_CONSTANT"]
            self.assertEqual(
                (row.evidence_kind, row.in_run, row.home),
                (gate.STATIC_EVIDENCE, "—", f"{run.name}/script-source.py:7"),
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
            rows = _by_name(params.params_table(run))
            self.assertEqual(
                rows["min_acc"].in_run,
                f"— (not recorded; {run.name}/script-source.py:1 holds min_acc = 0.7)",
            )
            self.assertEqual(rows["min_acc"].evidence_kind, gate.STATIC_EVIDENCE)

    def test_an_upper_case_copy_stands_in_the_registered_row(self) -> None:
        """A script that copies `min_acc` as `MIN_ACC`: the registered row
        names the copy, and the copy stands as no row of its own."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, SCRIPT.replace("min_acc = 0.7", "MIN_ACC = 0.7"))
            run = _run(
                area,
                "2026-10-01T10-00-00_aaaa",
                {"margin": 0.1},
                models_resolved=MODEL_A,
            )
            rows = _by_name(params.params_table(run))
            self.assertEqual(
                rows["min_acc"].in_run,
                f"— (not recorded; {run.name}/script-source.py:1 holds MIN_ACC = 0.7)",
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
            rows = _by_name(params.params_table(run))
            self.assertEqual(rows["min_acc"].in_run, "0.5  ≠ DIFFERS")
            self.assertEqual(rows["min_acc"].evidence_kind, gate.GUARANTEED)

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
            rows = _by_name(params.params_table(child))
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
            rows = _by_name(params.params_table(child))
            self.assertIn(
                "not recorded in models_resolved along lineage", rows["model"].meaning
            )
            self.assertIn(
                "2026-10-02T10-00-00_bbbb → 2026-10-01T10-00-00_aaaa",
                rows["model"].meaning,
            )
            self.assertEqual(rows["model"].evidence_kind, gate.GUARANTEED)


def _main(argv: list[str]) -> tuple[int, str]:
    return run_main(params.main, argv, capture_stderr=False)


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

    def test_a_named_older_run_shows_what_it_ran_with(self) -> None:
        """The protocol's constant and the script changed after run A: `--run
        A` shows A's registered constant and A's script literal, not today's;
        the newer run shows today's."""
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, SCRIPT + "BATCH = 8\n")
            old = _run(area, "2026-10-01T10-00-00_aaaa", {"min_acc": 0.7})
            protocol = area / "PROTOCOL-x.md"
            protocol.write_text(
                protocol.read_text(encoding="utf-8").replace("0.7 }", "0.8 }"),
                encoding="utf-8",
            )
            script = area / "scripts" / "01_measure.py"
            script.write_text(SCRIPT + "BATCH = 16\n", encoding="utf-8")
            new = _run(area, "2026-10-02T10-00-00_bbbb", {"min_acc": 0.8})
            then = _by_name(params.params_table(old))
            self.assertEqual(
                (then["min_acc"].value, then["min_acc"].in_run), ("0.7", "0.7")
            )
            self.assertEqual(then["BATCH"].value, "8")
            now = _by_name(params.params_table(new))
            self.assertEqual((now["min_acc"].value, now["BATCH"].value), ("0.8", "16"))

    def test_a_run_without_its_script_copy_shows_its_literals_as_not_available(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, SCRIPT + "BATCH = 8\n")
            run = _run(area, "2026-10-01T10-00-00_aaaa", {"min_acc": 0.7})
            (run / "script-source.py").unlink()
            rows = _by_name(params.params_table(run))
            self.assertNotIn("BATCH", rows)  # today's value is not the run's
            self.assertEqual(rows["script literals"].value, "not available")
            self.assertEqual(rows["min_acc"].in_run, "0.7")

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

    def test_a_script_that_does_not_parse_is_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            area = _area(d, script='min_acc = 0.7\nMODEL = f"{x\n')
            _run(area, "2026-10-01T10-00-00_aaaa", {"min_acc": 0.7})
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = params.main([str(area)])
            self.assertEqual(code, 2)
            # the script as the run kept it is the one read
            self.assertIn("script-source.py: cannot be read as Python", err.getvalue())


if __name__ == "__main__":
    unittest.main()
