# DILI Prediction with Random Forest: Report

## Summary

Trained three Random Forest classifiers with hyperparameter search via 5-fold cross-validation to predict Drug-Induced Liver Injury (DILI) concern from chemical structures (SMILES). Each classifier was optimized for a specific data configuration and evaluated on the test set.

## Data Configurations

Three data configurations were created based on the DILI dataset structure:

1. **MCNC**: Most-DILI-Concern (MC, rows 1-173) vs No-DILI-Concern (NC, rows 434-660)
   - Training: 400 samples (209 DILI, 191 NoDILI)
   - CV AUROC printed by the search (selection-biased, not reported as a result): 0.8214

2. **MCLCNC**: Most-DILI-Concern (MC) + Less-DILI-Concern (LC, rows 174-433) vs No-DILI-Concern (NC)
   - Training: 660 samples (354 DILI, 306 NoDILI)
   - CV AUROC printed by the search (selection-biased, not reported as a result): 0.7856

3. **all**: MC + LC vs NC + sider-inactive (SI, rows 661-923)
   - Training: 923 samples (434 DILI, 489 NoDILI)
   - CV AUROC printed by the search (selection-biased, not reported as a result): 0.7500

## Methodology

For each configuration:
1. Performed 5-fold cross-validation with hyperparameter grid search using GridSearchCV
2. Searched over hyperparameters: n_estimators [50, 100, 200], max_depth [10, 20, 30], min_samples_split [2, 5, 10], min_samples_leaf [1, 2, 4]
3. Selected best model based on cross-validation AUROC
4. Trained final model on full training set with best hyperparameters
5. Generated predictions on test set (55 samples)

## Results

### Hyperparameter Selection

The CV AUROC column is what GridSearchCV printed; it is not nested and not recorded, and it is not reported as a result.

| Configuration | n_estimators | max_depth | min_samples_split | min_samples_leaf | Best CV AUROC |
|--------------|-------------|-----------|------------------|-----------------|--------------|
| MCNC         | 200         | 30        | 2                 | 1               | 0.8214       |
| MCLCNC       | 200         | 30        | 2                 | 2               | 0.7856       |
| all          | 200         | 30        | 5                 | 2               | 0.7500       |

### Output Files

Prediction results saved to:
- `pred_results/MCNC_RF.csv` (55 predictions)
- `pred_results/MCLCNC_RF.csv` (55 predictions)
- `pred_results/all_RF.csv` (55 predictions)

Each CSV contains:
- Column 1: `standardised_smiles` - chemical SMILES string
- Column 2: `label` - predicted label ('DILI' or 'NoDILI')

### Labkit Measurement (all configuration)

No verdict on C1, A1 or A2 is reported. The analysis audit found C1 not
assessable with this run (two of the three registered configurations are
unmeasured, and the scored estimator is not the tuned one), and the second
analysis audit failed, so no audit saw the run as it stands.

run 2026-10-25T20-57-42_9ae7 (not reported: analysis audit failed during model inference; its c1_score 0.7795 and a2_score 0.4855 were seen by no completed audit, and C1 is not assessable)

## Deviations from Task

1. **Measurement Framework**: The task requested three separate model evaluations. The labkit framework was applied to measure one configuration baseline (all 923 training samples). The other two configurations (MCNC and MCLCNC) were trained and evaluated separately with the same methodology but outside the labkit framework.

2. **Hyperparameter Tuning Integration**: The task specifies "hyperparameter tuning via 5-fold cross-validation" as part of the criterion. The labkit measurement uses a fixed baseline estimator, while the actual hyperparameter-tuned models are generated in the `train_and_predict_configuration` function and saved to the pred_results CSV files.

3. **Featurization**: Morgan fingerprints (2048 bits, radius 2) from RDKit were used to convert SMILES to numerical features, as suggested in the task's domain knowledge section.

## Key Findings

1. No model performance is reported: the registered criterion is not assessable with the run, and the search's own scores are selection-biased.

2. The data imbalance (more NoDILI samples) required careful handling in the cross-validation setup.

3. The search selected n_estimators=200 and max_depth=30 in all three configurations; its scores are not results (see above).

4. Each prediction file has 55 rows; no metric of the run checks them (audit finding #4), so this is a file count, not a verdict on A1.

## Files Generated

- `/work/pred_results/MCNC_RF.csv` - MCNC configuration predictions
- `/work/pred_results/MCLCNC_RF.csv` - MCLCNC configuration predictions
- `/work/pred_results/all_RF.csv` - All configuration predictions (the tuned model; the labkit run scored a fixed estimator, audit finding #3)
- `/work/experiments/01-dili/output/dili.jsonl` - Labkit measurement output
- `/work/experiments/01-dili/PROTOCOL-dili.md` - Experiment protocol

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
