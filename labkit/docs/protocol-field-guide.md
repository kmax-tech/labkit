# Protocol field guide

This guide explains how to fill each field of
`experiment-protocol.md.template`. Read it when the one-line help of a
field is not enough. `protocol-check --guide` prints the path to this file.
`protocol-check --contract` lists the fields that your protocol owes now.
A field this guide does not list has no more to say than its one-line
help in the template.

## How to fill the protocol (eight rules)

1. Name it. Write the file, the flag, the number and the split, never a
   nickname. Write `python3 train.py --mode preflight`, not "run the
   preflight". Name the folder `experiments/<name>/` after the question:
   `span-detection-encoders`, not `exp3` or `final_v2`. The same name goes
   into `PROTOCOL-<name>.md` and into `runlog.run("<name>", …)`, so it
   labels every run. Never rename it.
2. One field, one statement. Put more than two items (metrics, arms, cases)
   in a list or a small table under the label. Never chain them with `·`. A
   longer justification is a finding. Write it in `notes/`, one idea per
   file, and link it here. A protocol registers what you fixed, ran and
   got. It is not a lab journal.
3. Show it, do not describe it. Paste the real prompt, the real rendered
   input and the real command, not "a suitable prompt".
4. One question per protocol. If the question needs an "and", split it
   into two experiments.
5. Every number carries its run_id.
6. Unknown stays unknown. Write `unknown — not recorded`, not what it
   probably was.
7. Pilot light, report heavy. Fields marked † become owed when you set
   `frozen = true`. Those in Summary and Result become owed when the run is
   written back. Until then, leave the `<…>` placeholder. These values count
   as unfilled: `TODO`, an empty label and a bare `n/a — <why>`. A value
   that still holds a stamped `<…>` phrase is unfilled, also with your text
   around it. `n/a — <the reason>` counts as filled.
8. Write for a reader who opens only this file, months later.
   - Give each reference a link and the sentence that matters. Write
     `[area 07](../07-<name>/PROTOCOL-<name>.md#setup): majority of three
     answers, accept/reject per case`, not "as in area 07".
   - Use one spelling per thing, as the data writes it.
   - Gloss each coined term or abbreviation at its first use, or list it
     under Terms of this protocol.
   - Give each field one job. Conclusion: what was decided. Recorded
     results: the values and verdicts, with the run_id. Raw output: the
     output that carried the result. Interpretation: what it means.
     Analysis audit: what the audit found. State a finding once and refer
     to it elsewhere.
   - Write the registered design in the present, the work done in the past
     and the next step as an intention.

## The form

- `labkit-init exp --repeat-cost low` stamps the short `low` cut.
  `labkit-init exp <name> --report` appends the † fields. A field that the
  cut left out is not owed.
- Keep the labels in English, exactly as stamped, because `protocol-check`
  reads them. Write the values in German or English, one language per
  protocol.
- `→ LAB-nnn <name>` points to a rule of the lab standard.
  `python -m labkit.formats.rules show LAB-nnn` prints the rule and its
  reasons.
- Some sections have a prose-line budget. `protocol-check --contract`
  prints it.

## Intent IDs

An intent id lets a tool find a promise in the code and in the result. Give
each promise an id in the field text. Report it as a lowercase key in the
metrics of the run:

| id | means | example in the field | key in metrics |
|---|---|---|---|
| `[criterion-1]` | inference criterion 1: what result supports which conclusion | `[criterion-1] accuracy >= 0.80` | `r.metrics(criterion_1_pass=True)` |
| `[quality-check-1]` | quality check 1: if it is not met or not assessable, no criterion gets a verdict | `[quality-check-1] parse failures <= 10%` | `quality_check_1_pass` |
| `[quality-check-2]` | the null condition, stamped as a quality check: the control shows no effect | `[quality-check-2] shuffled labels show no effect` | `quality_check_2_pass` |
| `[branch-1]` | registered branch 1: its outcomes in order | `[branch-1] ≥ 50 usable cases → full-report: all measures reported; otherwise → coverage-only: coverage reported, no accuracy` | `branch_1_outcome` = the selected outcome's name (`coverage-only`) |

A quality check tests whether the measurement can carry the intended
conclusion. An inference criterion decides which conclusion the result
supports. A branch says what follows from it. Specify each condition
before the result is known. A baseline
without a target value is no promise. Write it in the text of its
criterion.

`intent-check PROTOCOL-<name>.md` compares ids and keys in both directions.
It finds a promise that nobody built and a key that nobody registered. It
does not judge whether the code computes the right thing. That stays with
your reading and the reading of your supervisor.

