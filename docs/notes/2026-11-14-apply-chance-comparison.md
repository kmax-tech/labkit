# Comparing an apply measurement with chance — the permitted null deviation per run (2026-11-14)

Plan step 3, point 3 of the usage-round-24 findings (`TODO.md`): in sts512 the task asked whether the agreement exceeds chance, the bar was one the task states (`at_least`, Spearman ≥ 0.95), and no promise compared the measured 0.9225 with the null. Every one of the six auditors flagged the "above chance" sentence the agents wrote anyway; in one attempt the report dropped the answer to that question. Decided by the author on 2026-11-14: first state what the calibration's value denotes and which statement a comparison with it allows, then offer an optional, commented-out promise in the apply stamp — no general duty and no new threshold. The replay of a second run below led to a contract change of its own, also decided on 2026-11-14: each run computes its permitted deviation by the registered rule.

Terms, as in the [wording plan](2026-11-14-null-band-wording-plan.md): the *permitted deviation* `b` is how far the null's score may lie from its target `E`, in score units; the *null-check interval* is `[E − b, E + b]`, inclusive; the *comparison threshold* of `criterion-2` is `E + b`, which the measured score must strictly exceed.

**Released statement:** a pass of `criterion-2` says that the measured score exceeds the comparison threshold derived from randomly permuted labels. The false-alarm bound below has been derived and independently reviewed, but the author has not released it. Until the author does, neither the stamp, the skeleton nor a report states a level.

## The permitted deviation at apply

At kind apply with the seeded permuted null (no `NULL_ORDER`, no fixed null predictor), [quality-check-2] registers the rule, not the value (LAB-035 Thresholds belong to the run, not to the measure): `null_band_quantile`, `null_permutations` and `null_band_seed`, the calibration's seed, apart from the run's `seed` (the stamp registers 0.99, 200 and 1). Each evaluation (`run_null_band`, `band_by_rule` in the estimator skeleton):

1. takes the run's own registered predictions and gold, ordered by item;
2. scores them against `k` permutations of the gold, each seeded `null-band:<null_band_seed>:<n>`;
3. takes the absolute deviations `|S_perm − E|` from the exact permutation expectation `E` (`permutation_expectation`);
4. returns the deviation at rank `r = ceil(q·k)` (the 198th of 200), rounded up to two places.

The run keeps it as `quality_check_2_null_band` and prints it, and [quality-check-2] and `criterion-2` compare with it. The same inputs give the same value in any row order and under any run seed; the run's seed moves only the null lane's one draw, the anchor. The calibration never scores the true gold. `--calibrate-null` previews the value on the predictions for the labelled items and writes nothing. Registering `null_band` there, or a part of the rule, is refused before the run opens (`null_check`) and in the evaluation. Predictions that answer one class give no spread, and the rule refuses a permitted deviation of 0.

At fit, with a registered `NULL_ORDER` and with a fixed null predictor there is no permutation spread of these predictions: `null_band` stays a registered, reasoned value, a calibration rule there is refused, and so is `criterion-2`.

## Derivation of a false-alarm bound — not released

H0: the gold is exchangeable across the items, given the predictions. Let `b⁺` be the number of draws scoring at least the measured `S`. The one-sided Monte-Carlo permutation p-value `(1 + b⁺)/(k + 1)` is valid under H0, discrete scores and draws with replacement included. If `S − E > b ≥ d_(r)`, every draw with `T_n ≥ S` has a deviation strictly above `d_(r)`, and at most `k − r` draws do. So `b⁺ ≤ k − r`, and a pass implies a p-value of at most `(1 + k − r)/(k + 1)`: 3/201 ≈ 0.015 with the stamp's rule. The comparison is strict, since `≥` with `b` equal to `d_(r)` would admit ties at the rank. Rounding up only raises the threshold. `E` needs to be a function of the predictions and the gold multiset only, not the permutation mean. Requiring the quality checks to pass only shrinks the pass event.

Independent review of `ee2af670` (2026-11-14): the derivation holds, but only under five conditions.

