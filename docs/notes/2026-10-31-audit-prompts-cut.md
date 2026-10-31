# The audit prompts cut (2026-10-31)

The prompts of the agents labkit calls (`labkit/agents/*.agent.md`) went
through the sentence filter the stamped `AGENTS.md` went through
(docs/notes/2026-10-30-agent-surface.md, step 7): an instruction the agent
acts on stays, one per sentence, the condition first; a date, an incident
and a reason that only explains go; the answer format the parser reads
(`labkit-audit`'s finding, `FIX`, `READ`, `check:`, `verdict`/`scope`, the
refusal line, the decision and claim lines) stays word for word. The rules
each prompt cites are the part of the standard the caller inlines
(`audit.cited_rules`), so their set and order stay as they were. The kept
text then went through the self-check of the SimpleEnglish skill
(`~/projects/SimpleEnglish`, procedural register for agent prompts): a
sentence joined by a semicolon became two, `may` became `can` or went, a
list item lost its trailing semicolon. Kept as written: the quoted
warning a test binds, the scope format and quoted examples.

| Prompt | Words before (body, head comment dropped) | After | What went |
|---|---|---|---|
| `experiment-preflight` | 3,091 | 2,429 | dates and incidents, the reasons behind the low-cost note line and the cut by reversibility, repeated clauses |
| `decision-review` | 884 | 868 | one tangled sentence rewritten, `--from-run` named as the adoption |
| `code-clarity` | 809 | 738 | where each rule was observed |
| `report-review` | 661 | 662 | semicolon chains split |

Built on its own branch (`audit-prompts`), kept out of the release the
cold round 21/60 measures: cut in the same round, a change in the round
could not be told from a change in the audits. Its measure is the
injection benchmark — does the guaranteed tier still hold, and do the
audits still find the injected faults — not the round.

## Where the removed sentences came from

The evidence behind each instruction, kept here so the prompts carry
only the instruction:

- **Refuse an empty registration** (preflight): an audit of the unfilled
  template, 2026-09-08 — eight minutes, the top finding void.
- **Read real output rows** (preflight): 2026-09-09, a verdict that flipped
  with capitalisation passed two code-only audits; 2026-10-05, two request
  types were in effect unchecked (8 of 8 accepted) until a review read the
  data (coding-style CODE-011 Verify against the real system).
- **Read the result part as a stranger would** (preflight): 2026-10-07, a
  sound, audited protocol read "far too dense".
- **A number you cannot read becomes an assignment** (preflight): the
  calibration of 2026-09-08 showed that the findings on gates without an
  anchor live there.
- **One runner** (preflight's head comment): the Claude subagent copy
  drifted from this file once (2026-10-07) and read the whole standard
  twice per audit; `labkit.run.llm` has been the one runner since 0.79.0.
- **The clarity rules 9–16** come from the code-navigation rounds 11–15
  (2026-10-08, `docs/usability/2026-10-07-code-navigation.md`) and the
  audits of areas 17 and 18 (2026-10-09): rule 9 template residue (area
  18), 10 a term before its definition (round 15), 11 question and answer
  apart (round 15), 12 a conjunct missing from the formula's first
  sentence (area 18, a criterion left out), 13 a case id without its kind
  (round 15), 14 two languages without a shared word (round 15), 15 a
  value written as prose (area 17), 16 an ordinal where a name belongs
  (2026-10-09). The house copy `~/.claude/agents/code-clarity.md` keeps
  the rules identical; its cut is the rollout's.
