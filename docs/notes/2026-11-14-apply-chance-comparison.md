# Comparing an apply measurement with chance — what `null_band` licenses (2026-11-14)

Plan step 3, point 3 of the usage-round-24 findings (`TODO.md`): in sts512 the task asked whether the agreement exceeds chance, the bar was one the task states (`at_least`, Spearman ≥ 0.95), and no promise compared the measured 0.9225 with the null. Every one of the six auditors flagged the "above chance" sentence the agents wrote anyway; in one attempt the report dropped the answer to that question. Decided by the author on 2026-11-14: first state what the existing calibration's band denotes and which statement a comparison with it allows, then offer an optional, commented-out promise in the apply stamp — no general duty and no new threshold.

## What `null_band` is

At kind apply with the permuted null and a registered band rule (`null_band_quantile`, `null_permutations`; the stamp registers 0.99 and 200), `band_by_rule` in the estimator skeleton:

1. keeps the unchanged predictor's predictions on the labelled items fixed;
2. scores them against `k` seeded permutations of the gold (`calibrate-null:<seed>:<n>`);
3. takes the absolute deviations `|S_perm − E|` from the exact permutation expectation `E` (`permutation_expectation`);
4. returns the deviation at rank `ceil(q·k)` (the 198th of 200), rounded up to two places.

So `null_band` is a two-sided Monte-Carlo quantile of the score's spread under random label assignment, for exactly these predictions. The first measurement checks that the registered value is what the rule gives (`band_check`); a fixed predictor makes the measured predictions the calibrated ones.

## What `S > E + null_band` allows

H0: the predictions carry no information about the gold (the labels are exchangeable). Under H0 the measured score is distributed as one more permutation draw. If `S − E > null_band`, at most `k − ceil(q·k)` of the `k` draws deviate as far, so the Monte-Carlo permutation p-value `(1 + b)/(k + 1)` is at most `(1 + k − ceil(q·k))/(k + 1)` — with the stamp's rule 3/201 ≈ 0.015. The comparison is one-sided (all four scores, accuracy, r2, auc, spearman, are higher-is-better) on a two-sided band, so it is conservative. A simulation under H0 (Spearman, n = 30, 4000 repetitions, the rule as built): one-sided exceedance 0.0088, two-sided 0.0165 (bound 0.0149, within one standard error of 0.0019).

The statement it licenses: *the predictions agree with the gold more than random label assignment does, at a false-alarm level of at most 3/201.* It does not license:

- anything about size — with many items a weak association passes; the task's bar stays [criterion-1];
- a p-value finer than `1/(k + 1)` — 200 permutations cannot show p < 0.005;
- a statement where the band is not a permutation quantile: at fit (refits, a reasoned band), with a registered `NULL_ORDER` or a fixed null predictor, or without a registered band rule. The comparison is refused there.

sts512 for scale: the maximum over 200 permutations was 0.117 (attempt a-r2), the measurement 0.9225.

## What is built

The apply stamp carries, after [quality-check-2], a commented-out `[[promise]]` table `criterion-2`: "the registered SCORE exceeds the permutation expectation plus null_band". Uncommented, the skeleton reports `criterion_2_threshold` and `criterion_2_pass` (`MeasureConfig.chance_criterion`, set from the registered ids); not registered, it reports neither — a key no promise registers would be refused by intent-check. A failed quality check gives `criterion_2_pass` None, as for [criterion-1]. Making the comparison a duty, choosing another level, or extending it to fit would each be a separate decision.