1. **Exchangeable items.** Independence of predictions and gold alone is not enough. Items clustered by source, or near-duplicates, break the bound.
2. **The permitted deviation belongs to these predictions on these items.** Under the earlier contract only the first measurement was checked. Since the per-run computation it holds by construction for every run.
3. **The calibration seed is fixed independently of the calibration's outcome.** Choosing `null_band_seed` after previewing several values inflates the level. The registration fixes it before the first measurement, but nothing prevents a choice before the registration.
4. **One pre-registered comparison per protocol**, with no choosing among repeated full runs. `--repeat-of` draws are never the answer.
5. **3/201 holds only for q = 0.99 and k = 200**; other rules give `(1 + k − ceil(q·k))/(k + 1)`.

Supplementary, not a proof: a simulation under H0 (Spearman, n = 30, 4000 repetitions, the rule as built at `ee2af670`) gave a one-sided exceedance of 0.0088 and a two-sided one of 0.0165, against 0.0149 for the two-sided bound and within one standard error (0.0019) of it.

Not licensed in any case:

- anything about size — with many items a weak association passes; the task's bar stays [criterion-1];
- a p-value finer than `1/(k + 1)` — 200 permutations cannot show p < 0.005;
- a statement where the permitted deviation is not a permutation quantile: at fit (refits, a reasoned value), with a registered `NULL_ORDER` or a fixed null predictor. The comparison is refused there.

sts512 for scale: the maximum over 200 permutations was 0.117 (attempt a-r2), the measurement 0.9225; the rule gives 0.12 on comparable data (512 items).

## Later runs: why the value moved into the run

Under the earlier contract (`56e98995`, 2026-10-29) the protocol registered `null_band`, `--calibrate-null --write` wrote it before the first measurement, and `band_check` held it to the rule at the first measurement only: "After the first measurement nothing is checked: a repair changes the predictions while the registered band stands." The registration hold compares the protocol's texts and lets a code change measured again under the same fields pass (`labkit/gates/registration_hold.py:274`).

Replayed on 2026-11-14 with the end-to-end scenario's apply area (`tests/test_end_to_end.py`, `points_area`: 12 labelled points, 6 per class), a fixed threshold on feature 0 and real commands in a temporary git lab: first measurement, commit, the threshold repaired and committed, a second measurement into a new output file (runlog refuses the old one: rows from another instrument), then `finalize`. Scripts and logs are internal (labkit-evidence, `usability/2026-11-14-band-second-run/`).

| Repair         | Predictions pos/neg, 1st → 2nd | Earlier contract: registered value | Per run: value of the 2nd run | finalize, both contracts |
|----------------|--------------------------------|------------------------------------|-------------------------------|--------------------------|
| x > 4 → x > 0  | 4/8 → 6/6                      | 0.34                               | 0.34                          | exit 0                   |
| x > 4 → x > 10 | 4/8 → 1/11                     | 0.34                               | 0.09                          | exit 0                   |
| x > 10 → x > 4 | 1/11 → 4/8                     | 0.09                               | 0.34                          | exit 0                   |

Under the earlier contract the second run was compared with the first run's value and printed nothing about it. In the third row that value was a quarter of the run's own spread: a `criterion-2` threshold would have been 0.5 + 0.09 = 0.59, and the score 0.8333 would have passed it; with the run's own value the threshold is 0.84, and the same score does not. A stale value errs in either direction: too wide makes [quality-check-2] lax and `criterion-2` strict, too narrow the reverse. Under the per-run contract each run keeps and prints its own value (`per_run_*.log`).

Checked before the build:

