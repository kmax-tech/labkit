# Route probe on labkit a1ab9f0 — the log (2026-10-29)

Host run, no Docker. Scratch: `/private/tmp/claude-501/-Users-max-projects-labkit/be6bd47e-0561-4ffb-9175-694381a41bb5/scratchpad/route-probe/` (stage venv, `probe/` lab, `raw.log` with every line). Every command below was run from the probe repo root with `probe/.venv/bin/…` unless marked. Output lines are quoted; `…` cuts.

## Timings

| step | clock | wall | cost |
|---|---|---|---|
| first measurement (planted AUC) | 15:31:22 | 1 s | — |
| first analysis audit | 15:31:43 → 15:32:58 | 75 s | 0.67 USD |
| second measurement (repaired) | 15:34:48 | 1 s | — |
| second analysis audit | 15:35:03 → 15:36:34 | 91 s | 0.70 USD |
| decision review | 15:36:59 → 15:37:10 | 11 s | 0.27 USD |
| adoption (`--from-run`) | 15:37:30 refused, 15:37:50 clean | 1 s each | — |
| whole route, stage to final commit | 15:24:10 → 15:37:51 | 13.7 min | 1.64 USD |

## 0. Stage

```
15:24:10 $ stage-venv/bin/usability stage --task apply-screen probe          (stage-venv: labkit 0.103.0 from git+file://…@a1ab9f0)
Next (repeat_cost = "high": light pilot, heavy report — the instrument is an estimator, no model call):
  1. PROTOCOL-apply-screen.md: fill the pilot part … 7. `preflight …`, then the preflight audit … 8. … only now `frozen = true`. …
staged …/route-probe/probe   task: …/probe/TASK.md   prompt: …/probe.prompt.md
```
BEND 1: the protocol head says `repeat_cost = "<low | high>"` and TASK.md says "declaring it is part of the task", but the stage's next-step list (and `protocol-check --contract`: "repeat_cost = 'high' (an unfilled repeat cost reads so)") speaks the high-tier route: preflight, freeze, detached run. A cold agent reading only that list would go to `high`.

```
15:28:12 $ .venv/bin/labkit-check
pin        requirements.txt pins v0.103.0; requirements.lock pins a1ab9f0… STALE — .venv/bin/pip install -r requirements.txt, then lock
```
Known (the brief says so): the stamped requirements.txt pins a tag that is not pushed. Ignored.

## 1. Prepare and register (planted error in place)