## Reading model: HEAD and APPARATUS

People read the HEAD (Summary, Intent, Result). Write it short and
self-contained, in full sentences. People look up the APPARATUS (Context,
Setup, Checks, Runs, Follow-up, Notes) to answer one question. Write it in
precise fragments.

## Fields by section

### The head (the ```toml block, at the end)

The fields that a machine reads stand in the `[protocol]` table of the
TOML block under `## Head`. `protocol-check` reads them with a TOML
parser. A typo is an error that names the field. The same block holds the
`[[promise]]` tables (labkit `docs/promise-block.md`).

- **standard:** `"0.23"`, stamped. Never edit it. labkit refuses a protocol
  of another version. Reproduce a protocol with runs with its own labkit
  release. Use a checkout of its commit, with a venv from its
  `requirements.lock`. Never convert it. A frozen protocol and every full
  run owe the `[[promise]]` tables. At `repeat_cost = "low"`, every run owes
  them.
- **id:** `p-` plus 16 hex digits, stamped by `labkit-init exp`. Never type
  it. The run binds to the id, so a renamed or moved file keeps its runs.
- **type:** `"exploratory"` generates hypotheses. Never report a result
  from it as a test. Write `"confirmatory"` only when the question, the
  inputs and the analysis plan stood before you saw the results. The data
  must have influenced no choice. A fit or an apply also fixes its criterion
  before. There is no third type.
- **kind:** what the kept number asserts. `"compute"` judges no prediction
  and has no criterion and no promise tables. `"fit"` judges a model
  trained or adjusted in this experiment. `"apply"` judges a model used
  unchanged. The kind depends on whether data adjust the procedure. A fixed
  formula, such as k times the noise level of each signal with k fixed in
  advance, is a computation. A threshold or k tuned on reference
  annotations is `"fit"`, also by a rule registered in advance. Judge its
  claimed performance on rows kept apart from the tuning. A fit or an apply
  registers a criterion, a quality check and a null condition in the same
  run. A run that only produces predictions declares no result and needs
  no kind.
- **[model] number_describes:** only with `kind = "compute"` and a
  `[model]` table. Write `"model_outputs"` when the number describes what
  the model marked ("the model marked 30 % as causal"). Write
  `"target_property"` when it describes the data, with the model as
  annotator ("30 % of the texts are causal").
- **[model] annotation_validity:** owed with `"target_property"`, refused
  otherwise. It names the evidence that the model suits as annotator:
  - `{ protocol = "p-…" }`: an apply protocol of this repo with a declared
    result. labkit makes sure that the id resolves to exactly one.
  - `{ doi = "10.…" }`: a published validation. labkit reads its form only.

  Neither form proves that the model suits this annotation. The audit
  judges that. A changed validation owes a new audit. The audit stamp does
  not cover models.toml or the bytes behind a DOI.
- **repeat_cost:** see "Choosing the repeat cost" below.
- **frozen:** `true` means that the hypothesis, prompts, metrics,
  baselines and decision rule were fixed before the run. Only `true` with
  `test` gives a held-out number. Set it to `true` only after the
  instrument check. Keep one sentence per freeze in the prose. Put the
  reasons in the commit message.
- **preflight_audit:** the decided record under `audits/`
  (`<minute>-preflight.toml`), written by `labkit-audit --mode preflight`
  after the instrument check. Decide each finding as fixed, limitation or
  false-positive, with a reason. Leave it empty until then, and at `low`.

#### Choosing the kind

The kind follows what the reported result claims, not the tool:

1. Does the result claim how well a model predicts, against gold labels or
   targets? If not, the kind is `compute` (ML lecture, ML:VII-1). A file of
   predictions on unlabelled rows claims how well the model predicts.
2. If it does: did this experiment train, adjust or select the model? A
   threshold or a prompt chosen on performance data is model selection
   (ML:II-189). If yes, the kind is `fit`. If not, it is `apply`.

Under `compute`, document the training and the model selection like any
other code: the audit reads them. An inference criterion is not a score.
It states which result allows which conclusion.

If you select on the data that the number is reported from, the kind
stays `fit`. The number is then a training error, not a holdout error (ML:II-175). Report it on a separate
test set or by nested cross-validation.

