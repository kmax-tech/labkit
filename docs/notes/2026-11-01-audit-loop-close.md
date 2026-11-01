# 2026-11-01 — the analysis audit loop ends in a stated state, never a release (proposal)

Status: proposal, nothing built. Evidence: the registered pilot's part 1, the 15 lab traces
read end to end (labkit-evidence `usability/2026-10-31-registered-pilot/issues-rp/review-*.md`).

**Problem.** The loop measure → analysis audit → decide → measure again has no end but a
clean adoption. In part 1 it took most of each lab session where it ran long:

- 34: from the first audit to a clean adoption ~18 min (r1, 5 audits), ~15 min (r2, 5
  audits); r3 ~23.5 min, 5 audit attempts, handed over without a number.
- 21-r2: 6 audits in 27 min, no adoption. Each "Assignment:" became a metrics key, so a new
  run, so a new audit owed, so new WARNINGs about that diagnostic. The fifth audit called
  the bounding-box diagnostic the fourth had asked for useless.
- 60-r3: a third audit was owed because the second ran before the first record's BLOCKERs
  were decided `fixed`. The limit came during the third.
- Rounds came back to the same prose. Each hand-typed Conclusion before adoption drew new
  WARNINGs and READ hints, and the template's Conclusion is written after adoption anyway.

Some of this was labkit's own fault (refused answers, invisible audit state, P3/P4 in
`TODO.md`). What remains after those repairs is the question here. When the budget runs out,
the attempt ends with nothing a reader can use: no report, and the last run's state stands
only in the trace.

**Conditions (author's feedback, 2026-11-01).**
1. A round limit never releases a result by itself.
2. When the budget is reached, the area ends in a state someone can follow: the run kept so
   far, the open findings, what may be said and what may not, and the next step.
3. A convergence hint (findings come back, assignments contradict each other) informs a
   decision and nothing more. That it can be detected reliably is not shown.

**Proposal.**

1. *Count the rounds, as data.* A round is one analysis record on one registration of the
   area. `labkit-next` and `--findings` say "analysis audit round k". labkit does not know a
   wall-clock budget, and a pilot's 40 minutes is the harness's, not the protocol's. The
   count is what labkit can state exactly (guaranteed tier).
2. *From round 3 on, both ways stand side by side.* One way is to decide, measure and
   follow up. The other is to close: a handover generated from the records rather than
   written by the agent. It holds:
   - the newest kept run and its metrics, labelled "measured, audit unresolved";
   - every open finding as `<record>#n · grade · one line`;
   - what the report may carry: the number only as unaudited, with its open BLOCKERs named,
     and no criterion verdict;
   - the next step: the command that would follow up.

   The existing `protocol-fill --handover` becomes this close. The agent adds one `--why`
   line; labkit fills in the rest. report-check accepts a REPORT.md that carries the
   generated close block and holds its numbers to the record, as it does for a result
   block. Nothing is adopted and no criterion is met (condition 1).
3. *Hints at the decision, not gates.* These are static evidence and block nothing.
   - In the decision list, a finding that names the same `check` key, or the same
     `file:line` and grade, as a finding of an earlier record on this registration is
     marked `recurs from <record>#n`.
   - A new Assignment is shown next to the one the previous round gave, for the person to
     compare. labkit does not judge "contradicts".
   - Whether the marks are right gets checked by hand on the part 1 traces before they ship
     (a negative finding is a claim, LAB-001).
4. *Remove the rounds the loop makes itself, not the strict ones.*
   - The analysis audit gives no READ hint on the Runs list, Recorded results or the
     Conclusion before adoption. These are adopt's to write (`TODO.md` P4, Unklar 15).
   - `--findings` and `labkit-next` say "decide the open findings before auditing again";
     a round run on undecided BLOCKERs follows nothing up (60-r3).

**How it is judged.** This does not run before part 2 or the pubmedqa50 repeat, and it is
measured there per lab attempt:
- rounds;
- minutes from the first audit to adoption or close;
- the share of attempts that end with a complete REPORT.md, whether a result or a close;
- whether every close states its open findings correctly against the records.

The test from the feedback is whether the same claim gets through after the repairs with
fewer rounds and a complete report. Only then can the price of the strictness that remains
be judged.

**Open.**
- Is round 3 the right threshold? Part 1's clean adoptions took 1–5 rounds.
- Should a protocol be able to state its own round budget in the head?
- How does the close sit with the scored delivery a benchmark asks for? A close carries no
  deliverable judgement; the output file is the task's.
