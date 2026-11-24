# Adopting a documented analysis correction on unchanged answers

Task, 2026-11-24, for a separate labkit session. Not built yet. First question: does labkit already support this through a separate analysis run? Only if it does not: a concrete extension proposal with tests, presented to the author before it is built.

## The case

argmining27, experiment 14 (`experiments/14-fixed-scenario-cross-rating`), labkit `v0.115.0`.

| Run                        | Kind                                   | Code      | What it did                                                                       |
|----------------------------|----------------------------------------|-----------|-----------------------------------------------------------------------------------|
| `2026-11-24T12-28-53_aa0a` | `measurement`                          | `1d3d170` | 6 144 model answers into `output/fixed-scenario-cross-rating.jsonl`, then metrics |
| `2026-11-24T14-22-02_2b96` | `measurement`, `derived_from` = `aa0a` | `bf0bfc7` | the same answers evaluated again, no model call                                   |

The analysis audit `audits/2026-11-24T13-33-analysis.toml` found two implementation faults in the evaluation, not in the measurement:

1. `paired_draw_interval` read the lower bootstrap bound one rank too high (`int(0.025 * n)` instead of the nearest rank `ceil(0.025 * n) - 1`).
2. The inputs were not held to the digests the protocol registers.

Both were repaired in `scripts/01_measure.py` (commit `bf0bfc7`), declared as a protocol step (`--builds-on aa0a --step-id audit-repair-reevaluate --occasion repair`), and the answers were evaluated again in the derived run `2b96`. Result: of 64 interval bounds one changed in the fifth decimal, no reading changed, the kept number stayed 10.

`finalize` blocks `2b96`: `scripts/01_measure.py changed since 2026-11-24T12-28-53_aa0a ran it — its number came from other code (LAB-041)`, and its only way out is to measure anew. `02_analyze.py --check` refuses likewise. A new measurement would mean 6 144 paid calls only to clear a fault in the arithmetic, and it would replace the answers the audit looked at.

## What the person requires

- The original answers and the original run record stay unchanged.
- Old and new evaluation code can both be traced (which commit computed which number).
- A change to the prompts, to the rule that reads an answer (for example `parse_letter`), and to the metrics is told apart explicitly. Only the last may pass on unchanged answers; the first two change what was measured and keep needing a new measurement.
- No blanket release of changed measurement scripts.

## Questions for the investigation

