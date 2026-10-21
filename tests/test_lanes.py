"""labkit.run.lanes: the judge's run mechanics, moved out of the stamped skeleton.

What the move must keep (review 2026-10-21): each answer stays with its own
job whatever order the calls finish in; a break mid-run resumes to a
complete file with every job once; re-evaluating the kept rows gives the
run's numbers. And what the audit must still see: the stamped
`01_measure.py` keeps the prompts, the null lane, the answer words, the
config and the formulas — the audit's prompt carries them.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from labkit.run import lanes, llm
from protocol_fixture import head


@dataclass(frozen=True)
class Cfg:
    """A two-lane config as an area has one: the thresholds, the model, the prompts' digest."""

    margin: float = 0.25
    model: str = "fake"
    prompt_sha: str = "000000000000"


def evaluate_rows(rows: list[dict], cfg: Cfg) -> dict:
    """A stand-in formula: how many answers equal the item's gold, per lane."""
    out: dict = {"n_rows": len(rows)}
    for lane in ("registered", "null"):
        out[f"{lane}_right"] = sum(
            1 for r in rows if r["lane"] == lane and r["answer"] == r["gold"]
        )
    return out


def lanes_in(d: Path, n: int = 6) -> tuple[lanes.Lanes, list[dict]]:
    (d / "PROTOCOL-x.md").write_text(head(cost="minutes"), encoding="utf-8")
    items = [
        {"id": f"x{i}", "text": f"item {i}", "gold": "Yes" if i % 2 else "No"}
        for i in range(n)
    ]
    (d / "items.jsonl").write_text(
        "".join(json.dumps(i) + "\n" for i in items), encoding="utf-8"
    )
    run = lanes.Lanes(
        name="x", protocol=d / "PROTOCOL-x.md", items=d / "items.jsonl", out=d / "out.jsonl",
        prompts={"registered": "Q: {text}", "null": "N: {text}"}, text_field="text",
        parse_answer=lambda t: t.strip() or None, evaluate_rows=evaluate_rows,
        probe_cases_in="tests/test_01_x.py",
    )  # fmt: skip
    return run, items


