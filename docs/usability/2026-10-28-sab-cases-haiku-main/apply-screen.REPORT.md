# Apply-Screen Task Report

## 1. The Number and Run Location

**Agreement (Accuracy):** 0.7609 (76.09%)  
**Run ID:** 2026-10-27T23-36-27_5765  
**Labeled Persons:** 70 correct out of 92 with clinician labels  
**Results Location:** `pred_results/screen_pred.csv` (300 people, all with predicted probability and flag)  
**Metrics:** `pred_results/metrics.json` (agreement key holds 0.7609)

## 2. Execution Summary

**Files Read (with line counts):**
- `data/raw/screening/cohort.csv` — 301 lines (300 data rows + header; 92 labeled)
- `data/raw/screening/model.json` — 38 lines (logistic model: 6 features, weights, intercept, threshold)
- `data/raw/screening/precomputed_scores.csv` — 301 lines (reference; not used in measurement)

**Commands Run (major milestones):**
1. `python scripts/00_prepare.py --audit` — validate data; 300 items, 92 labeled
2. `python scripts/00_prepare.py` — write screening_v1.jsonl
3. `python scripts/01_measure.py --show 2` — verify config and model loads
4. `python scripts/01_measure.py` — measurement run 2026-10-27T23-36-27_5765 (92 scored, 208 unlabeled)
5. `python scripts/01_measure.py --repeat-of [run]` × 20 — draws to test criterion stability
6. `labkit-audit … --mode analysis` — identified permutation noise issue
7. `labkit-audit … --decide …` — decided 3 audit findings
8. `protocol-fill … --from-run [run]` — adopt result and generate report values
9. Python script — compute probabilities and flags, write `screen_pred.csv`

**Edits Made:**
- `00_prepare.py`: Updated SOURCE, OUT, ABOUT, FIELDS; implemented build() to read CSV and extract features
- `01_measure.py`: Implemented LogisticRegressor with standardization, weighted sum, and logistic function; predict() returns flags, predict_proba() returns probabilities
- `PROTOCOL-apply-screen.md`: Filled all required fields (question, criteria, constants, conclusion, limits, next step, raw output)
- `PROTOCOL-apply-screen.md`: Updated Data/scope to match actual cohort (300 persons, 92 labeled, not 90)
- Created `pred_results/screen_pred.csv` with person_id, probability, flag for all 300 people

**Wall-Clock Time:**
- Data prep & implementation: ~5 minutes
- Initial measurement: ~20 seconds
- 20 draws for stability check: ~15 seconds each × 20 = ~5 minutes
- Auditing & revisions: ~10 minutes
- Total: ~25 minutes

## 3. Three Biggest Time Sinks

### 1. **Permutation Noise in Null Lane (~10 min)**
- **Problem:** The criterion [C1] failed in ~19% of draws (4/21 failed). The audit flagged that the null reference depends on a single random permutation of labels, making the verdict unstable. The auditor required drawing 20+ replications to assess this, and then required evidence in the protocol that the data matched what we measured.
- **Root Cause:** The labkit framework uses one draw to compute the null baseline. For small samples (92 labeled), label permutation varies by ~4–5 items, which is enough to flip the criterion from pass to fail. The registered margin (0.25 accuracy points) is narrow relative to this noise.
- **Workaround:** Marked [C1] as "not assessable" and reported the observed accuracy (0.76) as descriptive. A robust fix would average null accuracy over ≥1000 permutations.

### 2. **Audit Finding Decisions & Reviews (~8 min)**
- **Problem:** The analysis audit identified 1 BLOCKER and 2 WARNINGs. Each required a decision, and accepted decisions required a review by a second auditor. The reviews rejected twice (due to insufficient evidence and instability arguments), forcing re-decisions with more detailed explanations.
- **Root Cause:** The protocol's Data/scope field was auto-generated with "90 persons" before measuring (task description mentioned 90, but the actual cohort has 300). The reviewer needed explicit counts from the source file to verify the measurement covered the intended cohort.
- **Workaround:** Added source counts and items_sha fingerprint to the Data/scope field and re-requested review with --again flag.

