# Cut proposal: `labkit/formats/findings.py`

> Written by a planning agent on 2026-11-26 that only read the repo (state `6e180505`); nothing here is built or decided. The author's decisions on the nine open points stand in `TODO.md`. Counts come from an `ast` walk, the suite was not run.

State read: `main` at `6e180505`. The file has 2 563 lines and 149 top-level names: 88 functions and classes, 61 constants. Counts come from an `ast` walk over `labkit/` and `tests/`, not from reading alone.

## 1. The parts, corrected against the audit's six

The audit named six parts. Reading the names and their dependencies gives seven, and two of the audit's six do not survive as modules.

| Audit's part           | What I found                                                                                                                                                                                                                            |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| data model             | Holds. It also carries the validity rules "one rule for the writer and the reader" (`count_problem`, `counts_outrun`, `verdict_disagrees`, `fix_verdict_problem`, `undetermined_finding_problem`, `undetermined_fix_problem`).          |
| request grammar        | Wider than requests: the whole required check (metrics key, `file:`, `diff:`, `code:`) and its wording as an order.                                                                                                                     |
| (not named)            | The grammar of an auditor's line: tag, fields, place, subject, rule. Read by `audit_reply`, `decision_review`, `report_review`.                                                                                                         |
| decision rules         | Two questions: which decision a finding may take and what it owes; and what a limitation does to the verdicts.                                                                                                                          |
| TOML writer and parser | Holds. It includes the rewrite of a decision in place (about 355 lines), which is separable only with a rename (decision 2).                                                                                                            |
| record status          | Splits in two. File names under `audits/` are needed by the writer and by five sibling formats, so they sit low. The area walk needs the reader's private `_record_of`, so it stays with the reader. As one module it would be a cycle. |
| ways out               | No part of its own: three functions, 45 lines. `decide_way` and `decide_ways` answer the decisions question; `record_way` answers the records question.                                                                                 |

The parts by the question each answers:

| #   | Question                                                                                 | Module                    | Names | Lines (approx.) |
|-----|------------------------------------------------------------------------------------------|---------------------------|-------|-----------------|
| A   | Which check does a finding require, and what does it ask for?                            | `finding_check` (new)     | 20    | 275             |
| B   | What does an auditor's line say: tag, fields, subject, rule?                             | `finding_line` (new)      | 23    | 260             |
| C   | What is a finding, a fix verdict, a record, and is a finding still open?                 | `findings` (stays)        | 31    | 610             |
| D   | What does a limitation do to the verdicts, and how does the protocol carry it?           | `finding_limits` (new)    | 11    | 95              |
| E   | What is a file under `audits/` called, of which kind, and in which order written?        | `audit_files` (new)       | 15    | 135             |
| F   | Which decision may a finding take, what does it entail and owe?                          | `finding_decisions` (new) | 11    | 300             |
| G   | How is a record written, read and decided in place, and which records does an area hold? | `audit_records` (new)     | 38    | 1 100           |

The naming follows the siblings: `audit_gaps`, `failed_attempts`, `reviews`, `report_reviews`, `handovers` are plural nouns for a file kind; `protocol_block`, `protocol_fields`, `decision_history` are noun plus aspect. All six stems are free. `finding_line` is a parameter name in `labkit/gates/ways_out.py:56`, a module that would not import it.

### Every top-level name

"L/T" is the number of labkit modules and test files that read the name in code. A dash means no outside reader.

**A · `finding_check`**

