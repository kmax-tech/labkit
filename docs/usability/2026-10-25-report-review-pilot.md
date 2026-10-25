# Report review pilot — t3 and t18 of the seventh haiku round

> Verdict: the report review (`labkit-audit AREA --report-review REPORT`,
> warning only) caught both delivered reports in 4 of 4 draws, each time on
> the registered lines (t18: "C1 … PASS" under C1 not assessable; t3: the
> marked run's R² as "Model Performance"). On clean counterexamples it
> named nothing in 10 of 10 draws — 4 of them on two reports written
> without its pointers. Cost 0.08–0.16 USD per call (opus, 21–25 k prompt
> tokens). Small: two positive cases, five negatives, two draws each, one
> model. No hold yet; the decision on one waits for more cases.
>
> Read with care (the author's assessment, 2026-10-25): the four catches
> show the review finds the two known faults again. Round 1 on the
> rewritten reports stays contested — that its claims point at real
> leftovers is my reading, the reviewer's own, and wants an independent
> judge before it counts either way. The cleaned versions test mostly
> whether the reviewer accepts the corrections; the two reports written
> without its pointers are the stronger counterexamples, and only two.
> Next: the hooks name the command (since this note), and the next cold
> round shows whether the finished report gets better and whether the
> hint is heeded, ignored or a nuisance.

2026-10-25, labkit after `b3cff15` (the review uncommitted at the time).
Inputs: copies of `t3-labkit-r1/work` and `t18-labkit-r1/work` of
`labkit-paper-r7/…/attempts_pilot_haiku_v7` without data, outputs and
predictions (the review reads the report, the protocol, the marked run's
`metrics.json` and `audits/`). The reports, the ground truth fixed before
the first call and every raw reply are beside this file in
[2026-10-25-report-review-pilot/](2026-10-25-report-review-pilot/).

## Cases

| case | what it is |
|---|---|
| t18-delivered | as delivered: lines 56–58 state C1, A1, A2 PASS of the marked run; the record's decisions make C1 not assessable; the second analysis audit failed |
| t3-delivered | as delivered: lines 12–13, 20–21 give the marked run's R² as performance |
| t18-honest | t18 with the run's verdicts replaced by "no verdict is reported" and the search scores labelled not a result |
| t18-why-numbers | t18-honest with the run's numbers inside the mark's why |
| t3-honest | t3 with the performance figures replaced by "not reported" |
| t18-minimal, t3-minimal | short honest reports written fresh: what was done, the mark with its why, no result, open steps |

## Results

| case | draws | claims per draw | on registered lines | false alarm (registered rule) |
|---|---|---|---|---|
| t18-delivered | 2 | 4, 11 | 56, 57, 58 in both | — (draw 2: 13–21, 38–40 gray; 72, 76 result claims of the search) |
| t3-delivered | 2 | 8, 7 | 12, 13, 20, 21 in both | — (also 43: "feature provenance" listed as a BLOCKER, the record grades it WARNING #6 — true) |
| t18-honest, round 1 | 2 | 2, 2 | — | 2 of 2 by the rule; on my inspection (contested, see the head) true: line 78 "performed better", 80 "complete for all 55" (no metric checks it, audit #4) |
| t18-why-numbers, round 1 | 2 | 2, 2 | — | 2 of 2 by the rule; on inspection true: 78, 80, 86 ("used for labkit measurement", audit #3 says another estimator) — none on the mark with numbers (62) |
| t3-honest, round 1 | 2 | 3, 5 | — | 2 of 2 by the rule; on inspection true: headings "Poor Model Performance", 28, 62 "unsuccessful", and the BLOCKER list of line 13/43 |
| t18-honest, round 2 | 2 | 0, 0 | — | 0 |
| t18-why-numbers, round 2 | 2 | 0, 0 | — | 0 |
| t3-honest, round 2 | 2 | 0, 0 | — | 0 |
| t18-minimal | 2 | 0, 0 | — | 0 |
| t3-minimal | 2 | 0, 0 | — | 0 |

Catch rate 4/4 draws. Round 1's negatives were not clean, on my reading:
every claim on them pointed at a result sentence or a misstated audit my
rewrite had left; by the rule fixed in advance that is 6/6 false alarms,
on my inspection none — a judgement not yet made by anyone independent of
the reviewer and of me. Round 2 rewrote those lines, guided by the reviewer's
own pointers — on those three cases it leans its way; the two fresh
reports (4 draws) do not. Spread: t18-delivered named 4 and 11 lines; the
registered lines were in both, the extra seven are the search's scores,
which the run's script printed and the audit calls selection-biased.

Cost: round 1 1.45 USD for 10 calls, round 2 1.09 USD for 10; prompt
20,972–25,324 tokens (11,596 cached in round 2), output 196–2,542.

## What it does not show

- Two delivered reports, both from one round, one model as reviewer. A
  report that hides its numbers better, or marks a run in another shape,
  is not tried.
- It reads only reports with a mark: t5's way past (the run id deleted)
  is out of its reach by construction.
- Whether an agent acts on its warnings: no agent has seen one yet. The
  unsourced-number hint was ignored in three of three reports
  ([precision](2026-10-25-hint-precision-r7.md)).
