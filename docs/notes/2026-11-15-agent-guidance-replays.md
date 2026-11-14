# Usage round 24: recurring agent errors replayed against the guidance

2026-11-15. Step 4 of the plan under task 7 in `TODO.md`: the recurring agent errors of [the round's findings](2026-11-13-usage-round-24-findings.md) (group 5) checked on concrete cases for missing or misleading guidance, and the environment problems (group 6) kept apart. Replayed with real commands in a freshly stamped count-task lab (`usability stage --task count`) plus a second area stamped as task 34's agents did (`labkit-init exp hrv --kind compute --repeat-cost low`), labkit `6236c799`. Each case: what the agents did (trace readings in labkit-paper, area 24, `output/trace-readings/`), what labkit printed at that point, and the gap in the guidance this shows. The replay shows the gap, not that it caused the agents' errors: whether closing it changes what agents do is not measured.

## 1. Stated values not registered before the first measurement

Agents: no task-34 agent registered the stated values (760 ms and 85 ms within 1 %) as `[reference]` before the first measurement, 0 of 6. Two entered it afterwards; one was then held for a registration changed after the first measurement and went to a successor protocol, the other took it back. Nobody used `labkit-init … --reference`.

What labkit says before the first measurement: `labkit-next` names the missing fields and "if the task asks for a report file, register it now"; `protocol-fill --list` and `protocol-check --contract` name `[kept]` but not `[reference]`; the stamped protocol has no `[reference]` placeholder; runlog's refusal of an uncommitted registration names neither the report nor `[reference]`. The rule stands only in the agent guide (`labkit/docs/agent-guide.md:55`) and in one sentence of the stamped `AGENTS.md`. One agent read the guide with `| head -50` and stopped five lines short of it.

Gap shown: guidance missing at the step the agent reads. Not a gate defect: once a `[reference]` was entered after the first measurement, finalize held it as it should.

## 2. The hand-checked case filled from the run

Agents: all six task-34 agents filled `KNOWN_ROWS` / `KNOWN_METRICS` with their own run's output ("Let me just fill in the key metrics I've already computed from the run"). The test then checks only that the code repeats itself.

What labkit says: nothing asks for the test before the run. The first demand comes after it, from finalize and `labkit-next`: "test_… failed … the area's own checks of evaluate() … no longer hold", next "fix the code (or a test that asks the wrong thing) until … passes". The run's values are on screen at that moment. The stub's own assertion says "with a case checked by hand"; "never by calling the code" stands only in a comment above it.

Gap shown: guidance comes after the run and reads as a repair ("no longer hold", "fix the code"), not as a test that was never filled.

## 3. A finished report never registered

Agents: sts512 b-r1 and task 34 b-r3 wrote REPORT.md without `report = "REPORT.md"` in the head; without the entry no report review is owed, and the reports went out unreviewed (b-r1 with three false statements the judges found).

What labkit says: `labkit-next` names the entry before the first measurement; runlog's refusal does not, and task 34 b-r3 first called `labkit-next` after measuring.

Gap shown: the hint stands in one of the two places an agent meets before the first run.

## Repair: one hint, both places

`standard_contract.first_measurement_hint` holds the sentences, and both `labkit-next` (`next_step._before_first_hint`) and runlog's first step (`start_check._first_step`) end with it, before the first measurement only: the report entry while none is registered; for a computation, a stated value as `[reference]` while none is registered, and the hand-checked case in `tests/test_<NN>_<name>.py` filled now, its expected values found apart from the run (by hand or from an independent source). The report and the reference sentences are conditional ("if the task asks …", "if the task states a value …"), as not every task asks for either; the test sentence is not, as finalize runs every computation's area test. A failing area test's way out adds that expected values are found apart from the run under test, never copied from a run's output; finalize's sentence says "do not hold" instead of "no longer hold"; the stamped quick test's message says the same. No new check and no new refusal (TODO: "Daraus nicht automatisch neue Sperren ableiten"); the ways out for a gap found after the first measurement (a successor with `[replaces]`, the report entered later, a repaired test) are unchanged.

Replayed after the change, same lab: fresh area — all three sentences in `labkit-next`; filled but uncommitted — runlog's refusal carries them, and `labkit-next`, which shows runlog's step there, tells them once (the first replay printed them twice; fixed, `tests/test_repair_paths.py` holds the count); `[reference]` registered — that sentence drops; after the first measurement — none. Tests: `tests/test_first_measurement_hint.py`, `test_next_step.TheChain`, `test_adoption_order.FirstStepBeforeARun`.

Whether agents now register the stated values or fill the case by hand is not measured; that takes a new usage round (plan step 5: a separate research order).

## Not repaired here

- **The detector chosen by closeness to the stated values** (task 34 b-r3) is a scientific error, not missing guidance: the guide forbids moving the number to meet a reference. The audit's discarded first draft named it, the valid second one did not (finding group 4); that is an audit-tier question.
- **Runs deleted, `git reset --hard`, `--no-verify`** (three attempts): the stamped `AGENTS.md` and the guide forbid each. That deleted, never committed runs leave no trace is a gate question (round a, task 34 r2) and belongs with the index-against-tree group, not here.
- **Environment.** The missing git identity in the sandbox image (one step per attempt in all 18) and `sandbox/labkit.pin` naming the tag instead of the commit are changes to labkit-paper's sandbox, each its own step there. The API errors are not product faults: in round a about ten minutes per attempt went to retries (assay a1–a3, sts512 a-r1 with four HTTP 502), and 6 of 18 attempts ended at the 2400 s limit with a median of 20.8 s per tool call; a time limit alone shows no product fault.