class AnswersStayWithTheirJobs(unittest.TestCase):
    def test_complete_many_returns_in_input_order_when_calls_finish_out_of_order(self):
        finished: list[str] = []
        lock = threading.Lock()

        def slow_first(alias, prompt, **kw):
            time.sleep(
                0.05 if prompt.endswith("0") else 0.0
            )  # the first prompt finishes last
            with lock:
                finished.append(prompt)
            return f"answer to {prompt}"

        prompts = [f"p{i}" for i in range(8)]
        with mock.patch.object(llm, "complete", slow_first):
            got = llm.complete_many("fake", prompts, workers=4)
        self.assertNotEqual(finished, prompts)  # the calls did finish in another order
        self.assertEqual(got, [f"answer to {p}" for p in prompts])

    def test_every_stored_answer_is_the_answer_to_its_own_job(self):
        with tempfile.TemporaryDirectory() as d:
            run, items = lanes_in(Path(d))
            jobs = run.plan(items)

            def echo(alias, prompt, **kw):
                time.sleep(0.03 if "0" in prompt else 0.0)
                return f"to {prompt}"

            with (
                mock.patch.object(llm, "complete", echo),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run.measure(Cfg(), jobs, run.out)
            rows = lanes.read_jsonl(run.out)
            by_id = {j["id"]: j for j in jobs}
            self.assertEqual(len(rows), len(jobs))
            for r in rows:
                self.assertEqual(r["answer"], f"to {run.render(by_id[r['id']])}")


class Broken(RuntimeError):
    """A backend that went away mid-run."""


class ResumeAfterABreak(unittest.TestCase):
    def test_a_break_mid_run_resumes_to_every_job_once(self):
        with tempfile.TemporaryDirectory() as d:
            run, items = lanes_in(Path(d))
            jobs = run.plan(items)  # 12 jobs
            asked: list[int] = []
            broke: list[bool] = []

            def breaks_on_the_second_batch(alias, prompts, **kw):
                asked.append(len(prompts))
                if len(asked) == 2 and not broke:  # once, in the first run
                    broke.append(True)
                    raise Broken("the backend went away")
                return ["Yes"] * len(prompts)

            with (
                mock.patch.object(lanes, "CHUNK", 5),
                mock.patch.object(llm, "complete_many", breaks_on_the_second_batch),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(Broken):
                    run.measure(Cfg(), jobs, run.out)
                self.assertEqual(
                    len(lanes.read_jsonl(run.out)), 5
                )  # the first batch is kept
                asked.clear()
                run.measure(Cfg(), jobs, run.out)  # the same call again
            self.assertEqual(asked, [5, 2])  # only what was missing, from the break on
            rows = lanes.read_jsonl(run.out)
            self.assertEqual(
                sorted(r["id"] for r in rows), sorted(j["id"] for j in jobs)
            )
            run.balance(run.out, jobs)  # complete, no doubles, no strays


class EvaluateKeptRows(unittest.TestCase):
    def test_eval_only_gives_the_numbers_of_the_rows_as_they_stand(self):
        with tempfile.TemporaryDirectory() as d:
            run, items = lanes_in(Path(d))
            jobs = run.plan(items)
            answer = lambda alias, prompts, **kw: ["Yes"] * len(prompts)  # noqa: E731
            with (
                mock.patch.object(llm, "complete_many", answer),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run.measure(Cfg(), jobs, run.out)
                first = run.evaluate(run.out, Cfg(), jobs)
            out = io.StringIO()
            with (
                mock.patch.object(llm, "complete_many") as calls,
                contextlib.redirect_stdout(out),
            ):
                run.main(Cfg(), ["--eval-only"])
            calls.assert_not_called()
            self.assertEqual(first, evaluate_rows(lanes.read_jsonl(run.out), Cfg()))
            for key, value in first.items():
                self.assertIn(f"{key:<13} {value}", out.getvalue())

    def test_the_probe_names_where_its_cases_go(self):
        with tempfile.TemporaryDirectory() as d:
            run, items = lanes_in(Path(d))
            answer = lambda alias, prompts, **kw: ["Yes"] * len(prompts)  # noqa: E731
            out = io.StringIO()
            with (
                mock.patch.object(llm, "complete_many", answer),
                contextlib.redirect_stdout(out),
            ):
                run.main(Cfg(), ["--probe", "2"])
            self.assertIn("paste into tests/test_01_x.py PROBE_CASES", out.getvalue())


class TheAuditStillSeesTheExperiment(unittest.TestCase):
    """The mechanics left the area; what decides the number did not. The
    audit's prompt of a freshly stamped judge area carries the prompts, the
    null lane, the answer words, the config, the formulas and the handover
    to lanes."""

    def test_the_audit_prompt_carries_what_decides_the_number(self):
        import subprocess

        from labkit.gates import audit
        from labkit.tools import scaffold

        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lab"
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(scaffold.main(["lab", str(root)]), 0)
                argv = [
                    "exp",
                    "judge",
                    "--repo",
                    str(root),
                    "--cost",
                    "seconds",
                    "--model",
                    "haiku",
                ]
                self.assertEqual(scaffold.main(argv), 0)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            area = root / "experiments" / "01-judge"
            reading = audit.gather(area, None)
            prompt = audit.bound_prompt("preflight", area, reading)[0]
        for needle in (
            "ANSWERS = {",
            "PROMPT = (",
            "PROMPT_NULL = (",
            "class MeasureConfig",
            "def parse_answer",
            "def _within_chance",
            "def _at_least",
            "def evaluate_rows",
            "cfg.null_band_items",
            "lanes.Lanes(",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, prompt)


if __name__ == "__main__":
    unittest.main()
