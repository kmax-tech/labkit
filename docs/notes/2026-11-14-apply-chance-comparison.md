# Comparing an apply measurement with chance — what `null_band` licenses (2026-11-14)

Plan step 3, point 3 of the usage-round-24 findings (`TODO.md`): in sts512 the task asked whether the agreement exceeds chance, the bar was one the task states (`at_least`, Spearman ≥ 0.95), and no promise compared the measured 0.9225 with the null. Every one of the six auditors flagged the "above chance" sentence the agents wrote anyway; in one attempt the report dropped the answer to that question. Decided by the author on 2026-11-14: first state what the existing calibration's band denotes and which statement a comparison with it allows, then offer an optional, commented-out promise in the apply stamp — no general duty and no new threshold.

**Released statement:** a pass of `criterion-2` says that the registered score lies *above the registered null band*. The false-alarm bound below has been derived and independently reviewed, but the author has not released it. Until the author does, neither the stamp, the skeleton nor a report states a level.

## What `null_band` is

At kind apply with the permuted null and a registered band rule (`null_band_quantile`, `null_permutations`; the stamp registers 0.99 and 200), `band_by_rule` in the estimator skeleton:

1. keeps the unchanged predictor's predictions on the labelled items fixed;
2. scores them against `k` seeded permutations of the gold (`calibrate-null:<seed>:<n>`);
3. takes the absolute deviations `|S_perm − E|` from the exact permutation expectation `E` (`permutation_expectation`);
4. returns the deviation at rank `r = ceil(q·k)` (the 198th of 200), rounded up to two places.

So `null_band` is a two-sided Monte-Carlo quantile of the score's spread under random label assignment, for exactly these predictions. The calibration never scores the true gold. At the first measurement `band_check` recomputes the band from the predictions on exactly the items the run measures and refuses a registered value the rule does not give; the measurement reuses those predictions as its registered lane.

## Derivation of a false-alarm bound — not released

H0: the gold is exchangeable across the items, given the predictions. Let `b⁺` be the number of draws scoring at least the measured `S`. The one-sided Monte-Carlo permutation p-value `(1 + b⁺)/(k + 1)` is valid under H0, discrete scores and draws with replacement included. If `S − E > null_band ≥ d_(r)`, every draw with `T_n ≥ S` has a deviation strictly above `d_(r)`, and at most `k − r` draws do. So `b⁺ ≤ k − r`, and a pass implies a p-value of at most `(1 + k − r)/(k + 1)`: 3/201 ≈ 0.015 with the stamp's rule. The comparison is strict, since `≥` with a band equal to `d_(r)` would admit ties at the rank. Rounding up only raises the threshold. `E` needs to be a function of the predictions and the gold multiset only, not the permutation mean. Requiring the quality checks to pass only shrinks the pass event.

Independent review of `ee2af670` (2026-11-14): the derivation holds, but only under five conditions.

1. **Exchangeable items.** Independence of predictions and gold alone is not enough. Items clustered by source, or near-duplicates, break the bound.
2. **The band belongs to these predictions on these items.** `band_check` checks this only at the first measurement, so a later measurement relies on a deterministic predictor and unchanged items.
3. **The seed is fixed independently of the calibration's outcome.** Calibrating under several `--seed` values and measuring with the one that gives the smallest band inflates the level; nothing in the code prevents it.
4. **One pre-registered comparison per protocol**, with no choosing among repeated full runs. `--repeat-of` draws are never the answer.
5. **3/201 holds only for q = 0.99 and k = 200**; other rules give `(1 + k − ceil(q·k))/(k + 1)`.

Supplementary, not a proof: a simulation under H0 (Spearman, n = 30, 4000 repetitions, the rule as built) gave a one-sided exceedance of 0.0088 and a two-sided one of 0.0165, against 0.0149 for the two-sided bound and within one standard error (0.0019) of it.

Not licensed in any case:

- anything about size — with many items a weak association passes; the task's bar stays [criterion-1];
- a p-value finer than `1/(k + 1)` — 200 permutations cannot show p < 0.005;
- a statement where the band is not a permutation quantile: at fit (refits, a reasoned band), with a registered `NULL_ORDER` or a fixed null predictor, or without a registered band rule. The comparison is refused there.

sts512 for scale: the maximum over 200 permutations was 0.117 (attempt a-r2), the measurement 0.9225.

## Open: the band at later measurements

This concerns [quality-check-2]'s band comparison itself, not only `criterion-2`. Only the first measurement of a protocol is held to the band rule:

- `band_check` returns early once a first measurement exists (`labkit/templates/measure-estimator-script.py.template:717`, "the band stands as registered"). This was a deliberate decision (`56e98995`, 2026-10-29): "After the first measurement nothing is checked: a repair changes the predictions while the registered band stands." It is pinned by `tests/test_apply_skeleton.py:279`.
- The registered band cannot change after the first measurement (report-check refuses a changed constant).
- The registration hold compares the protocol's texts and lets a code change measured again under the same fields pass (`labkit/gates/registration_hold.py:274`).

### Replayed 2026-11-14

Setup: the end-to-end scenario's apply area (`tests/test_end_to_end.py`, `points_area`: 12 labelled points, 6 per class), a fixed threshold on feature 0, real commands in a temporary git lab. Steps: `--calibrate-null --write`, commit, first measurement, commit; then the threshold is repaired, committed, and measured again into a new output file. A first attempt to measure into the old output file was refused by runlog: rows from another instrument. Then `finalize`. Script and logs are internal (labkit-evidence, `usability/2026-11-14-band-second-run/`, `de62011d`); the numbers:

