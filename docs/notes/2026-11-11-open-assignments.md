# The 68 open rule assignments, site by site — 2026-11-11

*Working note · read by one session, decided by the author where the text says so, not reviewed by a second reader · sites as at 91f9a1c6*

The [review of the rule assignments](2026-11-11-rule-assignment-review.md) left 68 finding sites with an open assignment. The author's work order (TODO, "Arbeitsauftrag für die 68 offenen Zuordnungen") asks for each site one of four findings: a technical contract with the contract named, a methodical duty with the sentence of the rule that states it, a methodical duty no decided rule states, or a check without grounds. A site that forwards several causes gets its assignment where the cause is found. An open assignment weakens no gate: every check blocks or warns as before. Two messages changed their wording, no check changed its grade.

State (`python -m labkit.tools.check_inventory`): 260 finding sites, 83 with a known rule, 76 technical contracts, 30 open, 9 whose rule the cause passes in. Before the pass: 256, 73, 52, 68, 1. The site count rose because four sites that told two causes are two sites each now.

| Finding                                       | Sites of the 68 | State                         |
|-----------------------------------------------|-----------------|-------------------------------|
| technical contract, contract named            | 21              | entered                       |
| known rule, sentence named                    | 8               | entered                       |
| the cause names the rule, at the source       | 9               | entered                       |
| several causes at one site, split still to do | 15              | open, next step               |
| methodical duty no decided rule states        | 15              | open, the author decides each |

No site was found whose check has no grounds at all. One part of a mixed site is a candidate: the README's route block (`finalize.check_open_fields`), which no rule names and no code reads.

## Entered: technical contract (21)

The contract is what a format module or a check needs before it can answer; none of these states a rule of the standard broken. "Decided" marks the author's decision of 2026-11-11.

| Site                                     | Condition                                                             | Contract or precondition                                                               |
|------------------------------------------|-----------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `labkit/checks/code_check.py:245`        | a promise's declared scope names a file or function that is not there | the scope must resolve before its digest can be computed                               |
| `labkit/checks/run_record_check.py:319`  | the record names no commit, or the area lies in no git repository now | comparing helpers with what the run ran needs both                                     |
| `labkit/checks/run_record_check.py:351`  | a helper is in neither the run's commit nor its patch (decided)       | it cannot be compared; the record tells neither the cause nor whether the run used it  |
| `labkit/checks/run_record_check.py:588`  | a `data=` entry without path, sha256 or rows                          | the shape `provenance.describe_data` always writes; a run through runlog cannot differ |
| `labkit/checks/run_record_check.py:844`  | a source is not at its recorded path (decided)                        | its bytes cannot be compared here                                                      |
| `labkit/gates/finalize.py:596`           | a run file could not be opened                                        | a check not executed                                                                   |
| `labkit/gates/finalize.py:603`           | a run file is missing or malformed                                    | an input that does not read                                                            |
| `labkit/gates/finalize.py:681`           | `[reference]` on a fit or an apply                                    | that kind judges by a criterion; the table can never be evaluated there                |
| `labkit/gates/preflight.py:631`          | the area's tests did not run (pytest exit 2–5)                        | a check not executed                                                                   |
| `labkit/gates/registered_report.py:302`  | the first measurements' commits register different reports            | which report was registered cannot be told                                             |
| `labkit/gates/report_check.py:375`       | the first measurement's record names no commit, without saying why    | the registration at that commit cannot be read                                         |
| `labkit/gates/report_check.py:378`       | the first measurement's commit is not in this clone                   | the registration at that commit cannot be read                                         |
| `labkit/gates/report_check.py:391`       | the protocol at that commit cannot be read                            | an input that does not read                                                            |
| `labkit/gates/report_check.py:506`       | the answering run has no `config.json`                                | the run's record is the input of every later check                                     |
| `labkit/gates/report_hold.py:676`        | a discussion block names a protocol that is no protocol file          | a reference that leads nowhere                                                         |
| `labkit/gates/report_hold.py:684`        | a discussion block names a run its protocol's area does not hold      | a reference that leads nowhere                                                         |
| `labkit/gates/report_replacement.py:125` | the `[replaces]` chain leads back to the protocol itself              | a predecessor chain must end                                                           |
| `labkit/gates/preflight.py:340`          | a bound protocol field written twice (decided)                        | readers and writers work on exactly one occurrence, equal wording included             |
| `labkit/gates/finalize.py:499`           | the same at finalize (decided)                                        | the same                                                                               |
| `labkit/gates/report_check.py:297`       | the same at report-check (decided)                                    | the same                                                                               |
| `labkit/checks/result_render.py:377`     | a generated label on two lines (decided)                              | the same                                                                               |
| `labkit/checks/report_blocks.py:588`     | two discussion blocks of one protocol and run (decided)               | the same                                                                               |

That is 22 rows for 21 of the 68: the row at `labkit/gates/report_check.py:375` is half of a site split by its cause, counted in the last section of entries. Two more sites were split and gained a technical half: a comparison of the evidence git could not run (`labkit/formats/evidence.py:386`; changed evidence stays open at `:388`), and an analysis check that did not end within its time (`labkit/gates/report_check.py:751`, `report_check.CheckUnfinished`, a check not executed — decided: after 300 s no result was found, so no violation is told).

