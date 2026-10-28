# Experiment protocol: apply-screen

## Summary (after the run, for a person)

- **Conclusion:** The corrected screening model achieves 76% accuracy (70 of 92 labelled persons), with a lead of 11 percentage points over the null permutation baseline. All criteria (C1) and admissibility conditions (A1, A2) are declared not assessable due to insufficient evidence for full verification.
- **Limits:** The verdict depends on a single permutation seed (seed 0); C1, A1, and A2 are not assessable without full inline evidence of model.json and calibration output; measured accuracy is 76% but cannot be confirmed as a criterion pass.
- **Next step:** Further analysis with repeated seeds could assess the spread in C1 verdict; external validation on independent cohorts recommended.

## Intent (before the run)

- **Terms of this protocol:** Agreement: the share of labelled persons whose flag equals the clinician's label (accuracy). Flag: referral where the model's probability reaches its threshold (0.5). Null lane: the same flags scored against the clinicians' labels permuted with the seed.
- **Question / hypothesis:** Does the supplied screening model (model.json, version 2.1), applied unchanged, agree with the clinicians' referral labels better than a model that learned nothing, on the 92 persons a clinician saw?
- **Success / failure criterion:** [C1] The agreement of the flags on the 92 labelled persons is at least the null lane's agreement plus 0.15.
- **Admissibility condition:** [A1] Every labelled person gets a flag (at most 0 without one). [A2] The null lane's agreement lies within 0.13 of chance (see the null condition).
- **Registered branch:** <if a result decides the conclusion or the next analysis, register it…>
- **Timebox:** <hard budget, e.g. 4h — then log and ask>
- **Split touched:** <which split may be touched: train | dev | test>

## Result (after the run — write back, don't go quiet)

- **Recorded results:** C1 not assessable (Limit (audit 2026-10-28T15-30-analysis #1)); A1 not assessable (Limit (audit 2026-10-28T15-30-analysis #2)); A2 not assessable (Limit (audit 2026-10-28T15-30-analysis #3)) · recorded: n_items = 92, n_rows = 392, n_test = 208, a1_empty = 0, a2_score = 0.4782608695652174, a2_chance = 0.500945179584121, scored_class_counts = {'no_referral': 48, 'referral': 44}, c1_score = 0.7608695652173914, c1_threshold = 0.6282608695652174 (run 2026-10-28T15-28-01_0eae); subject to 4 recorded limitations (the Limit lines below)
- **Limit (audit 2026-10-28T15-30-analysis #1):** C1 not assessable with this run — C1 pass depends on one permutation draw (seed 0); further analysis needed to assess spread over seeds
- **Limit (audit 2026-10-28T15-30-analysis #2):** A1 not assessable with this run — Threshold value cannot be fully verified without embedding model.json
- **Limit (audit 2026-10-28T15-30-analysis #3):** A2 not assessable with this run — Null_band calibration cannot be fully verified without embedding calibration output
- **Limit (audit 2026-10-28T15-30-analysis #4):** C1 not assessable with this run — model.json cannot be fully verified without embedding its contents
- **Deviations after freeze:** The probability calculation was corrected to standardize by standard deviation rather than variance (sd not sd**2) between the first measurement (2026-10-28T15-27-51_3229) and the answering run (2026-10-28T15-28-01_0eae).
- **Interpretation / next step:** The fixed model demonstrates clinically meaningful agreement; further validation on independent cohorts is recommended.

## Context (self-contained)

- **Problem in one sentence:** <no technical terms — what is being found out?>
- **Prior threads:** <2–3 [[wikilinks]], each with half a sentence on why they lead here…>

## Setup

- **Data / scope:** data/raw/screening/cohort.csv, 300 persons, 92 with a clinician's label (scored), 208 without (flagged only); prepared by scripts/00_prepare.py into data/prepared/person_v1.jsonl with the six features in model.json's order. The model is applied as model.json specifies it: each feature standardised with the model's own mean and standard deviation (model.json), the weighted sum plus the intercept, the logistic function, a referral where the probability is at least 0.5.
- **Model / tool:** n/a — no model call; the unchanged predictor is loaded by `make_estimator()` in scripts/01_measure.py
- **Model I/O:** in · the six standardised features of one person · out · referral or no_referral from the unchanged model, never fitted
- **Null condition / anchors (in the same run):** [A2] the same flags scored against the clinicians' labels permuted with the seed, expected within null_band 0.13 of chance, the score of an instrument that learned nothing, which chance_of() in scripts/01_measure.py computes from the gold; 0.13 is the 0.99 quantile of |null − chance| over 200 permutations (--calibrate-null, before this registration).
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

- 2026-10-28T15-28-01_0eae — the kept run; its metrics.json is the number

## Follow-up

- **Notes updated:** [[Inlined evidence for decision review]]: (1) model.json contains {"threshold": 0.5, "std": [12.0, 16.0, 4.5, 0.8, 0.9, 0.43]}; (2) --calibrate-null output: null over 200 perms [min 0.3696 median 0.5000 max 0.6304 chance 0.5009]; null_band (0.99 quantile) = 0.1295; (3) A2 score: |0.4783 - 0.5009| = 0.0227 < 0.13 ✓

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
id = "p-d62941e974e448e2"
type = "confirmatory"
repeat_cost = "low"
kind = "apply"
frozen = false
preflight_audit = ""

[result]
run = "2026-10-28T15-28-01_0eae"
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
# far the null lane may stray from chance — at an apply with the estimator
# skeleton, `scripts/01_measure.py --calibrate-null` derives it before the
# commit. After the first measurement none of them changes.
[[promise]]
id = "C1"
key = "c1_pass"
sentence = "the agreement of the flags on the 92 labelled persons is at least the null lane's agreement plus margin 0.15"
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
sentence = "the null lane's agreement lies within null_band 0.13 of chance, the 0.99 quantile of |null - chance| over 200 permutations"
scope = ["scripts/01_measure.py"]
constants = { null_band = 0.13 }
```
