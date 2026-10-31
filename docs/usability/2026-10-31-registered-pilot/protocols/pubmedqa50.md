# Experiment protocol: pubmedqa-haiku

## Summary (after the run, for a person)

- **Conclusion:** <the answer in at most two plain sentences…>

## Intent (before the run)

- **Terms of this protocol:** answer: one of yes, no or maybe, parsed from the model's reply as the first of these words; deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** [criterion-1] the registered lane's accuracy over the 50 labelled questions of train.json is at least the null lane's accuracy plus margin = 0.25; an empty or unparsable answer counts as not correct
- **Quality check:** [quality-check-1] at most max_empty = 2 of the 50 labelled questions without a parsable answer

## Result (after the run — write back, don't go quiet)

- **Recorded results:** <generated from the run and the audit records by `labkit-adopt`. Never…>
- **Raw output:** <one real prompt+answer pair per finding, read from the run's kept output>

## Setup

- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; the files stay outside git, pinned by the sha256 the run records for them
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7: a constant answer reaches at most 0.44, so the bar (chance plus 0.25) lies above every constant answer; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one question per call from the question and its contexts with a fixed instruction and no examples; one call per question, one request at a time; the answer is the reply's first yes, no or maybe
- **Prompt (verbatim, per variant):**

  ```text
  Answer the biomedical research question from the context passages of a study.
  Reply with one word: yes, no or maybe.

  Question: {question}

  Context:
  {contexts}
  ```

- **Null condition / anchors (in the same run):** [quality-check-2] the same calls with the gold labels of the 50 labelled questions permuted: the null lane scores within null_band_items of chance
- **Exclusions / filters:** none — every question enters; long_answer and annotator fields never enter a prompt or a choice
- **Unit:** one question; the kept number is the accuracy over the 50 labelled questions; the deliverable holds the test questions' answers

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
sentence = "registered accuracy over the 50 labelled questions >= null accuracy + margin; an empty answer counts as not correct"
scope = ["scripts/01_measure.py"]
constants = { margin = 0.25 }

[[promise]]
id = "quality-check-1"
key = "quality_check_1_pass"
sentence = "at most max_empty empty or unparsable answers on the registered lane"
scope = ["scripts/01_measure.py"]
constants = { max_empty = 2 }

[[promise]]
id = "quality-check-2"
key = "quality_check_2_pass"
sentence = "the null lane sits at chance, within null_band_items items"
scope = ["scripts/01_measure.py"]
constants = { null_band_items = 3 }
```
