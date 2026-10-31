# Plan: pubmedqa-haiku

The plan for this task, written before any work on it. Follow it; where it cannot be followed, say so in REPORT.md.

- **Terms:** answer: the first word of the reply, stripped of a trailing . , : ; or !, in any case, must be yes, no or maybe; any other first word — "not" in "not yes, but no", "the", an empty reply — is unparsable and counts as not correct; text: the one text both prompts show, built as "Question: <question>" and a blank line, then "Context:" and the contexts, one passage per line; placebo: a question about that text whose true answer is yes for every item; deliverable: pred_results/pubmedqa_pred.csv with the columns id and answer, one row per test question
- **Question / hypothesis:** Does claude-haiku-4-5-20251001, given a question and its context passages, answer the labelled PubMedQA questions clearly more often correctly than chance? Expected: yes.
- **Inference criterion:** the accuracy over the 50 labelled questions of train.json is at least the placebo prompt's accuracy plus margin = 0.25 (researcher's choice); an unparsable answer counts as not correct
- **Quality check:** at most max_empty = 2 of the 50 labelled questions without a parsable answer
- **Data / scope:** benchmark/datasets/pubmedqa/train.json (50 labelled questions, answer in gold) and test.json (50 questions) as supplied; only question and contexts enter the model's input; the files are used as supplied, not copied or changed
- **Data profile:** the 50 labelled questions answer yes 22, no 21, maybe 7 (counted in train.json): a constant answer reaches at most 0.44; whether a question word alone predicts the answer was not looked at
- **Model / tool:** claude-haiku-4-5-20251001 answers one prompt per call from the question and its contexts, with the fixed text below and no examples; one call per labelled question and prompt (50 × the question prompt and the placebo prompt), one request at a time, no aggregation; the 50 test questions get one registered call each for the deliverable
- **Null condition / anchors:** the placebo prompt asks "Is this passage written in English?" about the same text, with the same answer words; it cannot tell the gold apart. Its chance is the correct count its own answers reach against the gold permuted, computed exactly: every answer yes gives the gold count of yes, 22 of 50. The placebo prompt's correct count must sit within null_band_items = 3 items of that — a release condition chosen by the researcher: a placebo further off tracks the gold, and the run gives no verdict
- **Exclusions / filters:** none — every question enters; long_answer and annotator fields never enter a prompt or a choice. A test question whose reply is unparsable keeps an empty answer in the deliverable and is counted in the report; it is not asked again or filled (researcher's choice)
- **Unit:** one question; the kept number is the accuracy over the 50 labelled questions; the deliverable holds the test questions' answers
- **Prompt (verbatim):**

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

Fixed numbers, set before any result: criterion: margin = 0.25; first check: max_empty = 2; null check: null_band_items = 3.

## Task (verbatim)

  ```text
  Use the language model claude-haiku-4-5-20251001 to answer biomedical research questions. Each record in `test.json` holds a research question (`question`), the context passages of a PubMed abstract (`contexts`) and further fields of the published dataset. For every test question, prompt the model and record its answer: yes, no or maybe. The model's input may consist of the question and the context passages only, and every answer must come from the model's response to such a prompt. `train.json` holds labelled questions in the same format (answer in `gold`) for developing the prompt. Save the answers to `pred_results/pubmedqa_pred.csv` with the columns `id` and `answer`, one row per test question.
  ```