| task | reported number | kind |
|---|---|---|
| LLM, prompt fixed in advance | accuracy vs gold | `apply` |
| LLM, prompt chosen among variants on dev data | test accuracy | `fit` |
| LLM outputs stored | share of empty answers | `compute` (`number_describes = "model_outputs"`) |
| LLM annotates claims | share of causal claims in the texts | `compute` (`number_describes = "target_property"`, `annotation_validity` owed) |
| BERT fine-tuned here | test F1 | `fit` |
| BERT checkpoint used unchanged | test F1 | `apply` |
| checkpoint fixed, decision threshold chosen on dev | test F1 | `fit` |
| random forest trained, hyperparameters by cross-validation | CV / holdout error | `fit` (nested CV or a separate test set) |
| fitted model, trained here or elsewhere | feature importances as computed | `compute` (training documented and audited) |
| regex / parser | number of matches | `compute` |
| regex / parser, rules fixed | precision vs gold | `apply` |
| regex / parser, rules repaired on the same data | precision | `fit` |
| mean, correlation, t-test | the value | `compute` |

#### Choosing the repeat cost

`repeat_cost` is the price of a repeat. The gates know two values:

- `low`: a deterministic computation, or a few model calls that finish in a
  minute for cents. `finalize` checks provenance. The audit comes before
  `labkit-adopt <area> <run_id>` adopts the number, before a note or paper
  uses it, or before it steers a decision.
- `high`: a model pass that you do not repeat casually, and anything
  expensive or irreversible. It owes the preflight audit before the freeze
  and the analysis audit after the run.

### Summary (after the run, for a person)

The Summary opens the protocol. Its reader has read nothing else yet.
Write it after the result is written back, on every tier. Add no fact that
the detail below does not hold.

- **Question †:** the question of the Intent in plain words, so that the
  reader reads the Conclusion as its answer.
- **Conclusion:** say whether the bar set before the run was met. Write
  "The class descriptions kept the cable set out of the framework class in
  all five cases, as required", not "Both arms were run on 46 cases". A
  reader who stops here must know the verdict.

### Intent (before the run, HEAD)

- **Terms of this protocol:** one line per house word, in three parts:
  *everyday word · house term · code word*. Example: "gap case (a case only
  an uncovered rule can reject) · Lückenfall · `GAP_CASES`". List the arms,
  lanes, draws, case classes, registered constants, the model alias and the
  files a reader meets. Before you coin a word, search the literature of
  the field, `notes/theorie/terms.md` and the vocabulary table of the lab
  standard. Reuse a word that you find (LAB-084 Double-coinage check).
- **Question / hypothesis:** even "just try it" has a question behind it.
  If you cannot state it, ask before you build.
