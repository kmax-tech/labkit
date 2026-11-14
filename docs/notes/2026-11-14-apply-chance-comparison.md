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

## What is built

The apply stamp carries, after [quality-check-2], a commented-out `[[promise]]` table `criterion-2`: "the registered SCORE exceeds the permutation expectation plus null_band". Uncommented, the skeleton reports `criterion_2_threshold` and `criterion_2_pass` (`MeasureConfig.chance_criterion`, set from the registered ids). Not registered, it reports neither, since intent-check would refuse a key that no promise registers. A failed quality check gives `criterion_2_pass` None, as for [criterion-1]. `chance_check` refuses a registered `criterion-2` before the run opens where the band is no permutation quantile. Making the comparison a duty, choosing another level, or extending it to fit would each be a separate decision.
