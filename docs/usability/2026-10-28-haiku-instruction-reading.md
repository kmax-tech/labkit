# Instruction reading probe with Haiku readers (2026-10-28)

*The twelve cases of the [2026-10-27 probe](2026-10-27-common-workflow-reading-probe.md),
read for the first time by the model that works under these instructions
in the probes: Claude Haiku 4.5. The earlier probes had no Haiku reader
("No Haiku run was available", 2026-10-26). Comprehension only — not task
success, not a model comparison.*

## Setup

- Instructions: `labkit/templates/AGENTS.md.template` at sab-cases-on-main
  f16670a — labkit main fddb01b plus the deliverable paragraph (b21f917) —
  copied unchanged to [instructions.md](2026-10-28-haiku-instruction-reading/instructions.md).
- [Cases](2026-10-28-haiku-instruction-reading/cases.txt): the twelve cases of
  2026-10-27, unchanged except the file name and "answer as your final
  message" in the opening rules.
- [Assessment contract](2026-10-28-haiku-instruction-reading/assessment-contract.txt),
  written before any answer: the 2026-10-27 contract with two updates for
  text changed since — case 9 (the handover command is now documented) and
  case 11 (the deliverable paragraph now covers it).
- Readers: three independent Haiku 4.5 subagents, fresh context, told to
  read instructions.md and cases.txt only, run nothing and write nothing;
  answers [1](2026-10-28-haiku-instruction-reading/answer-haiku-1.md),
  [2](2026-10-28-haiku-instruction-reading/answer-haiku-2.md),
  [3](2026-10-28-haiku-instruction-reading/answer-haiku-3.md), extracted verbatim
  from their transcripts. Reader 1 reports one call of an unrelated docs tool
  that changed nothing; its answers rely on the two files only.

## Result

All three readers answer all twelve cases as the contract expects: 36 of 36
supported, none wrong, none incomplete on a contracted point. Each answer
cites the lines it rests on. The instructions carry Haiku through every
decision the cases test: kind, repeat cost and type; the low and high
additions; Conclusion before adoption; a full correction before `fixed`;
the miss reported first; not assessable under an A limit; review
staleness and `--again`; the discussion or handover path; replacement;
the external output; `--decide` with evidence preserved.

## What the readers could not settle

Counted by how many of the three name it unprompted:

| Gap | Readers | Where |
|---|---|---|
| Whether copying the area's output file to the task's path counts as "written from the measurement" | 3 | case 11; the deliverable paragraph |
| How to find an area's pin, and what governs after a pin upgrade | 3 | case 12; lines 3–4, 61–64 |
| Where a deliberately changed follow-up discloses what was already seen, and how it differs from an independent question | 3 | cases 6, 10; lines 254–258 |
| Whether an analysis audit with no findings is the "decided covering" audit adoption needs | 2 | case 4; lines 203–204 |
| How to change the Conclusion after adoption | 2 | case 8; line 179 says "before adoption" |
| Commands and scripts named but not spelled out (`02_analyze.py --check`, the compute script) | 2 | lines 139, 204 |
| Whether an unfixed BLOCKER blocks adoption; the `[[replaces.change]]` TOML form; the `<PROTOCOL>` placeholder; the ID form in `--effect "<ID> not assessable"`; `type` for a pure count | 1 each | various |

The cases leave the held-out labelled rows of case 1 and the type of cases
2 and 3 open; readers named that too, but it is the cases' gap, not the
instructions'.

## Next

- The first gap is in the deliverable paragraph of this branch: say that a
  copy of the run's own output is fine and a file recomputed apart from the
  run is not (done in the commit after this note, with a cold read).
- The others go to labkit main's author: the pin question, the follow-up
  disclosure, the empty audit's coverage and the post-adoption Conclusion
  were each raised by two or three of three readers.
