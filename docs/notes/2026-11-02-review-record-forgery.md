# 2026-11-02 — a review or audit record edited by hand releases what it held

**Question.** While checking the handover repair (`14a7fad7`: the handover
no longer binds what a report review writes): can an agent turn a review
that holds a report, or a decision, into one that releases it, and which
checks does it pass? This note records the limit; it adds no protection.

**Smallest case.** Count lab, `report = "REPORT.md"` registered, the run
adopted, `labkit-audit --report-review REPORT.md` naming one claim — the
gate holds the report ("the report review holds this state"). The agent
edits one file, `audits/report-reviews/<minute>-review.toml`, before that
file is first committed: `claims = 1` → `claims = 0`, the `[[claim]]`
table deleted. Nothing else changes. The kept answer
(`audits/answers/<id>-report-review-<hex>.txt`), the journal lines and the
evidence copy in the git directory still name the claim; nothing compares
a record with them (`attempts.evidence_copy`: "it is no check of a
record's content").

| Check | Result after the edit |
|---|---|
| `report-check AREA`, `report-check --if-reported --staged` | all clear |
| pre-commit hook | passes; the commit is made |
| `labkit-next` | "nothing holds it — the number may be reported" |
| `labkit-audit --findings`, `attempts.evidence_gaps` (tree, index) | nothing |

The release: the registered report counts as reviewed clean, so the
adopted number may be reported; with a handover, the end without a result
counts as complete.

**Variants.**

- *The record committed first, then edited:* the commit refuses it
  ("changed in the index since HEAD — labkit writes it once"); the tree
  checks (`labkit-next`, `report-check AREA`) said nothing holds until
  2026-11-03 — see "Committed records, 2026-11-03" below.
- *A decision review* (`audits/<minute>-review.toml`): `rejected` → `upheld`
  in three lines (`verdict`, `upheld`, `rejected`) releases the decision
  it judged — here a BLOCKER on the Conclusion decided `fixed`
  (`9c5ce7e9`); the same holds for a `limitation` with `stands` and a
  BLOCKER decided `false-positive`.
- *An analysis record* (`audits/<minute>-analysis.toml`, added on
  `7e80e7a0`): its one `[[finding]]` table deleted and `blockers = 1` →
  `0`, before the record's first commit. Read station by station against
  the unedited twin, which every station holds: `labkit-next` advises the
  adoption; `labkit-adopt` adopts ("finalized, audited, checked") and
  writes the Recorded results; `finalize` says all clear and
  `report-check AREA` holds only for the registered report's missing
  review; once the result block is written and a clean report review
  drawn, report-check is clear, the pre-commit hook passes the commit, and
  `labkit-next` says the number may be reported. The advice alone would
  prove no release; every later station releases too. The kept answer
  still names the BLOCKER.
- *A record deleted* is caught: the journal names it as lost evidence, and
  labkit-audit starts nothing until it is restored.

**What the repairs changed.** Nothing for the cases above: they passed on
`da7b2213` as well. One incidental guard went: before `14a7fad7`, an edited
review record after a handover voided the handover, so the stop held —
for the wrong reason, and the same binding voided the honest review.

**Where the documentation states this limit.** Explicitly only in a
dated note, `docs/notes/2026-10-26-escape-routes-checks-and-exits.md`,
rows 12 ("well-formed: no — no check ties a record to a journal entry")
and 13 ("a review with claims deleted — only when committed"); row 13's
reason, that report and decision reviews are not journaled, is outdated —
they are now (`attempts`, modes `report-review` and `review`). The code
says it in `attempts.evidence_copy`. The current contracts do not:
README's tier table and its instruction "the record is never edited by
hand", `docs/architecture.md` (the chain), `docs/workflow.md` and the
standard name no check of a record's content and no such limit.
`docs/notes/2026-11-02-workflow-simplification.md` says in general that
local files are no immutable history against an agent that can rewrite
every copy.

**Committed records, 2026-11-03.** report-check's first station is now
the pre-commit's own comparison against HEAD
(`evidence.change_blockers`), so report-check, `labkit-next` and the
adoption's check hold a committed record edited in the tree as the
commit does: the record named, its restore from HEAD the way out; a
`--decide` change passes, a restore clears it. Every release that reads
an area's records past that station holds the same comparison for that
area: `labkit-next` before it says a handover ended the protocol,
report-check on a protocol that declares no result (`hold_registered`,
the stop's and the commit's form), a replacement for its predecessor's
area when that is another area (`report_replacement`). Several
protocols of one area share the area's station: a changed record of one
holds them all, as the commit holds the area. Shown on the count lab in
`tests/test_repair_paths.py` (`RegisteredReportRepairs`, the `committed`
tests: a decision review turned `upheld`, an analysis BLOCKER removed, a
report review's claim deleted after a commit past the hook, the same
after a handover) and in `tests/test_replacement.py` (the predecessor's
BLOCKER removed in its own area). The repair-path probe and the
forgery scripts, run on main and on this change, differ only where
intended: forgery B is held in the tree, and the run edited by hand in
case 1 (B3) is named for its restore first; the handover and repair
paths are unchanged (labkit-evidence `978d8a4d`, `logs-747b09d8` against
`logs-01498270`). What stays outside:

- every variant before the record's first commit (the smallest case and
  the analysis record above);
- an edit committed past the hook (`--no-verify`) in an earlier session:
  HEAD holds the edited text, so nothing differs from it, and
  `commit_changes` reads only the current session's commits;
- an edit that also rewrites git's history or the attempt journal's copy;
- the decision lines themselves: `status`, `reason` and `effect` written
  by hand pass the comparison like a `--decide`; what a decision owes (a
  decision review, a follow-up audit) still holds it.

**Out of scope here.** By decision of 2026-11-02 no provenance protection
is added in this work; the limit is recorded. Reproduction: labkit-evidence
`usability/2026-11-02-repair-paths/scripts/forgery.sh`, log
`logs-fe40f50d/forgery.log`; the analysis record
`scripts/forgery-analysis.sh`, log `logs-7e80e7a0/forgery-analysis.log`
(labkit-evidence `b69edafa`); the boundary tests in
`tests/test_repair_paths.py` show what does hold (a changed input owes the
review again, a deleted record is lost evidence).
