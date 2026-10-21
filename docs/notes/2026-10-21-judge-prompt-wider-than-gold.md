# A judge prompt wider than its gold legend — 2026-10-21

The judge probe's number fell below its threshold once (0.6667, labkit
42f0ec8, judge-3), right after phase 5 of the 1.0 line. This note keeps
how the cause was told apart from labkit and from the model's draw. The
series report is [the bar after phase 5](../usability/2026-10-21-sandbox-42f0ec8.md).

## The problem

The judge probe asks haiku whether each of twelve sentences makes a causal
claim; C1 passes at 9 of 12 or more (null lane 6 of 12 + 0.25). The cold
agent writes the registered question itself (`PROMPT` in
`01_measure.py`). The gold legend, minted in `00_prepare.py`, says
`causal = the sentence claims one thing caused another`. Three series
before gave 0.8333 or 0.9167; this one gave 0.8333, 0.9167, 0.6667.

## Three questions, three answers

1. **Does labkit compute the number differently?** No. The kept answers of
   the six probes in standard 0.20 (series 9bc8d1c, 42f0ec8) re-evaluated
   with `01_measure.py --eval-only` against `git archive` of both states,
   imported from the archive: every metric equal between the states and to
   the stored `metrics.json`. (Older series carry standard 0.19, which 0.20
   refuses by design.)
2. **Is it the draw?** Partly. One full prompt (`prompt_sha` fa6c6ae28466)
   recurs in four probes over three labkit states, same items and model:
   0.9167, 0.8333, 0.8333, 0.9167. The draw moves the number by one item,
   mostly on c08 and c12.
3. **Is it the prompt?** Yes. Over all eleven judge series on this item
   set (30 probes), three agents wrote "state *or imply*" independently, in
   three wordings (07a610e judge-1, be50b1b judge-2, 42f0ec8 judge-3): 8 of
   12 in all three. The 27 without "imply" scored 9 to 12. The
   intervention — judge-3's final state, only the question swapped, five
   draws each on the host:

| question | correct of 12 | C1 passed | always missed |
|---|---|---|---|
| "…make a causal claim, i.e. state or imply that one thing caused another?" | 9, 9, 8, 9, 9 | 4 of 5 | c08, c10, c12 |
| "Does this sentence claim that one thing caused another?" (the legend's words) | 11, 10, 11, 10, 11 | 5 of 5 | — |

"Imply" asks wider than "claims": a sentence that sets two facts side by
side suggests a link without asserting a cause, and the model says `Yes`
where gold says `not_causal`. It moves the verdict to the threshold's
edge; the draw then decides it. The legend wording was not tuned on the
items (no clause about juxtapositions, which is what the misses are).

## What follows

- labkit is not the cause, and the audit caught it: judge-3's analysis
  audit named the prompt against the legend as a BLOCKER, the agent
  accepted it with the effect `C1 not assessable` — the first time that
  effect was chosen in five series.
- A bar for a format change asks two questions apart: does labkit compute
  and bind the same stored answers alike (replay, no model cost), and do
  cold agents get along with labkit (the probes). Equal accuracy over
  fresh model calls is no fixed bar.
- A skeleton hint at the `PROMPT` TODO — "ask in the gold legend's words"
  — is noted in `TODO.md` (observe at next use), not built: a new demand
  inside the stabilisation window, and the audit catches the case today.
- Method worth reusing: when a model-judged number moves, first replay the
  kept answers under both code states, then group probes by `prompt_sha`,
  then intervene on the one suspected field with repeated draws.