| Line | Name               | What it is                                                   | L/T |
|------|--------------------|--------------------------------------------------------------|-----|
| 428  | `CHECK_FIELD`      | pattern that finds a `· check:` field                        | –   |
| 434  | `_CHECK`           | pattern of the whole field: key and note                     | –   |
| 438  | `CHECK_KEY`        | shape of a stored check key                                  | –   |
| 441  | `FILE_CHECK`       | prefix of a check asking for a file's content                | 3/0 |
| 447  | `DIFF_CHECK`       | prefix of a check asking for two runs' code difference       | 1/0 |
| 451  | `CODE_CHECK`       | prefix of a check asking for a file as a run started from it | 1/0 |
| 454  | `REQUEST_CHECKS`   | the two prefixes a follow-up audit serves                    | 3/0 |
| 457  | `CHECK_FORM`       | the form sentence the refusals quote                         | –   |
| 465  | `_LINES`           | pattern of a closing line range                              | –   |
| 467  | `DIFF_SIDES`       | `old`, `new`                                                 | –   |
| 471  | `DiffRequest`      | a `diff:` check read                                         | 1/1 |
| 487  | `CodeRequest`      | a `code:` check read                                         | 1/1 |
| 496  | `_repo_path`       | holds a request's path inside the repository                 | –   |
| 507  | `_line_range`      | reads and orders a line range                                | –   |
| 515  | `diff_request`     | parses a `diff:` check                                       | 0/1 |
| 545  | `code_request`     | parses a `code:` check                                       | 0/1 |
| 563  | `evidence_request` | parses either request                                        | 1/0 |
| 573  | `check_of`         | (key, note) of a finding's closing check field               | 0/2 |
| 845  | `request_words`    | a request in words                                           | –   |
| 867  | `check_order`      | what a required check asks of the measuring code             | 2/3 |

**B · `finding_line`**

| Line | Name                    | What it is                                        | L/T |
|------|-------------------------|---------------------------------------------------|-----|
| 195  | `GRADES`                | BLOCKER, WARNING, NOTE                            | 1/1 |
| 202  | `LEAD`                  | what may stand before a line's keyword            | 3/0 |
| 203  | `SEP`                   | the separator after it                            | 3/0 |
| 206  | `tag_head`              | pattern of a tagged line's head                   | 1/0 |
| 215  | `GRADE_HEAD`            | that pattern for the grades                       | 1/0 |
| 218  | `_FIELD_SEP`            | separator between fields                          | –   |
| 222  | `TaggedLine`            | a line read: tag and fields, `file_place`         | –   |
| 250  | `tagged_line`           | the one reader of a tagged line                   | 2/1 |
| 279  | `IMPLEMENTATION`        | subject word                                      | 1/2 |
| 280  | `STATEMENT`             | subject word                                      | 0/2 |
| 281  | `UNDETERMINED`          | subject word                                      | 2/3 |
| 282  | `SUBJECTS`              | the three subjects                                | 0/2 |
| 284  | `SETTLED_SUBJECTS`      | the two a follow-up may name                      | 1/1 |
| 285  | `SUBJECT_FORM`          | the form sentence for the subject field           | –   |
| 606  | `subject_of`            | the subject a finding line names                  | 0/1 |
| 633  | `RULE_FORM`             | the form sentence for the rule field              | –   |
| 639  | `_RULE_FIELD`           | pattern of a `LAB-nnn` field                      | –   |
| 640  | `_NEW_CLASS_FIELD`      | pattern of a "new class" field                    | –   |
| 643  | `active_rule_of`        | the rule a finding line names, held to the ledger | 0/1 |
| 682  | `_ledger_titles`        | rule id to name, cached                           | –   |
| 687  | `recorded_rule`         | stored rule field to `RuleAssignment`             | 0/1 |
| 699  | `stored_rule`           | `RuleAssignment` to stored rule field             | 1/1 |
| 711  | `recorded_rule_problem` | why a stored rule cannot stand                    | –   |

**C · `findings` (stays)**