1. Does a supported path exist today? Candidates to check: `derived_from` with the evaluation moved into a script of its own (so the measuring script stays byte-identical to the parent's), `--reported-through` / an analysis run that names the measurement as its input, `02_analyze.py --check --run`, `labkit-adopt` on a derived run. For each: what `finalize`, `report-check` and `labkit-adopt` say, and whether the number would be adopted. Show it on a copy of the experiment 14 area or a small fixture, never on the live area.
2. If none fits: which check refuses, and on what evidence? (`finalize` and `recheck` compare the parent's script to the current one; find the lines.)
3. How can labkit tell "only the evaluation changed" from "the measurement changed" without trusting the author's word? Options to weigh: a declared split of the script into a measuring part (prompts, answer reading, model calls) and an evaluating part, each with its own digest; a recorded digest of the answer file plus a proof that the derived run read exactly those bytes; a diff restricted to named functions. Say what each option costs a lab and which faults it would let through.
4. How is the correction shown in the result? The adopted run, its parent, both code commits, the audit finding it repairs, and the numbers that changed.

## Acceptance for a proposal

- A test where only the evaluation changes: the derived run is adopted, the parent's record and answer file stay byte-identical, and the adopted result names both commits and the finding.
- A test where the prompt changes: refused, with the way out "measure anew".
- A test where the answer-reading rule changes (for example `parse_letter`): refused, with the same way out.
- A test where the answer file changed after the parent run: refused.
- The existing tests stay green; no change to standards or rule texts without the author's decision.

## Documentation acceptance — required before completion

These are requirements for the implementation's documentation, not instructions for an already available feature. Document the selected extension of `derived_from`; the alternative paths investigated below are not parallel user workflows.

1. Extend `docs/workflow.md`, in its existing "Repair and recovery" section, with the complete correction procedure. Distinguish reproducing an old result with its original code, correcting the evaluation of unchanged answers in a new recorded run, and collecting new answers after changing the measurement conditions. Explain that a new run does not necessarily make new model calls. Show the prerequisites, actual commands, expected outcome and failure cases through adoption and report checking.
2. Add a short decision guide to `labkit/docs/agent-guide.md`, beside "Finalize, audit and decide". This guide ships with the package: give agents the necessary next actions without requiring an unshipped repository note. Distinguish mechanical checks from the audit's judgement of answer reading outside the declared module. Keep the detailed worked explanation in `docs/workflow.md`.
3. Update the `derived run` entry in the README's "Terms" table. Explain what `derived_from` records, the additional declaration needed for the correction path, and which code checks remain in force without that declaration. Use the implemented spelling; do not invent a command or field for the documentation.
4. Make the blocker for a changed parent script name the supported correction path and its prerequisites, alongside the cases that require new answers or restoration of an accidental edit. Its next action must agree with the workflow and agent guide.
5. Exercise the documented procedure end to end with a self-contained scenario and an explicitly identified stand-in audit, as the existing scenario tests do. Demonstrate successful recomputation, adoption and report checking, unchanged original answers and records, and the reported relationship between the old and corrected results. Verify that a missing file never silently selects another check. Record what was actually exercised on the copy of experiment 14; a synthetic success is not a completed adoption in that laboratory.

Keep the investigation, decisions and evidence in this note. Keep only the current assignment, status and link in `TODO.md`. Mark unimplemented behaviour as planned until the supported procedure passes its acceptance checks. This documentation requirement authorizes no paid audit or model call and no change to the original argmining27 repository.

## Not in this task

- No change in argmining27 and no model call. Experiment 14 waits for the result; it is neither adopted nor handed over in the meantime.
- No change to the global release rule (separate decided task in `TODO.md`).

## Investigation, 2026-11-24 (questions 1 and 2; not built)

**Which check refuses.** `run_record_check.code_since_run` (`labkit/checks/run_record_check.py:119`) walks the answering run and every run it derives from (`runs.lineage`, along `derived_from`) and compares each run's script with the `script_sha` that run recorded (`:186`), and each imported module with the run's start commit. `2b96` derives from `aa0a`, so `aa0a`'s `scripts/01_measure.py` is compared, and the repair changed that file. `recheck.require_run_code` holds the same condition for `02_analyze.py --check`. The docstring says "Analysis code and the pin are not compared: a fix there needs no new measurement" — but the stamped skeleton puts the answer reading (`parse_answer`) and the evaluation (`evaluate_rows`) into the measure script (`labkit/templates/measure-script.py.template:200`, `:255`), and experiment 14 follows it (`parse_letter` from `lib/scenario_rating.py`, applied in `evaluate_rows`). So every evaluation fix reads as a measurement change.

**A supported path exists: a new run that reads the answers as an input with an origin, not a derived run.** A run with no `derived_from` whose recorded input is `aa0a`'s registered output gets `aa0a` as its origin (`labkit/run/input_origins.py`, decided by digest). Its lineage is itself, so `aa0a`'s script is not compared; finalize's input-origins station (`labkit/gates/finalize.py:714`) holds that the input is still the bytes `aa0a` registered and that the protocol `aa0a` was measured under reads back — not `aa0a`'s code. `02_analyze.py --check` recomputes it from the recorded inputs (`recheck.holds_from_inputs`). Shown end to end on the counting skeleton by `tests/test_origin_scenario.py:95-140`: run A measures, `01_measure.py` is changed to read A's rows, run C passes finalize, the adoption, the pre-commit and report-check, and the area's `--check` recomputes C.

What this path does not give, measured against "What the person requires":

- It does not tell the answer-reading rule from the metrics. The new run evaluates with whatever `parse_letter` stands now; a changed reading rule passes as silently as a fixed bootstrap bound. Prompts are covered only in effect (no model call, the answers are `aa0a`'s bytes).
- Not shown on a model area: the fixture has no `llm-calls.jsonl`; whether finalize's model checks accept a run that reads model answers but calls no model is untested.
- Not shown: what the adopted result names (origin run, both commits, the audit finding).
- No guidance names it: `labkit/docs/agent-guide.md` and `docs/workflow.md` do not mention a re-evaluation, and the blocker's way out names only "measure anew" or "restore".

Open for the author: question 3 (how labkit tells "only the evaluation changed" without trusting the author) decides whether the answer-reading rule is held; the declared scopes per promise (`declared_scope_sha`, compared for repeats in `labkit/formats/answering_run.py:282`) are the existing mechanism closest to "a diff restricted to named functions".

## Probe on a copy, 2026-11-24 (question 1 for experiment 14; nothing adopted, nothing changed in argmining27)

A `git clone --local` of argmining27 at `1f1f68a` in the session scratchpad, its pinned labkit 0.115.0. One change to the area's `run_reevaluate`: no `derived_from`, the answer file recorded as input `answers` with the chosen origin `runlog.RunOutput(OUT, run=aa0a)` (needed: `2b96` registered the same bytes, so the origin is not unique), no `r.output(OUT)`; `metrics_from_inputs` reads the rows from that input. Run `6ead`, no model call:

| Step                                    | Result                                                                                                                                                                                                                                                   |
|-----------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| run record                              | `derived_from` none; `answers` origin `aa0a`, chosen, sha `9602e84dbb10a2be`                                                                                                                                                                             |
| `finalize .`                            | exit 0, 0 blockers, 4 warnings: the three open findings of the analysis audit of `aa0a`, and "no outputs.json"; input origins: "the output of `aa0a` (chosen by the script), as both records hold it", the protocol `aa0a` was measured under reads back |
| `recheck.verified_from_inputs` directly | holds: 769 keys recomputed from the recorded inputs, none grown; against `aa0a` one key differs (`diff_sw_ell_alarm_g_lo`, −0.08333333333333333 → −0.08333333333333336), `n_weighting_expected` 10 in both                                               |
| `aa0a` and the answer file              | byte-identical to the original repository                                                                                                                                                                                                                |
| `02_analyze.py --check` as stamped      | exit 1: "run `6ead` did not register fixed-scenario-cross-rating.jsonl as an output" — the area's check always calls `recheck.holds` first                                                                                                               |
| same, through `holds_from_inputs`       | exit 1: the protocol has no answer yet — the check follows the adoption                                                                                                                                                                                  |
| `labkit-next .`                         | the new analysis audit is owed (the code changed since the audit of `aa0a`)                                                                                                                                                                              |
| `labkit-adopt . 6ead`                   | exit 2: the Conclusion is open                                                                                                                                                                                                                           |

Not run: the analysis audit (an agent call) and the Conclusion (the author's text), so neither the adoption, report-check nor what the adopted result shows of the origin, both commits and the finding.

Where the two ways are not yet clearly delimited in labkit:

- Three relations of a run to earlier answers exist; the skeleton carries two. `derived_from` re-reads the parent's rows and holds the parent's code (`runs.lineage`). An origin input with rows of its own is rechecked by the stamped `02_analyze.py` (`holds`, then `verified_from_inputs`). An origin input with no rows of its own — the correction case — has `recheck.holds_from_inputs`, which no template calls (`labkit/templates/analyze-script.py.template:112`, `analyze-quick-script.py.template:75`); only tests do.
- `code_since_run` says analysis code is not compared, while the skeleton puts the answer reading and `evaluate_rows` into the measure script (`labkit/templates/measure-script.py.template:200`, `:255`).
- The blocker on `derived_from` names "measure anew" or "restore", not the origin input.
- `finalize` warns "no outputs.json" on a run that by design writes none.
- The answer-reading rule (`parse_letter`) is held by neither way.

## Proposal, limited (for the author's decision; not built)

Join existing parts into one tested way; no new run kind and no new run-record field. A re-evaluation is a `measurement` run like today; it is declared by two named inputs its record already has room for.

**1. The declaration lives in two named inputs of the run, not in a new field.** Two places were ruled out. A new `config.json` field: the keys are a closed set both ways (`runs.RUN_CONFIG_KEYS`; a missing or unknown key is refused, `labkit/formats/runs.py:1418`, `:1457`) and this labkit reads schema 5 only, so the field means schema 6 — and schema-6 labkit could no longer read the basis run (schema 5): the correction would lose its origin. A new field in the protocol step `[builds_on]`: "a change to a rule or a field is the next version" and "a protocol of another version is refused" (`labkit/docs/standard.md:3`), so standard 0.34 — and experiment 14's protocol, measured under 0.33, could not carry it. What remains: the names of `data=` inputs are free, and an input entry already records its origin run. A re-evaluation passes `data={..., "re_evaluates": runlog.RunOutput(OUT, run=BASIS), "answer_reading": READING_MODULE}`: two input entries of the existing shape (path, sha256, origin), schema 5 and standard 0.33 unchanged. labkit 0.115.0 reads such a record as two plain inputs; the new labkit gives the two names their meaning (a CHANGELOG entry: two input names now carry a meaning). The basis run's record and every protocol stay as they are.

Every reader branches on these names in the run's record, never on a missing file: one of the two without the other, an `re_evaluates` without a chosen origin, or an `outputs.json` holding the answer file, is refused; a run without them is checked as today.

**2. What is held, and in which tier.**

| Condition                                                                                                                                                                                                 | Tier        | Existing part                                                                                                   | New code                                                                                                          |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| the input `re_evaluates` is the basis run's registered output, its bytes unchanged                                                                                                                        | guaranteed  | input origins (`origin_check.origin_gap`)                                                                       | the meaning of the name                                                                                           |
| the answer reading is unchanged: `answer_reading` and every repo-local module it imports, transitively, byte-equal at the basis run's start (its commit plus `uncommitted.patch`) and at this run's start | guaranteed  | `scope_sha._import_closure`, `repo.blobs_then`                                                                  | the comparison                                                                                                    |
| the registered prompts are unchanged: the field "Prompt (verbatim, per variant)" of the basis run's own text equals the one of this run's text                                                            | guaranteed  | the basis text's read-back (`protocol_then`)                                                                    | the comparison: `registration_differences` does not compare that field (`labkit/formats/protocol_history.py:520`) |
| no model call through labkit: `labkit.run.llm` refuses every call while a declared run is open                                                                                                            | guaranteed  | none — a run writes `llm-calls.jsonl` only when it opens the answer cache; ORIGIN made 6 144 calls and has none | the refusal                                                                                                       |
| all answer reading lies in the declared module                                                                                                                                                            | agent audit | the analysis audit                                                                                              | the audit is shown the declaration                                                                                |

Not held: reading code loaded another way (`importlib`, a path built at run time); reading that depends on a value outside the module's files; reading placed outside the module that the audit misses; a model called by a client other than `labkit.run.llm`.

**3. The recheck.** `recheck` reads the declaration from the run's inputs; the analyze templates call `holds_from_inputs` for a declared run and `holds` otherwise. `finalize` does not warn "no outputs.json" for a declared run.

**4. The result.** The adopted result block names: answers of the basis run (its commit), evaluated by this run (its commit), the step (`id`, `occasion = "repair"`, its `why` naming the finding) and the numbers that changed against the basis run's metrics.

**5. The way out.** The `derived_from` blocker in `run_record_check.code_since_run` names the declared re-evaluation beside "measure anew".

**Experiment 14 can meet the proof without a split and without touching a record.** `lib/scenario_rating.py` holds `parse_letter`, imports only the standard library, and is unchanged from the commit `aa0a` started at (`1d3d170`) to the repair (`bf0bfc7`); `aa0a`'s `uncommitted.patch` touches no file under `lib/`. Passed as `answer_reading`, it compares byte-equal; the protocol keeps standard 0.33 and its step `audit-repair-reevaluate`. Not covered by that guarantee: `unreadable_cause` and the letter filter in `evaluate_rows` stay in `scripts/01_measure.py`, which the repair changed; the repair's diff touches no line of them (read from `git diff 1d3d170 bf0bfc7`), which the audit has to confirm. Moving them into the module now would make the module differ from its state at `aa0a` and block — a split serves the next measurement, not this correction. A proof that would survive a split (run the reading as it stood at the basis run and as it stands over the answer file, compare the results) executes old code and is not proposed.

**Cost for a lab.** Any change to the declared module and its imports needs a new measurement, even a harmless one (in experiment 14 also a change to the scenario parser in the same file).

**Acceptance tests** (synthetic, a stand-in audit record as the scenario tests use; then the copy of experiment 14):

1. Only the metrics change: finalize 0, the template's `--check` passes, adoption passes; the basis run's record and the answer file byte-identical; the result names the basis run, both commits and the step.
2. `parse_letter` changes: refused, "measure anew".
3. A helper the reading module imports changes, and a constant in the reading module changes: each refused.
4. The answer file changed after the basis run: refused.
5. The registered prompt field changed: refused.
6. A model call through `labkit.run.llm` inside a declared run: refused before it is sent.
7. A declared run whose answer input is missing, or that registers the answer file as its output: refused, never checked another way.
8. A run without the two inputs and without output: as today; labkit 0.115.0 reads a declared run's record.
9. A basis run recorded before the change is read and held (the case of `aa0a`); the protocol keeps `standard = "0.33"`.
