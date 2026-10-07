# Protocol field guide

Decoder for `experiment-protocol.md.template` — explanations, examples,
rationale for each field. The template is the checklist you fill; this
document is the reference you read. `protocol-check --guide` prints the
path to this file.

## How to fill the protocol (seven rules)

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
2. **One field, one line.** A slot takes a sentence, not a paragraph. If a
   justification needs more, it is a finding: write it in `notes/` (one idea
   per file) and leave the [[wikilink]] here. A protocol is a registration —
   what you fixed, ran and got — not a lab journal of how you got there.
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
   label and a bare `n/a — <why>` count as unfilled; `n/a — <the reason>`
   counts as filled.

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

### The head (the ```toml block)

The fields a machine reads are data, not prose: the `[protocol]` table of
the protocol's one ```toml block. `protocol-check` reads them with a TOML
parser — exact keys, typed values; a typo is an error that names the field.
The same block may hold the `[[promise]]` tables (labkit
`docs/promise-block.md`).

- **standard** — `"0.18"`; stamped, never edited.
- **id** — `p-` plus 16 hex digits, stamped by `lib exp`, never typed: the
  run binds to it, so renaming or moving the file keeps the binding.
- **type** — `"exploratory"` generates hypotheses, iterate freely, but
  nothing from it may be reported as a test. `"confirmatory"` tests a
  hypothesis fixed BEFORE the run, on data that influenced no choice.
- **cost** — see below.
- **frozen** — `true` means hypothesis, prompts/rules, metrics, baselines
  and decision rule were all fixed beforehand; only `true` plus `test` gives
  you a held-out number. Goes from `false` to `true` only after the
  instrument check; per (re-)freeze ONE sentence stays in the prose — the
  reasoning goes into the commit message.
- **preflight_audit** — date · scope sha · N findings (blockers fixed /
  accepted with reason / dismissed with reason): the code-vs-intent audit
  after the instrument check and before freezing. Empty until then.

**cost** — the price of a *repeat*, not whether a model is involved. A
deterministic count, or a handful of model calls that finish in a minute
for cents, is `seconds`: rerunnable at will, so no agent audit per run;
`finalize` checks provenance, the independent audit comes when the number
is promoted into a note or paper or steers a decision. `minutes` is a model
pass you would not casually redo; `hours` is expensive or irreversible —
both keep the preflight audit before freezing and the analysis audit after.
Two cold agents declared `minutes` for sixteen calls and paid fifteen
minutes of audit waiting for a 64-second run (2026-10-05).


### Summary (write last, HEAD)

Write this LAST. Three lines — question, result, status — derived from the
detail below and containing no fact that isn't already there: a summary
carrying its own numbers becomes a second truth and drifts. Whoever reads
this has read nothing else yet, so rule 1 matters most here: no "see below",
no question numbers.

- **Question †:** the same sentence as in the Intent.
- **Did †:** what was done, one sentence — for a reader with no context.
- **Result †:** number(s) + run_id — no number that is absent below.
- **Status †:** on track | blocked by _what_ | needs a decision on _what_.

### Intent (before the run, HEAD)

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
  Using intent ids: one [C1], [C2] … per conjunct, [B1] per branch point.
- **Admissibility condition:** what must hold in the same run before any
  verdict is issued, fixed beforehand — e.g. "at most 10% unparsed answers",
  "the model is above chance on the hand-checked sanity examples", "the
  shuffled control shows no effect". If one fails, there is no C verdict,
  only the finding that the instrument failed — a bad outcome becomes a
  finding instead of weeks of tweaking. It complements the Timebox: the
  Timebox stops you on time, an admissibility condition on results.
  Result-based, not time-based — a deadline belongs in Timebox. Intent id:
  [A1] per condition.
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
  licenses, [B1] per branch point. "n/a" if there is only one outcome.
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

- **Answer to the question:** number(s) + run_id, produced by
  `analysis/<note>.py --check`, never retyped; long form → [[note]].
- **Raw output:** one real prompt+answer pair per finding.
- **Interpretation / next step:** one sentence; keep instrument findings
  apart from findings about the subject.
- **Outcome †:** expected or surprising — failures belong here.
- **Rival check †:** which rivals are ruled out, which still stand?
- **Caps/drops †:** what was omitted or limited.
- **Analysis audit †:** date · scope sha · N findings — the audit of the
  EVALUATION against the frozen criterion, before the number leaves.

### Context (APPARATUS)

- **Problem in one sentence:** no technical terms — what is being found out?
- **Terms of this protocol:** every label with a half-sentence or a pointer
  to the defining note; "n/a — standard vocabulary" if nothing is ambiguous.
- **Prior threads:** 2–3 [[wikilinks]], each with half a sentence on why
  they lead here.

### Setup (APPARATUS)

- **Data / scope:** source, N, producer script; pilot subset first. Look at
  the prepared file before running — otherwise a format bug and a model
  failure look identical. Once per dataset, at prepare time: count surface
  markers per gold class (hedges, modal words, length, boilerplate). A marker
  that appears in one class and never in the other is a free rule — the model
  can read the label off it without doing the task.
- **Model / tool:** alias from `models.toml` — never hardcode endpoint/ID.
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
- **Gate labels (expected) †:** which labels the gate accepts — the declared
  set for the mechanical check against code-extracted labels.
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
  comes from the null condition of THIS run.
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
- **Next step.**

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

## Arbeitsstandard cross-references

| Field              | § |
|--------------------|---|
| Intent ids         | AS-004 Kennungen machen den Intent adressierbar |
| Success criterion  | AS-003 Kein Lauf ohne Intent-Absatz |
| Admissibility      | AS-004 Kennungen machen den Intent adressierbar |
| Timebox            | — |
| Split touched      | — |
| Registered branch  | AS-013 Registrierte Weiche |
| Preflight audit    | AS-015 Preflight-Audit vor dem Einfrieren |
| Instrument check   | AS-014 Je Gold-Klasse ein voll gerendertes Beispiel-Paar |
| Resolution check   | AS-016 Auflösungsprobe vor dem Einfrieren |
| Yield per stage    | AS-023 Kein stiller Verlust |
| Rival explanations | AS-044 Der Prüfblick auf einen Konfund ist Code |
| Analysis audit     | AS-050 Auswertungs-Audit vor dem Berichten |
| Null condition     | AS-037 Jeder Anker trägt sein Soll mit Herleitung |
| Prediction         | AS-045 Die Prognose steht vor dem Folgelauf |
