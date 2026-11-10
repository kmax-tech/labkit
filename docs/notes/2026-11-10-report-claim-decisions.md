# Decisions on report-review claims — the contract (2026-11-10)

> Status: proposal for the author's decision; nothing built. Depends on the open question of the second review (TODO.md, „Analyse 2026-11-10", point 1): the confirmation path below is the recommendation, the alternative is named.

## The problem

A report review (`labkit-audit AREA --report-review REPORT`, `labkit/formats/report_reviews.py`) writes claims on report lines: `result` — a discussed run's number stated as a result —, `contradiction` — a statement the audit records contradict. `report_reviews.standing` holds the state (the fingerprint over every input the reader saw) as soon as any review of that state names a claim, an `--again` draw's included; a later clean draw does not outvote it. The only way out today is a changed input and a review of the new state (`report_hold.review_hold`).

That is right for a true claim and wrong for a false one. When the reader misread — the line is inside a discussion block that says „not reported", the number is the adopted one, the statement agrees with the record —, the author can only reword a correct text until a reader no longer trips over it. The claim is never answered; it is evaded. An audit finding has the answer a claim lacks: a decision with a reason, bound to the record, and a second auditor where a blocker would otherwise be released by the deciding agent's own word (`report_decisions.first_dismissals`).

## The contract

1. **Where a decision lives.** In the review record itself, as for audit findings: each `[[claim]]` carries `status` and `reason`. The record's folder is outside the fingerprint (`report_reviews` module docstring), so writing a decision leaves the state it judges unchanged. Command: `labkit-audit AREA --report-review REPORT --decide N STATUS REASON --record FILE`, the shape of `--decide` on findings. Writer: `report_reviews.write_claim_decision(path, n, status, reason)`, which keeps every other byte and replaces the file whole only when exactly that claim changed, as `findings.write_decision` does.

2. **Which decisions a claim can take — the limits.** One status besides `open`: `false-positive` — the reader misread, the reason names the counter-evidence (the line, the record, the number). Refused, each with its sentence, as `findings.subject_refusal` refuses a limitation on an implementation finding:
   - `limitation` on either kind. A `result` claim says an unadopted number is shown as a result; LAB-104 A number leaves the area only through its adoption allows no limit line around that. A `contradiction` says the report states what the records contradict; a limit line does not make the statement true.
   - `fixed`. A repair changes the report or a source, so the fingerprint changes and the record no longer covers the state; a review of the new state judges the repair. A status would add a word and release nothing.

3. **What a decision is bound to.** The record's file name, the claim's number in it and the state the record saw (its fingerprint), plus the decision's digest (status and reason, as `findings.decision_digest`). A change to the report or any source the reader read is a new state: the record no longer covers it, its decisions with it. Decisions are not carried into a new state's review; the next reader stays cold.

4. **What releases a state.** At least one review that is no `--again` draw saw the state, and every claim any review of that state named — an `--again` draw's included — is decided `false-positive` and upheld (point 5). An open claim holds; a new draw can add a claim, never remove one.

5. **Confirmation of a `false-positive` (recommended: a second reviewer).** `labkit-audit AREA --review --record <report-review file>` hands a cold reviewer the claim, the reason, the report lines and the inputs the first reader saw, and writes `audits/report-reviews/<minute>-claim-review.toml`: `record`, `fingerprint`, and per claim `claim`, `decision_sha`, `verdict` (`upheld` | `rejected` | `insufficient`), `why`. It upholds a decision when it names that record, saw that fingerprint, judged the decision as it stands (`decision_sha`) and says `upheld`, and is no `--again` draw. `rejected` and `insufficient` never release; once a review of a state did not uphold a decision, no later draw does (`reviews` „contested", same rule). One model call per contested report, none otherwise.

   Alternative, if the author settles the second review as a house rule, not a lab rule: the reason alone releases, and report-check names every such release as a WARNING „released on the author's word". Cheaper by one call; the deciding agent then releases its own blocker, which `first_dismissals` refuses for audit findings.

6. **Format break.** `[[claim]]` gains `status` and `reason`; a record without them is no longer read (announced in `CHANGELOG.md`, „Breaking", naming the last release that reads it). A review costs one call, so the old records are reviewed again rather than read by a second path.

## What changes in code

| Place                                                      | Change                                                                                                                       |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| `labkit/formats/report_reviews.py` `ReportClaim`, `_claim` | `status`, `reason`; reading refuses an unknown status, a decided one without reason                                          |
| `labkit/formats/report_reviews.py` new                     | `claim_refusal(kind, status)`, `write_claim_decision`, the claim-review record (write, read) and `upholding` for a claim     |
| `labkit/formats/report_reviews.py` `standing`, `held_by`   | the release of point 4; `held_by` names each claim as open, decided and not upheld, or contested                             |
| `labkit/gates/report_hold.py` `review_hold`                | the fix names the two ways: change the text or a source and review that state, or decide `false-positive` and have it upheld |
| `labkit/gates/audit.py`, `labkit/gates/audit_decisions.py` | `--decide` with `--report-review`; `--review` on a report-review record                                                      |

No second status logic beside the findings': the status words, the decision digest, the contested rule and the `--again` rule are the ones audit findings use, read from their home where they can be.

## Acceptance

Through the real commands, each with its twin:

1. A true misreading is decided `false-positive`, upheld by the second reviewer, and the report is released; the twin: the same decision `rejected` holds.
2. A real `result` claim stays held: `limitation` and `fixed` are refused with their sentence, and a `false-positive` the reviewer rejects holds.
3. A changed report line or source after the decision makes it stale: the state is held until a review of the new state.
4. An `--again` draw does not release an open claim, and a claim it adds holds until decided.
5. A record without `status` is refused with the sentence naming the version that reads it.
