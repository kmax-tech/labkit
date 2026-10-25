# Bulk modulus prediction — report

## What was done

A Random Forest regressor on `space_group` and `elastic_anisotropy` after
dropping G_VRH and poisson_ratio; predictions for the 232 test compounds are
in `pred_results/compound_bulk_modulus.csv`.

## Result

None is reported:
run 2026-10-25T20-18-03_3b26 (not reported: the analysis audit's three BLOCKERs are accepted with C1 not assessable — [C1] and [A2] registered twice with different bars, a trivial solution passes [C1]).

## Open

- Register one bar for [C1] and [A2] and anchor [C1] so a constant predictor fails it.
- Composition features from the formula; `elastic_anisotropy` is derived from the same elastic tensor as the target (audit warning #6).
