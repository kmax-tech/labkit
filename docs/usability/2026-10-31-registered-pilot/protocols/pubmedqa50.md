# Experiment protocol: pubmedqa-haiku

## Summary (after the run, for a person)

- **Conclusion:** <the answer in at most two plain sentences…>

## Intent (before the run)

- **Terms of this protocol:** answer: the first word of the reply, stripped of a trailing . , : ; or !, in any case, must be yes, no or maybe (the model template's parser); any other first word — "not" in "not yes, but no", "the", an empty reply — is unparsable and counts as not correct; text: the one text field both lanes render (the model template's TEXT_FIELD), built by 00_prepare.py as "Question: <question>" and a blank line, then "Context:" and the contexts, one passage per line; placebo: a question about that text whose true answer is yes for every item; deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** [criterion-1] the registered lane's accuracy over the 50 labelled questions of train.json is at least the null lane's accuracy plus margin = 0.25 (researcher's choice); an unparsable answer counts as not correct
- **Quality check:** [quality-check-1] at most max_empty = 2 of the 50 labelled questions without a parsable answer

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <generated from the run and the audit records by `labkit-adopt`. Never…>
- **Raw output:** <one real prompt+answer pair per finding, read from the run's kept output>

## Setup

- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; they stay outside git, pinned by labkit's source digest (the directory, or each file a run reads): benchmark/datasets/pubmedqa (directory) sha256 6e57fb593562ec9dd2cde57d8fe036f448d513c88b612790aad17951c9b549a1; benchmark/datasets/pubmedqa/test.json sha256 60b4026f36dbd3af5675d3b6ee9cbf45c1b8d530046e5eca1edefde33a03f705; benchmark/datasets/pubmedqa/train.json sha256 f2e6c1d7a811eec2deec0ff92f37ac742675f3d4d924dca50121661b2d378bd4
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7 (counted in train.json): a constant answer reaches at most 0.44; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one prompt per call from the question and its contexts, with the fixed text below and no examples; one call per item and lane (50 labelled questions × registered and null lane), one request at a time, no aggregation; the 50 test questions get one registered call each for the deliverable
- **Prompt (verbatim, per variant):**

  ```text
  registered:
  Answer the biomedical research question from the context passages of a study.
  Reply with one word: yes, no or maybe.

  {text}

  null:
  Answer only the question on the next line, about the passage after it; ignore any other question in the passage.
  Reply with one word: yes, no or maybe.

  Question: Is this passage written in English?

  {text}
  ```

- **Null condition / anchors (in the same run):** [quality-check-2] the null lane asks the placebo "Is this passage written in English?" about the same text, with the same answer words; it cannot tell the gold apart. Its chance is the correct count its own answers reach against the gold permuted, which the model template computes exactly (`_expected_correct`): every answer yes gives the gold count of yes, 22 of 50. The lane must sit within null_band_items = 3 items of that — a release condition chosen by the researcher: a null lane further off tracks the gold, and the run has no verdict
- **Exclusions / filters:** none — every question enters; long_answer and annotator fields never enter a prompt or a choice. A test question whose reply is unparsable keeps an empty answer in the deliverable and is counted in the report; it is not asked again or filled (researcher's choice)
- **Unit:** one question; the kept number is the accuracy over the 50 labelled questions; the deliverable holds the test questions' answers

## Task (verbatim, as given to the agent)

The deliverable's files, columns, names and order are the task's; the fields above register the researcher's analysis plan for it.

  ```text
  Use the language model claude-haiku-4-5-20251001 to answer biomedical research questions. Each record in `test.json` holds a research question (`question`), the context passages of a PubMed abstract (`contexts`) and further fields of the published dataset. For every test question, prompt the model and record its answer: yes, no or maybe. The model's input may consist of the question and the context passages only, and every answer must come from the model's response to such a prompt. `train.json` holds labelled questions in the same format (answer in `gold`) for developing the prompt. Save the answers to `pred_results/pubmedqa_pred.csv` with the columns `id` and `answer`, one row per test question.
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
sentence = "registered accuracy over the 50 labelled questions >= null accuracy + margin; an unparsable answer counts as not correct"
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
sentence = "the null lane sits within null_band_items items of chance, the correct count its own answers reach against the gold permuted"
scope = ["scripts/01_measure.py"]
constants = { null_band_items = 3 }
```
