# 2026-11-01 — a registered null order in the apply skeleton and its area test

**Problem.** The apply skeleton
(`labkit/templates/measure-estimator-script.py.template`) drew its null lane
from a seeded shuffle of the gold. Task sts512 of the reference pilot
registers a staged permutation instead: a file the organizer drew once, to be
read and never regenerated. The skeleton had no place for it. The agent kept
the seeded draw, and both the analysis audit and the evaluator caught the
mismatch. In trial 2, after `NULL_ORDER` existed (0.106.0), the area's stamped
test (`labkit/templates/test-estimator.py.template`) still built its
synthetic null rows without `gold_of`. Under `NULL_ORDER` with no band
registered, `evaluate_rows()` read those rows as an unordered null and
refused the missing band: nine of eleven stamped tests raised "registers no
null_band", and `finalize` refused a correct run.

**Solution.**

1. `NULL_ORDER` (0.106.0, `236c4913`): a JSON list, a permutation of the
   labelled items' positions. Row i of the null lane carries the gold of
   labelled item `NULL_ORDER[i]` and names it (`gold_of`). Because the order
   is one fixed control, its score plus `margin` is the bar.
   [quality-check-2]'s band applies only where it is registered. The file
   is recorded as a run input. `registered_donors()` refuses an order that is
   not a permutation of the items, since an order that does not fit them is
   no control.
2. The stamped area test serves that route (this change). When the script
   sets `NULL_ORDER`, its synthetic null rows carry `gold_of` as the run's do.
   The out-of-band test asserts the out-of-band refusal only where a band is
   registered. A test of its own holds that only a registered order's
   null, with donors, goes without a band; every other null without one is
   refused.

**Notes.** Without `NULL_ORDER`, the apply area test's synthetic null rows
carry no donors and so exercise the fixed-null branch of `evaluate_rows`
(score as the bar, chance as the target), not the seeded permutation's (the
permutation expectation as both). The real apply rows of a seeded null do
carry donors. The stamped test therefore does not exercise that branch;
`tests/test_apply_skeleton.py` holds it in labkit.