- **Standard and version.** The standard's version rule: "A change to a rule or a field is the next version; a dated change that alters no rule is listed under Changes." The test applied: does a protocol valid under the current contract become invalid or judged differently? No rule's text changes: LAB-035 already asks for the rule and not the value, and the per-run value is its case. No field the gates read changes: no package code reads `null_band`; the constants are the area's registration for its own skeleton, and an area keeps the skeleton it was stamped with, so a protocol registered under the earlier stamp reads and is judged as before. The precedents agree: the two earlier changes to how the apply band and bar arise (0.104.0: the registered band rule with the first-measurement check, the exact permutation expectation as the bar) were listed under "Changed" with the standard at 0.23 before and after. So the standard records a dated change under LAB-035 and stays at 0.29. The package release is assessed apart from the standard (author, 2026-11-14): the stamp registers other constants, the skeleton's `--write` and `--calibrate-null K` are gone, and the agent and field guides describe only the new registration, so an agent following them in an apply area stamped earlier fails loudly. The CHANGELOG lists it under "Breaking", with no support for the old format and no transition release: an apply area with no measurement yet is stamped anew in full; historical runs are reproduced with their commit and their pinned labkit release. The pre-run hook still lets an old area's `--calibrate-null --write` pass as a no-run stage, since `--calibrate-null` stays among the no-run flags.
- **What it removes.** `--calibrate-null --write` and `band_check`: both were a source of agent error (in the fifth SAB-like draw an agent registered 0.05 after reading 0.1276, `56e98995`). No value is seen or written before the measurement any more.
- **Calibration seed.** Decided by the author: an explicit `null_band_seed`, separate from the run's seed, not derived from the protocol id. A `--seed` run keeps the value; choosing among runs cannot select on it.
- **Reproducibility and cost.** The value is a deterministic function of the kept rows and the config, so `--eval-only`, `02_analyze.py` and a recheck recompute it exactly. Cost per evaluation at 200 permutations: Spearman at 512 items 0.5 s, at 2000 items 2.1 s, accuracy at 2000 items 0.07 s, AUC at 2000 items 4.8 s.
- **[quality-check-2]'s meaning** is unchanged: one permuted draw within the 0.99 quantile of its own permutation spread. With a correct null lane it fails in about 1 % of runs, now at every run. A null lane that is not permuted still fails it.

## What is built

The comparison is offered in two places, both commented out; turning it on takes both steps:

1. **Protocol:** after [quality-check-2] the apply stamp carries a commented-out `[[promise]]` table `criterion-2`: "the registered SCORE strictly exceeds the comparison threshold, the permutation expectation plus the permitted deviation quality-check-2 computes in the same run". Uncomment it and name the id, in brackets, in the Inference criterion field.
2. **Skeleton:** uncomment the block between the `criterion-2` markers in `evaluate_rows` of `scripts/01_measure.py`. It reports `criterion_2_threshold` and `criterion_2_pass`; a failed quality check gives `criterion_2_pass` None, as for [criterion-1].

Why the code is commented out too (decided by the author, 2026-11-14, after the review found it): with the key-writing lines active, code-check warned on every new fit and apply area of a key in the id namespace that no promise registers. Assembling the keys at run time to hide them would make code-check block a registered `criterion-2`, since it requires a key literal. Each step alone is held: the table without the code is a code-check BLOCKER (no script names the key), the code without the table a code-check WARNING and an intent-check BLOCKER at finalize. What stays active is the precondition: the registered table sets `MeasureConfig.chance_criterion`, and `null_check` refuses before the run opens where the permitted deviation is no permutation quantile.

Making the comparison a duty, choosing another level, or extending it to fit would each be a separate decision.

Independent review of `5d8cabfd` (2026-11-14): the value depends only on the rule and the multiset of (item, prediction, gold); the calibration sees the true pairing only through uniform permutations of the rows the score uses; refusals before the run and in the evaluation agree. Fixed after it: the sort key takes the whole triple; `null_check` refuses a missing `null_band` at fit and with a fixed null predictor; tests on forty continuous items, the inclusive interval and the evaluation's refusal now kill the five mutations that survived (order, run seed, strict interval, rank, refusal). Open, a decision for the author: predictions that give no permutation spread — a one-class predictor, all predictions missing, labels that match no gold — now fail after the run with no metrics, where the earlier first-measurement check refused them before it; an r2 with constant predictions gets 0.01 from float noise instead. Either a zero spread gives a permitted deviation of 0 (the null check exact, the criterion judged, the yield check reported), or the refusal moves before the run at the cost of one prediction pass.
