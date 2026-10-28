# Check-path case, second attempt — haiku at 1800 s on labkit 64040f2 (2026-10-28)

*The acceptance of `64040f2` (a required check is computed from the kept
rows) after the first check-path case
([note](2026-10-28-check-path-case-haiku-8645e31.md)) ended without a
number: the agent computed `z_sd` beside the rows, the recheck refused it,
and the agent dropped it. The same start state, built by `build_case.txt
--plant-check` on `64040f2`: apply-screen registered, the planted fault,
the first measurement, and the first analysis audit planted with the real
auditor's BLOCKER closed by `· check: z_sd` (`planted-answer.txt`; the
record names `opus`, though no model wrote it). Haiku 4.5, cold. Records:
`2026-10-28-check-path-case-2-haiku-64040f2/`.*

## Result

The whole chain held. The agent repaired the fault, let every kept row
carry its standardised features (`standardized`, written by `lane_row`)
and computed `z_sd` in `evaluate_rows()` from them
(`01_measure.delivered.txt`). The follow-up judged the repair `resolved`
with the check present, the recheck agreed, and the agent adopted the
number: `C1 met; A1 met; A2 met`, 0.7609, the hidden evaluation passes.
report-check on the delivered state, replayed in the image: area all
clear; REPORT.md 0 blockers, 1 static-evidence warning. 621 s, one
attempt — no rate.

| step | what |
|---|---|
| start | planted record `17-12`: BLOCKER with `check: z_sd` |
| `181ad05` | `/ sd**2` → `/ sd`; rows carry `standardized`; `evaluate_rows()` writes `z_sd` |
| run `3cc0` | `apply-screen_v2.jsonl`; `z_sd` = [1.132, 0.950, 0.986, 1.122, 1.018, 1.090] |
| audit `17-16` | the planted BLOCKER not yet decided, so no follow-up; one WARNING dismissed |
| audit `17-20` | `FIX … resolved`, `check_present = true` |
| adopted `81c449f` | `[result] run = "…3cc0"` |

No `vanished` refusal in the whole attempt. The adoption was refused on
the way for owed steps, each named with its way out: the planted BLOCKER
decided `fixed` but not yet followed up, a finding still open, no audit
of the current state, REPORT.md citing the run without its generated
block.

## What is left

Nothing from this case.
