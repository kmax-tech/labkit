# Protocol field guide

Decoder for `experiment-protocol.md.template` — explanations, examples,
rationale for each field. The template is the checklist you fill; this
document is the reference you read. `protocol-check --guide` prints the
path to this file.

## How to fill the protocol (eight rules)

1. **Name it.** The file, the flag, the number, the split — never a nickname.
   "The new variant", "see question 1", "the usual threshold" work only for
   whoever coined them, and in six weeks that is nobody. Write
   `python3 train.py --mode preflight`, not "run the preflight".
   This starts with the experiment's own folder, `experiments/<name>/`, which
   should name the **question** rather than the order things happened in:
   `span-detection-encoders` and `window5-vs-full-pairs` still mean something
   in March, while `exp3`, `test2` and `final_v2` never did. The same name
   goes into the protocol's filename (`PROTOCOL-<name>.md`) and into
   `runlog.run("<name>", …)`, so it labels every run-index row and every run
   folder — pick it once, and don't rename it afterwards.
2. **One field, one statement.** A slot takes one statement, not a
   paragraph. More than two items (metrics, arms, cases) go as a list or a
   small table indented under the label — never as a `·` chain in one line.
   If a justification needs more, it is a finding: write it in `notes/` (one
   idea per file) and leave the [[wikilink]] here. A protocol is a
   registration — what you fixed, ran and got — not a lab journal of how you
   got there.
3. **Show it, don't describe it.** "A suitable prompt" and "the whole
   tokenized post" are descriptions. Paste the actual prompt, the actual
   rendered input, the actual command.
4. **One question per protocol.** If "What I want to find out" needs an "and",
   you have two experiments. Split them — otherwise a problem in one taints a
   result in the other that was perfectly sound.
5. **Every number carries its run_id.** A number you cannot trace is a number
   you cannot defend.
6. **Unknown stays unknown.** Write `unknown — not recorded` rather than what
   it probably was. The gaps are information: they show which results are already
   defensible and which only exist in your memory.
7. **Pilot light, report heavy.** For a quick pilot you owe only the core:
   the question, how you'll recognize it worked, the type, the rendered
   prompt / model I/O, and what came out. Fields marked **†** are
   report-grade: they become mandatory the moment you set `frozen = true`
   in the head — that is, the moment you want to report the number; those
   in Summary and Result once the run is written back as well. Until then,
   leave the `<…>` placeholder rather than padding them. `TODO`, an empty
   label, a bare `n/a — <why>` and a value that still holds one of the
   stamp's `<…>` phrases (text written before or after it included) count
   as unfilled; `n/a — <the reason>` counts as filled.
8. **Write for the reader who opens only this file.** A protocol is read
   by a person, months later, without the session that wrote it
   (2026-10-07: a frozen, audited protocol was sound and still read "far too
   dense" — bare cross-references, two spellings of one case, every field
   retelling the result).
   - **A reference carries a link and the sentence that matters.** Not
     "as in area 07" but `[area 07](../07-<name>/PROTOCOL-<name>.md#setup):
     majority of three answers, accept/reject per case` — the reader gets
     the gist here and the detail one click away.
   - **One spelling per thing.** Case ids, file names and terms as they are
     in the data; a short form is defined once (Terms of this protocol).
   - **Every coined term or abbreviation is glossed on first use**, or
     listed under Terms of this protocol.
   - **One job per field.** Conclusion: what was decided. Recorded results:
     the measured values and registered verdicts, with the run_id. Raw output: the
     concrete output that carried the result. Interpretation: what the
     mechanism means and what follows. Outcome: one sentence. The audit
     field: what the audit found. A finding stated in one of them is
     referenced, not retold, in the others.
   - **Tense follows the time of the text:** the registered design in the
     present, what was done in the past, the next step as an intention.

## The form: cuts, languages, rule references

