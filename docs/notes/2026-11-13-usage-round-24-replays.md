# Usage round 24: three findings replayed on a real case

2026-11-13. Step 1 of the plan under task 7 in `TODO.md`: the three findings of [the round's trace readings](2026-11-13-usage-round-24-findings.md) chosen first, replayed with real commands on fresh count-task labs (`usability stage --task count`, the steps of `docs/examples/count-walkthrough.sh`), labkit `906eae16` (package code unchanged since `v0.113.0`). The two model calls are stand-ins with a fixed answer; everything else is the command a person runs. The replay script, its 15 checks and the logs stay internal (labkit-evidence, `usability/2026-11-13-usage-round-24-repro/`; all 15 read as expected). All three findings are confirmed; none is repaired yet.

## 1. A run in the tree, not in the index: the commit says "measure"

State: the run measured, adopted and written into REPORT.md, all in the working tree; only REPORT.md staged (the protocol's adoption and `runs/` not).

What the pre-commit prints: `labkit-next`'s step "measure: … opens a run bound to p-…", and two REPORT.md blockers "cites run … — no runs/<id>/ in the repo … a run that is gone reports no number" and "it has adopted no result".

Cause: the step to stage the area (`next_step._staged_area_step`, `labkit/gates/next_step.py:370`, and report-check's twin in `hold_declared`, `labkit/gates/report_check.py:1332`) applies only when the index's head already declares a result. Here only the tree's head does, so `next` judges the index alone, where no run exists. The citation check (`report_blocks.cited_gaps`, `labkit/checks/report_blocks.py:406`) knows only the index's runs and calls a run the tree holds "gone".

Twins, as expected: with the protocol staged too, the hold and `next` both name `git add -- <area>`; with everything staged the commit passes. A run that is really gone gets the loss sentence, not "measure".

Expected: when the tree holds a completed run or an adoption the index lacks, the step is to stage the area, and the citation names the run as unstaged, not as gone.

## 2. A rejected `stands` limitation on a WARNING: four signals disagree

State: a WARNING decided `limitation` (effect `stands`), the Conclusion written, the second auditor rejects the decision, the run adopted, the result block in REPORT.md.

What labkit prints:

| Where                   | Says                                                                                                                       |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `labkit-audit --review` | "review state: held — finding(s) 1 not released … decide the finding again first"                                          |
| report-check            | a WARNING whose way out is "`labkit-audit … --review --record …` asks a second auditor …; after a rejection, decide again" |
| `labkit-next`           | "has adopted …; nothing holds it — the number may be reported"                                                             |
| REPORT.md, result block | "Limitation …: the verdicts stand, read within this limit"                                                                 |
| commit                  | passes, with the warning                                                                                                   |

The contract in force is that an unreviewed or rejected `stands` on a WARNING only warns (`report_decisions.check_stands_upheld`, `labkit/gates/report_decisions.py:248`, decided in task 6b). Commit and `next` follow it; the review's "held" (`labkit/gates/decision_review.py:491`), the gate's way out that leads with the review already made, and the rendered "the verdicts stand" (`labkit/formats/findings.py:838`) do not.

Expected under the current contract: the four places say the same thing — nothing blocks, a rejection stands against the limit, the next step is to decide the finding again. Whether a rejected WARNING limitation should block instead is a contract question for the author (plan step 3), not part of this repair.

## 3. The handed-over predecessor's report review knows nothing of its successor

State: protocol 01 registers REPORT.md, is measured and handed over into it; protocol 02 (same question) is measured and adopted, its result block written into the same REPORT.md. The commit owes a clean report review of REPORT.md for each protocol.

What the predecessor's reviewer reads (the prompt kept by the stand-in): "ADOPTED: none — the protocol has adopted no result", protocol 01, the runs and audits of area 01, and the report text — which carries 02's result block with its number. Nothing of 02's protocol, adoption or metrics. The instructions exempt lines inside a discussion or handover block from being claims, not lines inside another protocol's generated result block.

Cause: `report_review_inputs.review_pieces` (`labkit/checks/report_review_inputs.py:78`) reads one area only, and `labkit/agents/report-review.agent.md` names no exemption for another protocol's result block. A careful reviewer of 01 must therefore name 02's number as a result 01 has not adopted; in the trace (task 34, round b) one attempt drew 13 such claims and the second reviewer upheld none of the agent's dismissals, for the same missing context.

Not replayed: the `[replaces]` block of the successor (the reviewer's input does not read it either way) and a real model's answer; the stand-in shows the input, the trace shows the answer. The second reviewer of a dismissed claim (`claim_review`) was not checked separately.

Expected: a block another protocol generated, which report-check already holds against its own protocol, is not the predecessor's claim — either the reviewer is told so, or such lines are left out of what it judges. Which of the two is a design choice for step 2.

## Repairs (2026-11-13, plan step 2)

Each with a test that failed before, a twin, and the replay rerun through the real commands: the old readings of cases 1 and 2 no longer occur, and the predecessor's reviewer now reads the successor's block as the successor's.

| Case | Commit      | What changed                                                                                                                                                                                        |
|------|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | `c43c842e`  | the staging step also stands when only the tree holds a completed run or the adoption; the citation names the run as lying in the working tree, with its `git add`                                  |
| 2    | `cde6124c`  | the review's state line follows the grade ("(grade WARNING) not released — nothing is held"); after a rejection the gate's way out is deciding again; the contract (a WARNING only warns) unchanged |
| 3    | this commit | the review's inputs list result blocks of other protocol files with protocol and run; both reviewer briefs exempt them; reports without such a block keep their fingerprint                         |

Not changed, open for the author: whether a rejected WARNING limitation should block, and whether the report's Limitation line ("the verdicts stand, read within this limit") should say that a second auditor rejected it. No real model was run on the new reviewer input; the stand-in shows the input, not an answer.