| Line    | Name                                            | What it is                                        | L/T                |
|---------|-------------------------------------------------|---------------------------------------------------|--------------------|
| 169–172 | `OPEN`, `FIXED`, `LIMITATION`, `FALSE_POSITIVE` | the status words                                  | 5/0, 4/0, 4/0, 2/0 |
| 173     | `STATUSES`                                      | all four                                          | 1/0                |
| 174     | `REASON_OWED`                                   | statuses that owe a reason                        | 2/0                |
| 179     | `CLOSING`                                       | statuses that leave no Limitation line            | 2/0                |
| 181     | `DECIDED`                                       | every status but open                             | 1/1                |
| 183     | `DECIDED_LIST`                                  | the decided statuses as a step names them         | 6/1                |
| 186     | `CARRIED_CLOSING`                               | closing a carried finding that owes a review      | –                  |
| 190     | `EFFECT_GRADES`                                 | grades whose limitation carries an effect         | 1/0                |
| 294     | `MODES`                                         | preflight, analysis                               | 5/0                |
| 297     | `NO_RUN`                                        | an analysis record's run when none was bound      | 4/6                |
| 300     | `FindingsError`                                 | a findings file that cannot be read               | 17/8               |
| 304     | `EffectFormError`                               | an effect missing or malformed                    | 1/1                |
| 311     | `Finding`                                       | one finding and its decision                      | 6/12               |
| 392     | `FIX_VERDICTS`                                  | resolved, unresolved, not_assessable              | 0/1                |
| 396     | `FixVerdict`                                    | a follow-up's verdict on an earlier BLOCKER       | 5/6                |
| 456     | `CARRIES_REF`                                   | shape of `<record>#<n>`                           | –                  |
| 763     | `undetermined_finding_problem`                  | why an undetermined finding cannot stand          | –                  |
| 786     | `undetermined_fix_problem`                      | why a verdict cannot stand on the finding judged  | 1/1                |
| 1088    | `AuditedState`                                  | the state a record binds                          | 3/3                |
| 1132    | `Record`                                        | one audit's findings file as data                 | 14/6               |
| 1192    | `OpenFinding`                                   | an open finding with its record                   | 3/0                |
| 1215    | `number_of`                                     | a finding's number in its record                  | 1/1                |
| 1226    | `open_findings`                                 | every open finding; the table of the gates' rules | 7/3                |
| 1274    | `open_blockers`                                 | the open BLOCKERs                                 | 2/1                |
| 1315    | `counts_outrun`                                 | counts exceed the listed lines                    | –                  |
| 1332    | `count_problem`                                 | a count is no non-negative integer                | –                  |
| 1341    | `verdict_disagrees`                             | counts differ from the listed lines               | –                  |
| 1626    | `fix_verdict_problem`                           | why fix verdicts cannot stand in one record       | 1/1                |

**D · `finding_limits`**

| Line | Name              | What it is                                | L/T |
|------|-------------------|-------------------------------------------|-----|
| 189  | `EFFECT_STANDS`   | the effect word `stands`                  | 2/3 |
| 191  | `_EFFECT_NOT`     | pattern of `<ids> not assessable`         | –   |
| 192  | `EFFECT_FORM`     | the form sentence for an effect           | –   |
| 1055 | `leaves_unjudged` | does the effect void verdicts             | 2/0 |
| 1063 | `effect_ids`      | the promise ids an effect leaves unjudged | 2/2 |
| 1079 | `effect_sentence` | the effect as the Limitation line opens   | –   |
| 1188 | `LIMIT_PREFIX`    | how a Limitation label opens              | 3/0 |
| 1282 | `limit_label`     | the label of finding N of a record        | 2/1 |
| 1289 | `UNCONFIRMED`     | opening of an unconfirmed limit           | –   |
| 1292 | `limit_line`      | the value of a Limitation line            | 1/0 |
| 1303 | `answer_note`     | the note in Recorded results              | 1/1 |

**E · `audit_files`**

| Line | Name                     | What it is                                | L/T  |
|------|--------------------------|-------------------------------------------|------|
| 141  | `DIR`                    | the `audits` folder                       | 10/8 |
| 143  | `JOURNAL`                | the attempt journal's name                | 3/0  |
| 145  | `ANSWERS`                | the answers folder                        | 2/1  |
| 147  | `FAILED_SUFFIX`          | suffix of a failed attempt                | 2/3  |
| 152  | `REVIEW_WORD`            | the word in a review's name               | 2/0  |
| 153  | `CLAIM_REVIEW_WORD`      | the word in a claim review's name         | 1/0  |
| 156  | `name_ending`            | how a `<minute>-WORD` name ends           | 1/0  |
| 166  | `REVIEW_NAME`            | pattern of a decision review's name       | 1/0  |
| 1659 | `create_file`            | exclusive create, numbering a second file | 3/0  |
| 2342 | `_NAME_MINUTE_SHAPE`     | the minute's shape as a pattern           | –    |
| 2349 | `_WRITTEN_WORDS`         | the words of the mode's place             | –    |
| 2355 | `_WRITTEN_NAME`          | pattern of every written name             | –    |
| 2361 | `written_order`          | sort key of a written file                | 3/2  |
| 2375 | `is_record_name`         | is this name a record of findings         | 1/0  |
| 2475 | `names_preflight_record` | is this name a preflight record's         | 1/0  |

**F · `finding_decisions`**