The convention "a field stands once" is stated where a writer reads it: `labkit/docs/protocol-field-guide.md`, "The form", and for the discussion block `labkit/docs/agent-guide.md`.

## Entered: known rule (8)

| Site                                     | Condition                                                      | Sentence                                                                                                                                   |
|------------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/report_blocks.py:389`     | a token in a generated block names no run of the repo          | LAB-104 A number leaves the area only through its adoption: "every cited run id names a run of the repo"                                   |
| `labkit/checks/report_blocks.py:392`     | the same in prose, a warning as static evidence                | the same sentence                                                                                                                          |
| `labkit/gates/report_check.py:404`       | the protocol was not committed at the first measurement        | LAB-003 No run without an intent paragraph: "What stood is what the commit of the first measurement holds."                                |
| `labkit/gates/report_check.py:416`       | the registration committed there lacks a choice                | LAB-003: "When it lacked a choice that could steer the result or how it is judged … that measurement is exploratory"                       |
| `labkit/gates/report_check.py:761`       | the analysis script is missing, or its `--check` fails         | LAB-041 Generate numbers, don't retype them: "One analysis script per area … `report-check` holds that the check passes"                   |
| `labkit/formats/answering_run.py:638`    | ids are registered and the answering run reports no intent key | LAB-004 Identifiers make the intent addressable: "every identifier appears as a lowercase key in the `metrics.json` of the reportable run" |
| `labkit/checks/run_record_check.py:1091` | the kept key is missing in `metrics.json` or no finite number  | LAB-041, by the standard's change list: "holds the answering run to the registered key as a finite number (LAB-041 …)" (decided)           |
| `labkit/formats/reference.py:202`        | the kept key cannot be compared with the reference             | the same change-list sentence (decided)                                                                                                    |

One reading to know: the intent-key site also fires before an adoption, on the newest bound run; that run is read as the reportable one. The change-list sentence is not in LAB-041's own text; joining the two is an editorial step the author named and did not order.

The run's own word that it started outside the history (`git` = `no-git` in its record) breaks LAB-010 Commit before the run ("must be in the history before the run"): `labkit/gates/report_check.py:374` for the first measurement (decided), and by the same distinction `labkit/checks/run_record_check.py:318` for the helper comparison. Each is the second half of a site whose other half is a technical contract above; the first-measurement site is counted in the next section, the helper site among the technical contracts.

## Entered: the cause names the rule (9)

These sites told several duties under one assignment. The cause now carries the rule to the site; the inventory lists them as `variable`, because it reads a rule from a constant or a local name, not from a value passed in. The ninth is the first measurement without a commit, which became two sites with one rule each.

| Site                                                                | Cause                                                                                            | Rule                                                                                                            |
|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `labkit/gates/preflight.py:449`, `:450`                             | a finding of an audit record still open                                                          | LAB-015 Preflight audit before freezing: "Every finding is decided"                                             |
|                                                                     | the named record covers no full run of this state                                                | LAB-015, from `audit_gaps.RecordGap.rule`                                                                       |
|                                                                     | the named record, the promise block or the stamp does not read                                   | technical contract, from `audit_gaps.RecordGap.rule`                                                            |
|                                                                     | no permanent test file                                                                           | LAB-016 Resolution check before freezing: "The permanent form is the template-generated test"                   |
| `labkit/gates/preflight.py:640`                                     | the tests fail at preflight                                                                      | LAB-016: "if left blank it fails"                                                                               |
|                                                                     | the tests fail at finalize                                                                       | CODE-003 Test the functions that produce numbers: "Run `python3 -m pytest tests/` before you report any number" |
| `labkit/gates/preflight.py:256`, `labkit/gates/finalize.py:935`     | the `[protocol]` table or a key of it is not there                                               | LAB-011 Required-field check: "fields required" (`protocol_block.HeadPartMissing`)                              |
|                                                                     | the head does not read                                                                           | technical contract (`protocol_check.head_rule`)                                                                 |
| `labkit/gates/preflight.py:334`, `labkit/gates/report_check.py:276` | an owed field or head value absent                                                               | LAB-011 (`protocol_check.MustGap.rule`)                                                                         |
|                                                                     | `frozen = true` without its preflight record named                                               | LAB-015: "Between the instrument check and `frozen = true`, an independent reader reads …"                      |
|                                                                     | the `[[promise]]` tables owed                                                                    | LAB-004: "requires them when `frozen = true` and for every full run"                                            |
|                                                                     | a table that does not read, `[reference]` on a kind with a criterion, ids in the earlier letters | technical contract                                                                                              |
|                                                                     | a model claim on the wrong kind; `frozen = true` at low repeat cost                              | open: no sentence states either                                                                                 |
| `labkit/gates/report_check.py:374`, `:375`                          | the first measurement's record says it started outside the history                               | LAB-010 Commit before the run; else the technical contract                                                      |
| `labkit/gates/finalize.py:759`                                      | a computation's `[kept]` table or value missing                                                  | LAB-011 (`protocol_check.kept_gaps`)                                                                            |
|                                                                     | `[kept]` does not read, or stands on a fit or an apply                                           | technical contract                                                                                              |

Two causes in the field list stay open and no longer show in the inventory's count of open sites: the model claim on the wrong kind (`protocol_check.kind_gap`) and `frozen = true` at low repeat cost.

## Open: several causes at one site (15)

Each forwards messages whose causes break different rules or none. The causes per site stand in the readers' tables of the review (`labkit-evidence`, folder `2026-11-11-rule-assignment-review`).

| Site                                     | What it forwards                                                                                                                     |
|------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/intent_check.py:287`      | key mismatch and constant mismatch (LAB-004), promises changed after the run (LAB-003), an old digest format (technical)             |
| `labkit/checks/notes_check.py:254`       | four softer note conventions, one of them stated by LAB-082                                                                          |
| `labkit/checks/report_blocks.py:287`     | a block's protocol: head does not read (technical), no protocol there, no result adopted (LAB-104)                                   |
| `labkit/formats/answering_run.py:622`    | no run stands: nothing measured, a newer run unreadable, two runs in one second (technical), the adopted run cannot answer (LAB-043) |
| `labkit/formats/protocol_history.py:391` | `annotation_validity` not bound: three causes without a sentence, one technical                                                      |
| `labkit/gates/finalize.py:306`           | model not recorded (LAB-027), a single draw (LAB-036), a run that cannot be reported                                                 |
| `labkit/gates/finalize.py:312`           | per declared arm: profile file missing, fingerprint or alias not in the run's record                                                 |
| `labkit/gates/finalize.py:519`           | the README's route block and its stations (no rule, no reader), `evaluate_rows` missing                                              |
| `labkit/gates/finalize.py:539`           | generated counts differ from the run (LAB-041), the named run is not there or no preparation run                                     |
| `labkit/gates/finalize.py:556`           | no `outputs.json`, no git repository (technical), an output untracked                                                                |
| `labkit/gates/report_check.py:518`       | the answering run is no measurement, or acknowledged an unfrozen protocol                                                            |
| `labkit/gates/registered_report.py:177`  | the registered report owes its result or handover block; the report or its blocks do not read                                        |
| `labkit/gates/report_hold.py:607`        | a block that does not parse (technical), a discussion head lacking a key (LAB-104)                                                   |
| `labkit/gates/report_replacement.py:65`  | `[replaces]` does not read (technical), a change without its reason                                                                  |
| `labkit/gates/report_replacement.py:116` | no protocol carries the predecessor's id, or several do (a doubled id, technical)                                                    |

