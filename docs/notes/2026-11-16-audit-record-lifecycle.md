# What labkit writes into audit evidence

> Bounded inventory, read at `1cf1cfc4` on 2026-11-16. This note proposes no new protection and changes no standard. The origin of a reported numerical result remains a separate contract question in [TODO](../../TODO.md).

The original answer text and the structured audit record are different artefacts. labkit retains the answer text, then creates records that include machine-derived metadata and explicitly mutable decisions. Second reviews and follow-up audits create new files; they do not replace the earlier auditor's findings. A rule that forbids every change to an audit record would therefore forbid the supported decision workflow.

## Findings and limits

1. **High consequence, existing provenance limit:** a syntactically valid record edited before its first commit has no committed baseline for `evidence.change_findings`. The attempt journal and its copy detect missing files, but `attempts.evidence_copy` explicitly does not compare record content. A stored answer does not itself establish that the structured verdict agrees with it. The existing [record-edit replay](2026-11-02-review-record-forgery.md) demonstrates the release consequence on its historical commit; this inventory confirms the relevant comparison boundaries in current code, not a new end-to-end replay of that release.
2. **Medium consequence, decision-history limit:** `--decide` replaces the current status, reason and effect in the existing finding. The report-claim writer likewise replaces status and reason. Neither command records each intermediate decision in `attempts.jsonl`. Intermediate decisions not committed or otherwise retained need not remain reconstructible. Review files bind decisions by digest and retain their own verdict and explanation, but that is not a complete log of every decision revision.
3. **Attribution limit:** the evidence comparison permits changes confined to decision fields. It cannot establish that those bytes were written through `--decide` rather than by hand. The supported writer validates those changes; readers accept valid hand-written decision values too. This is explicit in `findings` and tested by `HandDecisions` in `tests/test_findings.py`. It is not evidence that a malformed or substantively unconfirmed decision is automatically released: the format checks and required second reviews still apply.

These are limits of the current contract and its evidence, not newly decided violations. Local git history and copies are not an independent witness against someone who can rewrite all of them.

## Artefacts and supported writes

| Artefact                                                      | Initial contents and writer                                                                                                                                                                                                       | What later labkit operations change                                                                                                                                                                                           |
|---------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `audits/answers/<attempt-id>.txt`                             | The answer text returned by the backend, kept before parsing by `attempts.Running.keep_answer`; audits and all three review paths use it.                                                                                         | No decision is written into the answer. One running attempt refuses a second `keep_answer`. This is the retained text, not proof of backend authorship.                                                                       |
| `audits/<minute>-preflight[-n].toml` and `-analysis[-n].toml` | `findings.write` creates a new file: auditor findings, counts, parsed subject/rule/check, protocol and code fingerprints, and the run binding for analysis. Findings begin open.                                                  | `findings.write_decision` updates only the selected finding's `status`, `reason` and optional `effect`. It preserves the rest of the text and reads back the expected record before replacing the file atomically.            |
| Follow-up analysis record                                     | The next analysis audit writes a new record with `fix_verdict` entries. `followup.carried_finding` adds unresolved earlier BLOCKERs with a link to the earlier finding; the whole record's counts include these carried findings. | The earlier audit is retained. A carried finding in the new record is subsequently decided like another finding. Its content is not necessarily a verbatim subset of this call's raw answer: labkit also adds the carry data. |
| `audits/<minute>-review[-n].toml`                             | `reviews.write_review` creates a separate second-review file with finding numbers, their decision digests, the reviewed-state bindings, verdicts, reasons and the `again` flag.                                                   | A new draw creates another filename. It does not replace the earlier review or write its verdict into the original finding. A changed decision no longer matches the earlier digest.                                          |
| `audits/report-reviews/<minute>-review[-n].toml`              | `report_reviews.write_report_review` creates the report review, its input fingerprint and the claims identified by the reviewer. Claims begin open.                                                                               | `write_claim_decision` changes only the selected claim's `status` and `reason`; line, kind, original objection and head stay unchanged.                                                                                       |
| `audits/report-reviews/<minute>-claim-review[-n].toml`        | `write_claim_review` creates another file recording the second review of report-claim decisions, bound to the report state and each decision.                                                                                     | Another review is another file. It does not overwrite the first report review or its claim decisions.                                                                                                                         |
| Failed attempt and handover records                           | `failed_attempts.write_failed` creates a fresh failed-call record; `handovers.write_record` refuses an existing path.                                                                                                             | These are not decision containers. A later successful audit or another handover is separate evidence.                                                                                                                         |
| `audits/attempts.jsonl`                                       | Start and end events with mode, model and bindings; the end names the record or failed call and any retained answer.                                                                                                              | Appended to for calls. Decisions are not separate call attempts. A branch-specific copy and HEAD support detection of removed journal entries and files.                                                                      |
| Generated protocol and report lines                           | `protocol-fill --from-run`, `--render` and `--into` use records, run values and review state to render results and limitations.                                                                                                   | These are derived views and may be regenerated. Their changing wording is not a change to the original model answer.                                                                                                          |