| Line | Name                     | What it is                                    | L/T |
|------|--------------------------|-----------------------------------------------|-----|
| 722  | `subject_refusal`        | why a status cannot decide a finding          | 1/0 |
| 757  | `allowed_decisions`      | the statuses a finding can take               | 2/1 |
| 829  | `decision_after_restore` | the status after a field is restored          | 1/1 |
| 910  | `decision_entails`       | what a decided status entails                 | 1/1 |
| 1012 | `corrected_field`        | the protocol field a `fixed` finding corrects | 3/2 |
| 1033 | `decision_digest`        | the digest reviews and fix verdicts bind to   | 5/7 |
| 1359 | `false_positive_blocker` | owes a decision review                        | 2/0 |
| 1370 | `fixed_claim`            | a Conclusion BLOCKER decided fixed            | 4/0 |
| 1391 | `carried_and_closed`     | a carried finding closed false-positive       | 2/1 |
| 2520 | `decide_way`             | the `--decide` way out of an open finding     | 2/2 |
| 2546 | `decide_ways`            | the same for every open finding of a record   | 1/0 |

**G · `audit_records`**

| Line      | Name                                                       | What it is                                    | L/T  |
|-----------|------------------------------------------------------------|-----------------------------------------------|------|
| 1402      | `REASON_FORM`                                              | why a hand-changed record may not parse       | –    |
| 1409      | `_head_problem`                                            | what is wrong with the head `write` is handed | –    |
| 1435      | `write`                                                    | writes an audit's record                      | 1/30 |
| 1549      | `_carried_lines`                                           | carried findings as tables                    | –    |
| 1590      | `_fix_verdict_lines`                                       | fix verdicts as tables                        | –    |
| 1677      | `_audit_table`                                             | the `[audit]` table held to its shape         | –    |
| 1716      | `_run_fields_problem`                                      | run fields against the mode                   | –    |
| 1742      | `_finding`                                                 | one `[[finding]]` table read                  | –    |
| 1791      | `_replaced_decisions`                                      | a finding's replaced decisions read           | –    |
| 1814      | `_auditor_fields`                                          | check, note, subject, rule of a table         | –    |
| 1863      | `read`                                                     | reads a record                                | 4/8  |
| 1872      | `_record_of`                                               | reads a record's text                         | –    |
| 1926–1928 | `_FIX_VERDICT_KEYS`, `_FIX_CHECK_KEYS`, `_FIX_SUBJECT_KEY` | the allowed keys of a fix verdict             | –    |
| 1931      | `_fix_verdicts`                                            | the `[[fix_verdict]]` tables read             | –    |
| 1984      | `_FINDING_HEADER`                                          | the line that opens a finding table           | –    |
| 1987      | `_DECISION_LINE`                                           | a one-line decision value                     | –    |
| 1993      | `_DECISION_OPEN`                                           | the opening of a multi-line value             | –    |
| 1996      | `_closing`                                                 | where a multi-line string closes              | –    |
| 2016      | `_multi_line_end`                                          | where a multi-line value ends                 | –    |
| 2032      | `_decision_lines`                                          | where a table's decision lines stand          | –    |
| 2087      | `without_decisions`                                        | a record's text without decision lines        | 2/2  |
| 2112      | `findings_in`                                              | the findings a text holds, or None            | 1/2  |
| 2123      | `with_decision`                                            | a text with one table's status and reason set | 1/0  |
| 2145      | `write_decision`                                           | stores a person's decision                    | 1/10 |
| 2224      | `_effect_problem`                                          | why an effect cannot stand                    | –    |
| 2243      | `_hold_effect`                                             | raises on an owed or malformed effect         | –    |
| 2258      | `_decided_text`                                            | the record's text with the decision set       | –    |
| 2332      | `_head`                                                    | what a decision must leave unchanged          | –    |
| 2386      | `RecordStatus`                                             | readable records and errors                   | –    |
| 2393      | `record_status`                                            | every record of an area, tree or index        | 1/1  |
| 2452      | `_recovery_record_order`                                   | order with a naming error kept apart          | –    |
| 2462      | `area_records`                                             | the strict view of an area's records          | 8/13 |
| 2485      | `repo_records`                                             | every record under `experiments/`             | 1/1  |
| 2494      | `new_class_findings`                                       | findings the auditor gave no rule             | 1/1  |
| 2509      | `open_elsewhere`                                           | open findings in other areas                  | 1/1  |
| 2553      | `record_way`                                               | the way out of a record that does not read    | 8/2  |

