# Note 2026-10-23 — a report from the run, not from the protocol: the proposal

**Status: proposal, not a build order.** Decided by the author; the
TODO ("Abschluss-Audit des fertigen Berichts") carries the decision.

## The case

Sixth haiku round on c49e760 (`docs/usability/2026-10-23-sandbox-c49e760.md`,
t3 and t18). `protocol-fill --from-run` was refused five times at t3
(untracked data and failing tests; no audit; stale audit twice; two
unreviewed `stands`) and once at t18. Both agents then wrote REPORT.md
from the run's `metrics.json` by hand. The report hook saw a citation of
a run no protocol declares, said "an exploration's run is cited, not
reported" — a WARNING — and let the commit pass. At `cost = "seconds"`
the REPORT.md is the promotion: nothing else leaves the area. So the one
hold labkit had on the delivered number was a warning written for
another situation.

The warning is right for what it names. An exploration (a protocol that
declares no result, LAB-017 The number of audits follows the cost tier:
"an exploration ends with no reported result, probes or not") may cite
its runs in a note — "we looked at run X and dropped the design". A
blanket block on citing undeclared runs would hold every such note and
is out (TODO, "Historische Zitate").

## What a mechanical check can and cannot tell

Every fact below is computed today by an existing home; nothing new is
read.

| fact | home | tier |
|---|---|---|
| the report cites run R (a token that reads as a run id) | `report_blocks.cited_run_ids` | guaranteed |
| no protocol of the repo declares R as its result | `report_check.Sources.declaring` over `protocol_block.declared_run` | guaranteed |
| R is a run of area A, bound to protocol P | `runs.run_dirs`, `answering_run.bound_answering_run` | guaranteed |
| R is P's **answering run** — the full run (`run_kind = "measurement"`), completed, bound, that every gate would hold P to | `audit_binding.audited_run` (the one choice) | guaranteed |
| R is a probe, or acknowledged unfrozen — unreportable anyway | `runs.unreportable` | guaranteed |
| what `--from-run` would refuse for R now | `report_check.report_check(A, P, state=PROPOSED, text=fill_result_run(text, R))` — the adoption's own check, run without writing | guaranteed |
| the report carries numbers outside every block, on which lines | `report_blocks.unsourced_numbers` | static evidence |
| the prose presents R's numbers as the area's result | — | semantic |

The line between the two cases is the last row and only the last row:
t3's REPORT.md and a note saying "run X, dropped" cite the same kind of
run; the difference is what the sentence claims. A mechanical check
cannot read that. It can do two things: narrow the citations in
question to the ones where the claim matters, and make the author say
which claim it is, so a reader and an auditor can hold them to it.

## The proposal, in three tiers

**1. Guaranteed — the answering run's citation owes a declaration.** In
`report_check.hold_report`, a cited run that no protocol declares is a
WARNING today (`undeclared`). Split it:

- R is not the answering run of its protocol (a probe, an acknowledged
  run, a run of a protocol that answers with another run, a run under no
  protocol): the warning as today — an exploration's run is cited.
- R **is** the answering run of P and P declares no result: a BLOCKER at
  the commit and the stop — "cites R, the answering run of P, which
  declares no result: a full run's number leaves the area through
  `protocol-fill P --from-run R` (then `--into`); a run this report
  looks at without reporting it is cited as such". The sentence carries
  the adoption's refusals when there are any (the PROPOSED check above),
  so the agent reads in one place why the adoption was refused and what
  the report owes — t3 was refused five times and wrote the report after
  the fifth; the hold should name the five.

What is guaranteed: the condition, not the claim. A full run bound to a
protocol that declares nothing, cited in a report, is the promotion's
shape; the block holds it until the author either adopts (every gate of
the chain) or says in the report that this is not a reported result.

**The way out for a legitimate exploration citation: say so, once, in
the report.** A citation marked as not reported — the spelling is a
naming decision (candidates: `run <id> (not reported)`, a report-level
line `Not a reported result: <id>`; `lib term` and the field guide
first, LAB-084 Double-coinage check) — passes the mechanical hold. The
marker is a written claim the reader sees beside the number; a false
one ("not reported" next to a reported 0.80) is the kind of sentence an
audit reads and a reviewer catches — the lie moves from the gate's blind
spot onto the page. This is labkit's pattern elsewhere: make the claim
explicit, then hold it (the Conclusion, the `stands` reason).

**2. Static evidence — numbers beside a run cited as not reported.** For
a citation carrying the marker, `unsourced_numbers` on the citing line
and the lines of its paragraph are named as a WARNING: "a number beside a
run cited as not reported — a looked-at run's number in a report is a
reported number unless the sentence says what it is". A hint, never a
block (`gate.GateFinding` refuses a static-evidence blocker).

**3. Agent audit — the finishing audit of the report, conditional.** The
"Abschluss-Audit des fertigen Berichts" the TODO defers has its first
two cases here. Scope it small: the auditor gets the report, the
protocol (registration, Conclusion, Recorded results, Limit lines as
rendered) and the run's `metrics.json` — no code, no rows — and answers
one question per unsourced number or marked citation: is this number
presented as the area's result, and does any protocol declare it? Run
it only when tier 1 saw a marked citation or tier 2 saw numbers beside
one: the common path (adopt, `--into`, no prose numbers) costs nothing.
Cost to measure before it blocks anything: one report, one call, no
rows — a fraction of the analysis audit's 0.52 USD at t3. Until measured,
a warning.

## What the twins look like

- t3/t18 as delivered: REPORT.md cites the answering run, no protocol
  declares it, no marker → BLOCKER naming the adoption's refusals.
- A note citing a probe's run with its numbers → the warning as today.
- A note citing the answering run marked as not reported, no numbers →
  clean.
- The same with numbers in the sentence → the static hint, and the
  finishing audit's question.
- The adopted run with its block → clean (today's twin).

## Open to decide

1. The marker's spelling (naming, not mechanics).
2. Whether tier 1 blocks at the stop as at the commit (today both run
   `--if-reported`; the stop is heard first).
3. Whether a report inside the area (`experiments/NN/notes/`) is held
   like one at the root — the proposal says yes: the location is not a
   claim.
4. Whether the finishing audit (tier 3) is worth its measured cost before
   it warns; the first measurement decides.
