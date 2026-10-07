# Protocol reading, round 7 (2026-10-07): how the protocols read for a person

Question: with the 0.57 template (legend out, answer first, lists instead of
chains), do cold agents write protocols a cold reader understands — and
what still stops the reader?

Writers: four cold Sonnet agents (`count` ×2, `judge` ×2), labkit
`5fec2f7`, seconds track; their prompt carried only the seconds section of
the lab CLAUDE.md (round 6 carried the whole file). Readers: one cold
Sonnet agent per protocol, the protocol alone (`usability reader`), answer
held to the run's number (`usability read-score`); for comparison two real
protocols of uniagent (areas 08, 09, written under the old template).
Archive: labkit-paper `data/raw/agent-traces/2026-10-07/round7/`.

| protocol | lines | form lines before the first field | longest field (chars) | reader: number right | reading time | effort 1–5 | unclear terms (of them from the stamped form) |
|---|---|---|---|---|---|---|---|
| count-1 | 52 | 3 | 184 | yes | 19 s | 2 | 9 (8) |
| count-2 | 55 | 3 | 284 | yes | 16 s | 3 | 7 (7) |
| judge-1 | 75 | 3 | 260 | yes | 15 s | 3 | 10 (5) |
| judge-2 | 78 | 3 | 284 | yes | 16 s | 4 | 16 (11) |
| uniagent 08 | 160 | 37 | 1465 | — | 21 s | 5 | 15 (3) |
| uniagent 09 | 176 | 39 | 1592 | — | 21 s | 5 | 21 (2) |

"From the stamped form" is a heuristic: the term's first word occurs in
the template. The uniagent protocols record real, multi-arm experiments;
the probes are toy tasks — the comparison shows the form's share, not that
the template alone halves the effort.

- Every reader got the number right and stated the result and its limit in
  its own words.
- In the new protocols most of what readers could not place comes from the
  stamped form, not from the writer: `AS-015`/`AS-017`/`AS-050`, `scope
  sha`, `preflight audit`, `frozen`, `runlog`, `lib exp`,
  `protocol-fill`/`protocol-check`, and the open placeholder `Analysis
  audit †` (owed later at seconds, stamped now). Sources: the comments in
  the toml head, the pointer line, the placeholder.
- What the writers left unglossed: `MARGIN`, "lane", item ids (`c08`),
  the model alias and `models.toml`.
- In uniagent's protocols the unclear terms are the domain's (areas,
  cases, rule names, arms) — the writer's vocabulary, glossed nowhere a
  reader finds it.

Levers for the next round, one at a time:

1. the toml head without comments (their content is in the field guide);
2. `Analysis audit †` not stamped at seconds (it is owed when the number
   steers a decision, not in this session);
3. the writer glosses its own coined terms in `Terms of this protocol`
   (constants such as `MARGIN`, the lanes) — an instruction, measured by
   the reader's unclear list.

## Round 8: the three levers together (labkit 0.58.0)

Same set-up as round 7; the toml head without comments, no `Analysis
audit †` at seconds, and `Terms of this protocol` (template and the
seconds track of the lab CLAUDE.md) asking for every coined name.

| probe | round 7 → 8: lines | form terms unclear | writer terms unclear | effort | writing time |
|---|---|---|---|---|---|
| count-1 | 52 → 40 | 9 → 7 | 0 → 0 | 2 → 2 | 97 → 122 s |
| count-2 | 55 → 40 | 7 → 9 | 0 → 0 | 3 → 2 | 88 → 91 s |
| judge-1 | 75 → 70 | 7 → 4 | 3 → 3 | 3 → 3 | 128 → 144 s |
| judge-2 | 78 → 68 | 11 → 4 | 5 → 6 | 4 → 3 | 122 → 147 s |

"Form" and "writer" now by a keyword list over the reader's unclear
terms (head keys, the pointer line, rule ids, commands vs the rest). n = 2
per task: one term or one effort point is noise.

- Less form helps: the judge readers' form terms halve; what stays is the
  head's own keys (`standard`, `frozen`, `preflight_audit`, `cost`) and the
  pointer line's command names.
- The Terms instruction shows no effect: `MARGIN`, "lane", the model alias
  stay unglossed; the writers write a little longer.
- A cost of 0.57: with the legend gone the protocol shows no `[C1]`
  example; one writer wrote `c1:` and searched the standard for the form.
