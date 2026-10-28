# The null lane and the C1 bar: what must be fixed in advance (2026-10-28)

> **Decided and built the same day:** apply — the proposal below, the bar
> on the exact permutation expectation (`c54a4dc`); fit — option (a) with
> K = 5 (`NULL_REFITS`), the bar on the refits' mean (`7b9700b`).

*A decision for the author. The estimator skeleton
(`labkit/templates/measure-estimator-script.py.template`) passes [C1]
when the registered lane reaches the null lane plus `margin`, and the
null lane is one draw: at apply one permutation of the gold under the
fixed predictions, at fit one out-of-fold refit on permuted labels.
"Several permutations" is no specification; four things have to stand
before the first measurement: how many, which seeds, how they are
aggregated, and what the C1 bar then means.*

## Evidence

- Fourth SAB-like draw: both analysis audits (fit, apply) named the
  one-draw bar a BLOCKER; fit-assay's first run passed with `c1_score` =
  `c1_threshold` = 0.7625, one null item from failing
  ([note](../usability/2026-10-28-sab-cases-haiku-87036d3.md), fault 4).
- Third draw: apply-screen's [A2] failed at a null of 0.391 against
  chance 0.5 — one permutation's noise.
- apply-screen, the correct model (agreement 0.761 on 92 labelled
  persons), 2000 permutations: a single null lies between 0.391 and
  0.630 (1 %–99 %), so the bar `null + 0.15` lies between 0.541 and
  0.780 — whether 0.761 passes is decided by the seed.
- At apply the permutation null's expectation is exact: with the flags
  fixed and the gold permuted uniformly, every item's permuted label is
  distributed as the gold, so E[accuracy] = Σ_c q_c·p_c (q the flags'
  class shares, p the gold's); 0.5028 here, the mean of the 2000 draws
  0.5033. `chance_of` gives Σ_c p_c² = 0.5009 — the gold alone. The two
  differ whenever the flag rate differs from the label rate, so [A2] at
  apply mixes draw noise with that difference.

## Proposal for apply

1. **The bar without a draw.** [C1]: the registered lane's score is at
   least the permutation expectation plus `margin` — E_perm computed
   exactly from the fixed predictions and the gold: accuracy Σ_c q_c·p_c,
   auc 1/2, r2 −Σ(ŷ − ȳ)² / (n·var(y)) (SST is fixed under permutation,
   so E[r2] = 1 − E[SSE]/SST exactly). Meaning: the predictions agree
   with the gold more than the same predictions agree with labels
   assigned at random, by `margin`. No count, no seed, no aggregation.
2. **The null lane stays, as the anchor in the same run** (LAB-034 Null
   condition in the same run; finalize's null-lane station reads its
   rows): one permutation, seed `apply-null:<seed>`, as today. [A2]: that
   draw lies within `null_band` of E_perm (not of `chance_of`) — a check
   of the scoring code, with a false alarm rate fixed in advance.
3. **The band from the same rule.** `--calibrate-null`: 200 permutations
   with seeds `apply-calibrate:<seed>:<k>`, k = 0…199, apart from the
   run's own; `null_band` = the 0.99 quantile of |null − E_perm|. One run
   in a hundred fails [A2] by chance, and says so.

What changes: the skeleton's `evaluate_rows` (the bar, [A2]'s target),
`calibrate_null`, the metrics keys (`a2_chance` becomes the target
E_perm, or both are written), the stamped [C1]/[A2] sentences, the field
guide and the standard's null-condition paragraph. Existing areas keep
the script they were stamped with; nothing reads an old record
differently.

## For fit — open

The null refits on permuted labels; its expectation has no closed form
(a learner on structured data, or a leak, sits above chance — that is
what the lane is for). Options, each fixed before the first measurement:

- **(a) K refits, the bar on their mean.** K fixed in the script (e.g.
  5), seeds derived from the run's seed per repetition and fold (today
  `(seed + 1) * 1000 + k` per fold), aggregate the mean, [C1] `registered ≥ mean + margin`, [A2] the mean within
  `null_band` of `chance_of`. Costs K refits; at high repeat cost the
  spread comes free from the same K.
- **(b) The bar from chance, the lane as anchor only.** [C1]
  `registered ≥ chance_of + margin`; the one-refit null lane is held by
  [A2] alone. Cheap; a null that sits above chance (a leak) fails [A2]
  rather than raising the bar.
- **(c) As today, one refit** — the bar keeps the draw noise; only
  `margin` large against the spread makes the verdict stable.

## To decide

1. Apply: the proposal above (bar on E_perm, one-draw anchor held to
   E_perm, band from the same rule)?
2. Fit: (a), (b) or (c) — and for (a), K?
3. Whether `chance_of` stays the target at fit (it is the gold-only
   chance there, which a refit on permuted labels does approach).
