# Check-path case — haiku at 1800 s on labkit 8645e31 (2026-10-28)

*The targeted test of a finding's required check, owed since the second
repair case ([note](2026-10-28-repair-case-2-haiku-5a26902.md)): there no
finding asked for a `check:` key, so the work order `5a26902` was never
exercised. Start state as in the repair case (`build_case.txt
--plant-check`): apply-screen registered and committed with the
permutation-expectation null (`c54a4dc`), one planted fault (`sd**2` for
`sd`), the first measurement in the container. In addition, the first
analysis audit stands in the start state: `labkit-audit` ran in the
container with its model call answered by `planted-answer.txt` — the real
first auditor's BLOCKER on the fault (repair case 2, `15-27`), closed by
`· check: z_sd — per feature in model.json's order, the standard
deviation of the standardised feature over the 92 labelled persons; each
lies between 0.8 and 1.25 when the run standardises as model.json
states`. The record therefore names `opus` as its model, though no model
wrote it. A record with an undecided BLOCKER does not commit, so it stood
uncommitted in the tree, as after any audit. Haiku 4.5, cold, TASK.md and
AGENTS.md only. Records: `2026-10-28-check-path-case-haiku-8645e31/`.*

## Result

The check path works through the follow-up and breaks at the adoption.
The agent repaired the fault, computed `z_sd` and wrote it to
metrics.json; the follow-up audit saw the value and judged the repair
`resolved` with the check present. The adoption was then refused:
labkit's recheck recomputes every metrics key from the kept rows and
refused `z_sd`, which the agent had computed beside them. The agent
removed the key, and every later follow-up judged the repair not
assessable. It ended without an adopted number (1017 s, 8 measurements,
5 analysis audits; the hidden evaluation fails: no predictions
delivered).

| step | what |
|---|---|
| start | planted record `16-28`: BLOCKER with `check: z_sd`; the decision list printed the work order |
| repair `c9d5b5d` | `/ sd**2` → `/ sd` |
| run `da39`, audit `16-31` | without `z_sd`; the BLOCKER not yet decided, so no follow-up |
| `a2ebd08`, run `fd5c` | `compute_z_sd(items, model)` in `evaluate()`, beside `evaluate_rows()`: `z_sd = [1.138, 0.956, 0.991, 1.128, 1.024, 1.096]` — the values of the correct standardisation |
| audit `16-35` | `FIX … resolved`, `check_present = true`; a WARNING that `compute_z_sd()` re-implements the standardisation outside the kept rows |
| `protocol-fill --from-run fd5c` | refused: `recheck: … vanished ['z_sd']` |
| `48a9ff6` and later | `z_sd` removed "to pass report-check"; runs `a5eb`, `f7ae` without it; follow-ups `16-38`, `16-41`: `not_assessable`, check missing, the BLOCKER carried |
| run `a802` | `z_sd` back, no audit followed; the last commit says "measurement incomplete" |

## The fault, in labkit

Two of its own rules disagreed. The work order (`findings.check_order`)
said: compute the key "from what the run measures" and write it to
metrics.json. The recheck (`02_analyze.py --check`, LAB-041 Generate
numbers, don't retype them) holds every metrics key to a recomputation
from the kept rows by `evaluate_rows()`, and a key that only
metrics.json holds is refused — with no way out named beyond "fix what
the check names". Both are right on their own; together they left an
obedient agent one move, removing the check. The auditor saw it coming
(WARNING at `16-35`: "computed in `evaluate()` outside the kept rows").

Fixed on the branch (`A required check is computed from the kept rows`):
the work order now says that the kept rows carry what the check needs
and `evaluate_rows()` computes it from them; the recheck's refusal of a
vanished key names that way.

## What else the attempt shows

- The planted BLOCKER was decided `fixed` before any follow-up saw a
  run with the check; the hold then did its job (`16-38`, `16-41`).
- Eight measurements, each with a new output name, as the row-identity
  guard (`0796243`) asks; the extra runs came from the refusal, not from
  confusion about outputs.
- One attempt — no rate, no speed evidence.

## What is left

Accepted since: the same case on `64040f2` computed `z_sd` in
`evaluate_rows()` from what the rows carry, and the number was adopted
([second attempt](2026-10-28-check-path-case-2-haiku-64040f2.md)).
