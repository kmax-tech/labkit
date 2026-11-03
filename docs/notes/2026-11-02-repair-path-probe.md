# 2026-11-02 — the six repair paths followed to the gate

**Question.** Does the action `labkit-next` names repair the named fault
without bypassing another protection, and does each path reach a valid
continuation or an explicit end? B and A1 are implemented (labkit
`53082392`).

**Method.** The count task in staged labs (`usability stage --task count`,
registered `report = "REPORT.md"` before the first measurement, low repeat
cost). Every step is the real command; only the model behind
`labkit-audit` (analysis, report review, decision review) is replaced by a
fixed answer, so the audit verdicts are stand-ins and this checks binding
and guidance, not judgement. Per case: one named fault, `labkit-next`, its
action executed, `labkit-next` and the gate again, a correct twin and an
obvious forbidden shortcut. The scripts stayed outside the repo.

## Results by case

| Case | Named path | Verdict |
|---|---|---|
| 1. measuring code faulty (cases with more than 5 documents silently dropped; 3.27 instead of 3.5) | decide `fixed`, measure again, follow-up `resolved`, adopt | passes; old run with repaired code, `fixed` without a change and edited metrics are held |
| 2. setup description wrong (Data / scope "14 cases", the run read 12) | correct the field, `fixed`, follow-up `resolved`, adopt the unchanged run | passes; a fresh audit without a verdict, a silent rewrite, `false-positive` and an `unresolved` redefinition are held |
| 3. Conclusion alone (overclaim) | rewrite, decide | WARNING passes without a new audit; **BLOCKER has no way out** (F3) |
| 4. registered choice changed (Exclusions / filters) | restore, or hand over and register a successor | restore passes; **successor and handover stall** (F1, F4) |
| 5. adopted result faulty | withdraw, repair, measure, follow-up, adopt | passes; re-adopting without withdrawal and restoring the faulty code are held |
| 6. registered report removed or redirected | restore, or hand over and register anew | redirect via `protocol-fill` refused, a dropped `report` key held; **a deleted adopted report passes every gate** (F2); the handover stalls (F1) |

## Findings, most severe first

**F1 — the handover and the report review invalidate each other.**
After `protocol-fill --handover --into REPORT.md`, `labkit-next` says
"nothing", but the commit refuses: the registered report owes its review.
The review writes `audits/report-reviews/`, `audits/answers/` and
`audits/attempts.jsonl`; the handover binds `audits/` and expires
(`handovers.mismatch`: "audits/ changed since the handover"). The commit
of handover plus review passes once; afterwards `labkit-next` and
`report-check AREA` hold the area again (scope hold, owed audit). A new
handover rewrites REPORT.md's block, which makes the review stale. The
documented end without a result has no stable state when a report is
registered. Seen in cases 4 and 6.

