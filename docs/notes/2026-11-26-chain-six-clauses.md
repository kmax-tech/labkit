# Six ambiguous bullets of `docs/chain.md`, resolved from the code (2026-11-26)

Each entry gives the old wording, what a reader could not decide, what the code shows, and the new wording. The bullets are named by the section of `docs/chain.md` they stand in. No code or test changed.

## run → report (meaning): the diagnostic a finding may require

Old: "A finding may require a diagnostic (`· check: <metrics key>`, or `· check: file:<path>` for a file the run declares as a dependency, optionally ` (<note>)` or ` — <note>` to the line's end, the note kept whole as `check_note`; the auditor's, kept by every decision and bound in the digest)."

Unclear: what "the auditor's" refers to, and what is kept and bound.

The code:

- The check field closes the finding line, and only the key is machine-read; the note is kept whole (`labkit/formats/required_check.py:164`, the two note forms at `labkit/formats/required_check.py:27`).
- Key and note are fields the audit takes from the auditor's line and no decision sets (`labkit/formats/findings.py:130`, `labkit/formats/audit_records.py:470`).
- A decision builds the decided finding with the old `check` and `check_note` (`labkit/formats/audit_records.py:853`).
- The decision's digest includes the key, and the note when there is one (`labkit/formats/finding_decisions.py:224`).

So "the auditor's" is the key with its note, and both are kept and bound.

New: a lead sentence and three sub-bullets — the two forms of the field; the two forms of the note, with "only the key is machine-read"; "The key and the note are the auditor's: they are set from the finding line when the record is written, and no decision sets them. Every decision keeps both unchanged, and the decision's digest binds both (`finding_decisions.decision_digest`)."

Not added: the code reads two more keys, `diff:` and `code:` (`labkit/formats/required_check.py:40`). The bullet did not name them, and they stay out here.

## run → report (a discussed run, the registered report): the state a review is of

Old: "report-check holds the report, per protocol its discussions name, until a review of its state — the report and protocol as the gate's state holds them, at the commit only records the index holds and the area's tree equal to the index — names no claim."

Unclear: what "state" is at the stop and what it is at the commit.

The code:

- The review's state is the inputs the reviewer reads, with the report and protocol as the gate's state holds them (`labkit/gates/report_hold.py:1234`, docstring of `review_gap`).
- The gate's state is the working tree, or the index when staged (`labkit/formats/repo.py:654`).
- Staged, a difference between the area's working tree and the index is a blocker (`labkit/gates/report_hold.py:1268`, `labkit/gates/report_hold.py:226`).
- Staged, a review and a claim review count only when the index holds the record (`labkit/gates/report_hold.py:1282`).

New: "report-check holds the report, per protocol its discussions name, until a review of its state names no claim. The state is what the reviewer reads, with the report and the protocol as the gate's state holds them:" with two sub-bullets — the working tree at the stop; at the commit the index, only the review records the index holds, and a tree that differs from the index blocks the commit.

## run → report (the report a protocol owes): the duty of a protocol that is gone

Old: "a protocol id the area measured under that no protocol of the area carries now while it owed a report — by report-check's chain, by its area form on an area without a protocol, and by the stop's and the commit's hold (`report_check.orphaned_duty_gaps`, one reading in the file state each judges)."

Unclear: who holds the duty where, and what "one reading in the file state each judges" means.

The code:

- One function reads the duty from an area state; the ids carried now come from that state's protocol texts (`labkit/gates/report_check.py:824`).
- The chain calls it with its state (`labkit/gates/report_check.py:820`).
- `report-check AREA` calls it when the area has no protocol, before the refusal "no protocol" (`labkit/gates/report_check.py:641`).
- The hold over changed paths, which the stop and the commit run, calls it for every touched area in which no chain ran (`labkit/gates/report_check.py:1433`), with the state of its file state — the index when staged (`labkit/gates/report_hold.py:532`).

New: "a protocol id the area measured under that no protocol of the area carries now, while that id owed a report. One function finds it (`report_check.orphaned_duty_gaps`), and three callers hold it: report-check's chain; `report-check AREA` on an area without a protocol; the stop's and the commit's hold, on an area the change touches where no chain ran. Each caller passes the file state it judges (the working tree, or the index at the commit), and the ids carried now are read from the protocol texts of that state."

## run → report (the gates that run unasked): changed and ignored evidence

