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

This concerns [quality-check-2]'s band comparison itself, not only `criterion-2`. Only the first measurement of a protocol is held to the band rule. After it, nothing ensures that the registered band belongs to a later run's predictions and items:

- `band_check` returns early once a first measurement exists (`labkit/templates/measure-estimator-script.py.template:717`, "the band stands as registered"). This was a deliberate decision (`56e98995`, 2026-10-29): "After the first measurement nothing is checked: a repair changes the predictions while the registered band stands." It is pinned by `tests/test_apply_skeleton.py:279`.
- The registered band cannot change after the first measurement (report-check refuses a changed constant).
- The registration hold compares the protocol's texts — question, data field, exclusions, unit, kind — and lets a code change measured again under the same fields pass (`labkit/gates/registration_hold.py:274`).
- From reading the code, nothing compares the items' or the predictor's digests of a later run with those of the first measurement. This was not reproduced with a run.

So a later run with a repaired predictor, a changed predictor file or edited items under an unchanged protocol text is judged against a band calibrated on other predictions. Then [quality-check-2] holds its null draw to a spread that is not its own, and `criterion-2`'s threshold is not a quantile of this run's permutation distribution. Ways to decide, by the author:

1. **Check the rule at every measurement:** recompute the band from the run's own predictions and items before the run opens, and refuse a mismatch. Since the band is frozen after the first measurement, a repair that moves the band then needs a new registration or a handover.
2. **Record and compare:** each run records the band its own predictions give under the rule, and report-check or finalize compares it with the registered one, as a WARNING or BLOCKER. The measurement still runs, and the mismatch is visible at adoption.
3. **Keep the current state and state the limit:** the band carries its meaning for the first measurement's predictions only; for a later run it is a registered constant.

## What is built

The comparison is offered in two places, both commented out; turning it on takes both steps:

1. **Protocol:** after [quality-check-2] the apply stamp carries a commented-out `[[promise]]` table `criterion-2`: "the registered SCORE exceeds the permutation expectation plus null_band". Uncomment it and name the id, in brackets, in the Inference criterion field.
2. **Skeleton:** uncomment the block between the `criterion-2` markers in `evaluate_rows` of `scripts/01_measure.py`. It reports `criterion_2_threshold` and `criterion_2_pass`; a failed quality check gives `criterion_2_pass` None, as for [criterion-1].

Why the code is commented out too (decided by the author, 2026-11-14, after the review found it): with the key-writing lines active, code-check warned on every new fit and apply area of a key in the id namespace that no promise registers. Assembling the keys at run time to hide them would make code-check block a registered `criterion-2`, since it requires a key literal. Each step alone is held: the table without the code is a code-check BLOCKER (no script names the key), the code without the table a code-check WARNING and an intent-check BLOCKER at finalize. What stays active is the precondition: the registered table sets `MeasureConfig.chance_criterion`, and `chance_check` refuses before the run opens where the band is no permutation quantile.

Making the comparison a duty, choosing another level, or extending it to fit would each be a separate decision.
