# SAB-like cases, third draw — haiku at 1800 s on labkit main fddb01b (2026-10-28)

*The three SAB-like probes once more, on labkit main fddb01b (2026-10-27
23:23) with only the probe harness added (the cases and the worktree pin
fix, branch `sab-cases-on-main`); the fixes of branch `sab-like-cases`
(the null-lane guard in the skeleton, the deliverable sentence in
AGENTS.md) are not in it. Same image, model, runner and limit as the
second draw, so a difference to that draw belongs to labkit (and to one
draw per case). Records: `2026-10-28-sab-cases-haiku-main/`. The first two
draws: [2026-10-27-sab-cases-haiku.md](2026-10-27-sab-cases-haiku.md),
[2026-10-27-sab-cases-haiku-1800.md](2026-10-27-sab-cases-haiku-1800.md)
(run on branch `sab-like-cases`).*

## Result

| case | agent work time | evaluation of `pred_results/` | REPORT.md | report-check on the delivered state |
|---|---|---|---|---|
| compute-hrv | 1171 s | pass — heart rate exact, RMSSD 25.40 ms (truth 25.36) | yes | 9 blockers |
| fit-assay | 1238 s | pass — test ROC-AUC 0.841 (bar 0.75) | yes | 2 blockers |
| apply-screen | 1058 s | pass — model 2.1 exactly | yes | 0 blockers, 1 warning |

Work time is Claude Code's own `duration_ms`; the runner's monotonic clock
agrees (1174, 1241, 1066 s). Docker's clock says 2362 s for fit-assay and
2204 s for apply-screen: the host slept — the lid closed at 23:51:34
(`host-sleep-pmset.txt`), inside apply-screen, whose commit at trace 27:50
spans 503 s. fit-assay's two pauses of about 520 s (trace 3:51–12:23,
12:50–21:42) fall before that and have no sleep entry; they stay
unexplained.

## The three draws side by side

| | draw 1 | draw 2 | draw 3 |
|---|---|---|---|
| labkit | 2763d54 (d0e02f7 + cases) | 41d31c9 (+ guard, deliverable sentence) | fddb01b main + cases |
| limit | 600 s | 1800 s | 1800 s |
| task output and REPORT.md | 0 of 3 | 3 of 3 | 3 of 3 |
| hidden evaluation passed | 0 of 3 | 2 of 3 | 3 of 3 |
| registration after the first measurement (report-check) | apply-screen (others not replayed) | 3 of 3 | 0 of 3 |
| apply-screen's null lane | equal to the registered lane, band widened to 0.5 | equal again, guard deleted, band 0.3 | moves: 0.391 against 0.761, band 0.1 kept |
| kept number under the task's key (fit, apply) | no | no | no |

## Findings

1. **Main's fixes hold on these attempts.** The applied instrument's own
   null (2847c1e) gave apply-screen a null lane that moves (`a2_score`
   0.391, `c1_score` 0.761); the agent kept `null_band` 0.1 and `margin`
   0.25, so [A2] failed — 0.391 lies 0.11 from chance — and [C1] has no
   verdict: an honest outcome where both earlier draws widened the band.
   The first measurement at low needed a committed registration
   (5760496): report-check names no late registration in any of the
   three, where draw 2 had three.
2. **The deliverable came without the AGENTS.md sentence.** Main does not
   carry the sentence of 41d31c9, and all three still wrote the task's
   output and a report. With draw 1 at 600 s and draws 2 and 3 at 1800 s,
   time — not the sentence — is the likelier cause of draw 1's missing
   outputs; the sentence is not shown to be needed.
3. **The fixed band can fail by chance.** [A2] failed in apply-screen at a
   distance of 0.11 with 92 labelled persons, where the permutation spread
   is about 0.05; the stamped `null_band` 0.1 was kept, not derived from
   the null's spread as the skeleton asks. A cheap derivation (the null
   lane over a few seeds) would have told chance from fault.
4. **What still blocks.** compute-hrv refined its peaks after its analysis
   audit, and report-check holds the declared result run and two audit
   BLOCKERs on the changed code (`compute-hrv.report-check.txt`);
   fit-assay changed its promises after the run (intent-check, recheck).
   Both are labkit doing its job on a state the agent left unfinished.
5. **Still above ten minutes.** 1058–1238 s of agent work per case, against
   724–1156 s in draw 2.

## Next

- ~~The probe harness: accept the skeleton's key~~ — done (b3737c6): fit
  and apply read `c1_score`; rescored, this draw's fit-assay keeps 0.8675
  (within [0, 1]) and apply-screen 0.76087 (equals the truth).
- The null band: whether the estimator skeleton should derive `null_band`
  from the null lane's spread instead of stamping 0.1.
- More than one draw per case before any rate is read from these.
