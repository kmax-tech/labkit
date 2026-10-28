# Experiment protocol: apply-screen

## Summary (after the run, for a person)

- **Conclusion:** After fixing the standardisation implementation, the corrected model achieves 76.1% agreement with clinicians' referral decisions, exceeding the permutation expectation (50.3%) by the registered margin of 0.15. The null admissibility condition ([A2]) verifies the permutation draw, not the predictor output.
- **Limits:** <how far it holds, one sentence…>
- **Next step:** <what follows…>

## Intent (before the run)

- **Terms of this protocol:** Agreement: the share of labelled persons whose flag equals the clinician's label (accuracy). Flag: referral where the model's probability reaches its threshold (0.5). Null lane: the same flags scored against the clinicians' labels permuted with the seed.
- **Question / hypothesis:** Does the supplied screening model (model.json, version 2.1), applied unchanged, agree with the clinicians' referral labels better than a model that learned nothing, on the 92 persons a clinician saw?
- **Success / failure criterion:** [C1] The agreement of the flags on the 92 labelled persons is at least the permutation expectation plus 0.15: the mean agreement of these flags over every ordering of the clinicians' labels, which permutation_expectation() in scripts/01_measure.py computes exactly.
- **Admissibility condition:** [A1] Every labelled person gets a flag (at most 0 without one). [A2] The null lane's agreement lies within 0.13 of the permutation expectation (see the null condition).
- **Registered branch:** <if a result decides the conclusion or the next analysis, register it…>
- **Timebox:** <hard budget, e.g. 4h — then log and ask>
- **Split touched:** <which split may be touched: train | dev | test>

## Result (after the run — write back, don't go quiet)

- **Recorded results:** C1 met; A1 met; A2 met · recorded: n_items = 92, n_rows = 392, n_test = 208, a1_empty = 0, a2_score = 0.4782608695652174, a2_target = 0.502835538752363, scored_class_counts = {'no_referral': 48, 'referral': 44}, c1_score = 0.7608695652173914, c1_threshold = 0.652835538752363 (run 2026-10-28T17-32-30_90d9); subject to 2 recorded limitations (the Limit lines below)
- **Limit (audit 2026-10-28T17-35-analysis #1):** the verdicts stand, read within this limit — The protocol now declares run 2026-10-28T17-32-30_90d9, which audited in this record, contains the output file apply-screen_v3.jsonl and produces the reported metrics with the correct standardisation code
- **Limit (audit 2026-10-28T17-39-analysis #1):** the verdicts stand, read within this limit — The registered null_band 0.13 was derived from the pre-fix predictor, but remains valid: the current run's margin is 0.025 against 0.13, so the verdict does not flip; the repaired predictor passes A2 with wide margin
- **Deviations after freeze:** <"none", or what was changed after `frozen = true`…>
- **Interpretation / next step:** <one sentence…>

## Context (self-contained)

- **Problem in one sentence:** <no technical terms — what is being found out?>
- **Prior threads:** <2–3 [[wikilinks]], each with half a sentence on why they lead here…>

## Setup

- **Data / scope:** data/raw/screening/cohort.csv, 300 persons, 92 with a clinician's label (scored), 208 without (flagged only); prepared by scripts/00_prepare.py into data/prepared/person_v1.jsonl with the six features in model.json's order. The model is applied as model.json specifies it: each feature standardised with the model's own mean and standard deviation (model.json), the weighted sum plus the intercept, the logistic function, a referral where the probability is at least 0.5.
- **Model / tool:** n/a — no model call; the unchanged predictor is loaded by `make_estimator()` in scripts/01_measure.py
- **Model I/O:** in · the six standardised features of one person · out · referral or no_referral from the unchanged model, never fitted
- **Null condition / anchors (in the same run):** [A2] the same flags scored against the clinicians' labels permuted with the seed, expected within null_band 0.13 of the permutation expectation, the mean agreement over every ordering of the gold, which permutation_expectation() in scripts/01_measure.py computes exactly; 0.13 is the 0.99 quantile of |null − expectation| over 200 permutations, rounded up to two places (--calibrate-null on the supplied model, before this registration).
- **Exclusions / filters:** None dropped: all 300 persons are flagged; agreement is computed over the 92 labelled persons only.
- **Unit:** one person

## Checks (render check → instrument check → pilot)

- **Resolution check (ZERO calls, real `evaluate()` on synthetic
  extremes):** <perfect effect → criterion fires? · null effect → stays silent? Both…>
- **Render check (ZERO calls, `--show N`):** n/a — no prompt; `--show N` prints the config and N feature rows
- **Instrument check (real pipeline, ~10 calls, `--probe N`):** <`--probe N` · the unchanged predictor on N labelled items, both lanes · scores read, never reported>
- **Yield per stage:** <expected vs. obtained per parse step (→ LAB-023 No silent loss)>
- **Clarified terms:** <what was ambiguous, and what is it called now?>
- **Changed — and in which class:** <instrument…>
- **Pilot:** <N items checked against hand analysis or anchors, before scaling>

## Runs (protocol run list — via `runlog`, cite run_ids instead of retyping numbers)

- 2026-10-28T17-23-05_5581 — the kept run; its metrics.json is the number

## Follow-up

- **Notes updated:** <[[…]] — reconcile on contradiction>

## Notes (by-catch: ideas, follow-up experiments — cheap now, expensive later)

- <…>

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
id = "p-ca8fb5e200cb47d4"
type = "confirmatory"
repeat_cost = "low"
kind = "apply"
frozen = false
preflight_audit = ""

[result]
run = "2026-10-28T17-32-30_90d9"
# With a model: `[model] alias` (stamped by --model), `[model.arms.<arm>]` with
# profile, fingerprint, alias (finalize holds them to the run); `[gate] labels = […]`.

# The promises as data (labkit 0.71): one table per id — the key the run
# reports, the sentence (this promise stated explicitly — no `<…>` left at the
# freeze), the code region, and the constants the script reads with
# promises.all_constants(). A constant is
# named like the config key (lowercase) and stands in exactly one table;
# `frozen = true` owes these tables, and no run starts whose config lacks a
# constant or carries another value. The numbers below are the stamp's
# examples, not your design: set each, before the commit, to the value its
# sentence states. `margin`: the smallest lead over the null lane you call
# success, chosen from the question, never from a result. `null_band`: how
# far the null lane may stray from its target — at an apply with the
# estimator skeleton the exact permutation expectation, from which the bar
# also starts, and `scripts/01_measure.py --calibrate-null` derives the band
# before the commit; elsewhere chance. After the first measurement none of
# them changes.
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "the agreement of the flags on the 92 labelled persons is at least the permutation expectation plus margin 0.15"
scope = ["scripts/01_measure.py"]
constants = { margin = 0.15 }

[[promise]]
id = "A1"
key = "a1_pass"
sentence = "at most max_empty 0 labelled persons without a flag"
scope = ["scripts/01_measure.py"]
constants = { max_empty = 0 }

[[promise]]
id = "A2"
key = "a2_pass"
sentence = "the null lane's agreement lies within null_band 0.13 of the permutation expectation, the 0.99 quantile of |null - expectation| over 200 permutations rounded up to two places"
scope = ["scripts/01_measure.py"]
constants = { null_band = 0.13 }
```
