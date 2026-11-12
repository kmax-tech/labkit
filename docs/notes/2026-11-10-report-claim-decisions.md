# Decisions on report-review claims — the contract (2026-11-10)

> Status: decided by the author on 2026-11-11, with three corrections from an independent reading (the confirmation by a second reviewer is the rule, the way on after a rejection, the old records); built on 2026-11-12 (`labkit/gates/claim_review.py`, section "As built" at the end). The rule: LAB-015 Preflight audit before freezing, "A decision that releases a BLOCKER is confirmed by a second auditor".

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

5. **Confirmation of a `false-positive` by a second reviewer.** `labkit-audit AREA --review --record <report-review file>` hands a cold reviewer the claim, the reason, the report lines and the inputs the first reader saw, and writes `audits/report-reviews/<minute>-claim-review.toml`: `record`, `fingerprint`, and per claim `claim`, `decision_sha`, `verdict` (`upheld` | `rejected` | `insufficient`), `why`. It upholds a decision when it names that record, saw that fingerprint, judged the decision as it stands (`decision_sha`) and says `upheld`, and is no `--again` draw. `rejected` and `insufficient` never release, and no further call releases the same decision: once a review did not uphold a decision as it stands (`decision_sha`), no later draw on that decision does. The way on is a decision with a revised reason. It is a new decision with a new digest and owes a confirmation of its own; the earlier rejection stays in its claim-review record and `held_by` names it. The other way stays the changed report or source and a review of the new state. One model call per contested report, none otherwise.

6. **Format break.** `[[claim]]` gains `status` and `reason`; a record without them is no longer read (announced in `CHANGELOG.md`, „Breaking", naming the last release that reads it). A review costs one call, so the old records are reviewed again rather than read by a second path. The command reads every report review of the area before it writes a new one and refuses when one does not read (`report_review.report_reviews_of`), so an old record in place would refuse the very review that replaces it. The refusal therefore names the step: move the old record with `git mv` into `audits/report-reviews/superseded/`, a folder the reader does not list. The record is kept and the new review runs. To check while building: whether a hold on lost audit evidence (`undecided`) reads the moved record as lost; if it does, the folder is a named exception there, with its test.

## What changes in code

| Place                                                      | Change                                                                                                                       |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| `labkit/formats/report_reviews.py` `ReportClaim`, `_claim` | `status`, `reason`; reading refuses an unknown status, a decided one without reason                                          |
| `labkit/formats/report_reviews.py` new                     | `claim_refusal(kind, status)`, `write_claim_decision`, the claim-review record (write, read) and `upholding` for a claim     |
| `labkit/formats/report_reviews.py` `standing`, `held_by`   | the release of point 4; `held_by` names each claim as open, decided and not upheld, or contested                             |
| `labkit/gates/report_hold.py` `review_hold`                | the fix names the two ways: change the text or a source and review that state, or decide `false-positive` and have it upheld |
| `labkit/gates/audit.py`, `labkit/gates/audit_decisions.py` | `--decide` with `--report-review`; `--review` on a report-review record                                                      |

The last sentence of the rule's paragraph in `labkit/docs/standard.md` ("That decision is not built …") goes in the commit that builds this, so rule and code do not contradict.

No second status logic beside the findings': the status words, the decision digest, the contested rule and the `--again` rule are the ones audit findings use, read from their home where they can be.

## Acceptance

Through the real commands, each with its twin:

1. A true misreading is decided `false-positive`, upheld by the second reviewer, and the report is released; the twin: the same decision `rejected` holds.
2. A real `result` claim stays held: `limitation` and `fixed` are refused with their sentence, and a `false-positive` the reviewer rejects holds.
3. A changed report line or source after the decision makes it stale: the state is held until a review of the new state.
4. An `--again` draw does not release an open claim, and a claim it adds holds until decided.
5. A record without `status` is refused with the sentence naming the version that reads it and the move that keeps it; after the move the new review runs, and no gate holds the moved record as lost.
6. A `false-positive` the reviewer rejected is not released by another draw; the same claim decided again with a revised reason is released once a review upholds that decision, and the earlier rejection still reads in its record.

## As built (2026-11-12)

The six acceptance cases run in `tests/test_claim_review.py`, the rules from data in `tests/test_rules_report_claims.py`. Where the build departs from the text above or settles what it left open:

- **The decision's command** takes its reason with `--why`, as a finding's does: `labkit-audit AREA --report-review REPORT --decide N false-positive --why "REASON" [--record FILE]`. Without `--record` it takes the one review of the current state that names a claim. A record that read another state is refused: its claims hold nothing any more.
- **The moved record (point 6).** The hold on lost audit evidence did name a moved record as gone, at three places: the attempt journal's check of the tree and of the index (`attempts.area_gaps`), and the check of each commit of a session (`evidence.commit_changes`). The exception is narrow: only a record of the format without decisions counts as moved (`report_reviews.is_undecided_format`), read from the state checked. A record this labkit reads that is moved into `superseded/` is still named as gone — moving it would lift the hold its claim places.
- **Decision lines are the one change a committed review record takes** (`evidence.report_review_changed`), as for an audit record's findings; a claim review's file never changes.
- **The second reviewer's call** is journaled under the mode `report-review-claim`. The name contains `report-review`, so a handover leaves its journal lines and files out of what it binds, as it does the report review's.
- **Not built, and not measured:** whether a model judges such a decision right. The instructions (`labkit/agents/claim-review.agent.md`) have met no real model; the release condition is what is guaranteed.
