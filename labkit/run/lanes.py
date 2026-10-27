"""lanes — the run mechanics of a two-lane model measurement, one home.

A stamped judge area (`labkit-init exp <name> --model <alias>`) asks a model
one question per item in two lanes — the registered question and a null
question the data cannot answer — and computes its number from the rows.
What the number means is the area's: the items, the prompts, the answer
words, `parse_answer` and `evaluate_rows` stand in its `01_measure.py`,
where the audit reads them and the stamp covers them. How the calls are
made is the same in every area and lives here, tested once: one job per
item and lane, the batch of calls, resume after a break, the instrument
that keeps a resumed file to one prompt, the probe, the balance of the
kept rows against their source, and the command line (`--show`,
`--probe`, `--eval-only`, `--repeat-of`, the run through `runlog`).

    RUN = lanes.Lanes(name=…, protocol=PROTOCOL, items=ITEMS, out=OUT,
                      prompts=LANES, text_field=TEXT_FIELD,
                      parse_answer=parse_answer, evaluate_rows=evaluate_rows,
                      case_classes=CASE_CLASSES)
    if __name__ == "__main__":
        RUN.main(CONFIG)

The config is the area's frozen dataclass of one execution: its fields are
the registered thresholds plus `model` and `prompt_sha`, and the run's
config.json records it whole.
"""

from __future__ import annotations

import argparse
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from labkit.formats import protocol_block, runs, standard_contract
from labkit.formats.repo import adopt_command
from labkit.run import batch, llm, runlog

#: calls per batch handed to `llm.complete_many` (four workers); each batch
#: is written before the next starts, so a break loses at most one batch
CHUNK = 40


@dataclass(frozen=True)
class CaseClass:
    """One item the criterion names: its id, its class, and the facts the class rests on."""

    id: str
    cls: str
    facts: dict


def read_case_classes(path: Path) -> tuple[CaseClass, ...]:
    """The [[case]] rows of PATH (`id`, `cls`, `facts`), empty when the file
    does not exist. Which classes exist and which facts decide them is the
    area's: its data file names them, its test recomputes each class from
    its facts. Raises ValueError on a duplicate id or a row without a
    string `id` and `cls` — a silent gap here puts an item in no class."""
    if not path.is_file():
        return ()
    rows = tomllib.loads(path.read_text(encoding="utf-8")).get("case", [])
    seen: set[str] = set()
    out = []
    for n, row in enumerate(rows, 1):
        if not isinstance(row.get("id"), str) or not isinstance(row.get("cls"), str):
            raise ValueError(f"{path.name}: [[case]] #{n} needs string `id` and `cls`")
        if row["id"] in seen:
            raise ValueError(f"{path.name}: {row['id']} stands twice")
        seen.add(row["id"])
        out.append(CaseClass(row["id"], row["cls"], dict(row.get("facts", {}))))
    return tuple(out)


def ids_of(cls: str, cases: tuple[CaseClass, ...]) -> tuple[str, ...]:
    """The ids of one class, in table order."""
    return tuple(c.id for c in cases if c.cls == cls)


def one_per_class(cases: tuple[CaseClass, ...]) -> tuple[str, ...]:
    """The first id of every class — one case per thing the criterion distinguishes."""
    first: dict[str, str] = {}
    for c in cases:
        first.setdefault(c.cls, c.id)
    return tuple(first.values())


def read_jsonl(path: Path) -> list[dict]:
    """Input or output records; the `_meta` header line is documentation, not data."""
    return batch.Store(path).records()