- Every reader got the number right — the measure no longer separates.

How understanding is measured, and its limits: the number is held to the
run mechanically; question, result, limits and next step are free text
and not scored; unclear terms and effort are the reader's self-report;
reading time comes from the transcript. The reader is a language model,
which knows terms a human newcomer does not — the measure shows what
disturbs, less how much it disturbs a person.

## Round 9 (2026-10-07): the Summary for a person, a stricter reader

Changes under test (labkit 0.59.0, `66c3f55`): every protocol with a run
opens with a Summary of three lines — Result (two plain sentences carrying
the question, no ids), Limits, Next step — on the seconds cut too; the toml
head and the pointer stand at the end under `## Head`. The reader prompt
changed with it: a newcomer who knows basic statistics, not this lab;
three answers held to the run (the number, whether the criterion held,
whether every admissibility condition held), plus what it understood
after the first ten lines.

Writers: four cold Sonnet agents, seconds track, as in round 8. Readers:
one cold Sonnet agent per protocol — the four new protocols, the four of
round 8 (head on top) re-read with the new prompt, and uniagent's areas 08
and 09 before and after an editorial rewrite of their Summary (same
content, head at the end, legend out). A qualitative pilot: one reader per
protocol, two writers per task — it shows directions, it proves no rule.
Archive: labkit-paper `data/raw/agent-traces/2026-10-07/round9/`.

| protocol | lines | form lines before the first field | checkable answers right | effort 1–5 | unclear terms | result stated after ten lines |
|---|---|---|---|---|---|---|
| count-1 (0.59) | 50 | 0 | 3/3 | 2 | 22 | yes |
| count-2 (0.59) | 50 | 0 | 3/3 | 3 | 17 | yes |
| judge-1 (0.59) | 73 | 0 | 3/3 | 3 | 22 | yes |
| judge-2 (0.59) | 73 | 0 | 3/3 | 3 | 19 | yes |
| count-1 (round 8) | 40 | 3 | 3/3 | 3 | 15 | no |
| count-2 (round 8) | 40 | 3 | 1/1 | 2 | 18 | no |
| judge-1 (round 8) | 70 | 3 | 3/3 | 3 | 14 | no |
| judge-2 (round 8) | 68 | 3 | 3/3 | 3 | 21 | no |
| uniagent 08 before | 160 | 37 | 2/2 | 5 | 27 | no |
| uniagent 09 before | 176 | 39 | 2/2 | 5 | 27 | yes (claimed) |
| uniagent 08 after | 116 | 0 | 2/2 | 5 | 29 | yes |
| uniagent 09 after | 130 | 0 | 2/2 | 5 | 23 | yes |

"Checkable" counts what the run decides: round 8's count-2 registered no
criterion, uniagent's number is not scored (several arms, no single number
the result rests on). Writer time by log span: 1:09, 2:15, 2:28, 2:26.

- **Every checkable answer is right, in every version.** The stricter
  reader does not separate the versions on comprehension either; at these
  sizes a careful reader extracts the verdict from any of them.
- **The Summary moves the answer to the top.** Every reader of a 0.59
  protocol and of the rewritten uniagent protocols stated the result from
  the first ten lines; the readers of round 8 saw the head and the pointer
  there. One exception counts against the measure itself: uniagent 09's
  reader "before" claims the result after ten lines, where the old file
  shows the legend — a reader that has seen the whole text cannot report
  what it knew at line ten. That answer is self-report, not measurement.
- **Effort does not follow the form.** Moving the head and dropping the
  legend cut uniagent's protocols by 44 and 46 lines and left effort at 5
  and the unclear terms at 23–29: what a newcomer cannot place is the
  domain — arms, areas, case ids, rule and profile names, the gold
  version — not the form. The new probe protocols are longer than round 8's
  (50 vs 40) because the Summary is now written at seconds too.
- **Writers fill the new fields without being told twice.** All four wrote
  Result, Limits and Next step in plain words with no ids; three wrote
  "Next step: none", correct for a one-off count or judge.
- What the writers report as time sinks is the fill, not the reading:
  12–14 separate `protocol-fill` calls, `type` not settable by
  `protocol-fill`, the Runs line still a placeholder, `evaluate()` having
  to return `c<i>_pass` learnt from the script's docstring.