The parts are interleaved in the file today (34 alternating line runs), so no step is one contiguous block.

## 2. Dependency graph and the cut

| Module              | Uses of other parts                                                                                                                                                                                                                                                                                                                                                                                 |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `finding_check`     | none (outside: `runs.RUN_ID`)                                                                                                                                                                                                                                                                                                                                                                       |
| `finding_line`      | none (outside: `gate`, `rules`)                                                                                                                                                                                                                                                                                                                                                                     |
| `findings`          | `finding_check`: `CHECK_FORM`. `finding_line`: `GRADES`, `IMPLEMENTATION`, `STATEMENT`, `UNDETERMINED`, `SETTLED_SUBJECTS`, `tagged_line`.                                                                                                                                                                                                                                                          |
| `finding_limits`    | `findings`: `Finding`, `Record` (annotations). Outside: `promises`.                                                                                                                                                                                                                                                                                                                                 |
| `audit_files`       | `findings`: `FindingsError`, `MODES`. Outside: `repo`, `runs`, `standard_contract`.                                                                                                                                                                                                                                                                                                                 |
| `finding_decisions` | `finding_check`: `REQUEST_CHECKS`, `check_order`. `finding_line`: the three subject words. `findings`: ten names (statuses, `Finding`, `Record`, `OpenFinding`). `finding_limits`: `EFFECT_STANDS`.                                                                                                                                                                                                 |
| `audit_records`     | `finding_check`: `CHECK_KEY`, `REQUEST_CHECKS`, `check_of`, `evidence_request`. `finding_line`: `GRADES`, `SUBJECTS`, `subject_of`, `active_rule_of`, `recorded_rule`, `recorded_rule_problem`, `stored_rule`. `findings`: 17 names. `finding_limits`: `EFFECT_FORM`, `effect_ids`. `audit_files`: `DIR`, `create_file`, `is_record_name`, `written_order`. `finding_decisions`: `subject_refusal`. |

The graph has no cycle. Where one would arise, and how the cut avoids it:

1. **Model and line grammar.** `Finding.place` calls `tagged_line`; `subject_of` needs `SUBJECTS`. So `GRADES` and the subject words go down into `finding_line`, and the model imports them.
2. **"Record status" as one module.** `write` needs `DIR` and `create_file`; `record_status` needs `read` and `_record_of`. So the names go down into `audit_files`, and the walk stays with the reader.
3. **Model and limits.** `Finding.effect_allowed` needs `EFFECT_GRADES`; `limit_label` and `limit_line` take a `Record` and a `Finding`. So `EFFECT_GRADES` stays in the model. It loses the comment it shares with `EFFECT_STANDS` (lines 187–188).
4. **Ways out in `commands`.** `decision_entails` imports `commands.audit_command`, and `decide_way` needs `allowed_decisions`, so the ways out cannot move into `commands`.
5. **Intermediate commits.** A part above the model, moved out while a higher part is still in `findings.py`, makes `findings` and the new module import each other. `NoImportCycle` in `tests/test_architecture.py:197` fails on that commit. So the parts above the model move top-down (section 5).

**Private names across a boundary: none in this cut.** Each private name stays with all its users. No module in `labkit/` imports another module's private name today, so a crossing would be the first. These names would cross under other cuts, and each would need a decision:

| Private name      | Would cross if                                             | Users                                                    |
|-------------------|------------------------------------------------------------|----------------------------------------------------------|
| `_record_of`      | the area walk or the decision writer became its own module | `read`, `findings_in`, `write_decision`, `record_status` |
| `_effect_problem` | the effect rules sat below the reader                      | `_finding`, `_replaced_decisions`, `_hold_effect`        |
| `_decision_lines` | the text helpers were split from `write_decision`          | `without_decisions`, `with_decision`, `_decided_text`    |
| `_FIELD_SEP`      | `active_rule_of` were split from `tagged_line`             | both                                                     |
| `_WRITTEN_NAME`   | `names_preflight_record` were split from `written_order`   | both                                                     |
| `_ledger_titles`  | `recorded_rule` were split from `recorded_rule_problem`    | both                                                     |

## 3. Readers outside the module

77 files read `findings` in code: 29 in `labkit/`, 48 in `tests/` (71 as `findings`, 4 as `audit_findings`, 12 through `from labkit.formats.findings import`). Nothing patches an attribute of `findings`.

