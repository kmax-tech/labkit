# Plan: pubmedqa-haiku

The plan for this task, written before any work on it. Follow it; where it cannot be followed, say so in REPORT.md.

- **Terms:** answer: the model's reply stripped of surrounding whitespace and one final period, lowercased; it must be exactly yes, no or maybe — any other reply ("not yes, but no", two words, an empty reply) is unparsable and counts as not correct; permutation expectation: the accuracy the answers reach on average against the gold labels permuted uniformly, exactly the sum over yes, no and maybe of (share of the answers) × (share of the gold); deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** the accuracy over the 50 labelled questions of train.json is at least their permutation expectation plus margin = 0.25 (researcher's choice); an unparsable answer counts as not correct
- **Quality check:** at most max_empty = 2 of the 50 labelled questions without a parsable answer
- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; the files are used as supplied, not copied or changed
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7: a constant answer reaches exactly its own permutation expectation, so no constant answer can pass the margin; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one question per call from the question and its contexts with the fixed instruction below and no examples; one call per question, one request at a time; no aggregation
- **Null condition / anchors:** the answers scored against the gold permuted with the seed, one draw kept: within null_band of the permutation expectation, where null_band is the 0.99 quantile of |accuracy − expectation| over 200 permutations with the seed — derived from the permutation distribution, not chosen
- **Exclusions / filters:** none — every question enters; long_answer and annotator fields never enter a prompt or a choice
- **Unit:** one question; the kept number is the accuracy over the 50 labelled questions; the deliverable holds the test questions' answers
- **Prompt (verbatim):**

  ```text
  Answer the biomedical research question from the context passages of a study.
  Reply with one word: yes, no or maybe.

  Question: {question}

  Context:
  {contexts}
  ```

Fixed numbers, set before any result: criterion: margin = 0.25; first check: max_empty = 2; null check: null_band_quantile = 0.99, null_permutations = 200.

## Task (verbatim)

  ```text
  Use the language model claude-haiku-4-5-20251001 to answer biomedical research questions. Each record in `test.json` holds a research question (`question`), the context passages of a PubMed abstract (`contexts`) and further fields of the published dataset. For every test question, prompt the model and record an answer: yes, no or maybe. From the test record, only `question` and `contexts` may enter the model's input. Each saved answer must come from an actual response of the specified model to such a prompt, either directly or by aggregating multiple such responses. You may make multiple calls per question and use majority voting or another aggregation rule. Fix the aggregation rule, including tie handling, before evaluating the test questions. All calls count toward the same time and cost budget. `train.json` holds labelled questions in the same format (answer in `gold`) for developing the prompt. You may include fixed instructions and labelled examples from `train.json` in the prompt; each example may contain its `question`, `contexts`, and `gold` answer only. Do not use `long_answer` or annotator prediction fields as prompt content or to select or modify examples, instructions, aggregation rules, or final answers. Save the answers to `pred_results/pubmedqa_pred.csv` with the columns `id` and `answer`, one row per test question.
  ```
