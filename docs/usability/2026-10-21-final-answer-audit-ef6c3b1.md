# The finished answer, audited — the ef6c3b1 judge protocols (2026-10-21)

*The unchanged analysis audit (`labkit-audit --mode analysis`, labkit
ef6c3b1, alias opus) run once more on copies of the three finished judge
protocols, their Answers, Limit lines and decisions written. The
question: does the semantic audit judge whether the answer, read within
its limits, still answers the research question ("does the model
recognise a causal claim?") — or only that C1, a threshold on twelve
items, was met? It names the gap as a finding (judge-1: answering the
question "needs an item set with near cases, which is a new experiment");
what carries it into the finished answer is the Result sentence, and
that sentence nobody wrote (below). Outputs:
`~/projects/labkit-probes-sandbox-ef6c3b1/final-audit/judge-<n>.audit.out`.*

| protocol | verdict | what it found again | what is new | on the answer's limits |
|---|---|---|---|---|
| judge-1 | 0 B · 2 W · 6 READ | the connective cue; one draw | — | readability only: "Real:" unglossed, bookkeeping in Limit #1, no Interpretation field |
| judge-2 | 0 B · 2 W · 6 READ | the cue; one draw | no comparator measures the cue against the threshold; the model's two errors sit on marker-free items, so the cue's influence is undemonstrated | readability only: the Limits out of order, "Real:" unglossed |
| judge-3 | 0 B · 3 W · 7 READ | one draw | C1's chance pass rate at N=12 is about 0.073 and the protocol states none; the prepare run records no `data=` sha | readability only: the Limits #3, #2, #1, Data profile and Limit #2 disagree (5/6 vs 6/6) |

What the audit does with the finished answer: it re-finds the cue and
says C1 "cannot tell causal-claim recognition apart from connective
spotting" (judge-1), "does not separate the model from the cue"
(judge-2), and judge-1's WARNING closes with "Answering the question
itself needs an item set with near cases, which is a new experiment" —
so the audit does say the question stays open while C1 passes. None of
the three says whether "stands" is the right effect. It reads the Answer
and the Limit lines as text for a person — order, glosses, repetition —
and suggests an Interpretation field. A green report-check here is
mechanical consistency, as expected.

Where the finding is lost (read 2026-10-21, after this audit): the
Summary's Result field — "the answer to the question above, in at most
two plain sentences" — is in all three protocols the Answer line word for
word, a dump of ten metric keys with the "read within Limit" tails.
`protocol-fill --from-run` wrote it there (Result was among the fields it
writes), and the AGENTS.md hint "reword the Result line for a person if
you like" was followed by none of the three. The one field meant to say
whether the question is answered held machine text; the audit's READ
lines name exactly that ("The Summary is a dump of metric keys", "The
Answer repeats the Summary word for word"). The analysis audit runs before
the limits are decided and the answer is written, so it cannot judge the
finished Result; what it found has to be carried over by the author, in
that sentence. Consequence (decided 2026-10-21): `--from-run` writes the
Answer and the Runs line and leaves Result to the author, who answers the
question in two sentences — "C1 met on these twelve items; whether the
model recognises causal claims independent of connectives stays open";
`protocol-check` already holds an empty Result after a measure run as a
must. A second audit after the write-back, or a third effect form, waits
for a judge series on that change.

Found on the way and fixed: the Limit lines stood in reverse record order
(`72d2e12`), named by all three.