**Proposal: `findings.py` stays as the data model; the six other parts become new modules that callers import directly.** No forwarder, no second name. `findings.Finding`, `findings.Record`, `findings.OPEN`, `findings.open_findings` keep reading as they do; `AGENTS.md:11` and `docs/promise-block.md:21` cite `findings.Finding` and stay true.

| Step | Module              | labkit files | test files | Other                            | `findings.X` occurrences | Prose-only files |
|------|---------------------|--------------|------------|----------------------------------|--------------------------|------------------|
| 1    | `finding_check`     | 5            | 3          | –                                | 41                       | 0                |
| 2    | `finding_line`      | 7            | 3          | `docs/examples/standin-audit.py` | 49                       | 2                |
| 3    | `audit_records`     | 15           | 35         | `standin-audit.py`               | 406                      | 5                |
| 4    | `finding_decisions` | 13           | 9          | –                                | 64                       | 7                |
| 5    | `finding_limits`    | 6            | 5          | –                                | 39                       | 1                |
| 6    | `audit_files`       | 11           | 11         | –                                | 70                       | 2                |

- **Total:** 125 file edits over six steps, in 73 distinct files (29 labkit, 43 tests, one example script).
- 30 of the 77 files no longer import `findings` at the end.
- "Prose-only" files name a moved `findings.<name>` in a comment or docstring without reading it; `EveryNamedHomeExists` (`tests/test_architecture.py:611`) fails on those unless they follow.
- Inside the new modules four import lines are re-pointed later: `audit_records` in steps 4, 5 and 6, `finding_decisions` in step 5.

**The alternative** is that the record part keeps the name `findings` and the model moves out. Then 59 files change instead of 72, `findings.write`, `read`, `area_records` and `write_decision` stay, and the order is strictly lowest-first. The cost is a new name for `Finding`, `Record`, the statuses and `FindingsError`, which 47 files read. I recommend the model keeps the name; this is decision 1.

## 4. What each step drags along

**`tests/test_one_home.py`.** Six rules name `{"findings"}`. The home is matched by file stem.

| Line | Rule                      | Where it matches in `findings.py`                                     | Change                                                           |
|------|---------------------------|-----------------------------------------------------------------------|------------------------------------------------------------------|
| 136  | answer-line separator     | 203 (`SEP`)                                                           | step 2: home `{"finding_line"}`; comment line 135                |
| 227  | open-finding walk         | 1270 (`open_findings`), 2516 (`open_elsewhere`), 2550 (`decide_ways`) | step 3: add `"audit_records"`; step 4: add `"finding_decisions"` |
| 236  | open BLOCKERs filtered    | 1279 (`open_blockers`)                                                | none                                                             |
| 274  | decided statuses spelled  | 66 (module docstring), 182 (comment)                                  | none, if that docstring paragraph stays in `findings.py`         |
| 286  | status compared as a word | no match                                                              | none                                                             |
| 469  | review name part          | no match                                                              | step 6: home `{"audit_files"}`; comments 462–464                 |

A rule with a match fails loudly when its home is stale. The rule at 469 has no match, so its stale home would pass silently.

**`tests/test_architecture.py` and the layer table.**
- Every step adds the new module to `docs/architecture.md:70`, in both the modules cell and the doctrine cell. All `formats` modules share that one row, and `findings` is doctrine. `test_every_module_stands_in_the_map` fails otherwise.
- `KNOWN_CROSSINGS` (line 79) is held as an exact set. `start_check` is core and reads `record_way` and `FAILED_SUFFIX`. Step 3 adds `("start_check", "audit_records")`, step 6 adds `("start_check", "audit_files")`. The comment says the list only shrinks; this is the same crossing under more names (decision 3).
- Line 231: the comment on `record_status` names `findings` (step 3).
- Lines 671 and 681: `findings.decision_after_restore` in a docstring and a sample string (step 4).

**`docs/architecture.md`, rows naming `findings.…`.**
- Step 1: line 186 (`evidence_request`).
- Step 2: line 410 (`SUBJECTS`).
- Step 3: lines 152, 162, 246, 337, 410, 427 (`write`, the sentence "`findings` reads and writes audit findings", `area_records`, `record_way`, `write_decision`).
- Step 4: lines 217, 218, 239, 268, 318, 337, 410, 411 (`decision_digest`, `fixed_claim`, `corrected_field`, `decide_way`, `subject_refusal`, `decision_after_restore`).
- Steps 5 and 6: none.
- Unchanged: lines 25, 248, 313, 320, 322, 383, 439 name model names.

