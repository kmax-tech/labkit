# The 68 open rule assignments, site by site — 2026-11-11

*Working note · first pass by one session, not reviewed by a second reader · sites as at a61dd7a3*

The [review of the rule assignments](2026-11-11-rule-assignment-review.md) left 68 finding sites with an open assignment. The author's work order (TODO, "Arbeitsauftrag für die 68 offenen Zuordnungen") asks for each site one of four findings: a technical contract with the contract named, a methodical duty with the sentence of the rule that states it, a methodical duty no decided rule states, or a check without grounds. A site that forwards several causes gets its assignment where the cause is found. An open assignment weakens no gate: every check blocks or warns as before, and this note changes no effect of a check.

State after the first pass (`python -m labkit.tools.check_inventory`): 257 finding sites, 79 with a known rule, 67 technical contracts, 45 open, 6 whose rule the caller passes in. Before: 256, 73, 52, 68, 3.

| Finding                                       | Sites | State                   |
|-----------------------------------------------|-------|-------------------------|
| technical contract, contract named            | 14    | entered                 |
| known rule, sentence named                    | 6     | entered                 |
| rule passed in from the cause                 | 3     | entered                 |
| several causes at one site, split still to do | 20    | open, next step         |
| a field or block written twice                | 5     | open, author's decision |
| a sentence exists outside the rule's own text | 5     | open, author's decision |
| methodical duty no decided rule states        | 15    | open, author's decision |

No site was found whose check has no grounds at all. One part of a mixed site is a candidate: the README's route block (`finalize.check_open_fields`), which no rule names and no code reads.

## Entered: technical contract

The contract is what the format module or the check needs before it can answer; none of these states a rule of the standard broken.

| Site                                     | Condition                                                             | Contract or precondition                                                               |
|------------------------------------------|-----------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `labkit/checks/code_check.py:245`        | a promise's declared scope names a file or function that is not there | the scope must resolve before its digest can be computed                               |
| `labkit/checks/run_record_check.py:311`  | the run recorded no commit, or the area lies in no git repository now | comparing helpers with what the run ran needs both                                     |
| `labkit/checks/run_record_check.py:584`  | a `data=` entry without path, sha256 or rows                          | the shape `provenance.describe_data` always writes; a run through runlog cannot differ |
| `labkit/gates/finalize.py:595`           | a run file could not be opened                                        | a check not executed                                                                   |
| `labkit/gates/finalize.py:602`           | a run file is missing or malformed                                    | an input that does not read                                                            |
| `labkit/gates/finalize.py:680`           | `[reference]` on a fit or an apply                                    | that kind judges by a criterion; the table can never be evaluated there                |
| `labkit/gates/preflight.py:631`          | the area's tests did not run (pytest exit 2–5)                        | a check not executed                                                                   |
| `labkit/gates/registered_report.py:302`  | the first measurements' commits register different reports            | which report was registered cannot be told                                             |
| `labkit/gates/report_check.py:367`       | the first measurement's commit is not in this clone                   | the registration at that commit cannot be read                                         |
| `labkit/gates/report_check.py:380`       | the protocol at that commit cannot be read                            | an input that does not read                                                            |
| `labkit/gates/report_check.py:495`       | the answering run has no `config.json`                                | the run's record is the input of every later check                                     |
| `labkit/gates/report_hold.py:676`        | a discussion block names a protocol that is no protocol file          | a reference that leads nowhere                                                         |
| `labkit/gates/report_hold.py:684`        | a discussion block names a run its protocol's area does not hold      | a reference that leads nowhere                                                         |
| `labkit/gates/report_replacement.py:125` | the `[replaces]` chain leads back to the protocol itself              | a predecessor chain must end                                                           |

`formats.evidence.change_blockers` was one site for two causes and is two now: a comparison git could not run records the technical contract (`labkit/formats/evidence.py:386`); changed evidence stays open as the rule candidate (`:388`).

## Entered: known rule