```
15:28:20 $ .venv/bin/python experiments/01-apply-screen/scripts/00_prepare.py --audit
  labelled 92 · labelled gold 0 48 · labelled gold 1 44 · rows read 300 · unlabelled 208
15:28:20 $ .venv/bin/python experiments/01-apply-screen/scripts/00_prepare.py
300 items -> …/data/prepared/screen_persons_v1.jsonl: 92 labelled {'0': 48, '1': 44}, 208 unlabelled
```
Edits: `00_prepare.py` (cohort.csv → id, six features in model.json's order, gold 0|1|null, split); `01_measure.py`: `ITEMS`, `PREDICTOR_FILES = {"primary": data/raw/screening/model.json}`, a `ScreenModel` class (standardise, weighted sum, logistic, flag at threshold), `apply_rows` keeps `probability` and `flag` on every registered and test row, `deliverable_rows` builds the CSV from those rows.
**PLANTED:** `SCORE = "auc"` and `ScreenModel.predict()` returns the probability. The registration (next) says accuracy of the flag.

```
15:29:07 $ … 01_measure.py --show 2        → score auc · predictor_sha {'primary': 'c94491aa…'} · train 92 items · test 208 items
15:29:07 $ … 01_measure.py --calibrate-null
null over 200 permutations of the gold, predictions fixed: min 0.3632  median 0.5014  max 0.7017  permutation expectation 0.5000
null_band by the rule (the 0.99 quantile of |null - expectation| over 200 permutations, seed 0): 0.1444, registered as 0.15
```
GUESS 1: no `protocol-fill` syntax sets a `[[promise]]` constant; `margin` 0.25 → 0.1 was edited by hand in the TOML head (AGENTS.md: the protocol is yours to edit).

```
15:29:50 $ .venv/bin/protocol-fill PROTOCOL… "type=confirmatory" "repeat_cost=low" "C1 sentence=…" … (19 labels)
protocol-fill: line 33 ('Model / tool') is already filled: 'n/a — no model call; …'. Overwrite with --force.        exit=2
15:29:50 $ .venv/bin/protocol-fill PROTOCOL… --data-counts
Data / scope: counts (prepare run 2026-10-29T15-28-20_dcd3): read model.json 38 lines, cohort.csv 301 lines; 300 items prepared — 92 labelled (0 48, 1 44), 208 unlabelled
15:29:50 $ … 01_measure.py --calibrate-null --write
null_band = 0.15 written in PROTOCOL-apply-screen.md; commit the registration, then measure
15:30:14 $ .venv/bin/protocol-fill PROTOCOL… (18 labels, without Model / tool)
protocol-fill: line 32 ('Data / scope') is already filled: 'counts (prepare run …'. Overwrite with --force.        exit=2
```
REFUSAL 1 and 2 (both all-or-nothing): a stamped field and a `--data-counts` field count as filled. Way out: fill the rest without them, then `--force` each; `--force` on Data / scope dropped the counts, `--data-counts` wrote them again.
GUESS 2: the order "prose first, then `--data-counts`" is implied by "as the field's end" in AGENTS.md, not stated.

```
15:30:39 $ .venv/bin/protocol-fill PROTOCOL… (17 labels)          → filled: type, repeat_cost, C1 sentence, A1 sentence, A2 sentence, Terms …, Prior threads
15:30:39 $ .venv/bin/protocol-fill PROTOCOL… --force "Data / scope=…" ; --data-counts                → filled; counts written again
15:30:39 $ .venv/bin/protocol-check PROTOCOL…
…: Runs: the stamped entry is written by `protocol-fill … --from-run <run_id>` after the run
…: 1 line(s) still verbatim template text, e.g.:  - <…>                                              exit=0
15:30:57 $ .venv/bin/code-check experiments/01-apply-screen                 → code-check: all clear.
15:30:57 $ .venv/bin/python -m pytest -q tests/test_01_apply_screen.py
FAILED …::test_class_counts_are_the_scored_items_per_gold                   (1 failed, 9 passed)
```
The stamped test uses string golds; with `auc` the TODO in its docstring says make them numeric — done (`POS, NEG = 1, 0`); then the class-count assertion fails because `scored_class_counts` keys are text — `{str(NEG): 5, str(POS): 7}`. The exact-bar test was rewritten for auc (ties count half: 0.75 exactly).
```
15:31:07 $ pytest → 10 passed
15:31:20 $ git add experiments/01-apply-screen tests/test_01_apply_screen.py && git commit -m "apply-screen: register the protocol …" -- experiments/01-apply-screen tests/test_01_apply_screen.py
43ee1dc   (hook: protocol-check as above, exit 0)
```

## 2. First measurement, finalize, first audit

```
15:31:22 $ .venv/bin/python experiments/01-apply-screen/scripts/01_measure.py
rows: 392 — 92 labelled items in two lanes, 208 test items
  a1_pass True · a1_empty 0 · a2_score 0.49384469696969696 · a2_target 0.5 · a2_pass True
  c1_score 0.8257575757575758 · c1_threshold 0.6 · c1_pass True
run: 2026-10-29T15-31-23_914a
next: finalize … · labkit-audit … --mode analysis, then decide its findings · write the Conclusion and the report fields (…, once frozen and declared) · then protocol-fill … --from-run 2026-10-29T15-31-23_914a
```
The kept number is an AUC (0.826) where accuracy (0.761) was registered; the CSV looks fine (300 rows, person_id, probability, flag). Minor: the next-step line says "once frozen and declared" at `low`, where no freeze exists.
```
15:31:32 $ .venv/bin/finalize experiments/01-apply-screen
  intent-check: 3 id(s) registered, all report in metrics.json. Promise block 6d4883c4d144 is the one the run recorded.
  WARNING: README.md:18: <per registered promise its key, … — a stamped placeholder, fill or delete the line
  WARNING: output apply-screen.jsonl is not yet tracked … WARNING: output screen_pred.csv is not yet tracked …
finalize: 0 blockers, 3 warning(s)
outputs.json: apply-screen.jsonl sha256 ed171b4bfac6f726 (392 lines) · pred_results/screen_pred.csv sha256 b1cf9ea74ef1a7ed (301 lines)
15:31:43 $ .venv/bin/labkit-audit experiments/01-apply-screen --mode analysis
labkit-audit: analysis · PROTOCOL-apply-screen.md · 3 code file(s) in full, 0 indexed · opus · 157 kB
labkit-audit: tokens · prompt 64,802 (649 cached) · output 7,658 · 0.67 USD
stamp: 2026-10-29 · scope sha 9cd8c4be3710 · 2 findings to decide (2 blockers, 0 warnings, 0 notes …)
```
What the audit said about the planted error, verbatim:
> BLOCKER · experiments/01-apply-screen/scripts/01_measure.py:156 · The criterion is computed on the wrong quantity. `SCORE = "auc"` scores the raw probability: the registered and null rows carry `pred` = probability (`apply_rows`, `lane_row("registered", it, p, …)` with `p` from `predict()`). [C1] instead registers "the accuracy of the flag over all labelled persons" against "the permutation expectation plus margin" (PROTOCOL-apply-screen.md:13, Terms:11). The code ranks probabilities by Mann–Whitney AUC, and its bar is AUC's expectation of 1/2. Switching `SCORE` to `"accuracy"` alone would not repair it: `_accuracy` compares `p == g`, so a float probability against an int gold is almost never "correct". · The reported `c1_score = 0.8257575757575758` is an AUC, not the accuracy [C1] names. `c1_threshold = 0.6` is 0.5 + 0.1, not the flags' permutation expectation (Σ flag share × gold share over 48/44 gold) + 0.1. `c1_pass = true` therefore judges a different metric. `a2_score 0.4938` and `a2_target 0.5` are AUC values too. Rows show where the two scores part: output/apply-screen.jsonl:4 (P009, probability 0.692, flag 1, gold 0) and :14 (P033, probability 0.547, flag 1, gold 0) each cost accuracy a full error, while AUC only loses rank pairs. · LAB-003 No run without an intent paragraph (Criterion ≠ code) · An implementation error, so fix the code to the registration: score the registered and null lanes on the flag (the `pred` the score reads is the flag) with `SCORE = accuracy`, so that `permutation_expectation` gives the flags' exact expectation. Withdraw nothing, since no result is declared. Then measure again under the unchanged registration and audit the new run.

The second finding, not planted, a consequence of the plant:
> BLOCKER · experiments/01-apply-screen/PROTOCOL-apply-screen.md:121 · [A2]'s registered `null_band = 0.15` was derived under the AUC scorer. The first measurement's `band_check` ran with `cfg.score = "auc"` on probabilities and passed, so 0.15 is the rule's value for AUC. Once the first measurement exists, `band_check` returns None without checking … A code repair to accuracy-of-flag would therefore hold the null lane to a band that the registered rule … may not give for the registered score. · … Assignment for the caller: run `band_by_rule` with `score = "accuracy"` on the 92 labelled persons' flags, seed 0, q 0.99, k 200, and compare its rounded-up `registered` value with 0.15. If they differ, the registered constant contradicts its own registered rule. · LAB-004 … · If the rule under the registered score gives 0.15, this is resolved by the code repair of the finding above. If it gives another value, the way out is an invalid registration: register anew with `[replaces] protocol = "p-0c357b674e4e460c"`. Do not change null_band in place. · check: a2_band_by_rule (the rule's band under the registered score, equal to the registered null_band)

Plus five READ hints (Summary placeholders, Terms as a `·` chain, Data / scope in one line, the Runs placeholder, the Checks placeholders). Record: `audits/2026-10-29T15-32-analysis.toml`, exit 1.

## 3. The auditor's assignment, the repair, the decisions

```
15:33:18 $ one-off python: band_by_rule(score=accuracy) on the 92 flags, seed 0, q 0.99, k 200
accuracy on flags: 70 / 92 = 0.7609 · permutation expectation 0.5028 · band 0.1276 · registered (rounded up): 0.13
```
So the registered 0.15 is not what the rule gives under the registered score. The auditor's way out for that case is a replacement protocol. GUESS 3 (a judgement): a band two hundredths too wide does not change the question, and a registered constant does not change after the first measurement; I decided it `accepted --effect stands` with the limit named, and made the rule's band a metrics key (`a2_band_by_rule`, computed in `evaluate_rows` from the registered rows) so the discrepancy is visible in the run and the follow-up can judge it.

Repair: `SCORE = "accuracy"`, `predict()` returns the flag, `OUT` renamed to `output/apply-screen-flag.jsonl` (a repaired code writes its own file, AGENTS.md step 4), the exact-bar test back to the accuracy case; the Checks fields filled (not owed at `low`; the hints asked). `code-check: all clear.` · `10 passed`.
```
15:34:47 $ .venv/bin/labkit-audit … --decide 1 fixed "SCORE is accuracy and ScreenModel.predict() returns the flag …" --record …/2026-10-29T15-32-analysis.toml
decided: … finding 1: fixed — … · 1 open
15:34:47 $ .venv/bin/labkit-audit … --decide 2 accepted "The rule under the registered score … gives … 0.13; the registered null_band 0.15 was derived under AUC and is 0.02 wider. … Limit: [A2] is held to 0.15, not 0.13." --effect stands --record …
decided: … finding 2: accepted (stands) — … · 0 open
15:34:47 $ git add … && git commit -m "apply-screen: score the flag, not the probability (… #1 fixed, #2 accepted …)" -- …     → e89f81a
```

## 4. Second measurement, finalize, second audit, review

```
15:34:48 $ .venv/bin/python experiments/01-apply-screen/scripts/01_measure.py
  a1_pass True · a1_empty 0 · a2_score 0.4782608695652174 · a2_target 0.502835538752363 · a2_pass True
  c1_score 0.7608695652173914 · c1_threshold 0.602835538752363 · c1_pass True
run: 2026-10-29T15-34-48_315a
15:34:57 $ .venv/bin/finalize experiments/01-apply-screen        → 0 blockers, 1 warning (apply-screen-flag.jsonl not yet tracked)
metrics.json: "a2_band_by_rule": 0.13 · CSV: 300 rows, 111 flagged, header person_id,probability,flag
15:35:03 $ .venv/bin/labkit-audit experiments/01-apply-screen --mode analysis
labkit-audit: tokens · prompt 66,874 (2,251 cached) · output 9,036 · 0.70 USD
stamp: 2026-10-29 · scope sha 6e4e00838eed · 1 findings to decide (1 blockers …)
FIX · 2026-10-29T15-32-analysis.toml#1 · resolved · repaired: the scored `pred` is now the flag and the score is accuracy, as [C1] registers. … metrics.json `c1_score` 0.7609 equals 70/92, an accuracy. · `a2_target` 0.502835 equals 4256/8464. That is the accuracy permutation expectation for 52 flags of 0 and 40 flags of 1 against gold 48/44. …
FIX · 2026-10-29T15-32-analysis.toml#2 · unresolved · the required check `a2_band_by_rule` = 0.13 (metrics.json) is not equal to the registered `null_band = 0.15` … The fault is present, but in this run it does not move [A2]'s verdict. `a2_score` 0.4783 against `a2_target` 0.5028 is |Δ| = 0.0246, which lies within both 0.13 and 0.15.
  1 · carried from 2026-10-29T15-32-analysis.toml#2 (unresolved): BLOCKER · …                      record: audits/2026-10-29T15-36-analysis.toml, exit 1
15:35:16 $ .venv/bin/protocol-fill PROTOCOL… "Conclusion=Applied unchanged, the supplied screening model's flag agrees with the clinician's referral label on 70 of the 92 labelled persons (accuracy 0.761), well above the permutation expectation of 0.503 plus the registered margin of 0.1. …" "Limits=…" "Next step=…" "Deviations after freeze=n/a — …" "Interpretation / next step=…"     (while the audit ran; the Summary is not bound)
15:36:53 $ .venv/bin/labkit-audit … --decide 1 accepted "The registered null_band 0.15 was calibrated under the first code's score (AUC); under the registered score the rule gives 0.13 … the kept null draw deviates 0.0246 …, within both bands. Limit: [A2] is held to 0.15 where its rule gives 0.13." --effect stands --record …/2026-10-29T15-36-analysis.toml
decided: … finding 1: accepted (stands) · 0 open
15:36:59 $ .venv/bin/labkit-audit experiments/01-apply-screen --review --record 2026-10-29T15-36-analysis.toml
labkit-audit: review · 2026-10-29T15-36-analysis.toml · 1 decision(s) · opus · 71 kB · … 0.27 USD
DECISION #1 · upheld · The reason uses the inlined metrics to address the finding's own scenario. … `a2_pass` holds under 0.13 as well as 0.15. [C1]'s bar of 0.603 does not use `null_band`. …
review state: every decision reviewed is released          record: audits/2026-10-29T15-37-review.toml, exit 0, 11 s
```

## 5. Adoption, report block, commit

REPORT.md was written (prose only) at 15:37 while the review ran. Then:
```
15:37:30 $ .venv/bin/protocol-fill PROTOCOL… --from-run 2026-10-29T15-34-48_315a
filled from run 2026-10-29T15-34-48_315a: Recorded results, [result] run, Runs, Limit (audit 2026-10-29T15-36-analysis #1) — adopting as the result:
  BLOCKER: …PROTOCOL-apply-screen.md registers REPORT.md as its report, and REPORT.md carries neither the result block of run 2026-10-29T15-34-48_315a, its declared result nor the protocol's handover block — … way out: `protocol-fill … --into REPORT.md` writes the result block; …
protocol-fill: not adopted — report-check refuses the written result (above); PROTOCOL-apply-screen.md is as it was. …                  exit=1
15:37:31 $ .venv/bin/protocol-fill PROTOCOL… --into REPORT.md
protocol-fill: no [result] run declared — `--from-run <run_id>` declares the run and writes the result; a report shows a declared result only       exit=2
15:37:31 $ git commit … → the hook: the same BLOCKER (its head declares no result; its registered report is delivered) · pre-commit: report-check reports blockers         exit=1
```
BEND 2 (circular hold): with the registered REPORT.md already in the tree, `--from-run` refuses because the report lacks the block, and `--into` refuses because no result is declared; the printed way out (`--into`) cannot be taken. GUESS 4: move REPORT.md aside, adopt, move it back, `--into`.
```
15:37:50 $ mv REPORT.md ../REPORT.md.aside; protocol-fill … --from-run 2026-10-29T15-34-48_315a      → report-check: all clear.   exit=0, 1 s
15:37:51 $ mv ../REPORT.md.aside REPORT.md; protocol-fill … --into REPORT.md                            → REPORT.md: the result block for run 2026-10-29T15-34-48_315a written
15:37:51 $ git add experiments/01-apply-screen tests/test_01_apply_screen.py pred_results REPORT.md && git commit -m "apply-screen: adopt run 2026-10-29T15-34-48_315a …" -- …
  PROTOCOL-apply-screen.md: read from the index; the head declares 2026-10-29T15-34-48_315a; the answering run is 2026-10-29T15-34-48_315a
  PROTOCOL-apply-screen.md: repeat_cost = "low" — no freeze and no preflight audit owed … · finalized, audited, checked
report-check: all clear.
═══ report-check REPORT.md (a report citing runs) ═══
  WARNING: REPORT.md: no assigned source found for the numbers on 6 line(s) … (2.1, 0.5, 1.4, 2.1, 0.15, 0.13 — version numbers, the threshold, the two bands in the prose)
report-check: 0 blockers, 1 warning(s)                                                    → 1bc9b2b
```

## 6. The checks at the end

```
15:38:07 $ .venv/bin/report-check experiments/01-apply-screen        → PROTOCOL-apply-screen.md: finalized, audited, checked · report-check: all clear.   exit=0
15:38:08 $ .venv/bin/report-check --if-reported REPORT.md            → all clear for the protocol; REPORT.md: 0 blockers, 1 warning (the unsourced numbers)   exit=0
outputs.json (run 2026-10-29T15-34-48_315a): output/apply-screen-flag.jsonl sha256 911d0db67c3d889a 392 lines · pred_results/screen_pred.csv sha256 b1cf9ea74ef1a7ed 301 lines
shasum -a 256 pred_results/screen_pred.csv → b1cf9ea74ef1a7ed… · header person_id,probability,flag · 300 data rows · 0 rows with other than 3 fields
PROTOCOL line 21: Recorded results: C1 met; A1 met; A2 met · recorded: n_items = 92, …, a2_band_by_rule = 0.13, c1_score = 0.7608695652173914, c1_threshold = 0.602835538752363 (run 2026-10-29T15-34-48_315a); subject to 1 recorded limitation
PROTOCOL line 22: Limit (audit 2026-10-29T15-36-analysis #1): the verdicts stand, read within this limit — The registered null_band 0.15 was calibrated under …
REPORT.md 39-42: <!-- labkit result: experiments/01-apply-screen/PROTOCOL-apply-screen.md run 2026-10-29T15-34-48_315a (protocol-fill --into; edit the protocol, not this block) --> C1 met; A1 met; A2 met · recorded: … <!-- /labkit result -->
```
Note: the CSV's sha256 is the same for the AUC run and the flag run — the planted error never touched the file, only the kept number.

## 7. The two holds

```
15:38:25 $ sed: P001's probability 0.05786368003488371 → …372 in pred_results/screen_pred.csv; .venv/bin/report-check experiments/01-apply-screen
  BLOCKER: finalize: …/pred_results/screen_pred.csv: not the file run 2026-10-29T15-34-48_315a recorded — its sha256 916e4889ae63fc7d is not the recorded b1cf9ea74ef1a7ed — way out: measure anew and audit that run
  BLOCKER: analysis audit: no analysis audit saw the area as it is now (… shown 0272d3d59593; audited: … shown 00c25a6e29b9 …) …
  BLOCKER: result section: the Recorded results line differs from its rendering … · BLOCKER: … "Limit (audit …#1)" names a limit no covering record decides … · BLOCKER: audit …15-32#1: followed up in …15-36, which no longer covers this state … · BLOCKER: audit …15-36#1: decided `accepted`, never followed up …
report-check: 6 blocker(s), 0 warning(s)
git checkout -- pred_results/screen_pred.csv → restored
15:38:41 $ REPORT.md: the block (lines 39-42) replaced by "The accuracy of the flag over the 92 labelled persons is 0.7609 (70 of 92); C1 met." — run ids left: 0; git add REPORT.md && git commit -m "test: report without its block" -- REPORT.md
  BLOCKER: …PROTOCOL-apply-screen.md registers REPORT.md as its report, and REPORT.md carries neither the result block of run 2026-10-29T15-34-48_315a, its declared result nor the protocol's handover block — a registered report owes the result or an explicit end without one; a number with its run id removed, or a run id typed in, releases nothing — way out: `protocol-fill … --into REPORT.md` writes the result block; …
pre-commit: report-check reports blockers for a written-back number (see above).           commit refused; git checkout HEAD -- REPORT.md → HEAD stays 1bc9b2b, tree clean
```
(The first attempt at hold 2 edited nothing: I looked for the marker `labkit:result`, the block says `labkit result:`. A cold agent grepping for the block would trip on the same.)

The first hold's one true blocker names the file and both digests; the other five are its consequences (the edited file changes what the audit "was shown", so the audit no longer covers the state and the rendered lines no longer match) — noisy but all point back to one event.
