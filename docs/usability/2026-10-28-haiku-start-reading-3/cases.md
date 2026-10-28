# Start-of-experiment cases (2026-10-28)

Rules for the reader:

1. Read instructions.md completely first; it is the AGENTS.md of the lab you work in.
2. Each situation below is independent. You are the agent working on a task in a fresh lab
   repository (labkit installed in `.venv`, git hooks installed). Tool output is quoted verbatim.
3. Answer every question (a)-(d) of both situations from instructions.md and the quoted output only.
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
     terms, question, unit, data, exclusions — no criterion, no promise table: a computation judges no prediction, so it has no bar to clear; `protocol-check --contract` names the labels.
  3. scripts/01_measure.py: expected_ids(), rows(), evaluate_rows(); after every code change `code-check experiments/01-hrv`; tests/test_01_hrv.py on hand-checked cases.
  4. git add + commit, then scripts/01_measure.py — in the foreground; it is the instrument check too.
  5. `finalize experiments/01-hrv` checks the provenance (source frozen in the run, tracked in git), then the analysis audit (`labkit-audit experiments/01-hrv --mode analysis`), decided.
  6. the Conclusion, then `protocol-fill experiments/01-hrv/PROTOCOL-hrv.md --from-run <run_id>` adopts the number: it runs report-check, whose last station is scripts/02_analyze.py --check; a task's output file is written from that run only after it.
```

You then ran `protocol-check experiments/01-hrv/PROTOCOL-hrv.md --contract`; its first part:

```
at repeat_cost = "low" (nothing freezes, no SHOULD) the protocol owes: Terms of this protocol, Question / hypothesis, Data / scope, Exclusions / filters, Unit; with a bar (kind fit or apply) also the criterion, the admissibility condition, the null condition and Model / tool; with a `[model]` table also Data profile, Prompt; after the run: Recorded results, Conclusion; with a model also Raw output.
fill a field by its label, multi-line placeholders included: protocol-fill PROTOCOL-x.md "<label>" "<value>"; what is still open: protocol-fill PROTOCOL-x.md --list; the Prompt block from the scripts' PROMPT constants: protocol-fill PROTOCOL-x.md --prompts

what PROTOCOL-hrv.md owes, by occasion — its repeat_cost, kind and model, from the one table every gate reads (standard_contract):
  repeat_cost = 'low', kind = 'compute', no model: the compute skeleton (01_measure.py, 02_analyze.py; the run is the instrument check)
    before a full run: the registration written and committed (the first measurement is held to what its commit holds): Question / hypothesis — runlog checks these; the pre-commit hook holds every field the first line names, so the commit carries all of them; the run may start in the foreground
    after the run: `finalize` clean — the answering run bound and cited, the promises answered, the scopes unchanged, the source frozen in the run and tracked in git
    at the release (`protocol-fill --from-run`, the stop, the commit): no freeze owed, the registration as committed at the first measurement, finalize clean, a full run (no probe, no acknowledged run), a decided analysis audit of code, promises and that run (a BLOCKER accepted with `stands` upheld by a decision review, `labkit-audit --review`), `scripts/02_analyze.py --check` passing
```

## Situation T4 — the measurement is refused: registration not written

In the area of T1 you implemented `expected_ids()`, `rows()` and `evaluate_rows()` in
`scripts/01_measure.py` and ran it (`.venv/bin/python experiments/01-hrv/scripts/01_measure.py`).
The protocol is still as stamped. Output (exit code 1):

```
runlog: this run declares run_kind='measurement', but its protocol is not ready for one:
  PROTOCOL-hrv.md: `repeat_cost = "low"`, but the registration is not written: Question / hypothesis (the commit also owes the other fields `protocol-check --contract` names) — at low repeat cost the gate is the registration the kind owes (a computation its question; a fit or an apply also criterion · admissibility condition · null condition; with a model the data profile), not the freeze (LAB-003 No run without an intent paragraph, LAB-017 The number of audits follows the cost tier)
At repeat_cost = "low" nothing freezes: write and commit the registration the kind owes (`protocol-check --contract` names it), then start the run again. No other run yields a reported number: a probe (run_kind='probe') and a run acknowledged with LABKIT_UNFROZEN=1 (at high repeat cost only over an audit the backend refused, audits/*-failed.toml written by labkit-audit) are recorded as such, and report-check refuses their numbers.
```

