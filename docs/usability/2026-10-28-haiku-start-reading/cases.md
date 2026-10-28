# Start-of-experiment cases (2026-10-28)

Rules for the reader:

1. Read instructions.md completely first; it is the AGENTS.md of the lab you work in.
2. Each situation below is independent. You are the agent working on a task in a fresh lab
   repository (labkit installed in `.venv`, git hooks installed). Tool output is quoted verbatim.
3. Answer every question (a)-(d) of every situation from instructions.md and the quoted output only.
   Where the two leave you unsure, or contradict each other, say so and name the passage.
4. Do not invent flags or commands that neither source names.

Questions for every situation:

(a) What does the quoted output ask of you, in your own words?
(b) What exactly do you write or decide before the next commit — list every field, value or
    setting, and say for each whether it is your own decision or given by the tool.
(c) Which commands do you run next, in order, up to and including the first full measurement?
(d) What do you not do, and why?

## Situation T1 — a computation area was just stamped

Task: compute the RMSSD of an ECG recording (`data/ecg.csv`) and write it to
`pred_results/hrv.csv`. You ran `labkit-init exp hrv --repeat-cost low --kind compute`. Its output
ends with:

```
Next (repeat_cost = "low" — no freeze, no audit before the run, the run is the instrument check):
  1. Check the kind before anything else. (1) Does this area train, adjust or select a model or prediction procedure (a threshold or prompt chosen on performance data counts)? yes: fit — also when the deliverable is predictions on unlabelled rows; the kept number is then the model's score on held-out labelled rows. (2) Otherwise: does the number judge how well a model used unchanged predicts, against gold labels or targets? yes: apply, no: compute. Repeat cost does not decide the kind: a fit that takes seconds is a fit. If (1) is yes: `labkit-init exp hrv --kind fit --change-kind` — before the first measurement; it keeps what you wrote and refuses to replace a file you changed.
  2. PROTOCOL-hrv.md: fill the low cut — `type` in the head, then
     question, unit, data, exclusions — no criterion, no promise table: a computation judges no prediction, so it has no bar to clear; `protocol-check --contract` names the labels.
  3. scripts/01_measure.py: expected_ids(), rows(), evaluate_rows(); after every code change `code-check experiments/01-hrv`.
  4. git add + commit, then scripts/01_measure.py — in the foreground; it is the instrument check too.
  5. `finalize experiments/01-hrv` checks the provenance (source frozen in the run, tracked in git), then the analysis audit (`labkit-audit experiments/01-hrv --mode analysis`), decided.
  6. `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --from-run <run_id>` adopts the number: it runs report-check, whose last station is scripts/02_analyze.py --check.
```

You then ran `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract`; its first part:

```
at repeat_cost = "low" (nothing freezes, no SHOULD) the protocol owes: Terms of this protocol, Question / hypothesis, Data / scope, Exclusions / filters, Unit; with a bar (kind fit or apply) also the criterion, the admissibility condition, the null condition and Model / tool; with a `[model]` table also Data profile, Prompt; after the run: Recorded results, Conclusion; with a model also Raw output.
fill a field by its label, multi-line placeholders included: protocol-fill PROTOCOL-x.md "<label>" "<value>"; what is still open: protocol-fill PROTOCOL-x.md --list; the Prompt block from the scripts' PROMPT constants: protocol-fill PROTOCOL-x.md --prompts

what PROTOCOL-hrv.md owes, by occasion — its repeat_cost, kind and model, from the one table every gate reads (standard_contract):
  repeat_cost = 'low', kind = 'compute', no model: the compute skeleton (01_measure.py, 02_analyze.py; the run is the instrument check)
    before a full run: the registration written and committed (the first measurement is held to what its commit holds): Question / hypothesis; the run may start in the foreground
    after the run: `finalize` clean — the answering run bound and cited, the promises answered, the scopes unchanged, the source frozen in the run and tracked in git
    at the release (`protocol-fill --from-run`, the stop, the commit): no freeze owed, the registration as committed at the first measurement, finalize clean, a full run (no probe, no acknowledged run), a decided analysis audit of code, promises and that run (a BLOCKER accepted with `stands` upheld by a decision review, `labkit-audit --review`), `scripts/02_analyze.py --check` passing
```

## Situation T2 — a fit area was just stamped

Task: train a classifier on labelled assay compounds (`data/assay.csv`), predict the unlabelled
ones and write `pred_results/assay_pred.csv`. You ran
`labkit-init exp assay --repeat-cost low --kind fit`. Its output ends with:

