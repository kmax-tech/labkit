# Consolidated maintainability repair plan

2026-11-03. Reviewed against `fb318da2` (package unchanged since `e5fdf363`).
This combines the [repair-guidance review](2026-11-03-maintainability-review.md)
(M1–M2) and the [shared-rules review](2026-11-03-shared-rules-review.md)
(R1–R5, V1–V8, N1–N6, S1–S2). Both reports are already on main;
there is no outstanding branch merge for their contents. Their IDs remain
stable evidence references. This document owns the combined work order;
it changes no gate, scientific duty or evidence tier.

## Review conclusion

The reports support small repairs, not a rebuild or a module-size target.
V3 and M1 share a cause. V5 and M2 belong in the same repair area, but V5
is a distinct, not yet reproduced case: treating a released correction as
an unreleased departure. Do not count it as independently demonstrated
by M2's command-order probes.

The most urgent findings concern omitted checks, followed by contradictory
repair advice. Equal implementations are maintenance risks, not current
bugs merely because they are duplicated. A helper returning the wrong
answer establishes that local defect; a complete release bypass needs a
command-path test before it is claimed.

### Confirmed in this review

These probes used real package functions, synthetic protocol text and a
temporary directory; the Data profile comparison used a model-bearing
fixture head so its audit stamp actually includes that field. No model calls or paid runs were made.

| Finding | Input and observed result | Limit of evidence |
|---|---|---|
| R1 | A Prompt fence containing `<instructions>`, text and `</instructions>` is not `is_stamp_placeholder_block`, but `Lanes._prompt_blocks` drops it. | Confirms the filter defect. The repair must prove drift refusal before a model call, including the static reader. |
| V1 | `Unit: seconds → milliseconds` is found by `scope_differences`; the same change under `Unit (per judged item)` returns no differences although `fields` identifies `unit`. | Confirms inconsistent field identity, not a full adoption bypass in this probe. Duplicate labels also need one explicit policy; first-value and last-value selection must not disagree. |
| V2 | Data profile `alpha beta → alpha  beta` changes `registration_differences`, while `registration_stamp` is equal. | Whitespace disagreement confirmed. A simple wrapped `alpha\n  beta` is already equal: do not describe every reflow as failing. |
| S2 | A current-header index with a row containing only `only-id` returns `[]` for a protocol-filtered `indexed_runs`; a two-column old header is read though `header_refusal` refuses it for writing. | Confirms silent omission and reader/writer disagreement. The affected report-binding path must get its own regression test. |

M1 and M2 retain their executable evidence in labkit-evidence `ca57d387`,
`usability/2026-11-03-maintainability/`. This review re-read their relevant
call sites; it did not repeat their complete command probes. The additional
probes above ran from `/private/tmp/labkit-combined-review.py`; the exact
function calls and inputs in the table make them reconstructible without
that temporary file.

## Ordered work packages

The numbers define work order, not commit size. Each independent repair
gets its own commit with a faulty case, a correct counterpart, and any
affected repair path; grouped candidates are not one bulk commit. Establish a reproducing test
before changing production code. Full commit checks remain required.
Do not add model calls to test exact bindings and command routing.

| Order | Scope and severity | One authoritative rule / smallest repair | Acceptance and boundary |
|---|---|---|---|
| 1 | R1 — high, skipped prompt check; implemented in `cb8a30c3` | Use `is_stamp_placeholder_block` in both readers; share the fixed-line comparison where static and runtime inputs permit it. Keep static-unreadable source distinct from a runtime-resolved prompt. | Tagged prompt drift is refused before `complete_many`; matching tagged prompts pass; the actual stamp placeholder retains its current treatment. Both static and runtime paths are tested. Done: `protocol_check.registered_prompt_blocks` and `unheld_prompt_lines` are the one reader and comparison; placeholders stamped before 0.53.0 and author-written `<…>` blocks now block (Breaking, last 0.107.0). |
| 2 | V1 + V2 — high for omitted scope comparison; medium for whitespace drift | Normalize field identity with `field_name` in one reader. Define duplicate-field handling explicitly; ambiguous held fields must not silently select different values. Fold Data profile whitespace in both comparisons. | Gloss/case variations cannot hide a changed Unit or Question; unchanged values and allowed reflow pass; duplicate held fields give one clear refusal. A real content change is still found. Normalize Data profile whitespace only: do not copy Data/scope's generated-count stripping without a contract. |
| 3 | S2 — high, silently omitted run evidence | Share current index validation between readers and writers; reject a truncated row with file/row context. | Valid current index still reads, including deleted-run evidence; a short row is not interpreted as no measurement. Cover `has_measured`/report setter. Old-format refusal follows the announced compatibility policy, not a new migration reader. |
| 4 | M1 = V3 — medium, display-dependent control | Carry the checked withdrawal requirement as data from the existing comparison. | Rewording findings preserves withdrawal-first order; unrelated blockers do not acquire it. Inspect the predecessor/deleted-script cases separately: V3's broader claim is not covered by the wording mutation alone. |
| 5 | M2 + V5 — medium, conflicting repair guidance | Use current answering-run/code facts for the needed action; retain the old record's separate review binding. Reproduce V5, then consult the existing released-field comparison instead of reimplementing it. | Decide before/after measuring B; description-only correction; already released correction; changed Question beside pending correction. Existing B requires its audit, not an invented run C. No automatic decision or new release exception. |
| 6 | N1 + N2 — medium, liveness and wait advice | Compare what `next`, `--wait`, twin-run refusal and output locks each protect before sharing readers. Include detached starts and the existing true/false/unknown process result. | Detached start before config creation, real writer, dead writer, reused PID and unavailable process inspection. PID existence alone must not claim a writer; uncertain identity must not authorize lock deletion. Do not replace output-lock ownership with area-wide liveness. |
| 7 | V4 + N3 + N5 + N6 — medium candidates, reproduce first | Use resolved protocol ownership for report blocks. Have advice consume the same applicable report obligations as the corresponding gate. | Alternate equivalent protocol paths; touched versus untouched reports; handed-over protocol with report-binding gap; valid discussion beside a malformed other block. Preserve progress-first saving: it grants no release and may intentionally precede blockers. If a proposed discrepancy is only that ordering, close it without new logic. |
| 8 | R2–R5 + V6–V8 — cleanup/candidates, bounded commits | Merge genuinely identical rules after stating their inputs and error policy. Prefer existing owners over a new omnibus state object. | Preserve unreadable-record treatment, first/deleted measurements, duplicate fields, preflight fields and release-vs-preview boundaries. For V8 align the readiness hint with start requirements. See the per-ID register below. |
| 9 | N4 + S1 — decided and implemented | N4: both lanes and the setter use the first measurement's committed report binding, including absence. S1: old unbound audit starts are refused. | Both changes have Breaking entries; no migration reader or run-schema change. See the contract decisions below. |