@dataclass(frozen=True)
class Lanes:
    """One two-lane measurement as its area defines it (see the module docstring)."""

    name: str  # the run's name in runs.tsv
    protocol: Path
    items: Path  # the prepared items: id · the text field · gold
    out: Path  # the run's output file; a repeat writes <stem>_draw<N>.jsonl
    prompts: dict[str, str]  # lane -> template with `{text}`; "registered" and "null"
    text_field: str
    parse_answer: Callable[[str], str | None]
    evaluate_rows: Callable[..., dict]  # (rows, config) -> metrics
    probe_cases_in: str  # the area test the probe's parser cases are pasted into
    case_classes: Path | None = None

    def plan(self, items: list[dict]) -> list[dict]:
        """One job per item per lane; `id` is the resume key (one line per
        model call), `item_sha` the item as it is now, which its row carries
        (`balance`). Raises ValueError when two jobs share an id."""
        # `**it` first: the lane-qualified id must win, or both lanes share
        # one resume key and a resumed run skips the twin lane
        jobs = [
            {
                **it,
                "id": f"{lane}:{it['id']}",
                "lane": lane,
                "item_sha": batch.content_sha(it),
            }
            for lane in self.prompts
            for it in items
        ]
        if len({j["id"] for j in jobs}) != len(jobs):
            raise ValueError(
                "plan(): job ids are not unique — two lanes would share one resume key"
            )
        return jobs

    def render(self, job: dict) -> str:
        """The one prompt renderer: `--show` prints it, `measure` sends it."""
        return self.prompts[job["lane"]].format(text=job[self.text_field])

    def instrument(self, cfg: Any) -> dict:
        """What makes two answers comparable — both prompts' digest, the
        model alias and the model it resolves to now (`llm.identity`).
        Every row carries it; a resume refuses rows of another, so an
        edited models.toml cannot mix two models into one file."""
        return {
            "prompt_sha": cfg.prompt_sha,
            "model": cfg.model,
            "model_identity": llm.identity(cfg.model),
        }

    def measure(
        self, cfg: Any, jobs: list[dict], out: Path, prov: dict | None = None
    ) -> None:
        """Ask the model every job OUT does not hold yet, CHUNK at a time,
        each answer stored with its own job. Resume is the same call again;
        the store's lock keeps a second writer out and refuses rows of
        another instrument. `llm.complete_many` returns the answers in the
        order of the prompts, whatever order the calls finish in; the
        pairing is strict — a shorter or longer answer list raises
        ValueError, never a cut. PROV stamps every row (`_prov`)."""
        with batch.Store(out, prov=prov, instrument=self.instrument(cfg)) as store:
            todo = list(store.pending(jobs))
            print(f"to measure: {len(todo)} of {len(jobs)}")
            for start in range(0, len(todo), CHUNK):
                chunk = todo[start : start + CHUNK]
                answers = llm.complete_many(cfg.model, [self.render(j) for j in chunk])
                for j, text in zip(chunk, answers, strict=True):
                    store.append({**j, "answer": text})
                print(f"  {min(start + CHUNK, len(todo))}/{len(todo)}")

    def probe(self, cfg: Any, items: list[dict], n: int) -> list[dict]:
        """N jobs per lane through the real pipeline into a throwaway file,
        and its rows — one case per class when the area names classes. A
        fresh file each time: resumed, a probe showed an edited item's old
        answer."""
        out = self.out.with_name(self.out.stem + "_probe.jsonl")
        out.unlink(missing_ok=True)
        wanted = (
            set(one_per_class(read_case_classes(self.case_classes)))
            if self.case_classes
            else set()
        )
        jobs = [
            job
            for lane in self.prompts
            for job in [
                j
                for j in self.plan(items)
                if j["lane"] == lane
                and (not wanted or j["id"].split(":", 1)[1] in wanted)
            ][:n]
        ]
        self.measure(cfg, jobs, out)
        return read_jsonl(out)

    def balance(self, out: Path, jobs: list[dict]) -> None:
        """Every job on exactly one row, no row without a job, every row made
        from its item as it is now — or SystemExit naming each gap, before
        any number. An item edited since its row was written stays stale
        here: write a new output file. The rows share one instrument —
        whichever it was, so `--eval-only` still reads rows an edited
        models.toml no longer resolves to; two in one file are two
        measurements (a mixed file balanced, review 2026-10-23)."""
        batch.Store(out).ledger(
            jobs, expect={"item_sha": lambda j: j["item_sha"]}
        ).require_complete()
        seen = {runs.as_stored(r.get("_instrument")) for r in read_jsonl(out)}
        if len(seen) > 1:
            raise SystemExit(
                f"{out}: rows of {len(seen)} instruments — "
                + " · ".join(sorted(seen))
                + " — one file holds one measurement: write a new output file"
            )

    def evaluate(self, out: Path, cfg: Any, jobs: list[dict], run: Any = None) -> dict:
        """Balance the kept rows against JOBS, then the area's
        `evaluate_rows`; print every key, and record them on RUN when given."""
        self.balance(out, jobs)
        metrics = self.evaluate_rows(read_jsonl(out), cfg)
        for key, value in metrics.items():
            print(f"  {key:<13} {value}")
        if run is not None:
            run.metrics(**metrics, llm_retries=llm.retries())
        return metrics

    def _parser(self, cfg: Any) -> argparse.ArgumentParser:
        ap = argparse.ArgumentParser(
            description=f"{self.name}: the two-lane measurement"
        )
        ap.add_argument("--model", default=cfg.model)
        mode = ap.add_mutually_exclusive_group()
        mode.add_argument(
            "--show", type=int, metavar="N", help="render N prompts per lane, no calls"
        )
        mode.add_argument(
            "--probe", type=int, nargs="?", const=12, metavar="N",
            help="instrument check: N items per lane through the REAL pipeline, "
            "throwaway output, prints parser cases to paste into the test",
        )  # fmt: skip
        mode.add_argument("--eval-only", action="store_true")
        mode.add_argument(
            "--repeat-of", metavar="RUN_ID",
            help="draw the kept run RUN_ID again: the same jobs and instrument, a run of "
            "its own (repeat_of) into <out>_draw<N>.jsonl — the spread, never the answer",
        )  # fmt: skip
        return ap

    def _show(self, cfg: Any, items: list[dict], n: int) -> None:
        print("===== config (what a run writes to config.json)")
        for key, value in asdict(cfg).items():
            print(f"  {key:<16} {value}")
        for lane in self.prompts:
            for j in [x for x in self.plan(items) if x["lane"] == lane][:n]:
                print(f"===== {j['id']}\n{self.render(j)}")

    def _print_probe(self, rows: list[dict]) -> None:
        for r in rows:
            got = self.parse_answer(r["answer"])
            print(f"{r['id']:<28} {r['answer']!r:<40} -> {got!r} (gold {r['gold']})")
        print(f"\n# parser cases — paste into {self.probe_cases_in} PROBE_CASES:")
        for r in rows:
            print(f"    ({r['answer']!r}, {self.parse_answer(r['answer'])!r}),")

    def main(self, config: Any, argv: list[str] | None = None) -> None:
        """The area's command line: `--show N` renders, `--probe [N]` checks
        the instrument (refused at repeat_cost = low), `--eval-only`
        re-evaluates the kept rows, `--repeat-of RUN_ID` draws a kept run
        again, no flag runs the full measurement through `runlog`. CONFIG is
        the registered execution; `--model` replaces its one field."""
        ap = self._parser(config)
        args = ap.parse_args(argv)
        head = protocol_block.head(self.protocol.read_text(encoding="utf-8"))
        if (
            args.probe is not None
            and not standard_contract.lane(head.repeat_cost).probe_allowed
        ):
            ap.error(
                "--probe is not available at repeat_cost='low'; run the full measurement"
            )
        cfg = replace(config, model=args.model)
        if not self.items.is_file():
            # a missing file read as no items: --show and --probe passed on
            # nothing (audit 2026-10-27, third, I7)
            ap.error(
                f"{self.items}: no prepared items — write them first "
                "(scripts/00_prepare.py), then show, probe or measure"
            )
        items = read_jsonl(self.items)
        if args.show is not None:  # `is not None`: `--show 0` must not start a paid run
            self._show(cfg, items, args.show)
        elif args.probe is not None:
            # throwaway: own output file, no runlog — the moment a number is kept, it is a run
            self._print_probe(self.probe(cfg, items, args.probe))
        elif args.eval_only:
            self.evaluate(self.out, cfg, self.plan(items))
        else:
            self._run(cfg, items, args.repeat_of)

    def _run(self, cfg: Any, items: list[dict], repeat: str | None) -> None:
        """The full run: the whole config recorded, the items frozen (`data=`),
        bound to the protocol; a repeat writes a file of its own."""
        with runlog.run(
            self.name, config=asdict(cfg), base_dir=self.protocol.parent,
            data={"prepared": self.items}, run_kind="measurement",
            protocol=self.protocol.name, repeat_of=repeat,
        ) as run:  # fmt: skip
            out = run.draw_output(self.out)
            run.output(out)
            jobs = self.plan(items)
            self.measure(
                cfg, jobs, out, prov={**llm.provenance(cfg.model), "run": run.run_id}
            )
            self.evaluate(out, cfg, jobs, run)
            if repeat is None:
                print(f"run: {run.run_id}  → {adopt_command(self.protocol, run.run_id)}  "
                      f"(writes Recorded results, [result] run and the run entry from metrics.json)")  # fmt: skip
            else:
                print(
                    f"repeat of {repeat}: {run.run_id} → scripts/02_analyze.py --draws"
                )
