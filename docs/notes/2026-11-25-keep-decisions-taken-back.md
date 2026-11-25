# Keeping a decision taken back — proposal

Status: decided by the author on 2026-11-25; the proposal below is kept as written on 2026-11-24, and where the decision departs from it, the decision holds.

## Decided by the author — 2026-11-25

1. The history stands in the record (option A), one entry for every decision a later one replaces; a decision equal to the current one writes no entry. Taking a decided status back to `open` owes a reason. `--findings` shows each replaced decision on one line.
2. A decision taken back and restored word for word needs new confirmations. The proposal's comparison of a review file's age with `until` is dropped: `until` is exact to the minute, so a take-back and a restore within one minute could not be told apart. Instead the history joins `decision_digest` when there is one. A record without history keeps its digests, and so its reviews and fix verdicts. Built as its own commit with its own review, released together with point 1.
3. The history logic has its own module, `labkit/formats/decision_history.py`. It is no general journal, and the claims of a report review keep no history yet.

Two limits belong to the order: the history is not shown to the decision reviewer or the follow-up auditor (their prompts stay as long as they are), and `--findings` gives each replaced decision one line, the full reason staying in the record.

Departures from the text below: an entry's `until` is written as the record's `[audit] date` is (`2026-11-24T14:02`); a present `replaced_decisions` key holds at least one entry, so an empty array is refused; a record that does not read is left to the reader's own error, and the committed-record check compares its history only when both versions read.

## The problem

`labkit-audit AREA --decide N STATUS --why REASON` stores a person's decision on one audit finding through `findings.write_decision` (labkit/formats/findings.py:2039). It rewrites the finding's `status`, `reason` and `effect` lines in place (`_decided_text`, labkit/formats/findings.py:2129) and keeps every other byte. Taking a decision back (`--decide N open --why …`) therefore overwrites the earlier status, reason and effect; the reason for taking it back lands in the `reason` line of the open finding. The earlier decision survives only in git history, and only if the record was committed before. In argmining27 experiment 15 the person quoted the earlier reason by hand in `--why` to keep it.

This revises an earlier decision of the author. On 2026-11-16 the author decided that "no complete history of every uncommitted decision revision is required for now; committed states and stored reviews suffice" ([audit record lifecycle](2026-11-16-audit-record-lifecycle.md), section "Decisions by the author"). The second opinion of 2026-11-24 found that insufficient: a record need not be committed before a decision on it is taken back. The same note's other decision still holds and constrains this proposal: "A changed decision cannot inherit a confirmation of an earlier decision state."

## 1. Where the earlier decision lives

**Option A — in the record, a list per finding (recommended).** Each `[[finding]]` table gets an optional key `replaced_decisions`, an array of inline tables, one per decision that a later one replaced, oldest first:

```toml
[[finding]]
grade = "BLOCKER"
text = "…"
subject = "implementation"
rule = "LAB-015"
replaced_decisions = [
  { status = "fixed", reason = "seed now set in 01_measure.py", effect = "", until = "2026-11-24 14:02" },
]
status = "open"
reason = "the seed is set after the split; the fix does not hold"
```

Each entry is labkit's own: the replaced `status`, `reason` and `effect`, and `until`, the minute it was replaced (`runs.date_minute`, as the record's `[audit] date`). Every string is written on one line by `toml_string` (labkit/formats/findings.py:110), so each entry is one line and the array closes on a line of its own. Trade-offs: the history stands where the decision stands, in the one file the person, the decision reviewer and the follow-up audit already read; it is written in the same atomic replace as the decision (`files.write_atomic`, read back first), so the two cannot disagree; it commits and restores with the record. Cost: the record format grows, and the check of what may change in a committed record must learn the new lines (section 2).

**Option B — in the record, only the last decision taken back** (`taken_back = { … }`). Simpler to read and check, but a second change loses the first: fixed → open → limitation keeps only the open state, and the fixed decision the follow-up may already have judged is gone. Rejected: it fails the case that motivated the task as soon as the person re-decides.

**Option C — beside the record, an append-only journal** (`audits/decisions.jsonl`, like `attempts.jsonl`). The record, `decision_digest`, `without_decisions` and the committed-record check stay untouched, and the append-only check exists in `attempts`. But the decision and its history are written in two steps that can part (record written, journal not); a reader of one record does not see its history without joining the journal; and the journal is a second piece of evidence with its own rules (append-only against HEAD and against a copy in the git directory, restore ways, an unreadable-journal blocker; labkit/formats/attempts.py:636). Rejected for the extra machinery; it would be the choice only if the record format must not change.