Steps 1, 2 and 3 protect distinct inputs and can be prepared independently.
Integrate them one at a time and verify on the resulting main. Steps 4 and
5 share guidance code and should run sequentially. Later work starts only
when its candidate has an executable reproduction or a demonstrated shared
contract; this table is not permission for a broad cleanup sweep.

### Complete disposition of remaining IDs

| ID | Disposition / question to settle before implementation |
|---|---|
| R2 | Step 8: share placeholder-value recognition, preserving ID-prefix treatment; no broader guessing about author-written placeholders. |
| R1 follow-up | Step 8: `audit_prompt.py` still hands the audit agent every Prompt fence, the stamp's unfilled one included, as "current prompt sources"; read `protocol_check.registered_prompt_blocks` there so a placeholder-only protocol says "no Prompt block". Evidence only, no comparison; found in the R1 review. |
| R3 | Step 8: share declared-run extraction, retaining the present unreadable-as-None contract and the checks that name unreadability. |
| R4 | Step 8: compare the three callers' handling of unreadable and deleted runs first. File-reading discovery is not a pure `measurements(area, pid)` function; separate discovery from any reusable pure classification. |
| R5 | Step 8: reuse existing withdrawal wording/report-location rendering only after step 4 removes control dependence on that wording. |
| V6 | Step 8: make coverage compare the authoritative audited state; retain field-level explanations. Any intentionally excluded field must remain explicit. |
| V7 | Step 8 candidate: determine whether rendering is a preview or a release at each call site. Sharing registration comparison must not make an intermediate renderer perform finalization, or let an unregistered number be released. |
| V8 | Step 8: the registration-written hook must distinguish written from ready-to-run. Reuse start requirements where applicable; preserve contexts that intentionally precede committing. |
| N4 | Decided after this review: bind both lanes, hold late registration, and have the setter preview the shared gate. See [the implementation contract](2026-11-03-report-binding-both-lanes.md). |
| S1 | Removal authorized on 2026-11-03 and implemented in the [journal-format change](2026-11-03-audit-journal-format.md), with a Breaking entry naming 0.107.0 as the last compatible release. Evidence-loss detection remains. |

Every original ID is accounted for: R1 in step 1; V1/V2 in step 2; S2 in
step 3; V3/M1 in step 4; V5/M2 in step 5; N1/N2 in step 6;
V4/N3/N5/N6 in step 7; R2–R5/V6–V8 in step 8; N4/S1 in step 9.

## Contract decisions

**N4 — decided after this review:** Max authorized one report binding for
both lanes, using the commit of the first measurement, including no report.
The start check verifies report commitment on both lanes. The setter asks
the same gate about the proposed text, so restoration is allowed and late
registration is held. High retains its separate freeze/preflight duties.
This supersedes the earlier recommendation to defer high binding; see the
[decision and tests](2026-11-03-report-binding-both-lanes.md).

**S1 — decided after this review:** Max authorized removing old journal
starts now. The [format change](2026-11-03-audit-journal-format.md) refuses
starts without audit bindings; no migration reader remains. This replaces
the earlier recommendation to wait. No release or tag is made here.

The already chosen Question exception, per-run resolved binding, second-review duty,
report progress-first behaviour and unchecked origin of new audit records
remain unchanged. No source-authentication system follows from this plan.

## Completion and verification

A step is complete when the authoritative owner is named in architecture
where necessary, its old competing logic is removed, failing/correct
counterparts pass, and the affected real command route reaches its next
gate. A fixed reply can test routing; it cannot validate an auditor's
semantic judgement. Review the diff with an independent cold reader before
committing. Run the full hook per commit and the affected repair probes
after integration; run all shared probes once after the batch.

Measure simplification by removed duplicate decisions, consistent advice
and gate results, and preserved valid repair paths. Do not claim fewer
model calls or saved experimental time until a separately authorized usage
round measures them. Keep the area-17-then-18 evaluation order.

The planning review ran the focused prompt, lane, index, field and
architecture tests: 58 passed and 48 subtests passed. Their passing baseline does not refute the defects
above: the missing input variants need new regression tests during repair.
No production code or standard was changed by this consolidation.