**`docs/checks-overview.md` and `docs/checks-reach.tsv`.** Nothing moves and nothing is regenerated. `findings.py` holds no finding site: no gate finding, no `SystemExit`, no printed line. The overview has no section for it. `python -m labkit.tools.check_overview --check` exits 0 today; `tests/test_check_overview.py` in `just guard` holds it per step. The TODO's concern ("not in the last trace") does not apply to this module.

**`labkit/templates/`, `labkit/agents/`, `labkit/docs/`, `README.md`, `docs/*.md`.** No `findings.<name>` in templates, agents, `labkit/docs` or `README.md`. Two files outside `labkit/` and `tests/` import the module:
- `docs/examples/standin-audit.py` reads `findings.STATEMENT`, `findings.UNDETERMINED` (lines 24, 25, 28; step 2) and `findings.write` (line 39; step 3). Only `tests/test_repair_paths.py` runs it, and that file is marked slow.
- `docs/usability/2026-10-26-fixed-followup-pilot-2/replay_pilot2.py` reads `findings.area_records`. It is frozen evidence, excluded from ruff; leave it.

**Public API.** Confirmed: nothing of `findings` is in the table (`docs/architecture.md:79–128`) or in `tests/test_public_api.py`.

**Other single lines.**
- `tests/test_test_inventory.py:69` holds the string `"labkit.formats.findings.read"` (step 3).
- `labkit/formats/decision_history.py:119` names `findings._finding` (step 3).

**`tests/test_findings.py` (1 943 lines, 21 classes).** Its classes do not follow the parts. 16 of 21 go through `write` and `read`, most with model names beside them. Only `CorrectedField`, `OneGrammarOfTheGradeLine`, `UndeterminedVerdict`, `TemplatesNameTheTuples` and `NumberOf` test one part without the record file. I recommend it is not part of this task: here only its imports and attribute names change. A later step can rename it to follow `audit_records` and move the five classes; `docs/architecture.md:410` names the file and three of its classes, so that step drags the doc line.

## 5. Order of steps

Below the model the order is lowest first. Above it the order is top-down, for the reason in section 2, point 5. Each commit is acyclic.

| Step         | Module              | One-sentence docstring                                                                                                                                                     | Names   | Import sites      | Also changed                                                                                                                                              |
|--------------|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0 (optional) | –                   | –                                                                                                                                                                          | –       | 3 files, 7 places | callers name `gate.NEW_CLASS` and `runs.as_stored` (decision 8)                                                                                           |
| 1            | `finding_check`     | "the check a finding requires for its repair — a metrics key, a file, or evidence a follow-up audit shows — read from the finding's closing field and worded as an order." | 20      | 8                 | layer table; `architecture.md:186`                                                                                                                        |
| 2            | `finding_line`      | "an auditor's line read by one grammar: its tag and fields, and the subject and the rule a finding names."                                                                 | 23      | 11                | layer table; `architecture.md:410`; `test_one_home.py:135–136`                                                                                            |
| 3            | `audit_records`     | "an audit's findings file: written by labkit-audit, read loudly, a decision rewritten in place, and the records an area holds."                                            | 38      | 51                | layer table; six doc lines; `test_one_home.py:227`; `KNOWN_CROSSINGS`; `test_architecture.py:231`; `test_test_inventory.py:69`; `decision_history.py:119` |
| 4            | `finding_decisions` | "which decisions a finding allows, what a decided status entails and owes, the digest a review binds to, and the command that decides an open finding."                    | 11      | 22                | layer table; eight doc lines; `test_one_home.py:227`; `test_architecture.py:671, 681`                                                                     |
| 5            | `finding_limits`    | "a limitation's effect on the verdicts and the Limitation line the protocol carries it in."                                                                                | 11      | 11                | layer table                                                                                                                                               |
| 6            | `audit_files`       | "the files under an area's audits/: their names by kind, how one is created without overwriting, and their order as written."                                              | 15      | 22                | layer table; `test_one_home.py:462–469`; `KNOWN_CROSSINGS`                                                                                                |
| 7            | `findings`          | "what a finding, a fix verdict and an audit record are, the statuses a person decides, and which findings are still open."                                                 | 31 stay | –                 | module docstring settled (decision 6); CHANGELOG entry (decision 9)                                                                                       |

