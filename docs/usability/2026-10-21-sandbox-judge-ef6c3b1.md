# Judge at `seconds`, the effect of an accepted WARNING — labkit ef6c3b1 (2026-10-21)

*Three cold judge probes after an accepted WARNING may name its effect
(`63d1104`) and a cited run id must name a run (`1e78f50`). Harness
`agentsandbox` ecebd21, unchanged since the 07a610e series (selftest 14 of
14 then), image `labkit-probe` of ef6c3b1, model `claude-sonnet-5-5`;
labkit run and scorer ef6c3b1. The question: does an agent name the
effect of the marker-cue finding on its own, and does it reach the
result? Yes in three of three — the effect was chosen from what C1
claims, and it stands in the Answer. Scores and costs:
`2026-10-21-sandbox-ef6c3b1-judge-<n>.{score,costs}.json`.*

| probe | number | cue finding | its effect | Limit lines | log span | misuse | gate refusals | total USD |
|---|---|---|---|---|---|---|---|---|
| judge-1 | 1.0 | BLOCKER | stands | 2 | 2m53s | 0 | 0 | 0.793 |
| judge-2 | 0.8333 | BLOCKER | stands | 2 | 3m01s | 0 | 0 | 0.769 |
| judge-3 | 0.75 | WARNING | stands | 3 | 3m18s | 0 | 0 | 0.857 |

Misuse: the candidates of `failed_calls.py` (4, 4, 3) are text the agent
read (code, audit output) and an `ls experiments/*/tests` that found no
directory; none is a wrong labkit call. Context max 40.7–42.1k tokens.

## The effect, chosen from the promise

The marker cue — every causal item carries a connective, no other item
does, a keyword rule scores 12/12 — was graded a BLOCKER by two audits
and a WARNING by one. All three agents accepted it with `--effect stands`
and argued from C1's sentence, not from the grade:

- judge-1: "C1 claims a threshold on these 12 items, which the number
  meets; it is read within the cue limit, not as proof of causal
  reasoning."
- judge-2: "C1 only claims a threshold on these 12 items, not recognition
  beyond cue wording; reported read within that limit."
- judge-3: "C1 is a threshold against the constant null on these 12
  items; a keyword rule scores as well or better, so a pass shows no more
  than recognition of causal wording."

Each Answer reads `c1_pass = True (run …); read within Limit (audit … #1)`,
with the Limit lines below it; report-check passed in each.

Whether "stands" is the right call depends on C1's sentence, which the
agents wrote as a threshold; the Question asks whether the model
"recognises a causal claim". That gap between question and criterion is
the audit's to judge, and no audit was asked after the limits were
written.

## Every accepted WARNING got an effect

The agents gave `--effect stands` to every accepted finding, not only to
the cue: "one draw, spread unmeasured" in all three, "the pass sits
exactly at threshold" in judge-3. The Answer of judge-3 carries three
"read within" notes. Each is a real limit of the reading; the Answer line
grows with them.

## A fault of the profile

Two agents wrote the marker as `" so "` (padded, to keep it out of longer
words). The whole-word match then needed a non-word character outside
each space, and `…cut, so the…` went uncounted: the profile printed 5/6
where 6/6 was true. Both audits caught it (judge-1 as part of a BLOCKER,
judge-3 as a WARNING), and judge-1 corrected its Data profile after the
run. Fixed in `e3731f2`: a padded marker is refused with the form to
write.

## Open

1. All findings accepted with an effect, the Answer collects one note
   each. Whether the "one draw" kind belongs there or in a shorter form
   is a decision; it is not wrong.
2. The criterion is a threshold, the question a capability; with
   `stands` the gap is named in the Limit line, not resolved.