**Recommendation: option A.**

## 2. Format consequences

**Reading.** `Finding` (labkit/formats/findings.py:287) gets a last field `replaced_decisions: tuple[ReplacedDecision, ...] = ()`, a new frozen dataclass of `status`, `reason`, `effect`, `until`. `_finding` (labkit/formats/findings.py:1703) reads the key: absent means none, which is also what a newly written record holds — `write` (labkit/formats/findings.py:1396) and `_carried_lines` (labkit/formats/findings.py:1510) do not write the key. A present key that is not an array of tables with exactly those four string keys, a status outside `STATUSES`, an `until` not a minute, or an entry whose `effect` fails `_effect_problem` is refused with a sentence naming the field. A carried finding starts without history: its origin is followed by the chain (`followup.chain`), not copied.

**Editing.** `_decision_lines` (labkit/formats/findings.py:1953) learns a fourth key, `replaced_decisions`, spanning from its `= [` line to the closing `]` line; `_DECISION_LINE` and `_DECISION_OPEN` (labkit/formats/findings.py:1924, 1930) stay for the three scalar keys. `_decided_text` inserts the array before the `status` line when it is absent and appends one entry line before the closing `]` when it stands. `write_decision`'s read-back (`expected[n - 1] = decided`, then `_head`) compares the whole `Finding`, so the appended entry is checked by the existing comparison. `with_decision` (labkit/formats/findings.py:2017), which report reviews use for their claims, is not changed.

**The committed-record check.** A committed record may change only in the lines `--decide` writes: `evidence.record_changed` (labkit/formats/evidence.py:148) compares both versions without their decision lines (`findings.without_decisions`, labkit/formats/findings.py:1994); the stop, the pre-commit and the post-change hook read it through labkit/formats/evidence.py:282 and :495; the rule is stated in the module docstring (labkit/formats/evidence.py:8). `without_decisions` would drop the `replaced_decisions` array too — but then the history could be rewritten freely after a commit, which defeats the task. So `record_changed` gains a second, exact condition, a pure function `findings.history_kept(before, after)`: for every finding, the committed `replaced_decisions` are a prefix of the new ones, and when the decision changed, the committed decision (status, reason, effect) is the entry right after that prefix. Entries after it (decisions made and replaced again before the next commit) cannot be checked against git and are taken as written. This is a guaranteed-tier check: exact, mechanical, silent on a record that `--decide` alone changed.

**`decision_digest` and what is bound to it.** `decision_digest` (labkit/formats/findings.py:999) stays as it is and does not include the history. Reviews (`reviews.Decision.decision_sha`, labkit/formats/reviews.py:105; `verdicts_on_state`, labkit/formats/reviews.py:346) and fix verdicts (`FixVerdict.decision_sha`, labkit/formats/findings.py:362; `followup`, labkit/formats/followup.py:233, :413, :483) bind to the decision as it stands, and every existing record keeps its digests, so no review lapses at the upgrade. Including the history would make every review lapse after any take-back, even one later reversed.

A consequence the author has to weigh (decision 4): today, and unchanged by this proposal, a decision taken back and later restored with the identical status, reason and effect has the same digest again, and a review of the earlier state counts again. The author's rule of 2026-11-16 ("A changed decision cannot inherit a confirmation of an earlier decision state") suggests that it should not. The history makes the rule checkable: a review counts only if its file is newer than the last `until` of an entry with the same digest. That is a change to the review release, a contract change, and belongs in its own step.

**Other readers.** `audit_gaps` (labkit/formats/audit_gaps.py) and report-check (labkit/gates/report_check.py) read statuses and open findings, not reasons or history; they are unaffected. The decision reviewer's prompt (labkit/gates/decision_review.py:258) and the follow-up audit prompt (labkit/gates/audit_prompt.py:942) show the current reason only; showing the history to them is out of scope here (the follow-up prompt is being changed in parallel).

