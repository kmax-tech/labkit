# Writing probe for a `kind` head field — count, fit, apply on three real cases

*Decision gate before any code (decided 2026-10-22): Option A — a head
field that says what the kept number asserts — is built only if the three
real cases of labkit-paper area 09 can be registered under it without a
special rule. This note is the probe: the schema under test, four
registrations written by hand (one count, two fits, one apply), what each
forced that today's labkit does not, the ambiguities met, the consequences
for existing areas, and the schema recommendation. Options B and C are
recorded as rejected. Nothing here is implemented.*

## The schema under test

`kind` names the **activity the kept number reports on**, not the model
technology, and not the whole script:

| `kind` | the number says | has a bar | owes before the run, beyond the question |
|---|---|---|---|
| `count` | what is there, measured deterministically — no prediction is judged | no | data/scope, exclusions, unit |
| `fit` | how well a model **trained or adjusted in this experiment** predicts | yes | metric (Unit), success criterion, reference (null condition / anchors, computed in the same run), admissibility, the evaluation split named |
| `apply` | how well a model **used unchanged** predicts or judges against gold | yes | the same as `fit`, plus the data profile and the prompt where a prompt exists |

Metric, criterion and reference are three things and the template already
has three fields for them: `Unit` (what one measured thing is), `Success /
failure criterion` (`[C1]`, the value that supports the hypothesis), `Null
condition / anchors` (`[A2]`, the reference with its expected value). The
probe does not add fields; it asks which of the existing ones each kind
owes.

## The four registrations

Written as the protocol's registration fields and promise tables, from
the data as it is (the attempts' copies: `dkpes_train.csv` 44 rows,
`dkpes_test.csv` 12 rows with every label −999; `dili/train.csv` 923 rows
in four sorted blocks of 174/260/227/262, `test.csv` 55 unlabeled
molecules; the judge probe's `claims.jsonl` 12 items, 6 and 6).

### 1 · `count` — documents per case (the usability count task)

```
kind = "count"   cost = "seconds"
Question / hypothesis: What is the mean number of input documents per case over data/raw/cases.jsonl?
Data / scope:          data/raw/cases.jsonl (12 cases); documents under data/raw/inputs/<case_id>/
Exclusions / filters:  hidden files and nested directories are not counted; no case is dropped
Unit:                  one document = one visible regular file directly in a case's directory
```

No criterion, no reference, no promise table: there is no trivial result
a count could pass with — a wrong count is wrong, not optimistic. This is
exactly today's seconds cut for an area without `[model]`. Nothing new.

### 2 · `fit` — DILI random forest (t18)

```
kind = "fit"   cost = "seconds"
Question / hypothesis: Does a random forest on Morgan fingerprints predict DILI concern better than the majority class, in each of the three configurations MCNC, MCLCNC, all?
Model / tool:          sklearn RandomForestClassifier, 144-point grid, 5-fold CV inside the grid
Unit:                  accuracy on the held-out folds of an OUTER 5-fold CV per configuration (nested: the grid selects inside, the outer fold scores)
Success / failure criterion: [C1] outer-CV accuracy >= majority rate + 0.10 in every configuration
Null condition / anchors:    [A2] the majority-class rate per configuration, computed in the run from the configuration's own labels (expected 0.57 / 0.66 / 0.53 from the block sizes)
Admissibility condition:     [A1] every configuration featurised without a dropped molecule; [A3] the four label blocks of train.csv are selected by vDILIConcern value, and their sizes are recorded
Data / scope:          benchmark/datasets/dili/train.csv, 923 molecules; test.csv (55, unlabeled) is scored, not judged
Exclusions / filters:  none
[[promise]] C1 c1_pass · A1 a1_pass · A2 a2_pass (constants: margin = 0.10)
```

What the kind forced, against the attempt as delivered: a metric that is
not the grid's own best score (the winner's-curse BLOCKER becomes a
registration question, answered before the run), a reference computed in
the run (the hand-written "~59%" becomes `a2_*` keys), and an admissibility
that names the block selection — the off-by-one the assessment found is a
failed [A3], not a sentence in a Limit line. The 55 test predictions are
output, not the number: see ambiguity 1.

### 3 · `fit` — DKPES random forest (t5)

```
kind = "fit"   cost = "seconds"
Question / hypothesis: Does a random forest on the 24 chemical features separate above-median from below-median signal inhibition better than chance?
Model / tool:          sklearn RandomForestClassifier, 100 trees, labels = inhibition >= training median (0.284)
Unit:                  balanced accuracy on leave-one-out over the 44 training molecules (no test labels exist)
Success / failure criterion: [C1] LOO balanced accuracy >= 0.5 + 0.15
Null condition / anchors:    [A2] a constant classifier at 0.5 (22/22 split, recorded in the run); [A4] the forest on permuted labels, 20 permutations, 95th percentile recorded
Admissibility condition:     [A1] all 44 rows featurised; [A3] the median cut written into the run config and reported
Data / scope:          dkpes_train.csv, 44 molecules (the protocol of t5 said 28); dkpes_test.csv, 12 molecules with no labels — predicted, not judged
[[promise]] C1 · A1 · A2 · A3 · A4 (constants: margin = 0.15, permutations = 20)
```

What the kind forced: the Youden threshold on in-sample probabilities
cannot be the kept number, because `fit` owes an evaluation split and a
reference; the unregistered median cut becomes `[A3]`; the "28 training
samples" cannot stand once the run records 44 as the denominator of
`[A1]`. Every one of t5's nine findings is a field here.