| Repair         | Predictions pos/neg, 1st → 2nd | Registered band | Rule's band for the 2nd run | 2nd run: null draw off | finalize |
|----------------|--------------------------------|-----------------|-----------------------------|------------------------|----------|
| x > 4 → x > 0  | 4/8 → 6/6                      | 0.34            | 0.34                        | 0.0000                 | exit 0   |
| x > 4 → x > 10 | 4/8 → 1/11                     | 0.34            | 0.09                        | 0.0833                 | exit 0   |
| x > 10 → x > 4 | 1/11 → 4/8                     | 0.09            | 0.34                        | 0.0000                 | exit 0   |

The second measurement prints nothing about the band. `finalize` passes all three. In the third row the registered band is a quarter of the run's own spread. With it, a `criterion-2` threshold would be 0.5 + 0.09 = 0.59, and the score 0.8333 would read as above the band. With the run's own band the threshold is 0.84, and the same score lies below it. A stale band can thus err in either direction: too wide makes [quality-check-2] lax and `criterion-2` strict, too narrow the reverse.

### The variant the author prefers: a fixed rule, a band computed and kept per run

The protocol registers only the rule (`null_band_quantile`, `null_permutations`) at apply with the permuted null. `evaluate_rows` computes the band from the run's own kept registered predictions and gold by `band_by_rule` and writes it to the metrics, for example as `quality_check_2_band`. [quality-check-2] and `criterion-2` then read that band. Checked against the code and the standard:

- **Standard.** LAB-035 Thresholds belong to the run, not to the measure: "What can be preregistered is the *rule* …, not the *value*. A threshold with no reference to the null condition of the same run is a number without a unit." A per-run band from a registered rule is that rule's case. The registered value meets it only for the first measurement. The standard does not mention `null_band`, so the change needs no new standard version.
- **What it removes.** `--calibrate-null --write` and `band_check` become unnecessary; `--calibrate-null` can stay as a preview. Both were a source of agent error: in the fifth SAB-like draw an agent registered 0.05 after reading 0.1276 (`56e98995`). No band is seen before the measurement any more.
- **Validity.** Condition 2 of the derivation (the band belongs to these predictions on these items) holds by construction for every run. Conditions 1, 3 (as far as before the registration), 4 and 5 remain. No information about the measured score enters: the band reads the predictions and the gold only through permutations.
- **The permutations' seed** is a decision of its own. Seeded from the run's seed, as today, a `--seed` run gets another band, and choosing among runs would select on it. Seeded from something the registration fixes, such as the protocol id, the band is a function of the rule, the predictions and the items only, and a repeat with the same predictions gives the same band.
- **Reproducibility.** The band is a deterministic function of the kept rows and the config, so `--eval-only`, `02_analyze.py` and a recheck recompute it exactly. Cost per evaluation, measured with the skeleton's `band_by_rule` at 200 permutations: Spearman at 512 items 0.5 s, at 2000 items 2.1 s, accuracy at 2000 items 0.07 s, AUC at 2000 items 4.8 s.
- **[quality-check-2]'s meaning** is unchanged: one permuted draw within the 0.99 quantile of its own permutation spread. With a correct null lane it fails in about 1 % of runs, as it does today at the first measurement, now at every run. A broken null lane, one that is not permuted, still fails it.
- **Not covered.** At fit, with a registered `NULL_ORDER` or with a fixed null predictor there is no permutation spread of these predictions, and the band stays a registered, reasoned value. Two regimes remain; the same LAB-035 question at fit is not part of this change.
- **Scope of the break.** No package code reads `null_band` outside the templates; areas keep the skeleton copy they were stamped with, and their protocols still read. New stamps, the skeleton, the area test template, the stamp comparison files and the field guide change. This is a contract change of its own, with a CHANGELOG entry under Breaking, not part of plan step 4.

Against the three ways named before: check at every measurement and refuse a mismatch (it would force a new registration for every repair that moves the band); record and compare with the registered value (it keeps a value that is wrong for later runs and only signals); keep and state the limit (it leaves the gap the replay shows). The per-run band closes the gap without a new registration and without a refusal.

## What is built

The comparison is offered in two places, both commented out; turning it on takes both steps:

1. **Protocol:** after [quality-check-2] the apply stamp carries a commented-out `[[promise]]` table `criterion-2`: "the registered SCORE exceeds the permutation expectation plus null_band". Uncomment it and name the id, in brackets, in the Inference criterion field.
2. **Skeleton:** uncomment the block between the `criterion-2` markers in `evaluate_rows` of `scripts/01_measure.py`. It reports `criterion_2_threshold` and `criterion_2_pass`; a failed quality check gives `criterion_2_pass` None, as for [criterion-1].

Why the code is commented out too (decided by the author, 2026-11-14, after the review found it): with the key-writing lines active, code-check warned on every new fit and apply area of a key in the id namespace that no promise registers. Assembling the keys at run time to hide them would make code-check block a registered `criterion-2`, since it requires a key literal. Each step alone is held: the table without the code is a code-check BLOCKER (no script names the key), the code without the table a code-check WARNING and an intent-check BLOCKER at finalize. What stays active is the precondition: the registered table sets `MeasureConfig.chance_criterion`, and `chance_check` refuses before the run opens where the band is no permutation quantile.

Making the comparison a duty, choosing another level, or extending it to fit would each be a separate decision.