**Announcement.** A record without the key reads as before, so new labkit reads every record 0.115.0 wrote; this needs no reading path for an old format, since absence is also what new records hold. The break runs the other way: labkit 0.115.0 and earlier read a record with history but do not append to it when deciding, and their committed-record check refuses a commit that appended an entry ("rewritten beyond its decision lines"). `CHANGELOG.md` gets a "Breaking" entry: a record's findings may carry `replaced_decisions`, which `--decide` appends to and the committed-record check holds append-only; 0.115.0 is the last version whose `--decide` overwrites a decision without keeping it; a repo deciding with history pins the new version in every checkout.

## 3. Which entries are written

On every decision that replaces a decision, not only on a change to `open`. An entry is appended when the finding's current state is not the undecided start (`status = "open"`, empty reason, no effect) and differs from the new one in status, reason or effect. Why every change: fixed → open → limitation must keep the fixed decision and the reason it was taken back; writing only on a change to `open` would lose the open state and its reason at the next decision. A corrected reason (fixed with reason a → fixed with reason b) also gets an entry, because it is another decision to every review bound to the old digest; the history then says why a review no longer counts. A decision identical to the current one writes nothing.

Not part of the recommendation, but a small addition the author may want (decision 3): taking back a decided status (`fixed`, `limitation`, `false-positive` → `open`) owes `--why`. Today `open` owes no reason (`REASON_OWED`, labkit/formats/findings.py:150; `--why` defaults to "", labkit/gates/audit.py:346), so a take-back may leave no reason at all.

## 4. Tests

Rule tests from data in memory (`tests/test_findings.py`):

- reading: a record with entries reads them; absent key gives `()`; each malformed form (not an array, unknown key, missing key, status outside `STATUSES`, `until` not a minute, an effect on a non-limitation) is refused with the field named;
- writing (`_decided_text` on text): fixed → open appends the fixed decision; open with reason → limitation appends the open state; undecided start → fixed appends nothing; the identical decision appends nothing; a corrected reason appends one entry; every other byte is kept (`without_decisions` equal before and after); a CRLF record keeps its line endings;
- digest twin: two findings that differ only in `replaced_decisions` have the same `decision_digest`;
- `without_decisions` drops the array.

Twin tests of the committed-record check (`tests/test_evidence.py`, on texts): appended entry with the committed decision as its first new entry passes (no false blocker); the same commit without any history change but an unchanged decision passes; an edited, removed or reordered committed entry is refused; a changed decision whose committed state is missing from the new entries is refused.

If decision 3 is taken: `--decide N open` without `--why` after a decided status is refused, and its twin from the undecided start passes (`tests/test_audit.py`).

One scenario test (`tests/test_audit.py`, mark `slow`): in a temporary repo a record with a `fixed` finding is committed; `labkit-audit AREA --decide 1 open --why …` exits 0, the record holds the fixed decision in `replaced_decisions`, and `evidence.change_findings` reports nothing; a hand edit of that entry is then reported with the restore way.

## 5. Effort and scope

Three commits, four with the display:

1. Format: `ReplacedDecision`, reading and refusals, `_decision_lines` and `without_decisions` know the array, digest docstring states that history is excluded; rule tests.
2. Writing: `write_decision` appends (with a clock parameter for tests); decision 3 if taken; CLI test.
3. Committed-record check: `history_kept`, `record_changed`, the evidence module docstring; twin tests and the scenario test; `CHANGELOG.md` "Breaking".
4. Optional: `--findings` (`show_findings`, labkit/gates/audit_decisions.py:520) prints one line per replaced decision under the finding; `docs/workflow.md` and the README terms name `replaced_decisions`.

Out of scope: claims of a report review taken back (`report_reviews.write_claim_decision`, labkit/formats/report_reviews.py:452), which could follow the same pattern later; showing the history in the decision reviewer's and the follow-up auditor's prompts; the review release against a restored identical decision (decision 4); reconstructing history for records decided before the change; the release policy of 2026-11-16.

## Decisions for the author

1. Option A, the history in the record (recommended) — or option C, a journal beside it, if the record format must not change. A means a Breaking entry and a larger committed-record check; C means a second evidence file with its own rules.
2. Write an entry on every replaced decision (recommended) — or only on a change to `open`. The narrower rule loses the reason of a take-back as soon as the finding is decided again.
3. Taking back a decided status owes `--why` — yes or no. Yes refuses `--decide N open` without a reason after `fixed`, `limitation` or `false-positive`.
4. A restored identical decision does not revive reviews of the state before the take-back — own step now, later, or not at all. Taking it changes the review release (`reviews.verdicts_on_state`) and enforces the rule of 2026-11-16.
