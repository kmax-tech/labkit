# Task sentence similarity with an unchanged local model

Use the supplied local `all-MiniLM-L6-v2` model to predict semantic similarity
for the English sentence pairs in `benchmark/datasets/sts/validation.jsonl`
and `test.jsonl`. Implement the supplied analysis plan without changing it.
Do not train, select or modify a model. Where the plan cannot be followed,
describe the unresolved issue in `REPORT.md`.

The model is at `benchmark/models/all-MiniLM-L6-v2/`. The manifest
`benchmark/sts-manifest.json` identifies the fixed model, data and environment.
All model inference is local and offline. No training data or additional
datasets are needed. Test labels are unavailable.

Produce these files:

| File | Required content |
|---|---|
| `pred_results/sts_validation.csv` | Columns `id,similarity`, one prediction per validation pair, in input order |
| `pred_results/sts_test.csv` | Columns `id,similarity`, one prediction per test pair, in input order |
| `pred_results/sts_metrics.json` | The metrics specified in the plan |
| `REPORT.md` | Method, measured results, criterion outcome, checks, deviations, limitations and reproduction command |

Similarity is the cosine of the two sentence embeddings, unscaled and
unclipped. It is not a probability. Every pair must have its own prediction;
preserve IDs and duplicate pairs. The predictor receives only the two sentences,
never their human score or ID. Labels may be used only in the evaluation.

The report must state whether the registered criterion was met and name the
actual values used in that decision. Not meeting the criterion is a valid
scientific outcome. Distinguish an unmet criterion from an incomplete or invalid
measurement. Include the test predictions even when the criterion is missed.

All reported numerical results must be backed by a submitted artifact. Preserve
the analysis scripts and commands needed to reproduce the output. Do not use
reference predictions, published performance figures or other result files as
sources of predictions or to select an implementation.