Nothing is regenerated in any step.

Checks per step:
- The touched test files, with `pytest -q -n 4`. Steps 2 and 3 also run `tests/test_repair_paths.py`, which is slow and the only test of the example script.
- `just guard`.
- The source text of each moved name is identical before and after (a one-off script over `ast.get_source_segment`, not committed).
- No `findings.<moved name>` is left in `labkit/`, `tests/`, `docs/*.md` or `docs/examples/`.

At the end the whole suite runs once (`just check`), its exit status is reported, and an independent reader reads the final diff.

## 6. Risks and what reading could not settle

1. **A moved name stays reachable through `findings` without any test noticing.** `findings.py` will import seven moved names for its own use: `CHECK_FORM`, `GRADES`, `IMPLEMENTATION`, `STATEMENT`, `UNDETERMINED`, `SETTLED_SUBJECTS`, `tagged_line`. `findings.UNDETERMINED` in a caller keeps working, and `EveryNamedHomeExists` counts imports as defined names. This already happens today: `findings.NEW_CLASS` in `labkit/tools/check_inventory.py:998, 1004` and `tests/test_findings.py:855, 865, 924, 926`, and `findings.as_stored` in `tests/test_audit.py:1996`. Only the search per step guards it. A test for it would be a side finding and its own step.
2. **The example script breaks outside the fast tier.** A missed edit in `docs/examples/standin-audit.py` shows only in the full suite.
3. **Lab repos.** `docs/stagekit-areas.md:110` points labs to that script, which calls `findings.write`. Whether any lab copied it cannot be told from this repo. The names are internal, but the move breaks such a copy.
4. **`audit_records` stays at about 1 100 lines** under a pure move (decision 2).
5. **29 or more docstring references become cross-module without a module prefix** (for example `subject_refusal` named in `subject_of`'s docstring). No test catches a bare name.
6. **Not run:** the suite, ruff and pyright. The counts are from `ast` walks. A local variable named `findings` in a caller could inflate a count slightly; none produced an unknown attribute besides the two pass-through names above.
7. **Module-level order.** `GRADE_HEAD` and `_WRITTEN_WORDS` are computed at import from names that will come from another module. The final graph allows it; I did not execute it.

## Open decisions

1. **Which part keeps the name `findings`.** Recommended: the data model (72 files change, top-down order above it). Alternative: the record file (59 files, strict lowest-first, but the model needs a new name).
2. **Cutting `audit_records` further.** With `_record_of` made importable (a rename, its own commit) it splits into write and read (about 600 lines), the decision rewritten in place (about 330) and the area walk (about 130). The decision writer also needs `_effect_problem`. Recommended: decide after the pure move, at the TODO's stopping point.
3. **Two new `KNOWN_CROSSINGS` entries** for `start_check`, against the comment that the list only shrinks. Recommended: accept them, with a comment that they are the same crossing under the split names.
4. **Small parts.** `finding_limits` is about 95 lines; its readers (`result_render`, `protocol_result`) differ from the decisions' readers, so I recommend its own module. The ways out get no module: `decide_way` and `decide_ways` go to `finding_decisions`, `record_way` to `audit_records`.
5. **Module names.** `finding_check` can be misread as "a check of findings" (alternative `required_check`); `audit_files` sits beside `files` (alternative `audit_names`).
6. **The module docstring (lines 1–89).** Recommended: the file layout, the decide paragraph and "Reading is loud" move to `audit_records` in step 3; the rest stays. The paragraph at line 66 must stay in `findings.py` or the rule at `test_one_home.py:274` needs a second home.
7. **Bare docstring references to names now in another module.** Recommended: one commit after step 6 that prefixes them, so the move commits stay comparable text for text.
8. **Step 0.** Recommended: one preparatory commit so `check_inventory`, `test_findings` and `test_audit` name `gate.NEW_CLASS` and `runs.as_stored`; otherwise steps 2 and 4 force it as a by-product.
9. **CHANGELOG.** `docs/architecture.md` says an internal name changes "with a Breaking entry". Recommended: one entry under Unreleased, "Internal names moved", extended per step.
