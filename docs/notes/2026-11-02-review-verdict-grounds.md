# 2026-11-02 — grounds for a decision review that does not uphold (proposal)

Status: **not adopted in this form** (replay, 2026-11-02). The reviewer's
instructions (`labkit/agents/decision-review.agent.md`) and the gates are
unchanged.

**Problem.** A decision review answers one question per `stands` decision —
does the reason show that the reported claim stands with the finding
true? — with `upheld`, `rejected` or `insufficient`. A count of 26 reviewed
BLOCKER `stands` decisions in 15 attempts (rounds of 2026-10-22 to
2026-10-31; internal evidence) found every faulty acceptance rejected (10)
and held 9 correct ones. The nine had three causes the verdict word does
not tell apart:

| cause | held correct decisions |
|---|---|
| the evidence was not on the page (a count, a library's behaviour) | 4, all `insufficient` |
| the protocol's own registration was not met, or a bar stood outside a promise, while the reported number was right and the departure disclosed | 4, `rejected` |
| the reason did not engage the finding's scenario, the number right | 1, `rejected` |

The ten faulty ones were of two kinds: the claim as reported does not
hold (9), and a promise left unjudged decided `stands` instead of `not
assessable` (1).

A person reading `rejected` cannot tell whether to repair the number,
rewrite the reason, register anew, or change the effect — and a later
policy on the review cannot be measured per cause, because the records do
not carry it.

**Proposal.** Keep the three verdicts and what each releases. A `rejected`
names one ground from a closed list, written after the verdict word and
recorded beside the why:

| ground | meaning | the way out the gate names |
|---|---|---|
| `claim` | with the finding true, the number or a verdict as reported does not hold | repair and measure again, or hand over |
| `effect` | the fault leaves a promise unjudged: `<ID> not assessable`, not `stands` | decide again with that effect |
| `registration` | the code or the claim departs from the protocol's own registration (a scope not implemented, a bar outside a promise) | repair to the registration, or register anew (`[replaces]`) |
| `reason` | the reason does not engage the finding's scenario; whether the claim holds is not shown either way | decide again with a reason that engages it, citing what the run shows |

`insufficient` keeps its meaning (the page does not let the reviewer
tell) and names what is missing, as now.

**What it changes.** The way out per ground (`decision_review.rejected_way`
today gives one for all). The record gains one field; the review stays
bound as now (decision digest, claim digest). Nothing is released that is
held today: every ground still holds a BLOCKER's number.

**What it does not change.** The verdicts, the hold, the contested rule
(every draw counts), the review's inputs.

**Risks.** A second judgement can be wrong where the verdict is right — a
`claim` named `reason` would send the person to rewrite a reason over a
wrong number; since the hold is the same, the cost is a misdirected way
out, not a release. Parsing gains a field (refused when missing or
outside the list, as a verdict word is). Agreement on the ground across
draws is unknown; the verdicts agreed on 13 of 15 in the earlier replay.

**Before adoption.** Replay the stored review prompts with the amended
instructions (model calls; the plan, cases, expectations and cost are
fixed beforehand in the internal evidence). The grounds may overlap — a
scope not implemented can make the claim wrong too — so the replay asks
for one main ground and allows further ones. Two questions, judged apart:
*repeatability* (do two draws give the same verdict and the same main
ground) and *correctness* (does the main ground fit the case as checked
against code and data). A faulty acceptance may rightly get
`registration` as well as `claim`; a right number does not rule `claim`
out, since the Conclusion drawn from it can be wrong. Only if both hold
does a change follow: the instructions, the parser
(`decision_review.parse_review`), the record (`formats/reviews`) and
`rejected_way` in one step, with twin tests per ground.

**Replay (2026-11-02).** The stored review prompts of the reviewed cases,
and prompts rebuilt with the labkit each review ran with, were answered
under the shipped instructions and under the amended ones, two draws each,
with acceptance limits fixed before any call. Stopped after 37 of 68
answers: one limit failed — `claim` named twice on a correct decision whose
number and Conclusion had been checked. The verdicts did not move (the two
arms agreed on every pair made), and no faulty decision was upheld. Two
counter-examples carry forward to any next version:

- `effect` and `registration` overlap: a promise the run never computes is
  both unjudged and a departure from the registration, and the reviewers
  named `registration` every time. A main ground steers the way out only
  if the grounds are disjoint for such cases, or their order is fixed.
- `claim` as worded ("the Conclusion drawn from them does not hold") let the
  reviewer judge an unqualified Conclusion against the world rather than
  against its registration and the task's own method.

The open limits and the cases are kept in the internal evidence. A new
round waits until both points are settled.