Consequences:

1. Comprehension is saturated at this protocol size; the next measure of
   readability is the newcomer's vocabulary — the unclear terms that are
   the writer's coinages, held to the protocol's Terms field.
2. "After ten lines" needs a reader that sees only ten lines (a second
   prompt with the first ten lines), not a question to one that saw all.
3. For uniagent the lever is a glossary of the domain words in Terms, not
   more form work.

## Round 10 (2026-10-07): a reader of the first ten lines, terms by layer

Instruments new in labkit 0.60 (`16f18ae`), applied to round 9's twelve
protocols without new writers:

- **glance** — a reader that gets only the first ten lines of the file, as
  they are, and answers what was investigated, what came out (with the
  number and whether the criterion held), how sure it is, what follows,
  and what it could not place. Which Summary fields begin in those lines
  is checked mechanically; the excerpt's characters are reported beside
  its lines, because one field per long line holds more text than a
  wrapped one.
- **terms** — every term the full reader of round 9 could not place, held
  to two layers: inside the Summary it must be plain there; elsewhere it
  may occur in Terms or in a glossary note Terms links (occurrence:
  static evidence). A second reader judges whether the entry explains the
  term (uniagent 08 and 09 only, after the glossary note
  `notes/theorie/begriffe.md` was written and linked from every Terms
  field).

| protocol | chars in 10 lines | Summary fields in 10 lines | glance: number right | glance: criterion right | glance: of question/result/how sure/what follows answered |
|---|---|---|---|---|---|
| count-1, count-2 (0.59) | 322, 324 | all three | yes | no (null) | 3/4 |
| judge-1, judge-2 (0.59) | 492, 484 | all three | yes | no (null) | 3/4 |
| round 8, four protocols | 297–303 | none | no | no | 0/4 (one: 1/4) |
| uniagent 08, 09 before | 513, 560 | none | — | no | 0/4 |
| uniagent 08, 09 after | 1012, 1109 | all three | — | yes | 4/4 |

- **The first ten lines decide it.** With the head on top no reader took
  anything away — not the question, not the result. With the Summary on
  top every reader had question, result and limit; with uniagent's
  rewritten Summary also the verdict and the next step.
- **A gap in the 0.59 Summary:** the four probe Summaries gave the number
  but never said whether the bar set before the run was met, and all four
  readers answered `null`. uniagent's Summaries said it ("missed the
  criterion") and were read right. Fixed in 0.60.1: Result says whether
  the bar was met. "Next step: none" reads as no next step (`null`) —
  correct, not a gap.
- **Characters, not only lines:** uniagent's ten lines hold about twice
  the text of the probes'. The comparison within a protocol (before vs
  after) is fair; across writers it favours long lines.
- **Terms in the Summary:** of the glance readers' unclear terms in the
  0.59 probes, 4–5 of 7–8 stand in the Summary — "agent audit",
  "deterministic count", "placebo question", the alias "Haiku". These are
  the writer's words in the one place Terms cannot rescue.
- **Glossary coverage (uniagent, full reader of round 9):** the terms the
  reader could not place now occur in Terms or the glossary for 24 of 29
  (area 08) and 16 of 23 (area 09). Judged as explained: 12 of 24 and 12
  of 16. Not explained, or not covered: the lab's process words (scope
  sha, preflight and analysis audit, labkit, the dev split, `predict.py`,
  the model alias, Kassel), raw ids and run ids, and the intent ids as
  conjunct lists ("C1–C5") — those name things the glossary does not, or
  only by mention.
- **A measurement error of mine, caught before it counted:** the first
  judge saw, for most terms, the protocol's pointer line to the glossary
  instead of the definition (`entry_for` took the first mention) and said
  "not explained" — 4 of 16 and 7 of 24. Fixed in 0.60.1; the first
  judgement stays in the archive under `terms-judge/v1-wrong-entries/`.

Consequences:

1. The Summary carries the protocol for a reader who stops early — that is
   now measured, not argued. It must carry the verdict (0.60.1).
2. The next readability lever is the Summary's own words: the glance
   reader's unclear terms there are the writer's, and only the writer can
   fix them.
3. uniagent's glossary covers the domain; the lab's process words (audits,
   scope sha, split, alias) are the gap.

Archive: labkit-paper `data/raw/agent-traces/2026-10-07/round10/`.