| Site                                  | Condition                                                      | Sentence                                                                                                                                   |
|---------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/report_blocks.py:389`  | a token in a generated block names no run of the repo          | LAB-104 A number leaves the area only through its adoption: "every cited run id names a run of the repo"                                   |
| `labkit/checks/report_blocks.py:392`  | the same in prose, a warning as static evidence                | the same sentence                                                                                                                          |
| `labkit/gates/report_check.py:393`    | the protocol was not committed at the first measurement        | LAB-003 No run without an intent paragraph: "What stood is what the commit of the first measurement holds."                                |
| `labkit/gates/report_check.py:405`    | the registration committed there lacks a choice                | LAB-003: "When it lacked a choice that could steer the result or how it is judged … that measurement is exploratory"                       |
| `labkit/gates/report_check.py:736`    | the analysis script is missing, or its `--check` does not pass | LAB-041 Generate numbers, don't retype them: "One analysis script per area … `report-check` holds that the check passes"                   |
| `labkit/formats/answering_run.py:638` | ids are registered and the answering run reports no intent key | LAB-004 Identifiers make the intent addressable: "every identifier appears as a lowercase key in the `metrics.json` of the reportable run" |

Two readings to know. The `--check` site also fires when the check does not finish within 300 s; that is read as "does not pass". The intent-key site also fires before an adoption, on the newest bound run; that run is read as the reportable one.

## Entered: the rule comes from the cause

Three sites told two or three duties under one assignment. The cause now names the rule.

| Site                                    | Cause                                                          | Rule                                                                                                            |
|-----------------------------------------|----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| `labkit/gates/preflight.py:449`, `:450` | a finding of an audit record still open                        | LAB-015 Preflight audit before freezing: "Every finding is decided"                                             |
|                                         | the named record covers no full run of this state              | LAB-015, from `audit_gaps.RecordGap.rule`                                                                       |
|                                         | the named record, the promise block or the stamp does not read | technical contract, from `audit_gaps.RecordGap.rule`                                                            |
|                                         | no permanent test file                                         | LAB-016 Resolution check before freezing: "The permanent form is the template-generated test"                   |
| `labkit/gates/preflight.py:640`         | the tests fail at preflight                                    | LAB-016: "if left blank it fails"                                                                               |
|                                         | the tests fail at finalize                                     | CODE-003 Test the functions that produce numbers: "Run `python3 -m pytest tests/` before you report any number" |

The inventory lists these three sites as `variable`: it reads a rule from a constant or a local name, not from a parameter.

## Open: several causes at one site (20)

Each forwards messages whose causes break different rules or none. The assignment is to be made where the cause is found and carried to the output. The causes per site stand in the readers' tables of the review (`labkit-evidence`, folder `2026-11-11-rule-assignment-review`).

| Site                                     | What it forwards                                                                                                                     |
|------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/intent_check.py:287`      | key mismatch and constant mismatch (LAB-004), promises changed after the run (LAB-003), an old digest format (technical)             |
| `labkit/checks/notes_check.py:254`       | four softer note conventions, one of them stated by LAB-082                                                                          |
| `labkit/checks/report_blocks.py:287`     | a block's protocol: head does not read (technical), no protocol there, no result adopted (LAB-104)                                   |
| `labkit/formats/answering_run.py:622`    | no run stands: nothing measured, a newer run unreadable, two runs in one second (technical), the adopted run cannot answer (LAB-043) |
| `labkit/formats/protocol_history.py:391` | `annotation_validity` not bound: three causes without a sentence, one technical                                                      |
| `labkit/gates/finalize.py:305`           | model not recorded (LAB-027), a single draw (LAB-036), a run that cannot be reported                                                 |
| `labkit/gates/finalize.py:311`           | per declared arm: profile file missing, fingerprint or alias not in the run's record                                                 |
| `labkit/gates/finalize.py:518`           | the README's route block and its stations (no rule, no reader), `evaluate_rows` missing                                              |
| `labkit/gates/finalize.py:538`           | generated counts differ from the run (LAB-041), the named run is not there or no preparation run                                     |
| `labkit/gates/finalize.py:555`           | no `outputs.json`, no git repository (technical), an output untracked                                                                |
| `labkit/gates/finalize.py:758`           | `[kept]` does not parse, stands on the wrong kind, is missing, still a placeholder                                                   |
| `labkit/gates/finalize.py:934`           | the head does not read: a missing key (LAB-011), every other cause technical                                                         |
| `labkit/gates/preflight.py:256`          | the same head causes                                                                                                                 |
| `labkit/gates/preflight.py:334`          | `check_fields.missing_must`, filled from nine sources under four rules and the technical contract                                    |
| `labkit/gates/report_check.py:267`       | the same nine sources                                                                                                                |
| `labkit/gates/report_check.py:507`       | the answering run is no measurement, or acknowledged an unfrozen protocol                                                            |
| `labkit/gates/registered_report.py:177`  | the registered report owes its result or handover block; the report or its blocks do not read                                        |
| `labkit/gates/report_hold.py:607`        | a block that does not parse (technical), a discussion head lacking a key (LAB-104)                                                   |
| `labkit/gates/report_replacement.py:65`  | `[replaces]` does not read (technical), a change without its reason                                                                  |
| `labkit/gates/report_replacement.py:116` | no protocol carries the predecessor's id, or several do (a doubled id, technical)                                                    |

