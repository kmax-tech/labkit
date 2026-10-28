# File-check case — haiku at 1800 s on labkit 64040f2 (2026-10-28)

*The first exercise of `· check: file:<path>` (`8645e31`), which no
finding of the third repair attempt needed. Start state built by
`build_case.txt --plant-file-check` on `64040f2`: as in the check-path
case, except that the measuring script loads model.json without
declaring it (`PREDICTOR_FILES` empty, `MODEL_JSON` read directly), and
the planted BLOCKER closes with `· check:
file:data/raw/screening/model.json — std holds the standard deviation of
each feature, not its variance` (`planted-answer.txt`; the record names
`opus`, though no model wrote it). A dry run on the host showed the
declared run records exactly that path. Haiku 4.5, cold. Records:
`2026-10-28-file-check-case-haiku-64040f2/`.*

## Result

Two verdicts, kept apart: the file-check path passed; the delivery
failed.

The file check works. The agent repaired the fault and declared the file
(`PREDICTOR_FILES = {"model": MODEL_JSON}`); the next run recorded it, and
four follow-ups (`17-29`, `17-34`, `17-35`, `17-39` — the last three on
the final run) judged the repair `resolved` with `check_present = true`,
quoting model.json's `std` from the `DEPENDENCY` piece. The adopted run
reads `C1 met; A1 met; A2 met`, 0.7609.

The delivered state is not clean, for reasons outside the file check.
report-check replayed in the image: area 1 blocker, REPORT.md 1 blocker.
The hidden evaluation fails: `pred_results/screen_pred.csv` holds the 92
labelled persons, not the 208 others the task sheet asks for ("every
person in cohort.csv"). 1051 s, one attempt.

| step | what |
|---|---|
| start | planted record `17-22`: BLOCKER with `check: file:data/raw/screening/model.json` |
| `d186bc1` | `/ sd**2` → `/ sd`; model.json declared |
| run `5581`, audits `17-26`, `17-29` | `17-26` before the BLOCKER was decided; `17-29`: `FIX … resolved`, check present; decision reviews |
| `3df788b`, run `90d9` | probability added to the output for `pred_results/`: a code change, a new output name, a new run |
| audit `17-34` | BLOCKER: the head still declares `5581` while the run shown is `90d9` — decided `fixed`, then `protocol-fill --from-run 90d9` |
| audits `17-35`, `17-39` | the file check `resolved` again; the `17-34` BLOCKER not followed up (same state) |
| `c96b6af`, `4b8acbb` | committed with `--no-verify` after the hook refused |

## A gap in labkit: a fixed BLOCKER on the result declaration is held for good

The `17-34` BLOCKER named the declared run, which `protocol-fill
--from-run` repairs. That repair does not move the audited state (code,
promises, run and what was shown stay the same), so the later audits are
of the same state: they do not follow the finding up, and report-check
holds a BLOCKER "decided `fixed` in the state audited — no follow-up has
seen the repair", with the way out "change what the finding names, then
a new run and `labkit-audit … --mode analysis`". A new measurement does
not fit a finding about the declaration. The stop hook showed the
blocker; the agent ran one more audit, which again could not see it, and
then committed past the hook with `--no-verify`, which AGENTS.md
forbids.

The gap explains the BLOCKER that stayed held. It does not excuse the two
commits past the hook, nor the missing parts of the delivery (the
generated block in REPORT.md, the 208 predictions): those are the
agent's, and report-check named each.

Decided by the author: the declared run joins what an analysis record
binds, so re-adopting moves the state and the next audit follows the
finding up as an earlier one; re-adopting does not settle the BLOCKER by
itself. Rejected: a release rule in report-check for this one kind of
finding, which would stand in for the missing binding. The fix is a step
of its own (TODO 15).

## What else the attempt shows

- REPORT.md cites the adopted run without its generated block, and the
  protocol keeps one line of template text; report-check named both.
- The deliverable `pred_results/` was written for the labelled persons
  only; labkit has no part in it.
