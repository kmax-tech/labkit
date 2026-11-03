# Analysis plan for local sentence similarity

Researcher's choices, fixed before attempts. Implement this plan unchanged.

## Question and unit

Does the unchanged sentence encoder's cosine similarity rank the 512 supplied
validation pairs in agreement with human similarity judgements, with Spearman
correlation at least 0.30 above the registered permutation control?

The unit is one sentence pair. The kept number is Spearman correlation over
all 512 validation pairs. Test predictions are a separate deliverable and are
never scored against unavailable test labels inside an attempt.

## Data and model

Use the staged validation and test files in their given order, with no
exclusions, deduplication, sentence cleaning or score rescaling. Human scores
are already in [0, 1]. The manifest fixes source revision and file digests.

Use `sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, from the local snapshot. Use the
complete SentenceTransformer pipeline, including its attention-mask-aware mean
pooling and normalization, with the PyTorch backend on CPU in float32 and
evaluation mode, gradients disabled. Set maximum sequence length to 256 tokens,
batch size to 32, and PyTorch CPU threads to 2. Use no prompt prefix, model
training, adapters, calibration or hyperparameter selection. Researcher selected
these settings for a fixed local inference procedure, not through task scores.

Encode each sentence independently. For a pair with embeddings u and v, compute
`dot(u, v) / (norm(u) * norm(v))`. Reject zero-norm or non-finite embeddings.
Never treat a batch's all-pairs similarity matrix as the vector of paired
predictions. Store each pair's own cosine, without clipping to [0, 1], scaling
to the human-score range or rounding before evaluation.

## Scoring and control

Spearman correlation is Pearson correlation of the two average-rank vectors;
tied values receive their mean rank. Compute it over the full validation split,
not per batch. Use finite float64 values for scoring. Constant vectors and
non-finite correlations invalidate the measurement; never replace them with 0.

The registered score is `rho_registered = spearman(predictions, gold)`.
The control reuses exactly the same prediction vector and scores it against
`gold_null[i] = gold[null_order[i]]`, using the organizer's frozen permutation.
It requires no further model calls, refitting or selection of a favorable
permutation. Report `rho_null = spearman(predictions, gold_null)`.

The margin 0.30 is a researcher's chosen descriptive effect threshold, with no
source or task-specific optimization. This single permutation is a fixed
control, not a permutation significance test. Report no p-value from it.

## Criterion and quality checks

- `criterion_1_pass`: `rho_registered >= rho_null + 0.30`, inclusive,
  evaluated on unrounded numbers. Store the threshold as `criterion_1_threshold`.
- `quality_check_1_pass`: both splits have exactly their 512 expected unique
  IDs, in order, with one finite scalar prediction per pair and none missing.
- `quality_check_2_pass`: the null order is exactly the staged permutation
  of 0 through 511, the registered and null lanes share the same predictions,
  and both correlations are finite and defined.

Quality failure makes `criterion_1_pass` and `criterion_1_threshold` JSON null;
it never turns an invalid measurement into a negative scientific result. Retain
available outputs and report the failed check. A finite correlation on available
rows may not be substituted for the full-data criterion.

No band around zero blocks the null: a single shuffled correlation can differ
from zero. The exact expectation over uniform permutations is zero for fixed,
nonconstant rank vectors; report that as context, not as an observed control.

## Outputs and reporting

The two CSVs have the exact columns `id,similarity` and retain input order.
Serialize sufficient precision to reproduce each cosine within `1e-5` and
the aggregate correlations within `1e-6` in the fixed environment.

The metrics JSON contains at least:

| Key | Meaning |
|---|---|
| `n_validation`, `n_test` | Number of input pairs in each split |
| `n_validation_predictions`, `n_test_predictions` | Number of finite predictions matched to expected IDs |
| `rho_registered`, `rho_null` | Full-validation correlations; null if undefined |
| `margin` | 0.30 |
| `criterion_1_threshold`, `criterion_1_pass` | Registered threshold and decision, or null when quality fails |
| `quality_check_1_pass`, `quality_check_2_pass` | The two checks above |
| `model_revision` | The fixed model commit |
| `manifest_sha256` | Digest of the staged manifest |

Record loaded model files, input file digests, environment and command with the
measurement. Compute both split outputs through the same predictor. Read back
the saved validation predictions to compute the reported metrics, so the report
and evaluator can reconstruct the decision from the deliverable.

Report measured correlations and their difference, the actual threshold, both
quality checks, both split counts, and whether the criterion is met. State that
this is application of a fixed model, not evidence of training or guaranteed
generalization to data unseen during the model's original training. If reporting
example pairs, identify them by ID and read their scores from the output.
