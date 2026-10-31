# Experiment protocol: pubmedqa-haiku

## Summary (after the run, for a person)

- **Conclusion:** <the answer in at most two plain sentences…>

## Intent (before the run)

- **Terms of this protocol:** answer: the model's reply stripped of surrounding whitespace and one final period, lowercased; it must be exactly yes, no or maybe — any other reply ("not yes, but no", two words, an empty reply) is unparsable and counts as not correct; permutation expectation: the accuracy the registered answers reach on average against the gold labels permuted uniformly, exactly the sum over yes, no and maybe of (share of the answers) × (share of the gold); deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** [criterion-1] the registered accuracy over the 50 labelled questions of train.json is at least their permutation expectation plus margin = 0.25 (researcher's choice); an unparsable answer counts as not correct
- **Quality check:** [quality-check-1] at most max_empty = 2 of the 50 labelled questions without a parsable answer

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <generated from the run and the audit records by `labkit-adopt`. Never…>
- **Raw output:** <one real prompt+answer pair per finding, read from the run's kept output>

## Setup

- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; the files stay outside git, pinned by the sha256 the run records for them
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7: a constant answer reaches exactly its own permutation expectation, so no constant answer can pass the margin; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one question per call from the question and its contexts with the fixed instruction below and no examples; one call per question, one request at a time; no aggregation
- **Prompt (verbatim, per variant):**

  ```text
  Answer the biomedical research question from the context passages of a study.
  Reply with one word: yes, no or maybe.

  Question: {question}

  Context:
  {contexts}
  ```

- **Null condition / anchors (in the same run):** [quality-check-2] the registered answers scored against the gold permuted with the seed, one draw kept: within null_band of the permutation expectation, where null_band is the 0.99 quantile of |accuracy − expectation| over 200 permutations with the seed — derived from the permutation distribution, not chosen. The model template's null check at half the items (two classes) does not apply to three answers; the measurement script replaces it with this one
- **Exclusions / filters:** none — every question enters; long_answer and annotator fields never enter a prompt or a choice
- **Unit:** one question; the kept number is the accuracy over the 50 labelled questions; the deliverable holds the test questions' answers

## Task (verbatim, as given to the agent)

The deliverable's files, columns, names and order are the task's; the fields above register the researcher's analysis plan for it.

  ```text
  Use the language model claude-haiku-4-5-20251001 to answer biomedical research questions. Each record in `test.json` holds a research question (`question`), the context passages of a PubMed abstract (`contexts`) and further fields of the published dataset. For every test question, prompt the model and record an answer: yes, no or maybe. From the test record, only `question` and `contexts` may enter the model's input. Each saved answer must come from an actual response of the specified model to such a prompt, either directly or by aggregating multiple such responses. You may make multiple calls per question and use majority voting or another aggregation rule. Fix the aggregation rule, including tie handling, before evaluating the test questions. All calls count toward the same time and cost budget. `train.json` holds labelled questions in the same format (answer in `gold`) for developing the prompt. You may include fixed instructions and labelled examples from `train.json` in the prompt; each example may contain its `question`, `contexts`, and `gold` answer only. Do not use `long_answer` or annotator prediction fields as prompt content or to select or modify examples, instructions, aggregation rules, or final answers. Save the answers to `pred_results/pubmedqa_pred.csv` with the columns `id` and `answer`, one row per test question.
  ```

## Runs (protocol run list — via `runlog`, cite run_ids instead of retyping numbers)

- <run_id> — <one sentence: what this run was>

## Head (read by the checks)



*How to fill each field: `protocol-check --guide`. What this protocol
owes now: `protocol-check --contract`. To fill a field:
`protocol-fill PROTOCOL-<name>.md "<label>=<value>"`.*

```toml
# `[result] run = "<run_id>"` below [protocol] is written by `labkit-adopt`:
# the one declaration that this protocol reports a number.
[protocol]
standard = "0.23"
id = "{protocol_id}"
type = "exploratory"
repeat_cost = "low"
kind = "apply"
frozen = false
preflight_audit = ""

[model]
alias = "haiku"
# With a model: `[model] alias` (stamped by --model), `[model.arms.<arm>]` with
# profile, fingerprint, alias (finalize holds them to the run); `[gate] labels = […]`.

# The promises as data, one table per id: the key the run reports, the
# sentence (no `<…>` left at the freeze), the code region, and the constants
# the script reads with promises.all_constants(). Each constant stands in one
# table. The numbers below are the stamp's examples, not your design: set
# each before the commit to the value its sentence states, chosen from the
# question, never from a result. At an apply with the estimator skeleton,
# `scripts/01_measure.py --calibrate-null --write` registers `null_band`
# before the first measurement. After the first measurement none of them
# changes.
[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
sentence = "registered accuracy over the 50 labelled questions >= their permutation expectation + margin; an unparsable answer counts as not correct"
scope = ["scripts/01_measure.py"]
constants = { margin = 0.25 }

[[promise]]
id = "quality-check-1"
key = "quality_check_1_pass"
sentence = "at most max_empty unparsable answers on the registered lane"
scope = ["scripts/01_measure.py"]
constants = { max_empty = 2 }

[[promise]]
id = "quality-check-2"
key = "quality_check_2_pass"
sentence = "the registered answers against the gold permuted with the seed score within the 0.99 quantile of |accuracy - expectation| over null_permutations permutations of the permutation expectation"
scope = ["scripts/01_measure.py"]
constants = { null_band_quantile = 0.99, null_permutations = 200 }
```
