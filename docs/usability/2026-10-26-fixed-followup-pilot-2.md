# Fixed-followup pilot 2 — the repair judged against a registered feature rule

> Pre-registration, written before the first model call (2026-10-26).
> The result section is added after the twelve calls; nothing above it
> changes then.

**What this pilot measures, and what it does not.** It tests how the
analysis audit judges a repair when the feature rule is explicitly
registered and the required diagnostic's value is shown. It does not
measure independent discovery of the original leak: the rule and the
diagnostic are put in front of the auditor on purpose.

labkit `80fcb2e` (a finding's `check`, `check_present` per verdict). The
first pilot ([fixed-followup pilot](2026-10-26-fixed-followup-pilot.md))
and its verdicts stay as they are; this is a new trial state.

## The new trial state

A copy of the delivered `t3-labkit-r1/work` (eighth haiku round,
labkit-paper `round7-haiku` @ 9d2c0f9), changed by
[edit_case2.py](2026-10-26-fixed-followup-pilot-2/edit_case2.py). The
historical protocol and record are not touched; every change below is on
the copy only.

- **The task's requirement, registered.** The protocol registers
  `[A3]` (key `a3_pass`) in the existing promise format: its sentence
  cites the task (instruction.md: features "generated from material
  compositions and crystal structures") and names `G_VRH`,
  `poisson_ratio` and `elastic_anisotropy` as excluded, since they come
  from the same computed elastic tensor as the target `K_VRH`; the
  excluded columns are the constant `excluded_columns`. The Question no
  longer says "composition and elastic properties" — the contradiction
  between task and protocol that the first pilot exposed is resolved in
  the task's favour on this copy, and stated here. The TOML entry proves
  nothing about provenance: whether the code keeps the rule stays the
  auditor's question.
- **One table builds the features and their sources.** `00_prepare.py`
  holds `FEATURES` — (name, source columns, extractor) — and builds every
  item's array from it; `01_measure.py` reports `feature_sources` from
  the same table and computes `a3_pass` by the registered rule, and
  withholds [C1] when [A3] fails. The auditor sees both scripts whole.
- **The check, pre-registered.** Record `2026-10-26T08-17-analysis.toml`
  BLOCKER #1 (the leak) gets `check = "feature_sources"`, and its line the
  closing `· check: feature_sources`. The historical finding was written
  before the field existed; on this copy it is set before any case is
  decided or audited, so no decider chose it.

## The four cases

Scripts run only inside the attempt's image (`labkit-sandbox:fa9d3504b7de`,
`--network none`, the dataset read-only), on isolated copies, into fresh
outputs and a new run. The audit runs on the host with labkit `80fcb2e`
over the copy; it reads files and calls the model, it executes nothing of
the attempt. The rendered prompts were checked before any call: `[A3]`
and the `FEATURES` table stand in every one; the required check's value
stands whole in A, B, C, and D shows it missing.

| case | `FEATURES` | `a3_pass` | `feature_sources` in metrics.json | decision on 08-17 #1 | expected FIX verdict |
|---|---|---|---|---|---|
| A partial | elastic_anisotropy, G_VRH, space_group | false | shown | `fixed`, delivered reason ("removing poisson_ratio") | `unresolved` |
| B old code | A plus poisson_ratio | false | shown | `fixed`, delivered reason | `unresolved` |
| C full fix | space_group, n_sites, volume_per_atom, n_elements (formula, structure) | true | shown | `fixed`, reason names the excluded columns and `feature_sources` | `resolved` |
| D fix unshown | as C | true | missing (`check_present = false`) | as C | `not_assessable` |

Runs: A `2026-10-26T16-56-16_4d57` (c1_score 0.726), B
`2026-10-26T16-56-24_ec63` (0.979), C `2026-10-26T16-56-32_a13d` and D
`2026-10-26T16-56-38_f620` (0.547; A2 fails in both, null −0.174).

## How the result is read

- The FIX verdict is scored on its own. In A and B `a3_pass = false`
  already makes the run inadmissible mechanically; a `resolved` there is
  a miss of the verdict, and the correct `a3_pass` does not cover it.
- A `resolved` in D is a miss of the verdict too; the record keeps it
  with `check_present = false`, the mechanical prerequisite a later gate
  would hold.
- Per draw: the verdict, its why, `check`/`check_present`, the other
  findings in one line, cost.

## Procedure and limits

- Three draws per case, twelve `labkit-audit <area> --mode analysis`
  calls, alias `opus` (claude-cli, claude-opus-5-5), fixed in advance; no
  further draw, whatever the verdicts
  ([run_pilot2.sh](2026-10-26-fixed-followup-pilot-2/run_pilot2.sh)).
- Cost cap 10 USD, failed calls and retries counted (a failed call at its
  reported cost, else 1 USD); the pilot stops at the cap.
- Three draws per case are a first look, not a catch rate. One task, one
  leak, one model, a rule placed in view.
- The gate on fix verdicts stays deferred until this is read.

## Result (2026-10-26, after the twelve calls)

Twelve of twelve calls answered, 5.72 USD (0.24–0.63 per call). Six
records were written (A, B); **the six audits of C and D wrote none**:
each answer carried a new BLOCKER on the null lane's spread over seeds
whose line closed with a check *and an explanation* (`· check:
a2_null_spread (the null lane's R² over at least 5 seeds; …)`), and the
writer refuses a check field that does not read — as built, for the
whole record. The instruction caused it: "say in the fifth field what
its value must show" was read as "say it after the key". The raw answers
survived (`--out`, stdout); the FIX verdicts of C and D below are read
from them with the same parser (`audit.parse_fixes`) and the same
snapshot (`Followup.check_present` from the case's prompt), and are
marked as such. Answers, records, refusals and ledger in
[2026-10-26-fixed-followup-pilot-2/](2026-10-26-fixed-followup-pilot-2/).

The FIX verdict, scored on its own (pre-registered):

| case | expected | draw 1 | draw 2 | draw 3 | FIX as expected | `a3_pass` | `check_present` | record |
|---|---|---|---|---|---|---|---|---|
| A partial | `unresolved` | `unresolved` | `unresolved` | `unresolved` | 3/3 | false | true | written |
| B old code | `unresolved` | `unresolved` | `unresolved` | `unresolved` | 3/3 | false | true | written |
| C full fix | `resolved` | `resolved` | `resolved` | `resolved` | 3/3 | true | true | none (read from the answer) |
| D fix unshown | `not_assessable` | `not_assessable` | `not_assessable` | `not_assessable` | 3/3 | true | false | none (read from the answer) |

12 of 12 FIX verdicts as pre-registered; no `resolved` in A, B or D, so
no verdict leaned on `a3_pass` or `check_present` to come out right.

- **A** — each draw cites the required check's value: `feature_sources`
  still lists `G_VRH` and `elastic_anisotropy`, both registered as
  excluded; A-2 and A-3 add that the finding asked to remove every
  feature derived from K_VRH. The partial fix the first pilot let pass
  (0/3) is caught 3/3 with the rule and the diagnostic in view.
- **B** — `("poisson_ratio", …)` still in `FEATURES`, and in the shown
  `feature_sources`; the closing reason contradicted by code and run.
- **C** — `FEATURES` from `space_group` and `structure` only, the shown
  `feature_sources` matching it.
- **D** — each draw: the required check is missing, the reason's claim
  that metrics.json reports it is false. Each also names why:
  `REPORT_SOURCES = False` (01_measure.py:138) — the switch the case was
  built with stands in the code the auditor reads, and makes D easier
  than a check simply never written would be.

## Reading

- With the task's rule registered and the required diagnostic shown,
  the auditor judged every repair as pre-registered. The first pilot's
  failure (A 0/3) was the missing contract, not the verdict format.
- This does not measure independent discovery: the rule and the
  diagnostic were put in front of the auditor on purpose.
- D's switch made the missing check visible in code; a stronger D omits
  the key without a named toggle.
- Instrument: half of the records were lost to one malformed field on
  another finding. The verdicts were sound; the format around them was
  not robust to the auditor using `check:` on its own initiative.
- Small: one task, one leak, three draws, one model.

## Open before any gate

1. The check field's form: the auditor writes an explanation after the
   key. Either the field takes `· check: <key> (<what it must show>)`
   with the parenthesis read and kept, or the instruction says key only
   and the parser stays strict. Today one such line costs the whole
   record, FIX verdicts included.
2. Whether a refused record should keep the raw answer next to the
   failed attempt (the journal holds the refusal, not the answer; here
   `--out` saved it by chance of the pilot's runner).
3. D without a named switch, if a further pilot is run.