```
Next (repeat_cost = "low" — no freeze, no audit before the run, the run is the instrument check):
  1. PROTOCOL-assay.md: fill the low cut — `type` in the head, then
     question, unit, data, exclusions, criterion, admissibility condition, null condition — kind = 'fit': the number judges a prediction, so it has a bar and its reference; `protocol-check --contract` names the labels.
  2. scripts/01_measure.py: make_estimator(), SCORE, FEATURES_FIELD; --show 3, then the run; after every code change `code-check experiments/01-assay`.
  3. git add + commit, then scripts/01_measure.py — in the foreground; it is the instrument check too.
  4. `finalize experiments/01-assay` checks the provenance (source frozen in the run, tracked in git), then the analysis audit (`labkit-audit experiments/01-assay --mode analysis`), decided.
  5. `protocol-fill experiments/01-assay/PROTOCOL-assay.md --from-run <run_id>` adopts the number: it runs report-check, whose last station is scripts/02_analyze.py --check.
```

The stamped protocol `experiments/01-assay/PROTOCOL-assay.md`, as written by the stamp:

````markdown
# Experiment protocol: assay

## Summary (after the run, for a person)

- **Conclusion:** <the answer to the question above, in at most two plain sentences…>

## Intent (before the run)

- **Terms of this protocol:** <first, because the question uses them…>
- **Question / hypothesis:** <the one question — what do we expect?>
- **Success / failure criterion:** [C1] <how do we recognise whether it worked? One id per conjunct, written…>
- **Admissibility condition:** [A1] <what must hold in the same run before any verdict is issued…>

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <generated metrics, run_id and limits note…>

## Setup

- **Data / scope:** <source, N, producer script; pilot subset first>
- **Model / tool:** n/a — no model call; the instrument is the estimator of `make_estimator()` in scripts/01_measure.py
- **Null condition / anchors (in the same run):** [A2] <the same estimator on labels permuted inside each fitting fold, expected at chance_of() within null_band>
- **Exclusions / filters:** <what is dropped from the data or output and why…>
- **Unit:** <what one counted or judged thing is…>

## Runs (protocol run list — via `runlog`, cite run_ids instead of retyping numbers)

- <run_id> — <one sentence: what this run was>

## Head (read by the checks)



*How to fill each field, the cuts by tier and the intent ids:
`protocol-field-guide.md` (`protocol-check --guide`); which fields this
protocol's `repeat_cost` owes, and which fall due once a result is declared:
`protocol-check --contract` — the one list, never retyped here; fill by
label with `protocol-fill PROTOCOL-<name>.md "<label>" "<value>"`.*

```toml
# `[result] run = "<run_id>"` below [protocol], written by `protocol-fill --from-run`
# after a clean `finalize`: the one declaration that this protocol reports a number.
[protocol]
standard = "0.23"
id = "p-a3f9d70ca31a40ed"
type = "<exploratory | confirmatory>"
repeat_cost = "low"
kind = "fit"
frozen = false
preflight_audit = ""
# With a model: `[model] alias` (stamped by --model), `[model.arms.<arm>]` with
# profile, fingerprint, alias (finalize holds them to the run); `[gate] labels = […]`.

# The promises as data (labkit 0.71): one table per id — the key the run
# reports, the sentence (this promise stated explicitly — no `<…>` left at the
# freeze), the code region, and the constants the script reads with
# promises.all_constants(). A constant is
# named like the config key (lowercase) and stands in exactly one table;
# `frozen = true` owes these tables, and no run starts whose config lacks a
# constant or carries another value.
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "<the criterion · the registered lane's out-of-fold SCORE is at least the null lane's plus margin>"
scope = ["scripts/01_measure.py"]
constants = { margin = 0.25 }

[[promise]]
id = "A1"
key = "a1_pass"
sentence = "<the yield · at most max_empty labelled items without an out-of-fold prediction>"
scope = ["scripts/01_measure.py"]
constants = { max_empty = 0 }

[[promise]]
id = "A2"
key = "a2_pass"
sentence = "<the null condition · the permuted-label lane scores within null_band of chance>"
scope = ["scripts/01_measure.py"]
constants = { null_band = 0.1 }
```
````

`protocol-check experiments/01-assay/PROTOCOL-assay.md --contract`, first part:

