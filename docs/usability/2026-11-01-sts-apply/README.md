# Draft local sentence similarity task

This task evaluates an unchanged local sentence encoder against human similarity
judgements. It is a candidate `apply` task for comparing coding agents with and
without labkit. Model inference requires no external service.

- [Task](task.md): the common deliverable specification for both arms.
- [Analysis plan](PLAN.md): the researcher's fixed method, given to both arms;
  the lab arm receives the same content in its stamped protocol.

Status: specification only. Data staging, a reference implementation, a scorer,
the lab protocol and an offline technical trial are required before counted
attempts. No agent attempts or model measurements have run for this task.

## Sources and fixed revisions

The [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/blob/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/README.md)
describes a 384-dimensional sentence encoder with default truncation at 256
wordpieces. The [dataset card](https://huggingface.co/datasets/sentence-transformers/stsb/blob/ab7a5ac0e35aa22088bdcf23e7fd99b220e53308/README.md)
describes sentence pairs and human scores normalized to [0, 1].
Cosine similarity of sentence embeddings follows the
[Sentence Transformers STS workflow](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html).

The selected model and split define a workflow evaluation. Training overlap is
not established; results do not establish generalization to unseen training data.

## Preparation before any attempt

The organizer stages these immutable paths identically in both arms:

| Path | Contents |
|---|---|
| `benchmark/models/all-MiniLM-L6-v2/` | Local PyTorch snapshot of the fixed model revision, including weights, tokenizer and pooling configuration |
| `benchmark/datasets/sts/validation.jsonl` | First 512 rows of the pinned dataset's validation split, in source order; fields `id`, `sentence1`, `sentence2`, `gold` |
| `benchmark/datasets/sts/test.jsonl` | First 512 rows of its test split, in source order; fields `id`, `sentence1`, `sentence2`; labels withheld |
| `benchmark/datasets/sts/null_order.json` | A frozen permutation of integers 0 through 511 |
| `benchmark/sts-manifest.json` | Source revisions, source split indices, file SHA-256 digests, model file inventory, locked environment and image identity |

Assign IDs `validation-0000` through `validation-0511` and `test-0000` through
`test-0511`. Copy source strings and scores without preprocessing. Preserve
duplicates. Refuse staging if either source split contains fewer than 512 rows.
The prefix selection and size are researcher's choices for bounded CPU work,
not a representative sample of all sentence similarity tasks.

Generate `null_order.json` once with Python's `random.Random(0).shuffle` on
`list(range(512))`. Record the Python version and file digest; agents consume
the frozen file rather than regenerating it. The permuted gold for item i is
`validation[null_order[i]].gold`. Test gold and reference outputs stay outside
both attempt repositories and outside all agent-readable caches.

Build and lock the environment before staging: CPU PyTorch, Sentence
Transformers, Transformers, NumPy and SciPy. These are experiment dependencies;
labkit's runtime dependencies remain unchanged. Restrict the model snapshot to
the files the reference uses; alternative exports and published benchmark
results are not inputs. Record their upstream provenance in the manifest.

Run the complete reference computation offline on the actual attempt image.
Record runtime, peak memory, all artifact checksums and the dependency versions.
Set the common attempt budget before starting either arm, allowing time for
labkit's required audits as well as the computation. Agent and audit calls may
use their configured services; local predictor calls must not use the network.

## Reference and evaluation

Implement the reference before inspecting any agent output. Independently check
its cosine and rank-correlation calculations on hand-computed examples, including
ties and reversed ranks. A constant prediction vector is undefined correlation,
not a score of zero. Verify the reference against both the complete model
pipeline and a separate calculation of mean pooling with attention masks and
L2 normalization.

Use a per-pair absolute cosine tolerance of `1e-5` and aggregate correlation
tolerance of `1e-6`, proposed numerical tolerances for the fixed CPU environment.
Confirm their adequacy in the technical trial, then freeze them before counted
attempts. If the reference itself cannot repeat within those tolerances, fix
the environment or explicitly revise the task before evaluation.

Evaluate dimensions separately:

1. Delivery validity: required files, exact columns, 512 unique IDs per split,
   expected order and finite values. Structurally valid does not imply correct.
2. Computational agreement: compare every validation and test prediction with
   the reference, then independently recompute both correlations, the threshold
   and the criterion from the submitted predictions and the staged labels.
3. Plan adherence: inspect the code and manifest for the selected model, CPU
   inference, split, metric and null mapping; no training or selection.
   Matching correlations alone do not establish adherence.
4. Report support: compare every reported number and check claim with submitted
   files. A failed scientific criterion, truthfully reported, is successful
   task execution. A missing report is a missing answer, not an honest result.
5. Completion and cost: finished report plus outputs, elapsed time, timeout,
   turns and cost; missing cost on timeouts remains missing.

Two judges assess delivered artifacts independently using the same brief and
quote evidence. Hide the arm where practical; framework files can reveal it,
so do not claim complete blinding. Use traces only for workflow events and stop
causes, not as a requirement for proving an artifact inconsistency. Report
disagreements rather than silently resolving them in favor of one arm.

For labkit additionally record adoption and standard compliance as process
measures; neither replaces the common outcome dimensions.

## Labkit integration

Use `kind = "apply"`, with the local predictor rather than an LLM alias. A
predictor accepts sentence pairs and returns one scalar per pair without gold.
Hash the weights, tokenizer, pooling configuration and every other loaded model
file using the existing predictor dependency mechanism. Keep validation, null
and test outputs bound to the same measurement.

The estimator template currently supports accuracy, R2 and AUC; Spearman is not
implemented. This task therefore needs an experiment-local metric implementation
and corresponding tests before it can run through the lab route. Do not silently
substitute R2 or AUC. The permutation-integrity quality check in the plan also
needs an explicit experiment-local implementation. No labkit package or template
changes are part of this draft.

The lab protocol must carry the complete task and plan, including production of
the test predictions. Register the criterion and both quality checks as promises
and write the claim through labkit's existing adoption and report workflow.
The control receives the same task and plan, without framework commands.

## Fault detection checks

Before the comparison, verify the evaluator on a correct reference delivery and
separate faulty copies: reversed prediction order, a missing row, Pearson
reported as Spearman, a mismatched null permutation, a test output copied from
validation, and a report number that differs from its CSV. Each must fail the
appropriate dimension, without rejecting a truthful negative scientific result.
These checks validate the evaluator; they are not natural agent observations.

An additional planted-fault audit study must use a separate registration and
counts. Never mix known injected faults into the natural-attempt success rate.
