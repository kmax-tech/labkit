# AGENTS.md clarified for Haiku readers: rounds two and three (2026-10-28)

*Round one (branch `sab-cases-on-main`, `2026-10-28-haiku-instruction-reading.md`):
three Haiku 4.5 readers answered the twelve cases of the
[2026-10-27 probe](2026-10-27-common-workflow-reading-probe.md) as
contracted and named four gaps of AGENTS.md by two or three of three: the
pin, a follow-up question, an analysis audit with no findings, the
Conclusion after adoption. This branch (`agents-clarity`, from main
ea8d060) states each as labkit does it and reads the result again with
fresh Haiku readers. Comprehension only, not task success.*

## What labkit does, and what the text now says

Established by a separate reader of the code with path:line evidence; the
load-bearing lines checked again by hand (`protocol_fill.py:138`,
`reviews.py:99`, `test_findings.py:853`).

| Gap | labkit's behaviour | AGENTS.md now |
|---|---|---|
| Pin | the `labkit` line of `requirements.lock` (else `.txt`), for the repository (`scope_sha.find_pin`); in every area's stamp (`test_scope_sha.test_pin_is_part_of_the_stamp`); the head's `standard` is the protocol format (`protocol_block.py:38-48`); another standard is refused (`protocol_block.py:613-621`) | where the pin is, `labkit-check`, `standard` is the format, a raised pin leaves no earlier audit covering; reproduce an old protocol at its commit with a venv from its own lock, new work in a fresh area |
| Empty analysis audit | a record with no findings covers the state it saw (`findings.audit_coverage`); earlier decided BLOCKERs need the audit's own fix verdict (`report_check.followup_findings`) | it covers; nothing to decide; it re-checks earlier BLOCKERs itself, you add nothing |
| Conclusion after adoption | a filled Conclusion changes only with `--force`; the result and the REPORT.md block are rendered from the run; every decision review binds the Conclusion and goes stale (`reviews.claim_digest`) | `--force`; result and block stay; reviews redone where owed; the report's explanation must match |
| Follow-up question | only `[replaces]` tells a replacement from another question; no field holds a follow-up's disclosure (`Prior threads` is unchecked and missing at low) | a replacement only for a registration that cannot be answered as written; a later question — a miss included — is its own protocol, names the earlier one and what it showed in its Question / hypothesis, type `exploratory` (a place for an existing duty; no gate checks it) |

Also on this branch: the answering-run copy rule of the deliverable
paragraph (round one's three-of-three gap; `71f719d` on `sab-cases-on-main`).

## Round two: sixteen cases, three readers

[Cases](2026-10-28-haiku-instruction-reading-2/cases.txt) — the twelve plus
13 pin, 14 follow-up, 15 empty audit, 16 Conclusion after adoption —
and [contract](2026-10-28-haiku-instruction-reading-2/assessment-contract.txt),
committed (8a62409) before any answer; answers
[1](2026-10-28-haiku-instruction-reading-2/answer-haiku-1.md),
[2](2026-10-28-haiku-instruction-reading-2/answer-haiku-2.md),
[3](2026-10-28-haiku-instruction-reading-2/answer-haiku-3.md), verbatim.

All three answered all sixteen cases as contracted, with one exception and
two shared doubts:

- Case 14: all three hesitated over whether another model after a miss is
  "a new attempt at the same question" and so a replacement; one stayed
  undecided. The sentence was too wide.
- Case 15: all three asked what they must add to the record for an earlier
  BLOCKER ("needs its fix confirmed in that record").
- Case 13: all three asked how to reproduce at the old commit.

## Round three: the three cases, two fresh readers

The three passages revised (9edb14a): a replacement only for a
registration that cannot be answered as written, "a miss included, such as
another model on the same data" named as its own protocol; the audit
re-checks earlier BLOCKERs itself, "you add nothing to the record"; a
checkout of the old commit with a venv from its own lock.
[Cases](2026-10-28-haiku-instruction-reading-3/cases.txt) and
[contract](2026-10-28-haiku-instruction-reading-3/assessment-contract.txt)
committed before the answers
([1](2026-10-28-haiku-instruction-reading-3/answer-haiku-1.md),
[2](2026-10-28-haiku-instruction-reading-3/answer-haiku-2.md)).

Both readers answered 13–15 as contracted and neither hesitated where round
two did: case 14 "no replacement" is read as explicit, case 15 "nothing to
add". What remains named once each: no labkit command for the old checkout
(it is git and a venv), the full path of `02_analyze.py --check`, why
`protocol-check` refuses another `standard` (the text says that it does
not convert, not that this labkit reads only its own standard).

## For labkit to decide

- The refusal of another standard (`protocol_block.py:613-621`) offers
  "update the protocol"; AGENTS.md says not to convert a historical
  protocol. One of them should give way.
- The follow-up rule is a place for a duty no gate checks. Whether
  `report_hold`'s hint or the analysis audit should look for it is open.
