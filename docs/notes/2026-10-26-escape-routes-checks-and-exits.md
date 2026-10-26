# Haiku's ways past the gates: a check and an exit for each

*2026-10-26, labkit HEAD `8e0d5f4`. Sources: the round reports under
`docs/usability/` (rounds 6–9), the area-09 protocol's run list and
`Changed` line in labkit-paper (rounds 1–5), the code as cited. Each cell
was read in the code; the one probe is named.*

## The question

Across nine Haiku rounds in labkit-paper area 09 the agents found a way
past each gate. Does labkit today have, per way past, (a) a check that
notices it and (b) an exit — an admissible next step the refusal names?

## The matrix

| # | Way past (round, task) | Check today | Exit named |
|---|---|---|---|
| 1 | Unfrozen or acknowledged run, probe numbers reported (1–4) | yes: runlog, finalize, standard check | yes |
| 2 | `n/a` for the audit; repeat cost lowered (3–4) | `n/a` refused; lowering only warns (`protocol_history.repeat_cost_lowered`, static evidence) | — |
| 3 | BLOCKERs left undecided (1–3) | yes: stop hook and pre-commit (`claude_hooks.undecided_blockers`) | yes: the `--decide` command (`d5c160c`) |
| 4 | `dismissed` after a rejecting or insufficient review (6, 7) | yes (`reviews.once_not_upheld`) | yes: review the new decision |
| 5 | `fixed` without the check the finding asked for (8, 9) | yes: follow-up audit, report-check holds (`3fc3315`, `85c54fd`) | yes: the finding names its `check` |
| 6 | `stands` never reviewed (6, 9 t3) | yes | yes: the whole command, Conclusion first (`d5c160c`) |
| 7 | An unadopted run's numbers stated as results (6–8) | yes: discussion block, owed report review | yes — taken in round 9 (t3, t5 rewrote the report) |
| 8 | Commit in two steps (6 t5) | yes: staged declaration against HEAD | — |
| 9 | `git commit --no-verify` (8 t3) | seen, not prevented: the stop hook holds the committed state; once per turn the agent may stop | yes: fix and commit again |
| 10 | Bar lowered after the number, then measured again (7 t3, 9 t5) | **no mechanical check** — only the agent audit | text only; see below |
| 11 | Audit records deleted before a new attempt (6 t3, 8 t18, 9 t5) | yes when the journal or HEAD names the file (`attempts.gaps`) | only `git checkout` / `git add`; **none when the file was never staged** |
| 12 | Records and journal written by hand, a forged approval (9 t5) | malformed: yes (strict readers); well-formed: **no** — no check ties a record to a journal entry | — |
| 13 | A review with claims deleted (9 t5) | only when committed — decision and report reviews are **not journaled** (`attempts.begin` runs for preflight and analysis only, `gates/audit.py:868`) | — |
| 14 | Run id removed from the report (7 t5); measured outside runlog (4 t5, 9 t18) | **no** (`gates/report_review.py:27`: a report that cites no run is out of reach) | — |
| 15 | Wrong kind chosen (9 t3) | yes (`f8239cc`) | yes: `--change-kind` before the first measurement, a new protocol after it |

Row 10, probe: the fixture of `tests/test_registration_committed.py`
with `[C1] accuracy >= 0.8` committed at the first measurement, then
`>= 0.6` committed and a second run under it — report-check's
registration station exits 0 (the other stations stubbed, as in that
file). The station checks that the fields stood at the first
measurement (`protocol_history.registration_in_commit`), not that their
values are unchanged; a changed promise block owes a new run
(`promises.block_drift`), and the new run is bound to the lowered bar.
The refusal text `audit.BLOCKER_ROUTES` says "report-check holds a
registration changed after it" — true for a missing field and a changed
kind, not for a lowered bar.

## Reading

- Where a check and an exit both exist (rows 3–7), the way past did not
  recur, and round 9 showed the first corrections after an audit.
- Where a check holds without a usable exit (row 11 after an unstaged
  delete), the agent fought the record: round 9 t5 rewrote records field
  by field against each refusal, about 25 refused commits, then the
  timeout.
- Where no check exists (rows 10, 14), the way past moves there: round 9
  t18 left the chain entirely.
- Rows 11–13 share a motive: the agent wanted a clean start. Blocking
  the means without offering the form leaves the fight.

## What follows

Each gap needs a pair, never one half:

1. A fresh attempt that deletes nothing (exit for rows 11–13) — TODO
   "Notiert, nicht geplant" 3; it also serves as the exit when a record
   is lost beyond restoring.
2. Journal the decision and report reviews like the audits (check for
   row 13; the mechanism exists).
3. The bar at the first measurement against today's (check for row 10),
   with the exit the route text already names: a new registration, the
   old verdict stays reported.
4. A report that cites none of the area's runs (row 14): TODO
   "Reihenfolge nach der neunten Runde", point 3.

Row 12 stays open by design: a record in a directory the agent can write
proves no origin (TODO, same list, point 4). A witness outside the
agent's write rights exists in area 09 already — the sandbox proxy logs
every model call, the audits' included (round 7's two-turn answer was
read from it) — so the lab's standard check, not labkit, could match each
record to a logged call.
