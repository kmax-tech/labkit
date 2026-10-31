# 2026-10-31 — the fit skeleton's plan by repeat cost, and the Timebox as a budget the run holds

**Problem.** The fit skeleton (`labkit/templates/measure-estimator-script.py.template`)
trained 5 folds × (1 registered + 5 permuted-label refits) = 30 fits in every
run, whatever the protocol's repeat cost, and nothing read the protocol's
Timebox. In the pressure round of 2026-10-29 (docs/usability/2026-10-29-sab-round1.md)
the lab arm's two fit tasks paid for it: task 71 (a 16,540 × 3,400 regression)
ran out of memory at 5 GB and out of time at 12 GB — 239 s per fold —, task 15
out of time; two of three lab attempts per task ended in the container's
timeout, while the control arm, which trains once, finished. The 30 fits were
labkit's cost, not the task's, and the first sign of it was a killed
container, not a sentence.

**Solution.** Two parts, the control method unchanged (refits on permuted
training labels stay the null lane; the bar stays their mean plus `margin`):

1. The plan follows the protocol's repeat cost (`FIT_PLAN`): at `low`
   3 folds × (1 + 2) = 9 fits, at `high` 5 × (1 + 5) = 30 as before. Folds
   and refits are fields of the run's config (`n_folds`, `null_refits`), so a
   changed plan is a changed config, and `--repeat-of` refuses a repeat under
   another plan. Fewer than two refits are refused (`MIN_NULL_REFITS`): on
   2026-10-28 one draw's score decided a verdict (docs/notes/2026-10-28-null-lane-spec.md).
2. The Timebox is a budget the run holds (`labkit/formats/timebox.py`): when
   the field starts with a duration (`45 min — then record and ask`), the fit
   times its first fold, projects the run (`projected_seconds`) and stops
   before the second fold when the projection exceeds the budget
   (`over_budget`), naming the numbers and the way out — fewer folds or
   refits in the plan, or a larger Timebox, before the first measurement. A
   Timebox without a leading duration stays prose; the run says that no
   projection is made.

**Rejected.** Deriving the null band at `low` from permutations of the
predictions instead of refits (as the apply path does): it measures another
spread — the permutation of evaluation labels, not the variance of
retraining — and would change the control method under the name of a
saving (review 2026-10-31). Fixing the count alone: a count guarantees no
time; the projection does, before the budget is spent.

**Notes.** The projection is from the first fold: later folds train on the
same amount of data, the final fit on all labelled items on more, so the
projection is a floor, not a bound; the Timebox keeps its slack. The
measured minutes per fold on tasks 15 and 71 belong in the pressure round's
contract before its budgets are named.
