# The report review stays one review

2026-11-06. Decided by the author: the report review is not split into parts that a change could leave standing on their own. The question comes back only on the triggers below.

## Question

Since `1cbba86b` the brief (the reviewer's instructions and the standard's excerpt) is part of the review's fingerprint (`report_hold.review_fingerprint`), so a corrected brief makes every report review stale. Would reviews split into parts — per report section, or per task — let a change stale only the part it touches?

## Why not

1. **The reviewer needs the whole report.** Whether a number is a claim depends on text elsewhere: a heading marks every line below it up to the next heading of the same or a higher level, and the same number repeated outside the mark is a claim (`labkit/agents/report-review.agent.md:69`). A review of one section would miss the mark or the repetition — false claims or missed ones.
2. **The cost is measured and small.** All report reviews of a usage round took 157, 186 and 215 s over nine attempts each (areas 21a, 21b and 22, `TODO.md`, time split of 2026-11-06), about 20–60 s per review. The brief changes rarely; a change costs one review per report.
3. **The useful split exists.** The fingerprint has parts, and the hold names the part that changed (`changed since: …`, `report_hold.review_hold`). The agent learns why its review is stale. Reuse of a review under an old brief is not wanted: a verdict under a corrected rule is not to stand.
4. **More parts mean more bookkeeping** — which claim belongs to which part, what a new run stales, what holds when two parts disagree: new code where two readers can drift, against the simplification the package is under.

## Triggers to reopen

- A usage round shows stale reviews as a cost: re-reviews after a brief or run change take a visible share of the attempts' time (the round's `03_process` counters: report reviews, re-reviews after a run).
- The review's second task, the run history (`RUNS`: hidden searches, a number of another run), yields findings of its own. Then a split by task, not by report section, is the candidate. So far `RUNS` stood in all 30 review bundles of areas 22 and 23 and raised no claim.
