# The fifteen decisions, assessed from their sources — fifth haiku round (2026-10-22)

*The independent reading the [replay](2026-10-22-decision-review-replay-v5.md)
owed before its warning becomes a blocker: every `stands` decision of the
three labkit attempts judged against the code, the data and the rows — not
by another model draw, but by opening the files and recomputing what the
reasons assert. Done by the session's agent on the scratchpad copies
(`r5/t3`, `r5/t5`, `r5/t18`, datasets restored from the attempts' commits),
with the commands' results quoted. Two reviewer draws per record stand
beside each assessment (pass 1, pass 2). Two statements are kept apart
where the reviewers wavered: whether a baseline's value is right, and
whether the improvement claim built on it stands.*

## What the sources say

| attempt | checked | result |
|---|---|---|
| t3 | `compound_elastic_properties_test.csv`, column `K_VRH` | 232 rows, every value `0.0` — no test ground truth; the reason's premise holds |
| t3 | train `K_VRH` spread | population std 72.84 GPa; a mean predictor's RMSE is that, the model's CV RMSE is 70.08 |
| t3 | output rows | 232 predictions, 108 distinct values, one value 15 times (three string proxies, as WARNING #2 said) |
| t5 | `dkpes_train.csv`, `dkpes_test.csv` | 44 and 12 rows (the protocol says 28 and 10); all 12 test `Signal-inhibition` are `-999`; median 0.284, 22 of 44 at or above it |
| t5 | `01_measure.py` | the cut `>= median` at lines 85 and 122, unregistered; `evaluate_rows` never reads `items`; one `random_state=42`; Youden's J on the training probabilities of a forest fit on those same 44 points |
| t18 | `train.csv` block order | 1-based: MC 1–174, LC 175–434, NC 435–661, sider 662–923. The protocol's Setup and the code's slices say MC 1–173, LC 174–433, NC 434–660: **off by one**. Slice MCNC holds 173 MC + 1 LC + 226 NC (one MC and one NC dropped, one LC taken in); the counts 400/660/923 match, the categories do not |
| t18 | majority rates in the slices as cut | MCNC 226/400 = 0.565, MCLCNC 434/660 = 0.658, all 489/923 = 0.530; mean 0.584 — the reason's "~59%" is right within rounding, the "~14%" is 0.7296 − 0.584 = 0.146 |
| t18 | `test.csv` | 55 rows, one column `standardised_smiles` — no test labels, so no held-out accuracy was computable here |

## The decisions

**t3 09-10 #1** (BLOCKER: `cv_rmse` scores nothing of the kept rows;
reason: test ground truth unavailable, CV RMSE is the available metric).
Reviewer: upheld, upheld. **Assessment: upheld.** The premise is true
(the test column is zeros), the Recorded results line reports `cv_rmse`
and the Conclusion draws only "limited predictive power" from it. What
the Conclusion does not say, and the two accepted WARNINGs without effect
would have carried: a constant predictor sits at 72.8, so the forest
beats doing nothing by 2.8 GPa — "limited" is generous. That is the
unreviewed WARNING #3's point, not this decision's.

**t5 09-15 #1–#9.** Reviewer: nine rejected, nine rejected.
**Assessment: nine rejected**, each from the file:

- #1 the Youden cut on in-sample probabilities of a 100-tree forest fit
  on the same 44 points: the reason restates it; the Summary reports a
  classifier "successfully developed … achieving an optimal ROC
  threshold of 0.69 for binary classification" — the generalising claim
  the in-sample cut cannot carry.
- #2 "an exploratory count": the question is "can we develop a classifier",
  a yes/no, and the Summary answers yes with no registered value to
  answer against.
- #3 the Unit registers accuracy and predicted inhibition per test
  sample; the rows hold probabilities, no label, no accuracy (all test
  labels are −999) — the promise is unjudged, `not assessable`, not
  `stands`.
- #4 "Finding noted": the protocol still says 28 training and 10 test
  samples against 44 and 12 in the files; `test_samples = 12` in the
  Recorded results contradicts the protocol's own Setup.
- #5 the `>= median` binarisation is in the code twice and in no field;
  both numbers depend on it.
- #6 `predicted_inhibition` holds P(above median); a reader of row 1
  (`0.82`) takes an inhibition value.
- #7 `evaluate_rows` refits on the training CSV and returns 0.69 whatever
  the rows hold; the recheck cannot fail.
- #8 22 of 44 at or above the median — chance is exactly 0.5 and nothing
  compares against it; "successfully developed" has no floor.
- #9 one seed on 44 points, probabilities 0.51 and 0.41 next to a 0.69
  cut, no spread.

The twelve rejections of the round (nine here, three in t18) are not a
sample of one model's taste: on t5 every one follows from a line in the
file or a count in the data.

**t18 09-33 #1 and 09-34 #1** (BLOCKER: `grid_search.best_score_` is the
max over 144 configurations, the winner's curse; reason: "reflects the
selected hyperparameter performance … predictions are still generated").
Reviewer: rejected ×4. **Assessment: rejected, with a line to draw.** The
Conclusion names the bias ("though this reflects grid-search-optimistic
CV scoring"), which is more than t5 ever wrote; but the Unit field
describes the number as an honest "Mean cross-validation accuracy
(5-fold)", the Recorded results line carries `mean_cv_accuracy = 0.7296`
unqualified, and the question asks whether the model predicts
*accurately*. "Predictions are still generated" answers nothing. The
honest decision was `C1`-style: the accuracy claim not assessable from a
selection-optimistic score, or nested CV (cheap here). The size of the
bias was not measured in this assessment (it needs rdkit and the grid);
with 144 configurations on 400–923 points it is likely a few points, not
fourteen — which is why the next decision is the one that matters.

**t18 09-33 #2 and 09-34 #2** (WARNING: no majority baseline; reason:
"majority baseline is ~59% average vs reported 73%, ~14% improvement").
Reviewer: rejected, upheld, upheld, insufficient. **Assessment, in two
parts.** (i) *The baseline's value is right*: recomputed from the slices
as the code cuts them, 0.565 / 0.658 / 0.530, mean 0.584; the reason's
arithmetic holds. (ii) *The improvement claim*: its direction holds —
even a selection bias of several points leaves 0.73 above 0.58 — and its
magnitude ("~14%") is a number no run produced, written into the
Conclusion by hand: the `number_from_code` decision point of the round
(LAB-041 Generate numbers, don't retype them, LAB-034 Null condition in
the same run). So: the reason is true and the limit it names holds as a
reading; what does not stand is a hand-computed baseline as the
protocol's evidence. The reviewers' split tracks exactly this seam, and
a single verdict word cannot carry both halves — the repair is to put
the baseline in the run (one line per configuration), after which the
decision is a plain `upheld`.

**t18 09-34 #3** (WARNING: positional selection assumes the sort order;
reason: "Verified that train.csv is sorted by vDILIConcern with
MC/LC/NC/sider blocks as expected"). Reviewer: insufficient,
insufficient. **Assessment: rejected — the verification is false.** The
file is sorted, but the blocks are 174 / 260 / 227 / 262 rows, not 173 /
260 / 227 / 263 as the protocol's Setup and the code's slices assume:
every slice is shifted by one row (one MC molecule lost from MCNC and
MCLCNC, one LC molecule taken into MCNC and labelled DILI by its own
category, one NC molecule lost, the sider block gaining LC's last row in
`all`). The effect on 0.7296 is within noise; the claim "verified" is
not. This is the "false verified" the TODO names, and the reviewer was
right not to take the word for it — `insufficient` did its job, and the
source says what it could not.

## What follows

1. Of fifteen decisions, two upheld rightly (t3 #1; t18's baseline value as
   a value), twelve rejected rightly, one (the "verified" sort) rejected
   on the source where the reviewer had to stop at `insufficient`. No
   reviewer verdict was wrong in the direction that would matter for a
   gate: nothing it released should have been held, and the one it held
   as uncertain was indeed false.
2. The borderline case is a decision that bundles two statements. The
   fix is not a finer verdict scale but putting the baseline where a
   number belongs — in the run — which the round's other instruments
   (the generated block, the unsourced-number hint) already ask for.
3. The off-by-one in t18 is also a finding for labkit-paper's own reading
   of the attempt: the protocol's Setup line ("MC (1-173) …") is wrong,
   and the agent's REPORT.md rests on it.