Old: "Committed evidence changed against git — a record beyond its decision lines, another audit file, a closed run's files — or a file of labkit's that git ignores holds both as well, in the state checked against HEAD, at the stop also by a session commit or left behind in HEAD's reflog, and no handover acknowledges it: each line names its `git checkout`."

Unclear: what "both" is, and which states are compared.

The code:

- "Both" is the two gates of the section, the stop and the commit: `undecided_state` adds the change sentences and the ignored files to the blockers of either, outside what a handover acknowledges (`labkit/gates/undecided.py:113`).
- First comparison: the working tree, or the index when staged, against HEAD (`labkit/formats/evidence.py:608`).
- Second, at the stop only: each commit since the session began against its first parent, unless the working tree has undone the change (`labkit/formats/evidence.py:716`, called from `labkit/gates/agent_hooks.py:424`, which only the stop calls at `labkit/gates/agent_hooks.py:287`).
- Third, at the stop only: a closed run held by a commit that HEAD's reflog names since the session began and HEAD no longer holds, whose files the tree lacks or holds otherwise (`labkit/formats/evidence.py:839`).
- The way out of a change is a `git checkout` line (`labkit/formats/evidence.py:366`, `labkit/formats/evidence.py:876`). The way out of an ignored file is `git check-ignore -v` and staging (`labkit/formats/evidence.py:912`).

The old closing clause said every line names a `git checkout`. For an ignored file the code names another command, so the new wording says so per case.

New: a lead sentence, "Three more findings hold both gates as well, and no handover acknowledges them:", and three sub-bullets — the change against HEAD in the tree (stop) or the index (commit); at the stop also a session commit's change that the tree has not undone, and a closed run left behind in HEAD's reflog; a file of labkit's that git ignores, whose line names `git check-ignore -v`.

## audit → evidence (the attempts): the journal's copy in the git directory

Old: "In the tree a journal line its copy in the git directory keeps (one per branch, held as a set of lines) that the journal lacks blocks too, with the files its end names — `audits/` deleted whole before a first commit is noticed (not on a detached HEAD, in a fresh clone or with the git directory gone)."

Unclear: the subject of the sentence, what is "one per branch", whose end names the files, and what the clause after the dash states.

The code:

- Every journal line is also appended to a copy in the git directory (`labkit/formats/attempts.py:926`), one file per branch and area; none on a detached HEAD (`labkit/formats/attempts.py:949`).
- The check of the tree, which the next audit and the stop run, holds the journal to that copy; the staged check does not call this comparison (`labkit/formats/attempts.py:763`).
- A line the copy keeps and the journal lacks is named, and so is each file that an `ended` line among them names and `audits/` lacks. The comparison is by set of lines (`labkit/formats/attempts.py:1025`).
- What it is for and where it does not reach: `labkit/formats/attempts.py:56`.

New: "The check of the tree (the next audit and the stop) also holds the journal to its copy in the git directory, where every journal line is written too, one file per branch and area:" with four sub-bullets — the lost line and the files the end of its attempt names; the copy held as a set of lines; `audits/` deleted whole before a first commit is noticed; the three cases it does not hold in.

The old bullet's "blocks too" followed a bullet that names the next audit, the stop and the commit. The code shows the comparison of journal lines in the tree check only, so the new wording names the next audit and the stop.

## compute → reference comparison: where the table is refused

Old: "It is refused on a kind with a bar naming the criterion (`protocol_check.reference_gap`) and stands in the registration stamp."

Unclear: what "it" is, which kinds refuse it, and whether the bar or the refusal names the criterion.

The code:

- The refusal is of the head's `[reference]` table, by its presence (`labkit/formats/protocol_check.py:1099`).
- A kind with a bar is every kind but `compute`, that is `fit` and `apply` (`labkit/formats/standard_contract.py:190`, `labkit/formats/protocol_block.py:110`).
- The refusal's sentence names the criterion as where such a kind compares its number (`labkit/formats/protocol_check.py:1116`). So the refusal names the criterion, not the bar.
- The stamp holds the digest of the table as written (`labkit/formats/protocol_check.py:1384`).

New: "The `[reference]` table is refused on a kind with a bar: a fit or an apply, every kind but a computation (`protocol_check.reference_gap`). The refusal names the criterion as the place where such a kind compares its number. The table stands in the registration stamp as a digest (`protocol_check.registration_stamp`)."
