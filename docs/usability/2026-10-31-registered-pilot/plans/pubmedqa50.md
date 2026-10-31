# Plan: pubmedqa-haiku

The plan for this task, written before any work on it. Follow it; where it cannot be followed, say so in REPORT.md.

- **Terms:** answer: one of yes, no or maybe, parsed from the model's reply as the first of these words; deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** the accuracy over the 50 labelled questions of train.json is at least the accuracy of the same answers against permuted labels plus margin = 0.25; an empty or unparsable answer counts as not correct
- **Quality check:** at most max_empty = 2 of the 50 labelled questions without a parsable answer
- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; the files are used as supplied, not copied or changed
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7: a constant answer reaches at most 0.44, so the bar (chance plus 0.25) lies above every constant answer; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one question per call from the question and its contexts with a fixed instruction and no examples; one call per question, one request at a time; the answer is the reply's first yes, no or maybe
- **Null condition / anchors:** the same calls with the gold labels of the 50 labelled questions permuted: the answers scored against permuted labels stay within null_band_items of chance
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

Fixed numbers, set before any result: criterion: margin = 0.25; first check: max_empty = 2; null check: null_band_items = 3.
