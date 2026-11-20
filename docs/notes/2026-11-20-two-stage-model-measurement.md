# Two-stage model measurements — stagekit runs the stages, labkit holds the measurement (2026-11-20)

A plan, no code. Point 1 of the argmining27 usage findings (`TODO.md`, "Nutzungsfunde zu Wartung und Lesbarkeit"), decided by the author on 2026-11-18: show at an existing generate-then-judge experiment what labkit lacks and how it is closed with the fewest special cases. The first draft of this note compared opening `lanes` with a second skeleton and missed stagekit, which already runs pipelines of stages; revised the same day after the author's objection. Nothing here is decided; the questions at the end are the author's.

Terms: a *stage* is one round of model calls whose answers another stage or the evaluation reads (generation, judging). A *lane* is one prompt variant within a stage, as `lanes.Lanes` uses the word. A *two-stage* measurement is one whose second stage builds its prompts from the first stage's answers. *stagekit* is the lab's pipeline framework (`/Users/max/projects/stagekit`), split off fallacy-detection on 2026-11-03.

## The case

argmining27 experiments 02 and 03 (2026-11-17) ask whether the objections Haiku writes against a MISSCI argument hit the reasoning gaps the annotators marked. One run has two stages: generation (per argument and condition at most five objections) and judging (per gap and lane the same model names the candidate that captures the gap, or 0; lanes `context`, `no_context`, `null`, `anchor`). `evaluate_rows(gen_rows, judge_rows, cfg)` computes the numbers from both. `labkit-init exp … --kind apply --model` stamps the one-stage `lanes` skeleton, and the agent replaced `01_measure.py`, `02_analyze.py` and the area test entirely (argmining27 commits `e8bf110`, `095ba91`, `30406c9`). With the replacement went what `lanes` does: the prompt held to the protocol's Prompt block before any paid call, rows balanced against their jobs and items, the probe, the repeat; `02_analyze.py --check` was written by hand.

## Why stagekit

stagekit already has what a second stage needs, read at its code (fact sheet of 2026-11-20, spot-checked):

- stages with declared inputs and outputs, ordered by `depends_on` (`stagekit/stages/base.py:85`, `stagekit/pipeline/executor.py:356`); a stage builds its prompts from an earlier stage's answers (`task_fields`, `select_records`, `LLMWorkflowStage.run_llm_step`, `base.py:558`, `base.py:703`);
- model calls through labkit: the backend `labkit` calls `labkit.run.llm`, the raw answers in the labkit run's cache (`stagekit/models/backends/labkit_backend.py:1`, `answers_through`);
- a hash over everything that changes the output — config fields, prompt versions (sha256 of the template text), parser ids (`repro_hash`, `stagekit/analysis/repro_hash.py:286`).

And the coupling is already planned and used. labkit's [stagekit plan](2026-11-03-stagekit-plan.md), steps 4 and 6: an area's `01_measure.py` opens `runlog.run` and calls stagekit. fallacy-detection runs it so in three areas (`experiments/01-pilot-bigbench-zs/scripts/01_measure.py:290`, `02-…:291`, `03-…:389`):

```python
config["repro_hash"] = compute_repro_hash(cfg)
with runlog.run(name, config=config, base_dir=AREA, data=frozen,
                run_kind="measurement", protocol=PROTOCOL.name) as run:
    cfg.meta.labkit_run_id = run.run_id
    cfg.output_dir = str(run.dir / "stagekit")
    with answers_through(llm_cache.Cache(run, …)):
        stage_run = Path(run_pipeline(cfg))
    # stagekit's stored repro_hash checked against the composed one
    run.output(stage_run / "pipeline_summary.json", …)
```

Building stages into `lanes` would make a second stage framework beside stagekit — two homes for one question. A second skeleton would copy the run mechanics into every stamp.

## The split

| Question                                                        | Home                                                                            |
|-----------------------------------------------------------------|---------------------------------------------------------------------------------|
| which calls, in which order, built from which earlier answers   | stagekit: the stages, `depends_on`, the topic's stage classes                   |
| the model call, its raw answer, replay                          | labkit's `llm` and `llm_cache`, bound by stagekit's `labkit` backend            |
| what the run is: config, frozen inputs, outputs, code, protocol | labkit's `runlog.run` around `run_pipeline`; `repro_hash` in its config         |
| the prompt sent is the registered one                           | labkit — missing for stagekit areas (step 2)                                    |
| the number from the kept rows, its recomputation                | the area's `evaluate_rows`; labkit's `recheck` — one output file today (step 1) |
| intent, quality checks, audit, adoption, report                 | labkit, unchanged                                                               |

