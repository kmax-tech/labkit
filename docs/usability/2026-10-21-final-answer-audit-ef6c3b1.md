# The finished answer, audited — the ef6c3b1 judge protocols (2026-10-21)

*The unchanged analysis audit (`labkit-audit --mode analysis`, labkit
ef6c3b1, alias opus) run once more on copies of the three finished judge
protocols, their Answers, Limit lines and decisions written. The
question: does the semantic audit judge whether the answer, read within
its limits, still answers the research question ("does the model
recognise a causal claim?") — or only that C1, a threshold on twelve
items, was met? It does not do the first. Outputs:
`~/projects/labkit-probes-sandbox-ef6c3b1/final-audit/judge-<n>.audit.out`.*

| protocol | verdict | what it found again | what is new | on the answer's limits |
|---|---|---|---|---|
| judge-1 | 0 B · 2 W · 6 READ | the connective cue; one draw | — | readability only: "Real:" unglossed, bookkeeping in Limit #1, no Interpretation field |
| judge-2 | 0 B · 2 W · 6 READ | the cue; one draw | no comparator measures the cue against the threshold; the model's two errors sit on marker-free items, so the cue's influence is undemonstrated | readability only: the Limits out of order, "Real:" unglossed |
| judge-3 | 0 B · 3 W · 7 READ | one draw | C1's chance pass rate at N=12 is about 0.073 and the protocol states none; the prepare run records no `data=` sha | readability only: the Limits #3, #2, #1, Data profile and Limit #2 disagree (5/6 vs 6/6) |

What the audit does with the finished answer: it re-finds the cue and
says C1 "cannot tell causal-claim recognition apart from connective
spotting" (judge-1), "does not separate the model from the cue"
(judge-2). It reads the Answer and the Limit lines as text for a person
— order, glosses, repetition — and suggests an Interpretation field.
None of the three says whether "stands" is the right effect, nor that the
question stays unanswered while C1 passes. A green report-check here is
mechanical consistency, as expected; the semantic step that would judge
the limited answer against the question does not exist: the analysis
audit runs before the limits are decided, and in this mode its
instructions read the result part for readability only
(`labkit/agents/experiment-preflight.agent.md`, "read the protocol's
result part as a stranger would").

Found on the way and fixed: the Limit lines stood in reverse record order
(`72d2e12`), named by all three.
