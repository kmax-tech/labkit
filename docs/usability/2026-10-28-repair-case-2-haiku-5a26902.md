# Repair case, second attempt — haiku at 1800 s on labkit main 5a26902 (2026-10-28)

*The acceptance of the two repairs after the first repair case
([note](2026-10-28-repair-case-haiku-4054343.md)): a repair measured
again never counts the faulty run's rows (`0796243`), and a finding's
required check is a work order where it is decided (`5a26902`). The same
start state, now built by a script (`build_repair_case.txt`): apply-screen
registered and committed, `null_band` calibrated on the correct model,
one planted fault (`sd**2` for `sd`), the first measurement in the
container before the agent starts; host steps in UTC, so runs sort with
the container's. Haiku 4.5, cold, no explanation beyond TASK.md and
AGENTS.md. Records: `2026-10-28-repair-case-2-haiku-5a26902/`.*

## Result

The second repair attempt reaches the correctly bound, adopted number.
The guard against old measurement rows holds. The acceptance of the
required-check work order and whether C1/A1/A2 can be judged stay open:
a correct number and a clean report-check are not yet a confirmed claim.
651 s against the first attempt's 1242 s is one draw each — no evidence
of speed.

| step | what |
|---|---|
| audit `15-27` | BLOCKER: the `sd**2` fault against the registered standardisation |
| repair `88cb55b` | the code corrected; the registration untouched |
| measure again | refused: `runlog: WARNING — apply-screen.jsonl holds the rows of the completed run(s) …9548`, then `InstrumentError: … 392 row(s) of …9548 were measured with another instrument (code_sha '30f99ac7f841' → '786cd52cb15f') … e.g. apply-screen_v2.jsonl` |
| `1946e27` | the agent set `OUT` to `apply-screen_v2.jsonl` |
| run `0eae` | 0.7609 — the truth; fresh rows only |
| audit `15-30`, reviews | the follow-up could not confirm the repair (below); the agent accepted it with `C1 not assessable` |
| adopted | `[result] run = "…0eae"`, `pred_results/screen_pred.csv` passes the hidden evaluation (0 persons off model 2.1) |

report-check on the delivered state, replayed in the image: area all
clear; REPORT.md 0 blockers, 2 warnings.

## What the two repairs did

- **Rows of the old code:** the remeasurement was refused with the runs,
  the changed `code_sha` and a new output name; the agent took the name
  and measured fresh. The fault of the first attempt is gone.
- **The required check:** not exercised — no finding this time asked for
  a `check:` key (the reuse finding of the first attempt could not
  arise). Its acceptance is still owed.

## What is left

The adopted result reads `C1 not assessable; A1 not assessable; A2 not
assessable`, though the number is the true one and [C1] passes on it.
Two causes:

1. **The auditor never sees the declared predictor file.** The first
   audit's finding asked the caller to confirm from `model.json` that
   `std` holds standard deviations; the follow-up said `not_assessable`
   — "that result is in no file shown here" — and three decision reviews
   said `insufficient` because "model.json (sha c94491aa…) is not
   inlined". `PREDICTOR_FILES` are bound by digest (`predictor_sha`,
   `data=`), but `labkit-audit` inlines only the protocol, the scripts,
   the declared scopes and the run's rows. A small text predictor (a JSON
   model of six weights) could be shown; a binary one cannot. And a
   finding's request to confirm something from a file has no channel like
   a `check:` key: the agent cannot hand the auditor the answer.
2. **The C1 bar on one null draw** again (`15-27`, `15-30`): accepted with
   `C1 not assessable`. Decided and built since
   ([note](../notes/2026-10-28-null-lane-spec.md), `c54a4dc`, `7b9700b`);
   the shown dependencies are `23bdccd`.

The agent decided the planted fault's BLOCKER `fixed` and then, after the
follow-up's `not_assessable`, `accepted` with `C1 not assessable` — an
honest outcome labkit's rules lead to, not a slip.
