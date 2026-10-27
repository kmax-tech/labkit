# One experiment workflow: instruction reading probe (2026-10-27)

The stamped entry guide now separates the experiment's kind, repeat cost
and scientific type, then gives one workflow with high-cost additions at
the relevant steps. It replaces the separate low/high sequences and the
low-lane instruction to stop reading before the shared setup section.
The initial guide had 3,069 words; the final guide has 2,127. Word count
describes the edit, not a measured improvement in understanding.

## Sources and method

The change is to `labkit/templates/AGENTS.md.template`; no experiment
settings, historical instructions, package pins or gate contracts are
changed by this instruction edit. The package's workflow and README point
to the shared sequence. Existing concurrent gate changes were left to
their author; checks below exercise the shared working state, not an
isolated estimate of this edit's effect.
The parallel integration commit `5c4479c` includes the final template and
its changelog entry; the archived final instructions match that template.

Evidence is preserved beside this note:

- [Previous instructions](2026-10-27-common-workflow-reading-probe/entry-instructions-before.md).
- [First candidate](2026-10-27-common-workflow-reading-probe/entry-instructions.md),
  [twelve cases](2026-10-27-common-workflow-reading-probe/cases.txt) and
  [assessment contract](2026-10-27-common-workflow-reading-probe/assessment-contract.txt),
  recorded before answers were requested.
- [Template-only answers](2026-10-27-common-workflow-reading-probe/answer-entry.md):
  one independent reader with no parent conversation, restricted to the
  candidate and cases, no implementation access or experiment execution.
- [Contract review](2026-10-27-common-workflow-reading-probe/contract-review.md):
  a different independent reader, allowed the diff and immediate relevant
  implementation to establish actual obligations.
- [Final instructions](2026-10-27-common-workflow-reading-probe/entry-instructions-final.md),
  [targeted follow-up answers](2026-10-27-common-workflow-reading-probe/answer-final-boundaries.md)
  and [final contract review](2026-10-27-common-workflow-reading-probe/contract-review-final.md).

Neither reader's model was overridden. The targeted follow-up used the
same comprehension reader after its first answers: it is not another
independent cold sample. There is no original-guide comparison group and
no task-success or model benchmark.

## What readers understood and what was corrected

| Cases | Observed reading |
|---|---|
| 1–3: kind, cost, type and skeleton | A fast RandomForest remains fit; expensive compute skips show/probe but owes preflight and freeze; low-cost apply still owes criterion and analysis audit. Running the data-profile helper is not the judgement. |
| 4–5: completion and repair | Conclusion precedes adoption; generated results and authored explanation are distinct. Both leaking features need correction and diagnosis, followed by a new run and covering audit. |
| 6–7: miss and unassessable admissibility | An honest miss can be reported; changing a margin is no repair. An A limit withholds all C verdicts without rewriting raw metrics. |
| 8–10: reviews and recovery | Changed claims need their owed review; unchanged redraws release nothing. An unadopted run is discussed through the existing structured command and report review. Replacement preserves the earlier verdict and is distinguished from an independent question. |
| 11–12: delivery and evidence | A green gate does not establish an external output-path requirement. Decisions and generated projections may be updated through their tools while earlier evidence is preserved. |

The contract reviewer found four specific omissions in the first
candidate. They were corrected before finalizing:

1. A high-cost measurement-code repair must reopen `frozen = false`, keep
   the registration unchanged, renew preflight coverage and freeze again
   before the new measurement. Otherwise preflight sees a stale frozen audit.
2. Dismissing or deferring a carried BLOCKER needs an upholding decision
   review even without an earlier rejected review.
3. Audit, decision and review commands preserve their explicit
   `--protocol` selection when an area contains several protocols.
4. Raw output retains the existing obligation for a real prompt/answer
   pair per model finding, not merely generic examples.

The final version also defines C/A/B and gives full interpreter/script
paths for show/probe. In targeted cases 13–16 the comprehension reader
identified all four corrected obligations. It noted that frozen/audit
head fields have no dedicated setter command, the generic command
examples still rely on the explicit multi-protocol rule, and raw evidence
may be shared across findings only when it actually supports each one.
The final contract review reports zero remaining concrete findings.

## Verification and limits

- Real CLI smoke: stamp a temporary lab and low compute, high compute,
  low fit and high model-apply areas; inspect the stamped AGENTS.md and
  the printed next steps. No model calls or measurements were run.
- Focused tests after the final edits: **108 passed, 37 subtests passed**
  (`test_ways_out`, `test_scaffold`, `test_stamped_fences`,
  `test_workflow_example`, `test_rules`).
- Ruff check and format check, pyright and the standard's rule ledger
  check are clean. `git diff --check` is clean.
- Full suite outside the filesystem sandbox: **2,059 passed, 1 skipped,
  6,427 subtests passed**. The first sandboxed attempt failed two stop-hook
  tests because `ps` was prohibited; it was not treated as a clean run.
  The suite was repeated with the required process access and passed.

This establishes instruction comprehension in selected hypothetical
situations and consistency with the checked implementation. It does not
establish that a cold agent follows the workflow under time pressure,
repairs the real task, spends less, or avoids every escape route. A future
execution probe must record this new stamped text as an intervention;
the existing repair attempt keeps the instructions and pin it actually used.
