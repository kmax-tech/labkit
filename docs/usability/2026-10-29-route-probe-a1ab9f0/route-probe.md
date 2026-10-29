# Route probe on labkit a1ab9f0 — the full completion route by hand (2026-10-29)

*The apply-screen task walked by hand on the host (no Docker), stamped by `usability stage` from labkit a1ab9f0 (0.103.0): register, measure with one planted scientific error, audit, repair, measure again, adopt, deliver, pass the gates, test two holds. Auditor `opus` via claude-cli. Commands and quoted output: `2026-10-29-route-probe-a1ab9f0/log.md`.*

## Result

A hand-run probe on a1ab9f0 took 13.7 minutes and met five points of friction, one of which
(the adoption held against itself) was repaired the same day (42622ff); the state measured
here is the one before that repair. With those interventions the route reached the end: three commits in the probe lab (registration 43ee1dc, repair e89f81a, adoption 1bc9b2b), `report-check` on the area and `--if-reported REPORT.md` all clear, the pre-commit hook green. The adopted run `2026-10-29T15-34-48_315a` lists `pred_results/screen_pred.csv` in `outputs.json` with sha256 `b1cf9ea74ef1a7ed`; the file in the tree has that digest, exactly `person_id, probability, flag`, 300 rows; protocol and report block record `c1_score` 0.7609 = 70/92, C1 met. 13.7 minutes from stage to final commit, three paid calls, 1.64 USD.

The planted error — `SCORE = "auc"` on the probability where the registration says accuracy of the flag — was named by the first analysis audit as a BLOCKER at the right line, with the mechanism ("a float probability against an int gold is almost never correct"), the wrong number (0.826 is an AUC) and the repair route. The CSV was byte-identical before and after the repair.

The audit also found what the plant dragged along: `--calibrate-null --write` had registered `null_band = 0.15` under the AUC scorer, and `band_check` stops checking once a first measurement exists, so the repaired score ran under a band its rule does not give (0.13 under accuracy). I decided it `accepted --effect stands` (the kept null draw lies within both bands), put the rule's band into `metrics.json` as `a2_band_by_rule`, and the decision review upheld it; the limit stands in protocol and report block. The band binding silently to the score at the first measurement is a finding about the skeleton.

## Where the route bent

1. **The stage speaks `high`.** The head says `repeat_cost = "<low | high>"` and TASK.md says declaring it is the task, but the stage's next-step list and `protocol-check --contract` read an unfilled cost as `high` and prescribe preflight, freeze and a detached run.
2. **The adoption holds itself.** With the registered `REPORT.md` already in the tree, `--from-run` refuses (no result block), `--into` refuses (no result declared), the hook refuses the commit; the printed way out cannot be taken. Found by guessing: move the report aside, adopt, move it back, `--into`.
3. **`protocol-fill` is all-or-nothing with a stamped field in the list.** Two refusals, and `--force` on Data / scope silently dropped the generated counts.
4. **No command sets a promise constant**; `margin` was edited by hand in the head.
5. **The stamped test breaks on a score change** (string golds, text class-count keys) after `code-check` said all clear.

## The two holds

An edited probability in the CSV: `report-check` blocks, the first blocker names the file and both digests (recorded `b1cf9ea74ef1a7ed`, found `916e4889ae63fc7d`). The report without its block and run id, the number typed in: the hook refuses with the registered-report BLOCKER and prints the `--into` way out. Both held.

## What a cold agent would most likely get wrong

Take `high` from the printed list and spend the budget on preflight and freeze; write `REPORT.md` before `--from-run`, stall in the circular hold and reach for `--no-verify` or type the number; grep the report for the wrong marker (`labkit:result` against `labkit result:`); and, after a score repair, not notice that the null band still belongs to the old score — the audit does, because it reads the code.