- **One template, three cuts.** `labkit-init exp --repeat-cost low` stamps the
  `low` cut: head, terms, question, data, unit, exclusions, and after
  the run the Recorded results line (`protocol-fill --from-run` writes it) and the
  Conclusion, your two sentences — with `--kind fit` or `apply` also
  criterion, admissibility condition, model / tool and null condition; with
  `--model` also data profile, prompt and raw output. A computation registers
  no criterion, and unfrozen with no promise id in its prose no promise
  either (its number is held by `--check` and `finalize`). Every stamped placeholder is one line;
  this guide is the long form. The full form adds the rest; `labkit-init exp
  <name> --report` appends the † fields. A field the cut left out is not owed.
- **Labels English, values in the protocol's language.** The labels are
  read by `protocol-check`, so they stay exactly as stamped; what you write
  after them — status words included — is German or English, one per
  protocol.
- **`→ LAB-nnn <name>`** points to the rule in the lab standard (`python -m labkit.formats.rules show LAB-nnn`):
  the reasoning and the evidence live there, here only what the field
  demands.
- **Budgets.** The HEAD (Summary, Context, Intent, Setup) is read and has a
  prose-line budget per section; `protocol-check --contract` prints it.

## Intent IDs [C/A/B]

Small machine-readable anchors — they exist so a tool can later verify that
what the protocol promised actually shows up in the code and in the run's
result. Give each promise a short id in the field text, and report it as a
lowercase key in the run's metrics:

| id | means | example in the field | key in metrics |
|---|---|---|---|
| `[C1]` | criterion 1 — which value of which metric supports the hypothesis | `[C1] accuracy >= 0.80` | `r.metrics(c1_pass=True)` |
| `[A1]` | admissibility condition 1 — an outcome-neutral check that must pass before any C verdict | `[A1] parse failures <= 10%` · `[A2] shuffled labels show no effect` | `a1_pass`, `a2_pass` |
| `[B1]` | registered branch 1 — what a result licenses next | `[B1] if < 50 usable cases, report coverage only` | `b1_branch` |

The separation rule: **C judges, A releases the judgement, B says what
follows from it.** Does the condition depend on whether the hypothesis
holds? Then it is C; otherwise A. A baseline without a target value is no
promise — it belongs in the text of the C it serves.