## Open: a field or block written twice (5)

`labkit/gates/preflight.py:340`, `labkit/gates/finalize.py:498`, `labkit/gates/report_check.py:288` (a bound protocol field), `labkit/checks/result_render.py:377` (a generated label), `labkit/checks/report_blocks.py:588` (a discussion block per protocol and run).

The convention is stated in the format module only: `protocol_check.repeated_fields` says a bound field is written at most once, because "which copy the registration means cannot be told". No document under `docs/` states it. The purpose can be named: every reader takes a field by its label and gets one value (`protocol_check.field_values`), and both writers replace by label or key and refuse several matches (`report_blocks.with_discussion`). The checks refuse copies with equal wording too, where the purpose does not bite.

## Open: a sentence exists outside the rule's own text (5)

| Site                                     | Condition                                                       | The sentence and why it was not entered                                                                                             |
|------------------------------------------|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| `labkit/checks/run_record_check.py:1087` | the kept key is missing in `metrics.json` or no finite number   | "holds the answering run to the registered key as a finite number (LAB-041 …)" stands in the standard's change list, not in LAB-041 |
| `labkit/formats/reference.py:200`        | the kept key cannot be compared with the reference              | the same change-list sentence                                                                                                       |
| `labkit/checks/run_record_check.py:349`  | an imported helper is in neither the run's commit nor its patch | LAB-010 Commit before the run states it for a file untracked then; the site cannot tell that from a file that did not exist yet     |
| `labkit/checks/run_record_check.py:840`  | a source is not at its recorded path                            | technical (the bytes cannot be compared here), or LAB-024 Reproducible, "Script + data + output together", which names no path      |
| `labkit/gates/report_check.py:357`       | the first measurement recorded no commit                        | technical (the registration cannot be read), or LAB-010, whose duty the run broke when it started outside the history               |

## Open: methodical duty no decided rule states (15)

Provisional finding, in the work order's words: a methodical duty without a decided rule. Nothing follows for the standard from this list.

| Site                                     | Duty the check holds                                                              |
|------------------------------------------|-----------------------------------------------------------------------------------|
| `labkit/formats/reference.py:169`        | a comparison in the result is registered in `[reference]`                         |
| `labkit/formats/reference.py:183`        | a registered comparison gets its verdict from the run                             |
| `labkit/formats/reference.py:229`        | the reference stays as the run compared with it                                   |
| `labkit/gates/registered_report.py:328`  | the registered report stays as the first measurement's commit registered it       |
| `labkit/gates/report_check.py:254`       | a reported number at high repeat cost owes `frozen = true`                        |
| `labkit/gates/report_hold.py:995`        | an adopted run is not discussed as not reported                                   |
| `labkit/gates/report_replacement.py:80`  | a protocol that replaces another is exploratory                                   |
| `labkit/gates/report_replacement.py:179` | every difference against the predecessor is declared                              |
| `labkit/gates/report_replacement.py:192` | a declared change shows in the two registrations                                  |
| `labkit/checks/run_record_check.py:826`  | an output file is the one the run recorded                                        |
| `labkit/checks/run_record_check.py:996`  | a continued output holds no rows of a run with other code                         |
| `labkit/formats/evidence.py:388`         | committed evidence does not change beyond what labkit writes (the rule candidate) |
| `labkit/gates/finalize.py:241`           | warning: runs newer than the adopted one                                          |
| `labkit/gates/preflight.py:356`          | warning: the repeat cost was lowered after the first commit                       |
| `labkit/checks/run_record_check.py:510`  | warning: a criterion's denominator matches no recorded count                      |
