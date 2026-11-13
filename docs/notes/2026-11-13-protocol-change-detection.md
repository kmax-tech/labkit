# Detecting protocol changes after an audit or measurement

Date: 2026-11-13. Developer note explaining the current implementation; no new enforcement or format contract.

Labkit detects changes by comparing the current registration, promises and code with earlier records. Freezing does not make the Markdown file read-only, and the protocol id identifies the protocol rather than its contents. A successful comparison establishes agreement with the saved evidence for the parts compared.

## Registration fields

`protocol_check.registration_stamp` builds a mapping of registration entries. Each selected prose field contributes a digest of its value after whitespace normalization. A line reflow preserves the digest; changing the wording changes it. The field names remain in the mapping, so `registration_drift` can name the changed fields. Missing fields have an explicit absence marker. The protocol kind is stored as its value, rather than hashed.

The selection comes from `standard_contract.registration_fields`. It is narrower than the set of required form fields:

| Entry                      | Included when                                         |
|----------------------------|-------------------------------------------------------|
| `kind`                     | Always                                                |
| `Question / hypothesis`    | Always                                                |
| `Inference criterion`      | Fit or Apply                                          |
| `Quality check`            | Fit or Apply                                          |
| `Null condition / anchors` | Fit or Apply                                          |
| `Data profile`             | A model is named                                      |
| `[kept]`                   | Present in the protocol; digest of its canonical TOML |
| `[reference]`              | Present in the protocol; digest of its canonical TOML |

Conclusion, Recorded results and the run list are excluded from this registration mapping. Completing them after measurement leaves the registration comparison unchanged. Other checks still hold reported results and claims to their evidence.

The field digests use `digests.digest`: SHA-256 truncated to 12 hexadecimal characters. They are change detectors, not signatures authenticating who wrote the content.

## Stored evidence and later comparisons

The audit writer stores the registration mapping under `[audit] registration` in `audits/<minute>-<mode>.toml`. The record separately stores `block_sha` for the promise block and `scope_sha` for the area's code stamp. These are separate comparisons, not one digest over the entire protocol file.

At high repeat cost, `protocol-fill PROTOCOL --freeze` sets `frozen = true` and names the preflight audit record in `preflight_audit`. Before writing, it checks that the record covers the proposed state and that the required fields and decisions are complete. Preflight and the run-start checks also verify that coverage, including when someone edits the protocol by hand. `audit_gaps.audit_record_gap` compares the current code stamp, promise block and registration with the named record. A changed question or promise leaves the old audit without coverage and requires a new audit.

For example, changing a registered question from “mean line count per case” to “mean number of causal claims per case” changes the field digest. The comparison names `Question / hypothesis` as changed. Inserting only a line break in the original question preserves the digest. Both cases are held by `tests/test_registration_binding.py`.

A measurement also records its promise snapshot in `runs/<run_id>/config.json`. Finalize calls `intent-check`, which compares the current promise block with that snapshot. Changing a threshold after the run therefore cannot silently apply the new threshold to the old measurement. Finalize's `registration_hold` station additionally compares the answering run with the first measurement's registration; obtaining a fresh audit alone does not release a changed scientific registration after measurement.

At low repeat cost there is no freeze or required preflight audit. The committed registration, measurement records and later release checks provide the applicable comparisons. The workflow describes the different obligations of the two cost tiers.

## Limits and maintenance

Comparisons run when commands invoke the checks, not when an editor saves the file. Unselected prose is outside this registration mapping. The code stamp covers its defined scope, not every dependency that might affect a result. A digest comparison cannot establish that a scientific statement is correct or that an agent used the intended protocol.

The mechanism relies on the earlier evidence remaining trustworthy. Matching edits to both a protocol and its saved evidence are not prevented by hashing itself. Git history and labkit's evidence checks provide additional checks with their own limits; the architecture explicitly records the gap for hand edits before evidence is first committed.

When changing registration selection or normalization, inspect the audit writer and coverage readers together. Keep the correct counterpart passing: reflow and post-run reporting must not invalidate registration coverage.

## Sources

- [Architecture: records and their bindings](../architecture.md#where-verdicts-are-recorded) and [enforcement](../architecture.md#run-and-hook-enforcement).
- [Workflow: registration through reporting](../workflow.md) and [protocol–run binding](../protocol-run-binding.md).
- [Registration entries and comparison](../../labkit/formats/protocol_check.py): `registration_stamp`, `registration_drift`; [field selection](../../labkit/formats/standard_contract.py): `registration_fields`; [digest format](../../labkit/formats/digests.py): `digest`.
- [Audit serialization](../../labkit/formats/findings.py), [audit coverage and freeze refusals](../../labkit/formats/audit_gaps.py), and [run-start enforcement](../../labkit/run/start_check.py).
- [Promise comparison against the run](../../labkit/checks/intent_check.py): `check_block_against_run`; [first-measurement registration](../../labkit/gates/registration_hold.py).
- [Existing registration tests](../../tests/test_registration_binding.py), [freeze-gate tests](../../tests/test_runlog_freeze_gate.py), and [committed-registration tests](../../tests/test_registration_committed.py).