**F2 — a deleted registered report after the adoption is held nowhere.**
`git rm REPORT.md` and a commit of that path alone: the commit hook,
`report-check AREA`, `report-check --if-reported REPORT.md` all clear;
`labkit-next` says "nothing — the number may be reported" and calls
REPORT.md "a report the head does not register". `report_hold.missing_report`
names the gap, but only the stop hook calls it, and only for areas the
session touched (`agent_hooks.missing_reports`); a report at the repo root
touches none. Contradicts workflow step 2 ("removing or moving that bound
path later holds release") and step 8.

**F3 — a BLOCKER on the Conclusion, decided `fixed`, cannot be released.**
The Conclusion is not in the audited binding, so the record still covers
the state. `--decide` says the BLOCKER "waits for the follow-up audit …
no new measurement"; that follow-up is not shown the finding
(`followup.earlier_blockers` takes only records outside the cover), a FIX
verdict on it is refused ("which the prompt did not show … run the same
command again"), and `release_holds` keeps "decided `fixed` in the state
audited". `labkit-next` names only code, setup description and adoption.
`--review` refuses a `fixed` decision. What remains is re-deciding as
`limitation` or `false-positive` (both untrue) or a handover. The WARNING
twin (`tests/test_repair_paths.py`) does not reach this.

**F4 — the successor's declared change is refused for prose fields.**
The predecessor's hold compares every registered prose field
(`first_measured_differences`) and points to "register anew … one
`[[replaces.change]]` per change". The replacement station compares only
kind, promises and `COMPARED_FIELDS = ("Data profile",)`
(`protocol_history.registration_differences`), so a declared change of
Exclusions / filters is a blocker ("declares a change the registrations do
not show … remove that [[replaces.change]]"). The successor passes only
with `[replaces]` and no change: the reason for the new registration
remains only in prose. Two comparisons of the same fact disagree.

**F5 — measuring again after a correction closes the correction route.**
In case 2, after the correction is decided, the start of a new measurement
is not refused (the hold text says "a new measurement would carry the
change"). The new run becomes the answering run, overwrites the shared
output file, and the audit then reviews only that run; the unchanged run
can no longer be followed up or adopted ("a file of two measurements"). The
way back that `labkit-next` names is to restore the known-false
description and measure again; it worked here after 3 runs and 5 analysis
records and only because the stand-in audit flagged the false text again.
`labkit-next` also first asked for a progress account of the run that
cannot be adopted.

**F6 — the correction route also covers Question / hypothesis.** "mean" →
"median", decided `fixed`, a `resolved` follow-up: adopted. A1 is
deliberately not a list of field names, and the judgement is the
auditor's, but `labkit/docs/agent-guide.md` says "in place, never change
… the question". The guide and the mechanism disagree on the field whose
correction most often redefines the run.

**Smaller.**

- At a decided correction, `labkit-next` offers three alternatives,
  leading with restore, without the follow-up command; the decision line
  of `--decide` was exact.
- Adoption replaces only the matching discussion block; the progress
  account of a superseded faulty run stays in the final report ("audit and
  adoption open"), and only the report review can catch it (cases 1, 5).
- Case 5 without withdrawing first: after a second measurement
  `labkit-next` advises a renamed output and a third measurement; a
  `--withdraw` alone suffices. The withdrawal's "next, in this order"
  omits "measure again" for a code repair.
- Before the first measurement `labkit-next` names "measure" while the
  registration is uncommitted (runlog then refuses with the right fix),
  and committing a registered REPORT.md with only prose is refused before
  any run exists; "the registered path must be committed" means the head's
  key, not the file.

## Limits

Stand-in model answers: whether a real auditor flags, resolves or
withholds a verdict is not tested here, and F6 depends on that judgement.
Only low repeat cost, kind `compute`, one protocol per area. The stop hook
was checked through the functions it calls, not in a live session.

## Repairs (same day)

Each fault first kept as an expected failure (`8a18014c`), then repaired
with its correct twin; every commit passed the full hook.

| Finding | Commit | What changed |
|---|---|---|
| F2 deleted report | `d1d8e883` | `missing_report` reads the gate's state; `report-check` holds it once a result is adopted, the commit holds the removal of a report HEAD holds, the stop reaches the protocols registering a changed path |
| F1 handover and review | `14a7fad7` | the handover binds `audits/` without the report review's record, answer and journal lines (`handovers.review_trace`, `journal_digest`); `labkit-next` names the review owed after a handover |
| F3 Conclusion BLOCKER | `9c5ce7e9` | `findings.fixed_claim`; `--review` takes it, `report-check` holds it until an upheld review bound to the claim (`report_decisions.repaired_claims`), `--decide` names the review; a BLOCKER `fixed` with nothing changed is told it is not repaired |
| F4 successor declaration | `fe40f50d` | `registration_differences` includes `scope_differences`, the comparison finalize holds the predecessor to |

Decided, not built: F5 gets no start refusal for changed prose fields
until a description correction followed by a needed code correction has
a defined route — a refusal alone could be the next dead end. F6: a
mean → median rewrite changes the question and needs a new registration;
a given `resolved` shows only that labkit trusts the auditor, so the
contradiction between the agent guide and the correction contract is to
be settled explicitly. The smaller points follow where the repaired paths
have not removed them.

## The smaller points (2026-11-03)

Re-run of the probe scripts on main `4ab018bf` first: three of the smaller
points still occurred. Each repair reads the condition of the gate that
holds the state; no gate holds or releases anything it did not before (the
probe's refusals are the same before and after).

| Point | Commit | What changed |
|---|---|---|
| `labkit-next` names "measure" over an uncommitted registration | `e8e2fd19` | where the first hold's way out is a measurement before any run, `labkit-next` asks runlog's start gate (`start_check.measurement_refusal`) and names its refusal and first step |
| case 5 without withdrawing: a renamed output and a third measurement | `89bf3c42` | `report_check.chain_gaps` returns the declaration the later holds withdraw first (`held_declaration`); `labkit-next` names that withdrawal alone, `--into` the registered report, then itself again — the run already measured is adopted |
| a decided correction: three ways, the way back first, no follow-up command | `d042efb6` | `finalize.awaiting_followup` reads which corrections a follow-up of the state now is shown (as `audit_prompt.earlier_of`); where every held field has one, the scope hold names that follow-up first |

Not repaired here: the progress account of a superseded run in the final
report; a withdrawal's "next" without "measure again" after a code repair
(after the withdrawal `labkit-next` names the measurement); the withdrawn
run's progress account that `labkit-next` asks for before the measurement
(case 5 twin); a registered REPORT.md with prose only refused before any
run. The F5 contract (a new run under a corrected description) is
separate work.