labkit stays stdlib-only and imports nothing of stagekit; the area depends on both (`stagekit[labkit]`).

## What labkit adds

1. **The recomputation over several output files.** `recheck.holds` takes one `out` and a `recompute(rows)`; a two-stage number needs the rows of both stages. With it the public function for "the newest completed measurement run of a protocol and its derived runs" (point 5 of the findings), written by hand five times in argmining27. Needed whichever way the stages run; `recheck` is not public API (`docs/architecture.md`, "Public API"), so the change is a "Breaking" entry. Open: stagekit writes its stage outputs as JSON (`stage_outputs/<stage>/<key>.json`), `recheck` reads row files; whether the area writes labkit row files from them, as fallacy-detection 01 does (`rows(…)` with `_prov.run`), or `recheck` reads stagekit's files is to be decided at the code.
2. **The prompt check as a function of its own.** Today only `lanes.require_registered_prompts` refuses, before a paid call, a prompt whose fixed lines the protocol's Prompt blocks do not hold; the comparison itself is already pure (`protocol_check.unheld_prompt_lines`). Moved to a function that takes the templates as a mapping, `lanes` calls it and a stagekit area calls it with the templates it hands to stagekit. And `protocol-fill --prompts` reads only `PROMPT` constants of the area's scripts (`prompt_check.prompt_constants`), while stagekit loads templates from `.txt` files (`register_prompt_dir`, `stagekit/prompts/registry.py:29`): one of the two must meet the other (question 1).
3. **Nothing in the gates.** The run record, the audit and report-check read what `runlog` recorded; a stagekit run is a labkit run like any other. The second case under the plan shows whether that holds.

## Steps

1. labkit: `recheck` over several output files and the run-choice function (item 1 above), one commit each, with the scenario of a two-file run.
2. labkit: the prompt check as a function (item 2), `lanes` on it unchanged in behaviour; the reader of `--prompts` per question 1.
3. argmining27: a new area runs experiment 02's question through stagekit — a topic with two stages (generate, judge), its prompts in the area, the run under `runlog.run` by the fallacy-detection pattern, `02_analyze.py --check` on `recheck`. Under the plan's step-6 rule: the first attempt may change stagekit, each change a finding written down, both topics' tests green after it; done when a closing run needs no change to stagekit. The number is compared with experiment 02's on the same items as a check of the port, not as a result.
4. Only then: whether `labkit-init` stamps a stagekit skeleton, from what step 3 showed.

## What stagekit does not do that `lanes` did

- **No resume per item** (`stagekit/pipeline/executor.py:86`: every run is fresh). A run broken after paid calls is started again; whether the new run reads the broken run's raw answers from labkit's cache, or pays again, is not settled — the cache belongs to one labkit run (`labkit_backend.py`, module docstring). The plan's step 6 decided that a repeat keeps its raw answers in its own run directory.
- **No probe, no repeat flag.** A probe is a stagekit run on a few items outside `runlog`; a repeat is a new `runlog.run` with `repeat_of`.
- **The rendered prompt is not kept per row** (one example per stage, `template_rendered_example.txt`); labkit's `llm-calls.jsonl` holds the call's key, not its text. The prompt check of step 2 holds the templates, not the rendered text.

## Questions for the author

1. **Where the area's prompts live.** As `.txt` files that stagekit loads (`register_prompt_dir`): stagekit unchanged, labkit's `--prompts` and the prompt check learn to read them. Or as `PROMPT_*` constants in `01_measure.py`, handed to stagekit: labkit unchanged, stagekit needs a way to register a template from a string (not found in the fact sheet).
2. **A run broken after paid calls.** Pay again, or let the next run replay the broken run's cached answers (a cross-run replay that labkit's cache does not offer today).
3. **argmining27 as the plan's second case.** The plan names counterfactual-worlds for step 6, which has no stagekit yet. Taking argmining27 instead or as well brings a topic from outside earlier — and the step-6 rule that its first attempt may change stagekit.
4. **What a repeat draws.** Both stages again (the spread of the whole measurement), or the judge only on the kept objections (the spread of the judge); the second is a derived run of its own kind.
