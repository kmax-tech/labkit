# DILI prediction — report

## What was done

Three Random Forest configurations (MCNC, MCLCNC, all) were trained with a
grid search and wrote predictions for the 55 test compounds to
`pred_results/{MCNC,MCLCNC,all}_RF.csv`.

## Result

None is reported. The labkit measurement is
run 2026-10-25T20-57-42_9ae7 (not reported: the first analysis audit made C1 not assessable — two of three configurations unmeasured, the scored estimator untuned — and the second analysis audit failed).

## Open

- Score each configuration with the tuned estimator, nested inside the outer folds.
- Audit the run again before any number is reported.
