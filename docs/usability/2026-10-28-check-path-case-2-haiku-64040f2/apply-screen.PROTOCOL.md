# Experiment protocol: apply-screen

## Summary (after the run, for a person)

- **Conclusion:** The screening model with correct standardization (dividing by standard deviation, not variance) achieves 76.1% agreement with clinician referral labels on 92 labelled persons, exceeding the permutation expectation of 50.3% by 26.0% and satisfying the 15% margin criterion.
- **Limits:** This result holds for the cohort's 92 persons seen by a clinician; 208 additional persons without labels were flagged but not evaluated.
- **Next step:** The fixed model can be used for screening; further validation on external data is recommended.

## Intent (before the run)

- **Terms of this protocol:** Agreement: the share of labelled persons whose flag equals the clinician's label (accuracy). Flag: referral where the model's probability reaches its threshold (0.5). Null lane: the same flags scored against the clinicians' labels permuted with the seed.
- **Question / hypothesis:** Does the supplied screening model (model.json, version 2.1), applied unchanged, agree with the clinicians' referral labels better than a model that learned nothing, on the 92 persons a clinician saw?
- **Success / failure criterion:** [C1] The agreement of the flags on the 92 labelled persons is at least the permutation expectation plus 0.15: the mean agreement of these flags over every ordering of the clinicians' labels, which permutation_expectation() in scripts/01_measure.py computes exactly.
- **Admissibility condition:** [A1] Every labelled person gets a flag (at most 0 without one). [A2] The null lane's agreement lies within 0.13 of the permutation expectation (see the null condition).
- **Registered branch:** n/a — the result does not condition further analyses
- **Timebox:** n/a — task duration was not constrained
- **Split touched:** test — all 300 persons (92 labelled, 208 unlabelled test persons)

## Result (after the run — write back, don't go quiet)

- **Recorded results:** C1 met; A1 met; A2 met · recorded: n_items = 92, n_rows = 392, n_test = 208, a1_empty = 0, a2_score = 0.4782608695652174, a2_target = 0.502835538752363, scored_class_counts = {'no_referral': 48, 'referral': 44}, z_sd = [1.1319430826754953, 0.9504909569644793, 0.9858825073525805, 1.1216943909993424, 1.0184864670381597, 1.0901849672824986], c1_score = 0.7608695652173914, c1_threshold = 0.652835538752363 (run 2026-10-28T17-13-46_3cc0)
- **Deviations after freeze:** The standardization bug (dividing by sd**2 instead of sd) was discovered and fixed after the first measurement; a new run with the corrected code was performed.
- **Interpretation / next step:** The model shows strong predictive agreement with clinician judgments beyond chance level.

## Context (self-contained)

- **Problem in one sentence:** Does the supplied screening model flag for referral better than chance, on persons a clinician evaluated?
- **Prior threads:** n/a — initial application of a fixed model

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

- 2026-10-28T17-13-46_3cc0 — the kept run; its metrics.json is the number

## Follow-up

- **Notes updated:** <[[…]] — reconcile on contradiction>

## Notes (by-catch: ideas, follow-up experiments — cheap now, expensive later)

- n/a

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
id = "p-9d6c5c187052427e"
type = "confirmatory"
repeat_cost = "low"
kind = "apply"
frozen = false
preflight_audit = ""

[result]
run = "2026-10-28T17-13-46_3cc0"
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
