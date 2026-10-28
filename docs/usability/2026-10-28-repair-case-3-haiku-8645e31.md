# Repair case, third attempt — haiku at 1800 s on labkit 8645e31 (2026-10-28)

*The repair case again after its two open causes were fixed
([second attempt](2026-10-28-repair-case-2-haiku-5a26902.md)): the
analysis audit sees the run's declared dependencies (`23bdccd`), the C1
bar is the exact permutation expectation (`c54a4dc`), and a required
check may name a file (`8645e31`). The same start state, built by
`build_case.txt`: apply-screen registered and committed — now with the
bar on the permutation expectation and `null_band` the 0.99 quantile of
|null − expectation| (0.1276, registered 0.13) —, the planted fault
(`sd**2` for `sd`), the first measurement in the container. Haiku 4.5,
cold, TASK.md and AGENTS.md only. Records:
`2026-10-28-repair-case-3-haiku-8645e31/`.*

## Result

The third attempt reaches the correctly bound, adopted number, and this
time the verdict can be judged: the adopted result reads `C1 met; A1
met; A2 met`. One attempt — no rate; 403 s against 651 s and 1242 s is
one draw each, no evidence of speed.

| step | what |
|---|---|
| audit `16-46` | BLOCKER: the `sd**2` fault against the registered standardisation (no check asked); WARNING: the band was calibrated on the faulty code |
| repair `3b35ffe` | the code corrected, the registration untouched; `--calibrate-null` on the fixed code gives 0.1276, under the registered 0.13 |
| run `0fb5` | `apply-screen_v2.jsonl`, fresh rows: `c1_score` 0.7609 ≥ bar 0.6528 (expectation 0.5028 + 0.15); `a2_score` 0.4783, 0.0246 from its target |
| audit `16-49` | `FIX … resolved`; the band WARNING `accepted`, effect `stands` |
| review `16-50` | a second auditor upheld the band decision |
| adopted | `[result] run = "…0fb5"`, `pred_results/screen_pred.csv` passes the hidden evaluation (0 persons off model 2.1) |

report-check on the delivered state, replayed in the image
(`apply-screen.report-check.txt`): area all clear; REPORT.md 0 blockers,
2 warnings, one of them static evidence (a cited exploratory run; numbers
in the report's text).

## What the repairs did

- **The bar on the permutation expectation:** no auditor named the seed
  as deciding the verdict, as every audit of the second attempt did. The
  bar 0.6528 does not move with the draw.
- **The shown dependencies:** the first auditor read model.json's
  numbers itself ("a smoker scores 0.7·(1−0.25)/0.43² = 2.84 in z instead
  of 1.22") instead of asking the caller to confirm `std` from the file;
  the follow-up judged the repair against model.json's mean and std and
  said `resolved`, not `not_assessable`.
- **The file check:** not exercised — no finding needed it.

## What is left

Nothing from this case. The required-check path is the
[check-path case](2026-10-28-check-path-case-haiku-8645e31.md).
