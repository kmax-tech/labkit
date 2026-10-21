# Judge at `seconds`, limits and data profile — labkit 07a610e (2026-10-21)

*Three cold judge probes after two changes: an accepted BLOCKER says its
effect on the verdicts and the protocol carries it as a `Limit` line
(`b7802b3`); the stamped `00_prepare.py --audit` prints a data profile per
gold class, and its judgement is part of the registration with a model
(`df504b4`). Harness `agentsandbox` ecebd21 (`agentsandbox selftest`
with the agent check before the series: 14 of 14 held), image
`labkit-probe:0c5a073d2eae`, model `claude-sonnet-5-5`; labkit run and
scorer 07a610e. The series asks two things: does a limit reach the
protocol, and is the data profile judged before the measuring run? Both
held in three of three where they applied. Scores and costs:
`2026-10-21-sandbox-07a610e-judge-<n>.{score,costs}.json`.*

| probe | number | verdict as reported | log span | misuse | gate refusals | context max | total USD |
|---|---|---|---|---|---|---|---|
| judge-1 | 0.6667 | C1 not assessable with this run (accepted BLOCKER) | 2m56s | 0 | 0 | 41,300 | 0.855 |
| judge-2 | 0.8333 | c1_pass = True | 3m17s | 0 | 0 | 41,175 | 0.842 |
| judge-3 | 0.9167 | c1_pass = True | 2m30s | 0 | 0 | 39,712 | 0.736 |

Misuse: the candidates of `failed_calls.py` (2, 3, 2) are all false —
"refuses" in code the agent read or in audit output. No `--force` in any
transcript.

## The data profile, before the run

All three agents ran `00_prepare.py --audit` before the measuring run,
chose `MARKERS` (the same six connectives: because, due to, so, made,
prevented, drove) and `CONFOUNDS = ()`, and wrote the Data profile field in
the registration commit — before the run, as the registration now owes.
Each read the profile the same way: any marker in 6/6 causal items and in
0/6 not_causal ones, so a keyword rule alone scores 12/12, and a high
accuracy cannot tell understanding from the lexical cue. Two named the
minimal pairs and called the cue lexical, not topical.

Limit of this evidence: the agents chose the markers after reading the
twelve rows, so the profile confirmed what they had seen. That they would
find a cue they had not seen is not shown here.

## The limit, in the protocol

judge-1 wrote its prompt as "state or imply", as judge-2 did on be50b1b;
the analysis audit raised it as a BLOCKER. The agent accepted it with
`--effect "C1 not assessable"` on the first call, with the reason "tuning
the prompt after seeing the result would be selecting it". `--from-run`
wrote the `Limit (audit 2026-10-21T13-13-analysis #1)` line and "C1 not
assessable with this run" into the Answer and the Result; report-check
passed. The number 0.6667 stays reported, the verdict does not.

judge-2 and judge-3 had no BLOCKER. Their audits raised the marker cue as
a WARNING; both accepted it ("C1 is read as 'beats the English-placebo
null', not as proof of causal understanding"). That limit reached the
protocol through the Data profile field, which says it in so many words —
but not through a Limit line, and the Answer reads `c1_pass = True` with
nothing beside it. An accepted WARNING carries no Limit line.

## Against be50b1b

| | be50b1b | 07a610e |
|---|---|---|
| context max | 33.7k / 38.3k / 35.1k | 41.3k / 41.2k / 39.7k |
| total USD | 2.30 | 2.43 |
| Raw output reworked after the run | 2 of 3 (one with `--force`) | 0 of 3 |
| profile judged before the run | 0 of 3 | 3 of 3 |
| accepted BLOCKER as a limit in the protocol | 0 of 1 | 1 of 1 |

The context rose by 3–8k tokens: the longer AGENTS.md step 3, the
profile output and the Data profile field are more to read. Three runs a
side; no claim on time.

## Open

1. An accepted WARNING that limits how the number reads (here: the cue a
   keyword rule exploits) carries no Limit line; the Answer of judge-2 and
   judge-3 says `c1_pass = True` alone, and the limit stands in the Data
   profile field. Whether accepted WARNINGs owe a Limit line too is a
   decision.
2. A prompt broader than the gold ("state or imply") appeared in two of
   six judge probes across the last two series; the audit caught it both
   times, after the run.