Writers: `labkit/gates/audit_call.py:39`, `labkit/gates/audit.py:211` and `:494`; `labkit/formats/findings.py:1207` and `:1850`; `labkit/formats/reviews.py:137`; `labkit/formats/report_reviews.py:257`, `:444` and `:538`; `labkit/formats/attempts.py:1077`; `labkit/formats/followup.py:1`; `labkit/gates/claim_review.py:1`. These line references describe the inspected commit.

## What the current protection checks

`evidence.record_changed` strips `status`, `reason` and `effect` before comparing finding records; `report_review_changed` does the same for report-claim decisions. Beyond these fields, changes to committed audit evidence are held against git. Raw answers and second-review files have no decision-field exception. Closed run evidence has its own protection and is not evaluated as a mutable audit decision.

`attempts.Running.end` copies the new record and answer into the branch's evidence copy before appending the end event. That copy stays as first written when a later decision changes the working record. Comparing the whole record byte-for-byte with that copy would falsely reject legitimate decisions. `attempts.area_gaps` uses it to recover losses; it does not validate the record's semantic correspondence with the answer.

At `1cf1cfc4`, the relevant boundaries are `labkit/formats/evidence.py:129`, `:232`, `:398` and `:470`, and `labkit/formats/attempts.py:973` and `:1008`. A decision review is attached to the current decision through `findings.decision_digest` (`:811`) and `reviews._on_state` (`labkit/formats/reviews.py:327`). That binding prevents carrying an old confirmation to a revised decision; it does not identify who edited the current fields.

There is one narrow historical move-aside exception for an unreadable old report-review format (`evidence.moved_aside`). It is not a general permission to move or replace a currently valid finding record. The journal's extra copies are unavailable outside a git branch or on detached HEAD (`attempts.journal_copy`); do not present those copies as universal storage.

## Direct observation and verification

A synthetic case used the existing `tests/test_evidence.py` fixture and the supported writers, with no model call. The persisted rows before deciding were:

```toml
text = "WARNING · scripts/01_measure.py:9 · statement · LAB-015 Preflight audit before freezing · the seed is not recorded"
status = "open"
reason = ""
```

After `findings.write_decision`, the finding text was unchanged and the decision rows were:

```toml
status = "limitation"
reason = "The synthetic example documents the missing seed."
effect = "stands"
```

`evidence.record_changed(before, after)` returned false. Two second-review writes created distinct files, one ending `-review.toml` and one `-review-2.toml`; the first still held `insufficient` after the second recorded `upheld`. This demonstrates storage, not that the later draw releases the decision; the release rules additionally interpret `again` and prior verdicts.

A second synthetic observation used the committed-evidence fixture and a journaled attempt. After its answer and initial record had been copied, the text of the new, not-yet-committed finding was changed. `attempts.area_gaps(area).blockers` and `evidence.change_findings(area)` both returned `[]`. The same text edit to the fixture's already committed record yielded one evidence change. This positive control verifies the boundary at the current commit; it does not claim a complete end-to-end release after the edit.

Focused verification uses `tests/test_findings.py`, `tests/test_evidence.py`, `tests/test_attempts.py`, `tests/test_claim_review.py` and `tests/test_decision_review.py`. Their scope is existing writers, decision bindings and evidence comparisons with synthetic reviewer inputs. At the inspected commit, all 217 tests passed in one run (313.17 s), pytest exit 0, in the isolated worktree with its own editable install. The command was `.venv/bin/python -m pytest -q tests/test_findings.py tests/test_evidence.py tests/test_attempts.py tests/test_claim_review.py tests/test_decision_review.py`. No live model call, new scientific experiment or full-suite claim is part of this inventory.

## Decisions by the author — 2026-11-16, not implemented

The inventory separates the original answer and finding content from later decisions and regenerated views. The author decided to preserve original answers, original finding content and second-review results. The agent may revise its own decision, reason and effect before or after a commit; generated report text may be regenerated. A changed decision cannot inherit a confirmation of an earlier decision state.

No complete history of every uncommitted decision revision is required for now. Committed states and stored reviews suffice for the present need. An explicit release despite an open objection must nevertheless retain the release decision and its reason.

A separate contract change will introduce a global release policy set by the user or laboratory, which the executing agent may not relax. In strict mode an unresolved audit BLOCKER prevents release. The alternative allows release with a documented open audit objection: the release decision, reason, open findings, affected claims and effective policy remain traceable, and the report distinguishes this outcome from a clean audit. Technical prerequisites, including readable evidence and available measurements, remain mandatory. This is an approved direction, not an implemented flag; its scope, storage and integration with gates, reviews and reports need an implementation plan and versioned contract change.

The additional content comparison before the first commit is deferred. A future comparison with the initial copy must exclude mutable decision fields and account for labkit's generated metadata and carried findings. That copy exists in the local git directory, is not cloned, is unavailable in some working states and is itself editable. Comparing local evidence can establish agreement with the retained copy, not independent authenticity.

[TODO](../../TODO.md) records the decisions and implementation status. The origin of reported numerical results remains a separate open question. This documentation update adds no gate, changes no standard and starts no rollout.