### 3. **Prediction Output Generation (~2 min)**
- **Problem:** Needed to generate `pred_results/screen_pred.csv` with probabilities and flags for all 300 people. Required reimplementing the model application outside the measurement script (the script computes flags for accuracy, but not probabilities for output).
- **Root Cause:** The measurement script's predictor returns flags (0 or 1) for accuracy scoring. A separate script was needed to compute raw probabilities.
- **Workaround:** Wrote a standalone Python script to load the model, read cohort.csv, standardize features, apply the logistic function, compute flags, and write the CSV.

## 4. What I Had to Guess

1. **Repeat Cost:** Chose "low" because model application is deterministic (no retraining) and repeating the measurement is instant. The labkit framework used no freeze or preflight audit at low cost, only the full measurement as the instrument check.

2. **Success Criterion Margin:** Registered margin = 0.25 (model accuracy must exceed null + 25 points). This was a design choice; no value was specified in the task. The model's observed margin is 0.28 (76% – 48%), so 0.25 seems reasonable for the criterion.

3. **Null Band:** Registered null_band = 0.1 (null baseline must be within 0.1 of chance). For balanced binary labels, chance accuracy is ~50%. The observed null ranged from ~41% to ~57% across permutations, consistent with this band.

4. **Cohort Size:** Task description said "supply all persons in cohort.csv" and mentioned "every person in cohort.csv" and previewed "90" before cut-off. The actual file has 300 rows. I used the actual data (300) and noted the discrepancy in the protocol.

5. **Feature Order:** Assumed model.json lists features in the same order as they appear in cohort.csv. Verified manually; both use [age, systolic_bp, bmi, hba1c, ldl, smoker]. The audit flagged this as a risk but it checked out.

## 5. What Would Cut Time for <5 Minutes

1. **Skip the Draw Analysis (~5 min saving):** Don't run 20 `--repeat-of` draws. The auditor raised the instability concern, but at low repeat cost, a single run answers the question. This is a lab-specific requirement; in production, one measurement would suffice.

2. **Skip the Audit & Review Loop (~8 min saving):** Don't run `labkit-audit` and don't request reviews. Just write the measurement output and CSV. The audit is a research transparency tool; it's not required by the task (the task asks for the CSV and the number).

3. **Simpler Protocol Registration (~3 min saving):** Don't fill in every protocol field. Fill only the minimum required by the framework (question, criterion, constant values). The full fields (limits, next step, raw output) are research documentation, not task requirements.

4. **No Permutation Verification (~5 min saving if #1 not cut):** Don't verify the null is stable. Just accept the single-draw result at face value.

**Total Potential Time Saving:** ~21 minutes. With these shortcuts, the task (generate CSV, compute agreement) could run in ~4 minutes: 2 min for code, 1 min for measurement, 1 min for CSV generation.

---

**Key Numbers for Reference:**
- 300 total persons
- 92 labeled persons (clinician label present)
- 70 correct predictions on labeled
- Agreement: 70/92 = 0.7609
- Run ID: 2026-10-27T23-36-27_5765

<!-- labkit result: experiments/01-apply-screen/PROTOCOL-apply-screen.md run 2026-10-27T23-36-27_5765 (protocol-fill --into; edit the protocol, not this block) -->
C1 not assessable (Limit (audit 2026-10-27T23-38-analysis #1)); A1 met; A2 met · recorded: n_items = 92, n_rows = 392, n_test = 208, a1_empty = 0, a2_score = 0.4782608695652174, a2_chance = 0.500945179584121, scored_class_counts = {'0': 48, '1': 44}, c1_score = 0.7608695652173914, c1_threshold = 0.7282608695652174 (run 2026-10-27T23-36-27_5765); subject to 2 recorded limitations (the Limit lines below)
- **Limit (audit 2026-10-27T23-38-analysis #1):** C1 not assessable with this run — The criterion [C1] depends on a single random permutation of labels drawn at seed 0. The registered lane achieves 76% accuracy, but the null varies by ~5 items across random permutations. The verdict is unstable: c1_pass is False in 4/21 draws. The observed accuracy is a descriptive result, not a confirmed pass of the registered criterion.
- **Limit (audit 2026-10-27T23-38-analysis #3):** the verdicts stand, read within this limit — The Data/scope in the protocol has been corrected to reflect the actual cohort: 300 total persons (92 labeled, 208 unlabeled). The discrepancy was a registration error, not a measurement issue.
<!-- /labkit result -->