## Open: methodical duty no decided rule states (15)

Provisional finding, in the work order's words: a methodical duty without a decided rule. Nothing follows for the standard from this list. The author decides each (2026-11-11), in this order: registration, the comparison of the result, the provenance of the outputs.

| Group                 | Site                                     | Duty the check holds                                                              | The author's note, 2026-11-11                                  |
|-----------------------|------------------------------------------|-----------------------------------------------------------------------------------|----------------------------------------------------------------|
| registration          | `labkit/gates/report_check.py:263`       | a reported number at high repeat cost owes `frozen = true`                        |                                                                |
|                       | `labkit/gates/report_replacement.py:80`  | a protocol that replaces another is exploratory                                   |                                                                |
|                       | `labkit/gates/report_replacement.py:179` | every difference against the predecessor is declared                              |                                                                |
|                       | `labkit/gates/report_replacement.py:192` | a declared change shows in the two registrations                                  |                                                                |
|                       | `labkit/gates/registered_report.py:328`  | the registered report stays as the first measurement's commit registered it       | no sufficient scientific ground seen for a fixed report target |
| result comparison     | `labkit/formats/reference.py:171`        | a comparison in the result is registered in `[reference]`                         |                                                                |
|                       | `labkit/formats/reference.py:185`        | a registered comparison gets its verdict from the run                             |                                                                |
|                       | `labkit/formats/reference.py:231`        | the reference stays as the run compared with it                                   |                                                                |
| provenance of outputs | `labkit/checks/run_record_check.py:830`  | an output file is the one the run recorded                                        |                                                                |
|                       | `labkit/checks/run_record_check.py:1000` | a continued output holds no rows of a run with other code                         |                                                                |
| evidence              | `labkit/formats/evidence.py:388`         | committed evidence does not change beyond what labkit writes (the rule candidate) | needs the ways of correction that stay allowed, stated         |
| report                | `labkit/gates/report_hold.py:995`        | an adopted run is not discussed as not reported                                   |                                                                |
| warnings              | `labkit/gates/finalize.py:242`           | runs newer than the adopted one                                                   | each needs a bounded statement of the suspicion it gives       |
|                       | `labkit/gates/preflight.py:356`          | the repeat cost was lowered after the first commit                                | the same                                                       |
|                       | `labkit/checks/run_record_check.py:514`  | a criterion's denominator matches no recorded count                               | the same                                                       |
