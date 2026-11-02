# 2026-11-02 — grounds for a decision review that does not uphold (proposal)

Status: proposal. The reviewer's instructions (`labkit/agents/decision-review.agent.md`)
and the gates are unchanged.

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

**Before adoption.** Replay the stored review prompts of the 26 decisions
with the amended instructions, two draws each (model calls): accept when
every faulty decision gets `claim` or `effect`, no correct one gets `claim`,
and the grounds of the two draws agree on most decisions; then change the
instructions, the parser (`decision_review.parse_review`), the record
(`formats/reviews`) and `rejected_way` in one step, with twin tests per
ground.
