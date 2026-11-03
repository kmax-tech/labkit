# 2026-11-03 — a handover voided by the report review it owes

**Problem.** A handover written after an analysis audit was no longer
current once the report review it owes had run: `handovers.mismatch` said
"audits/ changed since the handover", `labkit-next` offered the adoption
instead of "handed over", and a BLOCKER the handover recorded as open held
the stop and the commit again. A handover with no analysis audit before it
stayed current. Seen in the F5 probe (successor case) and reproduced apart
on main `e9960c6d` (labkit-evidence
`usability/2026-11-03-correction-then-code-fault/scripts/handover-journal.sh`,
`logs-e9960c6d/handover-journal.log`).

**Cause.** The handover binds every file under `audits/` by its blob id,
except what a report review writes (2026-11-02,
[repair-path probe](2026-11-02-repair-path-probe.md), F1). For the journal
`attempts.jsonl` that exception was a second computation: while no line
was a review's, `journal_digest` returned the file's blob id; once the
review had appended its lines, it returned a sha256 digest of the other
lines. Written before the review and checked after it, the two never
matched, though the lines bound were unchanged. A journal the review began
(no earlier audit) bound nothing and so passed — which is why the first
twin did not see it.

**Solution.** One computation for writing and checking:
`handovers.journal_digest` is the blob id of the journal's text without
the lines of a report review's attempts (`repo.text_blob`, `git
hash-object --stdin --path`, the filters applied as for the file). With
no such line that text is the file, so the id is the file's own — the
binding labkit 0.107.0 wrote, which therefore still matches. A journal
whose bytes are not UTF-8 names no line, nothing is left out, and its id
is the file's.

**Twins.** `tests/test_handovers.py` `ReviewTrace`: the binding with and
without the review's lines is the same, before or after them; lines of
another attempt move it. `tests/test_repair_paths.py`
`test_a_handover_after_an_analysis_audit_stays_through_its_review`:
analysis audit with an open BLOCKER, handover, report review — the stop,
the commit and `labkit-next` agree on "handed over" before and after the
commit; a new analysis audit afterwards voids it in all three.
`test_a_handover_with_its_report_review_stays_a_handover` (no audit
before) is unchanged.

**Limits.** The index's journal is read as text (`repo.text_at`); a
journal with CRLF line ends staged through an eol filter could give
another id than the tree's — the handover then mismatches, loudly. A
handover written by this branch's predecessor commits (after 0.107.0,
with review lines already in the journal) was bound by the old digest and
must be written again; none was released.