`intent-check PROTOCOL-<name>.md` compares the two sets: a promised id with
no key means the promise was never built; a key with no registered id means
something reports that nobody registered. It checks EXISTENCE, not
correctness — whether the code computes the right thing is still your (and
your supervisor's) reading. Protocols without ids are simply skipped, so
this costs nothing until you opt in.

## Reading model: HEAD and APPARATUS

The template splits into two parts. **HEAD** (Summary, Intent, Result)
gets **read** — this is what your supervisor and future-you look at
before a meeting. Keep it short and self-contained. **APPARATUS** (Context,
Setup, Checks, Runs, Follow-up, Notes) gets **looked up** — it answers
specific questions ("what data?", "what prompt?") but nobody reads it top
to bottom. This split decides your writing budget: HEAD deserves polished
sentences, APPARATUS deserves precise fragments.

## Fields by section

### The head (the ```toml block, at the end)

The fields a machine reads are data, not prose: the `[protocol]` table of
the protocol's one ```toml block, stamped at the end under `## Head` so a
person meets the Summary first. `protocol-check` reads them with a TOML
parser — exact keys, typed values; a typo is an error that names the field.
The same block may hold the `[[promise]]` tables (labkit
`docs/promise-block.md`).

- **standard** — `"0.23"`; stamped, never edited. A protocol of another
  version is refused; use the labkit release it was written for, or
  update it: the refusal says what changed. Standard 0.23 renames `cost` to
  `repeat_cost` with the two values the gates read. Standard 0.22 adds `kind`
  (below). Standard 0.21 names the Summary's prose answer `Conclusion` and the
  generated metrics field `Recorded results`. 0.102.0 is the last release
  reading the old labels under standard 0.20. Standard
  0.19 (labkit 0.72): a frozen protocol and every full run — at `repeat_cost =
  "low"` every run — owe the `[[promise]]` tables; a run records every
  registered constant unchanged.
- **id** — `p-` plus 16 hex digits, stamped by `labkit-init exp`, never typed: the
  run binds to it, so renaming or moving the file keeps the binding.
- **type** — `"exploratory"` generates hypotheses, iterate freely, but
  nothing from it may be reported as a test. `"confirmatory"` tests a
  hypothesis fixed BEFORE the run, on data that influenced no choice.
- **kind** — what the kept number asserts: `"compute"` judges no prediction
  (a measurement that cannot pass trivially: no criterion, no promise
  tables); `"fit"` judges a model trained or adjusted in this experiment;
  `"apply"` judges a model used unchanged. A fit or an apply registers the
  bar (criterion), what must hold before it is read (admissibility) and
  what it is held against (null condition / anchors, computed in the same
  run), and carries promise tables; with a `[model]` table also the data
  profile and the prompt. The kind describes the number, not every
  operation of the run: a run that only produces predictions declares no
  result and needs no kind. A `compute` with a `[model]` table — the model
  produced the values the number is computed from — says what the number
  describes (`number_describes`, next entry). Choose it with the two
  questions below.
- **[model] number_describes** — only with `kind = "compute"` and a
  `[model]` table: `"model_outputs"` when the number describes what the
  model marked ("the model marked 30 % as causal"), `"target_property"`
  when it describes the data, the model serving as annotator ("30 % of the
  texts are causal"). The kind says what the number asserts; this says what
  it is about; whether the annotator suits is a third question.
- **[model] annotation_validity** — owed with `"target_property"`, refused
  with `"model_outputs"`: the evidence that the annotator suits (annotation
  validity; model annotations are a silver standard). Either `{ protocol =
  "p-…" }`, an apply protocol of this repo with a declared result — labkit
  checks that the id resolves to exactly one such protocol, so the bound
  validation can be checked — or `{ doi = "10.…" }`, a published
  validation, checked for its form only. Neither proves that the model
  suits this annotation (same model, prompt, target concept): that stays
  with the audit, which `labkit-audit` shows the bound protocol, its
  result (`metrics.json`), the model its run recorded (`models_resolved`)
  and its prompt; today's models.toml entry and prompt sources are shown
  as such. The audit record's stamp covers the protocol, the result, the
  run records and the scripts — not today's models.toml, which can change
  after the validation — so a changed validation owes a new audit. A
  DOI binds no document bytes: only its string is stamped, and nothing
  notices when the cited publication changes. With `fit` or
  `apply` both keys are refused — there the model is what the number
  judges, not an instrument.
- **repeat_cost** — see below.
- **frozen** — `true` means hypothesis, prompts/rules, metrics, baselines
  and decision rule were all fixed beforehand; only `true` plus `test` gives
  you a held-out number. Goes from `false` to `true` only after the
  instrument check; per (re-)freeze ONE sentence stays in the prose — the
  reasoning goes into the commit message.
- **preflight_audit** — the file name of the decided preflight record
  under `audits/` (`<minute>-preflight.toml`, written by `labkit-audit
  --mode preflight`; every finding in it fixed / accepted / deferred /
  dismissed, with reason): the code-vs-intent audit after the instrument
  check and before freezing. Empty until then, and at `low`.

**Choosing the kind** — the kind follows the reported number, not the
tool: the same LLM or random forest can stand under any of the three.
(1) Does the number judge how well a model or prediction procedure
predicts, against gold labels or targets? No → `compute`, a descriptive or
inferential statistic (ML lecture, ML:VII-1). (2) Was that model or
procedure trained, adjusted or selected in this experiment — a threshold or
a prompt chosen on performance data is model selection, the prompt a
hyperparameter (ML:II-189)? Yes → `fit` ("Learning task: Fit D", ML:I);
no → `apply`. Selecting on the very data the number is reported from keeps
the kind `fit` but makes the number optimistic, a training error rather than
a holdout error (ML:II-175): report it on a separate test set or by nested
cross-validation.

| task | reported number | kind |
|---|---|---|
| LLM, prompt fixed in advance | accuracy vs gold | `apply` |
| LLM, prompt chosen among variants on dev data | test accuracy | `fit` (model selection; prompt = hyperparameter) |
| LLM outputs stored | share of empty answers | `compute` (`number_describes = "model_outputs"`) |
| LLM annotates claims | share of causal claims in the texts | `compute` (`number_describes = "target_property"`, `annotation_validity` owed) |
| BERT fine-tuned here | test F1 | `fit` |
| BERT checkpoint used unchanged | test F1 | `apply` |
| checkpoint fixed, decision threshold chosen on dev | test F1 | `fit` |
| random forest trained, hyperparameters by cross-validation | CV / holdout error | `fit` (nested CV or a separate test set) |
| fitted model | feature importance or coefficients as a finding | `compute` (the training stays traceable) |
| regex / parser | number of matches | `compute` |
| regex / parser, rules fixed | precision vs gold | `apply` |
| regex / parser, rules repaired on the same data | precision | `fit` |
| mean, correlation, t-test | the value | `compute` |

**repeat_cost** — the price of a *repeat*, not whether a model is involved,
and the gates know two values and nothing in between. `low`: a deterministic
computation, or a handful of model calls that finish in a minute for cents —
rerunnable at will, so no agent audit per run; `finalize` checks provenance,
the independent audit comes before the number is adopted (`protocol-fill
--from-run`, its promotion into a note or paper) or steers a decision. `high`: a model pass you would not casually redo, and
anything expensive or irreversible — the preflight audit before freezing and
the analysis audit after. Until labkit 0.103.0 the head said `seconds |
minutes | hours`; `minutes` and `hours` owed the same, and the time words
misled: two cold agents declared `minutes` for sixteen calls and paid fifteen
minutes of audit waiting for a 64-second run (2026-10-05).


### Summary (after the run, for a person)

Two texts for a person, at two times: before the run a reader reads the
**Intent** (question, expectation, criterion); after the run the
**Summary**, which opens the protocol. Write the Summary once the result is
written back — on every tier, low included. Whoever reads it has read
nothing else yet; everything below it is the evidence for a check. It
derives from the detail below and carries no fact that isn't there.

- **Conclusion:** the answer to the Question line above it, in at most two
  plain sentences that say whether the bar set before the run was met —
  "The class descriptions kept the cable set out of the framework class in
  all five cases, as required", not "Both arms were run on 46 cases". A
  reader who stops after the Summary must know the verdict (round 10: four
  readers of the first ten lines got the number and the limit but not
  whether the criterion held). No intent ids, metric keys or run_ids (they are in Result below);
  a technical term gets a half-sentence gloss.
- **Limits:** how far it holds, one sentence — the sample, a single run,
  what was not tested.
- **Next step:** what follows — a decision, the next experiment, or "none".
- **Question †:** the first line of the Summary: the Intent's question in
  plain words, so the Conclusion is read as its answer (round 15, 2026-10-08:
  a person restated the question and did not read the Conclusion as the
  answer). Authority stays with Intent → Question / hypothesis; this line
  is its readable projection — one home means one source of truth, not
  that a sentence may appear once. Formerly: only where Result
  does not carry it.
- **Did †:** what was done, one sentence — for a reader with no context.

### Intent (before the run, HEAD)

- **Terms of this protocol:** the first field of the Intent, because the
  question uses the words. One line per house word, three parts — *everyday
  word · house term · code word*: "gap case (a case only an uncovered rule
  can reject) · Lückenfall · `GAP_CASES`". The everyday word is what a
  newcomer reads, the house term what the lab says, the code word what the
  script and the metrics carry — one line holds the three languages together
  (German prose, English tables, code), which is where four cold readers
  lost the thread (rounds 15–16, areas 18 and 19, 2026-10-09). Arms, lanes
  and draws, case classes and their id form, every registered constant, the
  model alias, the files a reader meets. Before coining: the field's
  established term (a textbook, the notation card the lab keeps), the repo's
  `notes/theorie/terms.md` (the lab's), the lab standard's vocabulary
  table (the method's) — a word
  found there is inherited, not re-coined (LAB-084 Double-coinage check).
  "n/a — standard vocabulary" only if the protocol coins nothing. Until
  2026-10-09 this field sat under Context, after Result; protocols written
  before keep it there, the checker reads the field by label.
- **Question / hypothesis:** the one question — what do you expect? Even
  "just try it" has a question behind it; if you can't state it, ask BEFORE
  you build.
- **Success / failure criterion:** a number, a behavior, a visual check —
  decided beforehand. Four questions to ask the criterion itself:
  (1) Does it test the *mechanism* or just a number? (2) Is the target a
  *property of one item* or a *relation between items*? A relation has no
  single-item criterion. (3) Does the scale have a floor/ceiling, and is the
  expected effect bigger than the run-to-run noise? Differences below the
  noise are not interpretable. (4) Could the run answer two *different*
  questions depending on a precondition? Then register that branch beforehand.
  Using intent ids: one [C1], [C2] … per conjunct, [B1] per branch point. Cases the criterion singles out are named by their
  class ("every case over its ceiling"), and `data/prepared/case_classes.toml`
  says which cases that is and from which facts — not a list of ids with a
  prose reason in the script (uniagent 17: "33 in Wien, 140 € > ARV 117" as a
  docstring; round 15, 2026-10-08). Where a number stands, the sentence names its constant from the
  [[promise]] table ("in at least `min_draws` = 2 of 3 draws"): the one
  word that links the prose (German or English), the table and the
  script's name; without it a person found no way from the sentence to
  the threshold (round 15, 2026-10-08).
- **Admissibility condition:** what must hold in the same run before any
  verdict is issued, fixed beforehand — e.g. "at most 10% unparsed answers",
  "the model is above chance on the hand-checked sanity examples", "the
  shuffled control shows no effect". If one fails, there is no C verdict,
  only the finding that the instrument failed — a bad outcome becomes a
  finding instead of weeks of tweaking. It complements the Timebox: the
  Timebox stops you on time, an admissibility condition on results.
  Result-based, not time-based — a deadline belongs in Timebox. Intent id:
  [A1] per condition. Each condition says WHY its failure makes the
  measurement uninterpretable: an A is about the instrument (yield,
  anchor, control), never about the hypothesis — a threshold the
  hypothesis needs is a C; as an A it would turn a clean negative result
  into "no verdict" (review 2026-10-08). A failed A does not void the
  data: descriptive readings may follow, labelled as such.
- **Timebox:** a hard time budget, independent of results — e.g. "4 hours,
  then log a blocker and ask". NOT a result-based condition with a
  deadline — "if the pipeline doesn't run by tomorrow" is a result
  condition that happens to have a clock, not a timebox. The distinction
  matters: an admissibility condition fires when you see a bad result and
  saves you from tweaking; a timebox
  fires when you've been stuck without any result and saves you from silent
  stuckness.
- **Split touched:** which split may be touched — train | dev | test.
  A pre-commitment, not a log: you write which split you PLAN to use, not
  which you ended up using. Anything you tune, sweep, or pick a winner from
  must say `dev`. The moment a `test` run decides something — a threshold, a
  variant, a checkpoint — the result is tuned, not held out, and must be
  reported that way.
- **Registered branch:** if a result decides the conclusion or the next
  analysis, register it BEFORE the run: condition + what each branch
  licenses, [B1] per branch point. The test: "and if [C…] fails — what
  then?" An answer you have now is a branch; no answer yet is "n/a — only
  one outcome", and a decision taken after the run goes to Next step,
  labelled as taken after the run (exploratory, not registered). A branch
  is decided on its own condition, not on the verdict: a stop rule fires
  during the run or on an inadmissible one too. The value the run records
  under `b1_branch` is the registered sentence, verbatim — one wording in
  the prose, the [[promise]] table and the code, so a reader of
  metrics.json finds the branch in the protocol by searching it. It says
  which branch and what follows; how to interpret votes or reasons is the
  protocol's business (rival explanations), not the branch value's
  (round 15: "extrem technisch — da muss ich erst nachschauen").
- **Why this design †:** choice of model, dataset, method — one sentence.
- **Rival explanations †:** per confound: what OTHER than the hypothesis
  produces the same number · error direction (does it push for or against
  the hypothesis?) · the check as CODE in `evaluate()`. Errors that favor
  the hypothesis are the ones you won't notice on your own.
- **Out of scope †:** the neighbouring questions this run leaves open —
  protects you from over-claiming in the write-up.

### Result (after the run, HEAD)

Write this back into the protocol as soon as the run finishes — a protocol
that ends before the result is only a plan, and the results then live
scattered in output files nobody can interpret.

- **Recorded results:** the reportable verdict of every registered
  promise — an admissibility condition not assessable or not met leaves
  each criterion not assessable, never a bare pass —, then every other
  reported key and value of the declared run as its `metrics.json`
  recorded them, the run_id, and one note on the recorded limits — written
  by `protocol-fill --from-run` and held exactly
  to that rendering by `report-check` (phase 5, 2026-10-21): never retyped,
  never reworded; after a changed decision `protocol-fill --render` writes
  it again. The Limit lines below it are rendered the same way from the
  audit records. What the number means goes into the Summary's Conclusion, in
  your words; long form → [[note]]. Example (the rendered form is one
  line):

  ```text
  - **Recorded results:** C1 met · recorded: c1_accuracy = 0.83 (run 2026-10-22T09-13-08_0dc3)
  ```
- **Raw output:** one real prompt+answer pair per finding.
- **Interpretation / next step:** one sentence; keep instrument findings
  apart from findings about the subject.
- **Outcome †:** expected or surprising — failures belong here.
- **Rival check †:** which rivals are ruled out, which still stand?
- **Caps/drops †:** what was omitted or limited.
- **Analysis audit †:** date · scope sha · N findings — the audit of the
  EVALUATION against the frozen criterion, before the number leaves. Not
  stamped at `repeat_cost = "low"`: there the audit comes before the number
  is adopted (`protocol-fill --from-run`) or steers a decision, and the field
  is added then — an open
  placeholder was what readers stumbled over (2026-10-07).

- **`[result] run` (TOML head, not a prose field):** the run the protocol
  reports — its run_id, written by `protocol-fill --from-run` after a clean
  `finalize`, the one declaration that the number is reported (phase 3 of
  the 1.0 line, 2026-10-21; before, a run id in the former Answer line and an
  `Answering run` field carried it). A projection of
  `answering_run.bound_answering_run` (the one choice intent-check, finalize
  and labkit-params share), never a second binding: `finalize` and
  `report-check` block when it names another run or no run of the area, and
  a table that does not read blocks where it stands (round 15, 2026-10-08:
  a person named the fresh run, not the derived one that answers).
- **Deviations after freeze:** "none", or what was changed after
  `frozen = true`. The registered plan (Intent) is not rewritten; a
  deviation stands here, in the Result block, and — where it touches the
  verdict — in Summary → Limits. Not to be confused with "Changed", which
  records instrument changes BEFORE the freeze.

### Context (APPARATUS)

- **Problem in one sentence:** no technical terms — what is being found out?
- **Prior threads:** 2–3 [[wikilinks]], each with half a sentence on why
  they lead here.

### Setup (APPARATUS)

- **Data / scope:** source, N, producer script; pilot subset first. Look at
  the prepared file before running — otherwise a format bug and a model
  failure look identical.
- **Data profile:** your judgement of the data, written before the
  measuring run: could a surface feature answer the question without the
  model? Owed whenever a model is named, at every kind. The prompt
  skeleton's `00_prepare.py --audit` prints an aid (the compute and
  estimator skeletons stamp none) — items and mean words per
  class always; cue words (hedges, modal words, connectives, boilerplate)
  and numeric confounds only if you list them in `MARKERS` and
  `CONFOUNDS` (`None` prints "none counted", `()` "none applies", a
  listed marker in no item "checked, no hit"). The counts are static
  evidence: a word found in one class only is a shortcut candidate, a
  reason to change the data or to name the limit, not proof the model
  uses it; a cue may sit in no word you listed, and a filled profile is
  no evidence that the data fit the question. Whether they do is the
  audit's question, and a control experiment's where it matters.
- **Model / tool:** the instrument in one sentence — what the model does
  here and what it sees. The alias itself stands in the head: `[model]
  alias = "<alias from models.toml>"`, stamped by `labkit-init exp --model
  <alias>` (a bare `--model` leaves the placeholder, `protocol-fill "model
  alias=…"` fills it); never hardcode endpoint or ID. The table is the one
  answer to "is a model in the loop" — for the low cut, the
  registration and `--report` — since phase 4 of the 1.0 line (2026-10-21;
  until 0.100.0 this prose line decided it, read with a pattern for "n/a",
  "none" and dashes). No `[model]`? Then the instrument is an estimator:
  `n/a — no model call; the instrument is …` names where it is built (the
  stamp of an area without `--model` writes `make_estimator()`); its fixed
  parameters go under Free knobs and its seed under Randomness controls —
  `--report` fills only the parser field and leaves the randomness and
  noise-ceiling fields owed, because a seed is a source of randomness.
  Two arms compared (a profile each)? Say here what `before` and `after`
  are — by the one thing that differs where you can (`with-gas-classes`) —
  and declare the profiles in the head, one table per arm:

  ```toml
  [model.arms.before]
  profile = "register/profiles/x.toml"
  fingerprint = "1d4c79af596a"
  alias = "gpt-oss-20b-leguin"
  ```

  and put the diff between the two profiles verbatim under Prompt. A
  reader of the protocol then knows what the arms are without opening the
  register; `finalize` holds every arm to the answering run (profile
  exists, fingerprint and alias recorded) and warns when the profile
  changed after the stamp. The profile is the instrument (model alias,
  temperature, repeats, rule texts, switches), versioned in the register
  and shared across areas; the run's config.json records what was
  resolved; the protocol names which are compared (2026-10-09).
- **Prompt (verbatim, per variant):** paste the actual prompt here. It
  belongs in the protocol, not only in the script.
- **Model I/O:**
  - *In:* ONE fully rendered example input, real data filled in.
  - *Out (expected):* what you told or expect the model to produce.
  - *Out (actual):* what it really returns — often differs.
  - *Out (decision rule):* how that becomes your label or number: which parse
    function, or which threshold/argmax — and which split the threshold came
    from. A threshold tuned on test invalidates the result. The parse
    function deserves a test fed with REAL model outputs.
  - *Out (yield):* how many items the parsing step was supposed to produce vs.
    how many it actually produced. Count EMPTY answers as their own number:
    reasoning models can burn the whole token budget thinking
    (finish_reason=length) — a binding token cap is a setup defect.
- **`[gate] labels` (TOML head, not a prose field):** which labels the gate
  accepts — `labels = ["causal", "not_causal"]`, the registered set. The
  code check extracts the code's string comparisons and lists them beside
  the declared set in the agent's bundle; the agent judges the match
  (LAB-038 What the prompt demands), no gate compares them (phase 4,
  2026-10-21; a prose field until 0.100.0).
- **Null condition / anchors (in the same run):** what runs along in THIS run
  and must show null — anchors of known rate, placebo, swap; not "was
  validated earlier". Per anchor its expected outcome WITH the derivation in
  half a sentence. Intent id: [A1] per control (an admissibility condition).
  A placebo question is safest when its true answer is the same for every
  item ("Is this text written in English?"): the expected accuracy is the
  gold share of the class that answer maps to, derived before any call. A
  placebo whose answer varies per item (numbers, length) can track the gold
  label and fail its band (usability probe 2026-10-07).
- **Exclusions / filters:** what is dropped from the data or output and why;
  which outputs get no gate label — "none" if nothing is excluded. Silent
  drops are the classic error: a filter that quietly loses the hard cases
  makes every score look better.
- **Data preparation †:** raw → prepared: which script wrote which file; the
  experiment reads prepared only.
- **Meaning of the gold label †:** what does the positive class REALLY mean?
  Check on the rendered example, not on the definition.
- **Answer form + resolution †:** how many distinguishable states does the
  answer have, and where does the expected value sit?
- **How measured †:** metric or mechanism: what is compared, what counted.
- **Validation †:** anchor items, second model or self-consistency, cross-check.
- **Noise ceiling → threshold †:** measure repetition spread; the threshold
  comes from the null condition of THIS run. Calibrate bands on the null
  lane or on a subset (`--probe`), never on the registered lane over all
  items before the freeze: a registered number seen before `frozen = true`
  makes the freeze empty, and the prediction for the follow-up run a
  reading. Where it happened anyway, it stands here with the numbers and
  the seeds (Sonnet v3 t3 and t5, 2026-10-16, wrote it under Randomness
  controls, where nobody looks for it).
- **Free knobs †:** every preprocessing parameter with its value: thresholds,
  filters, cutoffs, windows. Setting them a priori is right — but then vary
  each one and report the curve, not the point.
- **Randomness controls †:** seeds, number of runs, temperature setting and
  why — "deterministic" if no randomness. A single run at nonzero temperature
  is one draw, not a result.

### Checks (APPARATUS)

Numbers from this stage are never reported. Only after it may `frozen` go
to `true`.

- **Resolution check:** ZERO calls, real `evaluate()` on synthetic extremes —
  perfect effect → criterion fires? null effect → stays silent? Both numbers,
  with the run's real draw structure. Its permanent form is the stamped
  `tests/test_<NN>_<name>.py` (two fixtures plus the parser cases from the
  probe); `preflight` runs it, so a later change to `evaluate()` that mutes
  the criterion cannot pass the freeze gate.
- **Render check:** ZERO calls, `--show N` — per gold class ONE rendered
  prompt, read verbatim: stacked negation, fields inserted empty, sentences
  the question form cannot decide?
- **Instrument check:** real pipeline, ~10 calls, `--probe N` — per gold
  class ONE fully rendered prompt+answer pair as a code block, real data.
  Without a model: a reduced estimator on a few labelled items, both
  lanes, into a throwaway file. The full measurement without a run id is
  not an instrument check; it is the registered number, seen early.
- **Yield per stage:** expected vs. obtained per parse step.
- **Parser cases harvested:** the probe's answer forms as REAL cases into
  the parser test.
- **Clarified terms:** what was ambiguous, and what is it called now?
- **Changed — and in which class:** instrument changes (wording, answer form,
  parser, field names) are allowed; hypothesis, criterion, admissibility
  condition are not.
- **Pilot:** N items checked against hand analysis or anchors, before scaling.

### Runs (APPARATUS)

Via `runlog` — cite run_ids instead of retyping numbers. One entry per run.

### Follow-up (APPARATUS)

- **Notes updated:** [[…]] — reconcile on contradiction.
- **Prediction for the follow-up run †:** write the expected number HERE,
  before the follow-up starts — it makes the follow-up a test instead of a
  story told afterwards.

The next step lives in the Summary (one home).

### Notes (APPARATUS)

By-catch: ideas, follow-up experiments — cheap now, expensive later. Promote
the good ones to `notes/` (one idea per file) or bring them to the meeting.

## Training section (conditional)

If you trained or fine-tuned a model (not prompted), add these fields under
Setup. Prompting hides these choices; training makes every one of them yours.
Delete this section if everything was prompted.

- **Split:** sizes, and how they were split — randomly? by document? by
  author? Pass the files to runlog under the standard keys,
  `data={"train": …, "dev": …, "test": …}`.
- **Labels:** how a training label was built from the gold data, and what
  counts as a match. "Exact span match = 1, everything else = 0" is a strong
  decision.
- **Candidates / negatives:** what the model was asked to score at all, and
  the resulting positive:negative ratio.
- **What got dropped:** items that didn't fit the length limit or the
  candidate rules. How many, and are they special?
- **Gold vs. predicted inputs:** multi-stage pipeline: which stage was fed
  gold inputs, which the previous stage's predictions. Report both if you
  can — the gap between them IS the error propagation.

## Lab standard cross-references

| Field              | § |
|--------------------|---|
| Intent ids         | LAB-004 Identifiers make the intent addressable |
| Success criterion  | LAB-003 No run without an intent paragraph |
| Admissibility      | LAB-004 Identifiers make the intent addressable |
| Timebox            | — |
| Split touched      | — |
| Registered branch  | LAB-013 Registered branch when the run can answer two questions |
| Preflight audit    | LAB-015 Preflight audit before freezing |
| Instrument check   | LAB-014 One fully rendered example pair per gold class |
| Resolution check   | LAB-016 Resolution check before freezing |
| Yield per stage    | LAB-023 No silent loss |
| Rival explanations | LAB-044 The check on a confound is code |
| Analysis audit     | LAB-050 Analysis audit before reporting |
| Null condition     | LAB-037 Every anchor carries its target and rationale |
| Prediction         | LAB-045 The forecast comes before the follow-up run |