```
at repeat_cost = "low" (nothing freezes, no SHOULD) the protocol owes: Terms of this protocol, Question / hypothesis, Data / scope, Exclusions / filters, Unit; with a bar (kind fit or apply) also the criterion, the admissibility condition, the null condition and Model / tool; with a `[model]` table also Data profile, Prompt; after the run: Recorded results, Conclusion; with a model also Raw output.
fill a field by its label, multi-line placeholders included: protocol-fill PROTOCOL-x.md "<label>" "<value>"; what is still open: protocol-fill PROTOCOL-x.md --list; the Prompt block from the scripts' PROMPT constants: protocol-fill PROTOCOL-x.md --prompts

what PROTOCOL-assay.md owes, by occasion — its repeat_cost, kind and model, from the one table every gate reads (standard_contract):
  repeat_cost = 'low', kind = 'fit', no model: the estimator skeleton (00_prepare.py, 01_measure.py, 02_analyze.py; the run is the instrument check)
    before a full run: the registration written and committed (the first measurement is held to what its commit holds): Question / hypothesis, Success / failure criterion, Admissibility condition, Null condition / anchors; the run may start in the foreground
    after the run: `finalize` clean — the answering run bound and cited, the promises answered, the scopes unchanged, the source frozen in the run and tracked in git
    at the release (`protocol-fill --from-run`, the stop, the commit): no freeze owed, the registration as committed at the first measurement, finalize clean, a full run (no probe, no acknowledged run), a decided analysis audit of code, promises and that run (a BLOCKER accepted with `stands` upheld by a decision review, `labkit-audit --review`), `scripts/02_analyze.py --check` passing
```

Question (b) here in particular: which values in this protocol are already set, and by whom?

## Situation T3 — the first commit after stamping is refused

In the area of T1 you filled nothing yet and ran `git add -A && git commit -m "stamp"`. The
pre-commit hook printed:

```
experiments/01-hrv/PROTOCOL-hrv.md: Runs: the stamped entry is written by `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --from-run <run_id>` after the run
experiments/01-hrv/PROTOCOL-hrv.md: MISSING (must): [protocol] type
experiments/01-hrv/PROTOCOL-hrv.md:9: PLACEHOLDER ONLY (must): Terms of this protocol
experiments/01-hrv/PROTOCOL-hrv.md:10: PLACEHOLDER ONLY (must): Question / hypothesis
experiments/01-hrv/PROTOCOL-hrv.md:18: PLACEHOLDER ONLY (must): Data / scope
experiments/01-hrv/PROTOCOL-hrv.md:19: PLACEHOLDER ONLY (must): Exclusions / filters
experiments/01-hrv/PROTOCOL-hrv.md:20: PLACEHOLDER ONLY (must): Unit
experiments/01-hrv/PROTOCOL-hrv.md: must fields missing or empty — fill them in, or justify as 'n/a — <why>' (the reason must be there, not just the angle brackets): [protocol] type; Terms of this protocol (line 9, placeholder); Question / hypothesis (line 10, placeholder); Data / scope (line 18, placeholder); Exclusions / filters (line 19, placeholder); Unit (line 20, placeholder)

pre-commit: must fields missing (see above) — fill them, or justify as
'<field>: n/a — <why>'.
```

## Situation T4 — the measurement is refused: registration not written

In the area of T1 you implemented `expected_ids()`, `rows()` and `evaluate_rows()` in
`scripts/01_measure.py` and ran it (`.venv/bin/python experiments/01-hrv/scripts/01_measure.py`).
The protocol is still as stamped. Output (exit code 1):

```
runlog: this run declares run_kind='measurement', but its protocol is not ready for one:
  PROTOCOL-hrv.md: `repeat_cost = "low"`, but the registration is not written: Question / hypothesis — at low repeat cost the gate is the registration the kind owes (a computation its question; a fit or an apply also criterion · admissibility condition · null condition; with a model the data profile), not the freeze (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)
Freeze first: `preflight <AREA>` clean, audit stamped, `frozen = true` (at repeat_cost = "low": the registration the kind owes suffices — `protocol-check --contract` names it). No other run yields a reported number: a probe (run_kind='probe') and a run acknowledged with LABKIT_UNFROZEN=1 (at high repeat cost only over an audit the backend refused, audits/*-failed.toml written by labkit-audit) are recorded as such, and report-check refuses their numbers.
```

## Situation T5 — the measurement is refused: protocol not committed

In the area of T1 you have now filled `type`, Terms of this protocol, Question / hypothesis,
Data / scope, Exclusions / filters and Unit with `protocol-fill`; `protocol-check` passes. The
protocol and the script are not committed. You ran the script again. Output (exit code 1):

```
runlog: this run declares run_kind='measurement', but its protocol is not ready for one:
  PROTOCOL-hrv.md is not committed — the first measurement is held to the registration its commit holds; commit the protocol (`git add` + `git commit`), then start the run (LAB-003 No run without an intent paragraph)
Freeze first: `preflight <AREA>` clean, audit stamped, `frozen = true` (at repeat_cost = "low": the registration the kind owes suffices — `protocol-check --contract` names it). No other run yields a reported number: a probe (run_kind='probe') and a run acknowledged with LABKIT_UNFROZEN=1 (at high repeat cost only over an audit the backend refused, audits/*-failed.toml written by labkit-audit) are recorded as such, and report-check refuses their numbers.
```