### 4 · `apply` — causal-claims judge (the usability judge task)

```
kind = "apply"   cost = "seconds"   [model] alias = "haiku"
Question / hypothesis: Does the model behind alias haiku recognise whether a sentence makes a causal claim?
Model / tool:          haiku via labkit.run.llm, one call per item and lane
Unit:                  accuracy against gold over the 12 items, registered lane
Success / failure criterion: [C1] registered accuracy >= null accuracy + 0.25
Null condition / anchors:    [A2] the English-question placebo lane, expected 6/12
Admissibility condition:     [A1] at most 2 unreadable answers
Data profile:          6 and 6, minimal pairs, mean words 10.5 vs 11.3; every causal item carries a connective
Prompt:                verbatim, both lanes
```

This is the judge probe's registration as the agents write it today
(judge-2 on 86e38bc, word for word in its fields). `apply` changes
nothing for it; it names what was already owed through `[model]`.

## Ambiguities met, and how the schema answers them

1. **Inference without evaluation.** Both forests also predict unlabeled
   test sets (55 and 12 molecules). That is not a number about predictive
   quality; it is output. The schema answers: `kind` qualifies the **kept
   number** (`[result] run`, Recorded results). A run whose only product is
   predictions declares no result — it is a preparation or an exploration,
   as today — and its predictions are an output file, held by provenance,
   not by a criterion. No fourth kind. If a later area judges those
   predictions against gold, that area is `apply`.
2. **Fit then apply in one area.** The DILI script fits and predicts in one
   run. The kept number is the fit's; the predictions are its output. One
   area, one kind, decided by what is reported. An area that wants to
   report both a training score and a held-out score reports two keys of
   one `fit`.
3. **Reference is not always a constant predictor.** `fit` 3 registers two
   references (constant and permuted labels), 2 one. The schema requires
   *a* reference computed in the same run with its expected value
   (LAB-034 Null condition in the same run, LAB-037 Every anchor carries
   its target and rationale); which one is the author's registration,
   audited for fit to the claim. Nothing in the kind decides it.
4. **`fit` and the evaluation split.** The attempts' faults were in-sample
   fit (DKPES), selection-optimistic CV (DILI). The kind cannot check the
   split mechanically; it can make `Unit` owe the sentence "scored on
   …", which the analysis audit then reads against the code. The audit
   found both faults already — what was missing was a field that made
   the author write the split down before the number existed.
5. **Fine-tuning an LLM is `fit`, judging with it is `apply`.** The
   `[model]` table (alias, arms, prompt) says that a model answers through
   `models.toml`; `kind` says what the number asserts. They are
   orthogonal: `fit` with `[model]` is a fine-tune, `apply` without
   `[model]` is a trained classifier applied to labeled data outside
   labkit's model layer. Today the two are one switch.
6. **Does `count` stay exempt?** Yes, and now by its definition rather than
   by the absence of an alias: a number that judges no prediction has no
   bar to clear. A count that secretly predicts (a "count" of correct
   classifications) is a mis-declared `apply`, which the audit can name as
   such — a word to point at, which "no `[model]`" never was.

Nothing above needed a special rule. The gate's condition holds.

## Consequences for what exists

- Every stamped area gets a `kind`: the count skeleton `count`, the model
  skeleton `apply`, the estimator skeleton `fit`. `labkit-init exp --kind
  count|fit|apply` replaces the implicit choice through `--model`; `--model
  ALIAS` keeps stamping the `[model]` table and no longer decides the
  skeleton or the registration.
- `standard_contract.registration_fields(kind, model)`: count → question;
  fit and apply → criterion, admissibility, null condition / anchors, unit
  as a scoring sentence; apply with `[model]` → data profile and prompt.
  `skeleton(cost, kind)`: the estimator skeleton at `seconds` too.
- The head: `kind` a required `[protocol]` key with a stamped placeholder
  like `cost`; a placeholder refuses a full run (`start_check`); the
  standard's exemption sentence names `kind = "count"` instead of "a plain
  count whose prose names no id".
- The analysis audit's instructions get one line per kind (the sketch
  branch's `KIND_NOTES`): what the instrument check looks like for it.
- Existing protocols: a Breaking entry; `protocol-fill kind=…` sets it;
  labkit-paper's pinned areas stay as they are until the pin moves.
- Not changed: `cost` and its lanes; the promise block; the gates after the
  run.

## Rejected alternatives

- **B — drop the count exemption, every seconds area owes criterion and
  admissibility.** Simpler, but a document count would owe a criterion it
  cannot have, and authors would write "n/a" into it — the waiver by
  another name, which 0.99.0 removed for the audit line.
- **C — warn when an area without `[model]` imports sklearn or torch.**
  Cheap, catches the two attempts, decides nothing: a NumPy regression
  passes, a trained model applied to gold passes, and the obligation
  hangs on a library name instead of on what is claimed.

## Recommendation

Option A as laid out: `kind ∈ {count, fit, apply}` meaning what the kept
number asserts; obligations per the table; `count` exempt by definition;
inference without a reported number declares no result and needs no kind.
Build small on `main`, Breaking under Unreleased; the sketch branch
(`origin/claude/zealous-davinci-3hbhvk`, 32 commits, flat layout) is the
naming's precedent, not a merge. First measurement after the build: the
count and judge rounds as today, plus one cold `fit` probe on the DILI
data — does an agent register criterion and reference before the run,
and does the attempt's own delivered state fail [A3]?
