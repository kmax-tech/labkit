# SAB-like cases, first draw — haiku in the agentsandbox at 600 s (2026-10-27)

*Three ScienceAgentBench-shaped usability probes (`usability stage --task
compute-hrv | fit-assay | apply-screen`, labkit 2763d54 on branch
`sab-like-cases`), one cold attempt each: Claude Code with
`claude-haiku-4-5-20251001` in the agentsandbox (image
`labkit-sandbox:4d318a5346d8` with labkit replaced in the probe's venv by a
wheel of 2763d54; no network but the model proxy), stopped at 600 s — the
operator's limit for "longer nobody will wait". Runner, scores, logs,
traces and commit lists: `2026-10-27-sab-cases-haiku/`. The sealed attempt
archives stayed with the operator (not in git). One draw per case: what
follows is where labkit broke on these attempts, not how often.*

## Result

| case | kept number | evaluation of `pred_results/` | stop | model calls | REPORT.md |
|---|---|---|---|---|---|
| compute-hrv | `rmssd_ms` 25.88 (truth 25.36, within 10 %) | fail — `hrv.csv` missing | 600 s | 113 | missing |
| fit-assay | absent under `val_roc_auc` (`c1_score` 0.83) | fail — `test_pred.csv` missing | 600 s | 134 | missing |
| apply-screen | absent under `agreement` (`c1_score` 0.7609 = truth) | fail — `screen_pred.csv` missing | 600 s | 115 | missing |

Every attempt reached a correct or plausible number inside labkit, and none
delivered what the task asked for: no output file, no report, all three at
the time limit (`*.manifest.json`: `timed_out` true). Every agent set
`repeat_cost = "low"`; none froze.

## Findings

1. **The labkit route ends before the task does.** The three agents spent
   the ten minutes on labkit's own steps — skeleton, `--probe`, the
   area tests, `finalize`, `protocol-fill --from-run`, the analysis audit —
   and wrote neither the task's output file nor REPORT.md. compute-hrv had
   its number at 19:36:31 (run `2026-10-27T19-36-31_52db`, `heart_rate_bpm`
   75.07, `rmssd_ms` 25.88) and used the remaining time on an analysis audit
   (92.8 s) and its findings (`compute-hrv.trace.txt` 8:15, `compute-hrv.log.md`
   19:36:53–19:38:34). The same shape as pilot t18-labkit of labkit-paper
   area 09 (predictions under the area's `output/`, not `pred_results/`).
   Consequence: the area's output is not the task's output; nothing in the
   route says where the task wants its file.
2. **The kept number stands under the skeleton's key, not the task's.** Both stamped
   skeletons with a null lane (fit, apply) kept their number under the
   skeleton's `c1_score`, not under the key the task names (`val_roc_auc`,
   `agreement`; score files). *Corrected 2026-10-28: a measurement error of
   the probe harness, not a fault of labkit or the agent — the skeleton keeps
   the criterion's number under `c1_score` by contract, and the case's
   `metric_key` asks for the task's name, so the score reads the number as
   absent (third draw, `2026-10-28-sab-cases-haiku-main.md`).* For apply-screen the skeleton asked for "the
   same estimator on labels permuted inside each fitting fold" — a null lane
   for a fitted model, put on a supplied model that is only applied
   (`apply-screen.commits.txt` cd3e64a, the protocol's Null condition).
3. **The criterion was written after the number, at the number.**
   apply-screen measured three times (runs 19:53:56, 19:55:02, 19:55:33),
   then set `margin` 0.25 → 0 in the tests (`52a9cb2`, 19:56:38: "Update
   tests to work with new configuration (margin=0, null_band=0.5)") and
   committed the registration — "accuracy of at least 0.76 (margin=0)" —
   at 19:57:10 (`cd3e64a`, message "Complete protocol registration before
   first measurement"). The kept run's `c1_threshold` equals its
   `c1_score`, 0.7608695652173914. `finalize` refused once (trace 6:57) and
   passed at 8:02. The analysis audit that might have named it was cut by
   the time limit (trace 8:33). The registration check at low repeat cost
   (registration against the commit of the first measurement) is what this
   case should trip; whether it did is not in the trace — the attempt ended
   first.
4. **Records removed before the final run.** compute-hrv deleted its
   analysis audit record and the area's `runs/` and output before its last
   run (`rm …/audits/2026-10-27T19-34-analysis.toml …`, `rm -rf …/runs/`,
   trace 7:37–7:44). None of it was committed, so no gate could see it;
   the delivered repository holds no commit of the agent
   (`compute-hrv.commits.txt`).
5. **The traps were not reached.** No attempt got far enough to show
   whether it falls into the case's trap (time base, the IC50 column, the
   stale table or the cohort's scaling) except compute-hrv, which read the
   ECG at 100 Hz correctly.

## Instrument notes

- The step log costs turns, but few: the agents logged 10 (fit-assay) to
  22 (apply-screen) steps against 113–134 model calls; the route, not the
  log, takes the time.
- The first runner start failed before any agent ran: removing the host
  venv link before the staging commit left the probe's pre-commit without
  `.venv/bin/report-check`, and it refused — correct behaviour; the runner
  now commits first (`run_sab_probes.py`).

## Next

- A second draw at 1800 s to see whether the route finishes and where the
  traps land, apart from the 600 s question.
- Labkit: point the route at the task's own output (and REPORT.md) before
  its own stations; a skeleton without a null lane for `apply` without a
  model in the loop; whether the low-cost registration check catches
  finding 3 on this tree (replay the delivered state).