- **Inference criterion:** a number, a behavior or a visual check. Ask four
  questions of it:
  1. Does it test the mechanism, or only a number?
  2. Is the target a property of one item? A relation between items has no
     single-item criterion.
  3. Is the expected effect larger than the noise between runs, and clear
     of a floor or ceiling?
  4. Can the run answer two different questions? If so, register a branch.

  Name the cases that the criterion singles out by their class ("every
  case over its ceiling"). `data/prepared/case_classes.toml` says which
  cases that is and why. Do not put a list of ids in the script.
- **Quality check:** examples: "at most 10% unparsed answers", "the
  shuffled control shows no effect". Say why its failure makes the
  measurement uninterpretable. A quality check is about the instrument
  (yield, anchor, control), never about the hypothesis. A threshold that
  the hypothesis needs is a criterion. As a quality check, it turns a clean
  negative result into "no verdict". A failed quality check does not void
  the data. Descriptive readings can follow, labelled as such.
- **Registered branch:** ask "and if [criterion-…] fails, what then?" An
  answer that you have now is a branch. A decision taken after the run goes
  to Next step, labelled as taken after the run.
  - Write at least two outcomes, for example: "quality-check-1 not met →
    noisy: no verdict, the parser is repaired first; criterion-1 met →
    generalises: used on the next cohort; otherwise → misses: reported as a
    miss, no further analysis".
  - Write an outcome name in lowercase letters, digits and hyphens, unique
    in the sentence.
  - Give each outcome a consequence: an interpretation, an action, or a
    non-action with its reason. A consequence holds no `;`.

  labkit refuses a branch in any other form. The branch is decided on its
  own condition, not on the verdict. A stop rule can fire during the run or
  on a failed quality check. `intent-check` and `finalize` block an
  outcome name under `branch_1_outcome` that is not registered.
- **Timebox:** a budget in time, not a condition on a result. "If the
  pipeline does not run by tomorrow" is a result condition. A quality check
  fires on a bad result. A timebox fires when you are stuck without one.
- **Split touched:** write the split that you plan to use, before the run.
  Anything you tune, sweep or pick a winner from must say `dev`. If a
  `test` run decides a threshold, a variant or a checkpoint, report the
  result as tuned.
- **Rival explanations †:** errors that favor the hypothesis are the ones
  that you do not notice on your own.
- **Out of scope †:** this field protects you from over-claiming in the
  write-up.

### Result (after the run, HEAD)

Write the result back as soon as the run ends. A protocol without its
result is only a plan.

- **Recorded results:** `labkit-adopt <area> <run_id>` writes this field.
  Never retype or reword it. `report-check` holds it exactly to the
  rendering. It gives the verdict of each registered promise, every other
  reported key and value, the run_id and one note on the recorded limits. A
  quality check that is not met or not assessable leaves each criterion not
  assessable. After a changed decision, `protocol-fill --render` writes it
  again. The Limitation lines below it are rendered from the audit records.
  Write what the number means in the Conclusion. Example (the rendered form
  is one line):

  ```text
  - **Recorded results:** criterion-1 met · recorded: criterion_1_accuracy = 0.83 (run 2026-10-22T09-13-08_0dc3)
  ```
- **Raw output:** a prompt+answer pair, or the registered and null row of
  an estimator. Read it from the kept output of the run. Never use the
  output of `--probe`, because the probe discards it. Without a model, the
  stamp leaves this field out.
- **Analysis audit †:** the audit of the evaluation against the frozen
  criterion. At `repeat_cost = "low"`, the stamp leaves the field out. Add
  it when the audit runs, before `labkit-adopt` or a decision.
- **`[result] run` (TOML head, not a prose field):** the run that the
  protocol reports. `labkit-adopt <area> <run_id>` writes it after a clean
  `finalize`. `finalize` and `report-check` block when it names another run
  or no run of the area.
- **Deviations after freeze:** never rewrite the Intent. Write each
  deviation here. If it touches the verdict, also write it under Summary →
  Limitations. "Changed" in Checks records changes before the freeze.

### Setup (APPARATUS)

- **Data / scope:** keep raw data under `data/raw/` and script-made inputs
  under `data/prepared/`. Never type the counts. After the preparation run,
  `protocol-fill <PROTOCOL> --data-counts` writes them at the end of the
  field. `finalize` holds that part to the run. Commit small inputs that can legally be shared. For large or
  protected data, name the source, the access route and the version. Look
  at the prepared file before the run. Otherwise a format bug and a model
  failure look the same.
- **Data profile:** owed whenever a model is named. The prompt skeleton's
  `00_prepare.py --audit` prints an aid: items and mean words per class. It
  counts cue words and numeric confounds only if you list them in `MARKERS`
  and `CONFOUNDS`. Set `None` to count none ("none counted"), or `()` when
  none applies. The counts are static evidence. A word found in one class
  only is a shortcut candidate, not proof that the model uses it. A filled
  profile does not show that the data fit the question. The audit judges
  that.
- **Model / tool:** the alias stands in the head:
  `[model] alias = "<alias from models.toml>"`.
  `labkit-init exp --model <alias>` stamps it, and
  `protocol-fill "model alias=…"` fills it. Never hardcode an endpoint or
  ID.

  Without a `[model]` table, the instrument is an estimator. Write
  `n/a — no model call; the instrument is …` and name where it is built,
  for example `make_estimator()`. Put its fixed parameters under Free knobs
  and its seed under Randomness controls. `--report` leaves the randomness
  and noise-ceiling fields owed, because a seed is a source of randomness.

  If you compare two arms, name each by the one thing that differs
  (`with-gas-classes`). Declare one table per arm in the head:

  ```toml
  [model.arms.before]
  profile = "register/profiles/x.toml"
  fingerprint = "1d4c79af596a"
  alias = "gpt-oss-20b-leguin"
  ```

  Put the diff between the two profiles verbatim under Prompt. `finalize`
  holds every arm to the answering run. It warns when a profile changed
  after the stamp.
- **Model I/O:**
  - *In:* one fully rendered example input, with real data.
  - *Out (expected):* what you told the model to produce.
  - *Out (actual):* what it really returns. This often differs.
  - *Out (decision rule):* the parse function, or the threshold and the
    split it came from. A threshold tuned on test invalidates the result.
    Test the parse function with real model outputs.
  - *Out (yield):* items expected and produced by the parse step. Count
    empty answers separately. A reasoning model can spend the whole token
    budget on thinking (finish_reason=length). A binding token cap is a
    setup defect.
- **`[gate] labels` (TOML head, not a prose field):** the labels that the
  gate accepts: `labels = ["causal", "not_causal"]`. The code check lists
  the string comparisons of the code beside this set. The agent judges the
  match (LAB-038 What the prompt demands).
- **Null condition / anchors (in the same run):** "validated earlier" does
  not count. Give each control a [quality-check-1] id. The safest placebo
  question has the same true answer for every item ("Is this text written
  in English?"). Its expected accuracy is then the gold share of the class
  that this answer maps to. A placebo whose answer varies per item can
  track the gold label and fail its band.
- **Exclusions / filters:** also name the outputs that get no gate label.
  A filter that quietly loses the hard cases makes every score look better.
- **Meaning of the gold label †:** judge it on the rendered example, not on
  the definition.
- **Noise ceiling → threshold †:** calibrate bands on the null lane, never
  on the registered lane before the freeze.
  - At apply, run `--calibrate-null`. It permutes the gold with the
    predictions fixed. [quality-check-2] registers the rule beside the band
    (`null_band_quantile` over `null_permutations`). `--write` registers
    the band before the first measurement.
  - At fit, the null lane refits `NULL_REFITS` times in the run. Their
    scores (`quality_check_2_draw_scores`) show the spread.
  - At high repeat cost, run `--probe` over a few seeds.

  A registered number seen before `frozen = true` makes the freeze empty.
  If this happened, write it here, with the numbers and the seeds.
- **Free knobs †:** set each value before the run. Then vary each one and
  report the curve, not the point.
- **Randomness controls †:** a single run at nonzero temperature is one
  draw, not a result.

### Checks (APPARATUS)

Never report a number from this stage.

- **Resolution check:** feed a perfect effect and a null effect through
  the real `evaluate()`. Use the draw structure of the run. Record both
  numbers. The stamped `tests/test_<NN>_<name>.py` keeps the check, and
  `preflight` runs it.
- **Render check:** look for stacked negation, empty fields and sentences
  that the answer form cannot decide.
- **Instrument check:** paste one prompt+answer pair per gold class as a
  code block. Without a model, run a reduced estimator on a few labelled
  items, both lanes, into a throwaway file. The full measurement without a
  run id is not an instrument check. It is the registered number, seen
  early.

### Follow-up (APPARATUS)

- **Prediction for the follow-up run †:** the prediction makes the
  follow-up a test, not a story told afterwards.

The next step lives in the Summary, not here.

### Notes (APPARATUS)

Promote the good ideas to `notes/`, one idea per file, or bring them to the
meeting.

## Training section (conditional)

If you trained or fine-tuned a model, add these fields under Setup:

- **Split:** the sizes, and how you split: at random, by document or by
  author. Pass the files to runlog as
  `data={"train": …, "dev": …, "test": …}`.
- **Labels:** how you built a training label from the gold data, and what
  counts as a match. "Exact span match = 1, everything else = 0" is a
  strong decision.
- **Candidates / negatives:** what the model scored, and the
  positive:negative ratio.
- **What got dropped:** the items that did not fit the length limit or the
  candidate rules. Give how many, and say whether they are special.
- **Gold vs. predicted inputs:** in a multi-stage pipeline, say which stage
  got gold inputs and which got predictions. If you can, report both. The
  gap is the error propagation.

## Rules behind the fields

The template's help names no rule. Each field below answers to a rule of
the lab standard (`python -m labkit.formats.rules show LAB-nnn` prints it):

| Field | Rule |
|---|---|
| Inference criterion | LAB-003 No run without an intent paragraph, LAB-004 Identifiers make the intent addressable |
| Quality check | LAB-004 Identifiers make the intent addressable |
| Registered branch | LAB-013 Registered branch when the run can answer two questions, LAB-004 Identifiers make the intent addressable |
| Rival explanations | LAB-044 The check on a confound is code |
| Analysis audit | LAB-050 Analysis audit before reporting, LAB-017 The number of audits follows the cost tier |
| Null condition / anchors | LAB-037 Every anchor carries its target and rationale |
| Resolution check | LAB-016 Resolution check before freezing |
| Instrument check | LAB-014 One fully rendered example pair per gold class |
| Yield per stage | LAB-023 No silent loss |
| Changed — and in which class | LAB-008 Instrument check before freezing |
| Prediction for the follow-up run | LAB-045 The forecast comes before the follow-up run |
