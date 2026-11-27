# The chain — every check from the intent to the reported number

labkit's claim — *it detects violations of explicitly encoded scientific intent across implementation, execution and reporting* — runs along the links below, several checked more than once (one section per check). Each check names its tier: **guaranteed** (exact), **static evidence** (warns), **agent audit** (semantic).

Each section is one check: what it checks, then where the check stands in the code, the command that runs it, its tier and when it runs. Which gate runs a check at which station, and what it tells when it fails: [gate-stations.md](gate-stations.md) (generated). The order of the gates: [architecture.md](architecture.md#the-gates-in-order).

## intent → promise

head parses and is typed; required fields by exact label; promise tables parse; prose and block name the same ids

- **Where:** `protocol_block.head`, `protocol_check.check_fields`, `promises.parse_block`, `promises.prose_mismatch`
- **Command:** `protocol-check` (fields, tables); `intent-check` (prose ids = table ids, again after the run)
- **Tier:** guaranteed
- **When:** writing the protocol

## promise → code (keys, scopes)

every declared key appears exactly in the code; every declared scope resolves

- **Where:** `code_check.promise_block_findings`
- **Command:** `code-check`, `preflight`
- **Tier:** guaranteed
- **When:** before the run

## promise → code (quality checks)

every quality-check key the code writes is tested somewhere (`if`, `and`/`or`/`not`, `all()`/`any()`, a loop over a key tuple) — else the criterion verdict is reported whether the condition held or not

- **Where:** `code_check.quality_check_reads`
- **Command:** `code-check`, `preflight`
- **Tier:** static evidence
- **When:** before the run

## promise → code (ids, parsers, prompt)

each intent id appears as a key; every `parse_*` is named in a test (static evidence, a warning); every line of a `PROMPT` constant stands in the protocol's prompt block

- **Where:** `code_check.code_findings` (`prompt_check` for parsers and prompt)
- **Command:** `code-check`, `preflight`
- **Tier:** guaranteed
- **When:** before the run

## promise → code (stamp coverage)

code the audit stamp cannot follow — a `sys.path` edit, a dynamic loader, an import outside `lib/` and `src/` — is named by line

- **Where:** `import_check.stamp_coverage_findings`
- **Command:** `code-check`, `preflight`
- **Tier:** static evidence
- **When:** before the run

## promise → code (gate labels)

the string comparisons in the evaluation code are extracted into the bundle; whether they match the prompt is the judgement of an agent the lab runs on it (labkit ships none; the preflight audit reads the code whole) — the extraction never judges

- **Where:** `gate_label_scan.gate_labels`
- **Command:** `code-check --bundle`, then the lab's own agent
- **Tier:** agent audit, outside labkit
- **When:** before the run

## promise → code (meaning)

code does what the promise says

- **Where:** `audit` (experiment-preflight instructions + the area's files + the standard, one `llm` call); or the bundle (`code-check --bundle`) for an agent the lab runs
- **Command:** `labkit-audit --mode preflight`
- **Tier:** agent audit
- **When:** before the run

## run → report (meaning)

The evaluation means the frozen criterion: earlier decisions are shown, and the auditor writes one verdict per finding shown (pilot, no gate yet).

* Every earlier decided BLOCKER is shown with its decision: `fixed`, `limitation` or `false-positive` in a record not of the state audited, and only the head of each carried chain (`followup.chain`).
* Every earlier correction of a protocol field is shown too, at any grade: a finding naming the field as its place, decided `fixed` (`followup.earlier_corrections`). The field is shown as first registered, in the audited run's own text and as it reads now, each under the name of its text (`audit_prompt.FieldChange`).
* Once a text of 500 bytes or more would be printed twice, every text stands once in full under `FIELD TEXTS`, named by number, each change to judge once as a word diff (`audit_prompt.field_text_numbers`).
* The auditor writes one `FIX · <record>#<n> · resolved | unresolved | not_assessable · <why>` entry per finding (the why may continue below the line up to a blank line or the next entry, kept whole; an entry naming another shown finding is refused). The entry is stored as `[[fix_verdict]]`, bound to the decision shown (`finding_decisions.decision_digest`).
* A BLOCKER's verdict other than `resolved` carries the finding into the new record: open, origin text, check kept, `carries`, counted in `blockers` and `carried_blockers`.
* Nothing is recorded for a FIX line that does not read, names a finding not shown, repeats one or carries another word, or when a shown decision changed during the call. A finding without a line stays unchecked.
* A finding may require a diagnostic, named in the closing field of its line:
  - The field is `· check: <metrics key>`, or `· check: file:<path>` for a file the run declares as a dependency. Two further forms ask for evidence the follow-up is shown: `· check: diff:<run>..<run>` and `· check: code:<run>:<path>`, each optionally narrowed to a path or a line range (`required_check.CHECK_FORM`).
  - A note may follow the key, written as ` (<note>)` or as ` — <note>`, and runs to the line's end. Only the key is machine-read; the note is kept whole as `check_note`.
  - The key and the note are the auditor's: they are set from the finding line when the record is written, and no decision sets them. Every decision keeps both unchanged, and the decision's digest binds both (`finding_decisions.decision_digest`).
* The prompt carries the diagnostic's whole value from the shown metrics.json, or the file shown whole as a `DEPENDENCY` piece. Each verdict records its presence: `check_present`, from that snapshot (`audit_binding.check_evidence`, the same lookup report-check makes); absent when none is required.

- **Where:** `audit` in MODE analysis, `audit_reply.parse_fixes`, `followup.earlier_blockers`, `findings.FixVerdict`
- **Command:** `labkit-audit --mode analysis`
- **Tier:** agent audit (the verdict); guaranteed (its form and binding)
- **When:** after the run

## run → report (the decisions)

A limit states its effect. The cases below say which decisions need a second, cold auditor and when an `upheld` review releases them.

* A limit whose effect is `stands` claims the verdicts hold within the limit.
* A limit whose effect is `<ID> not assessable` claims that the fault prevents judging each promise it names — only those, a criterion beside a named quality check only when named too (`result_render.left_unjudged`, each with its recorded verdict; one verdict for all, `upheld` only when every one holds).
* Both release the finding, and a `not assessable` no review upholds voids no verdict (`result_render.limits_of`).
* The second auditor gets:
  - the finding and the reason;
  - the finding's required check with its value in the run or that it is missing (`audit_prompt.required_check_line`, the follow-up's wording);
  - the protocol (registration and reported claim);
  - the files the findings name as the auditor read them — when none names a code file, the reviewed run's measuring script as it ran (`run_record_check.script_as_run`: the area's file when its digest is the run's `script_sha`, else the run's own copy, labelled; else a line why none is shown);
  - what the auditor was shown of the run.
* The second auditor says per decision `upheld`, `rejected` or `insufficient`. Only `upheld` releases, and only when every draw on the decision as decided and claimed now says so. A contested state is settled by deciding again, never by another draw.
* A changed decision or a rewritten Conclusion makes the review stale. The Recorded results and Limitation lines are generated and bound through the record and the run.
* report-check blocks on a BLOCKER limitation's `stands` no review upholds and warns on a WARNING limitation's.
* A `stands` a review of the decision as decided and claimed now did not uphold renders in the Limitation line as "a limit proposed, not confirmed by a second auditor — unresolved", neither standing nor falling (`result_render.limits_of`, `reviews.contested`).
* A finding a review once did not uphold (`reviews.once_not_upheld`) and that is now `false-positive` or `fixed` (`findings.CLOSING`) is held the same way until a review upholds the new decision. The reviewer is asked whether the reason shows it inapplicable, gone or somebody else's.
* A BLOCKER on the Conclusion decided `fixed` (`finding_decisions.fixed_claim`) is held the same way: no follow-up audit is shown a rewritten claim, so the review judges the Conclusion as it stands.
* The review's record (`audits/<minute>-review.toml`) is held three ways, unequally:
  - It is bound to its inputs: a changed decision or a rewritten Conclusion makes it stale (guaranteed).
  - Once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed).
  - Its content is compared with no journal line, kept answer or evidence copy, so `rejected` rewritten to `upheld` before the first commit releases the decision — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md)).

- **Where:** `decision_review.gather_review`, `decision_review.parse_review`, `reviews.upholding`, `reviews.once_not_upheld`, `report_decisions.review_findings`, `report_decisions.check_repaired_claims_upheld`
- **Command:** `labkit-audit --review`, `report-check`
- **Tier:** agent audit (the release condition: guaranteed, on the record as written; the record's origin: unchecked)
- **When:** after the analysis audit is decided

## run → report (the follow-up)

An earlier decided BLOCKER (`fixed`, `limitation`, `false-positive` in a record not of the state reported) is released in one of two ways only.

* By a covering analysis record's valid `resolved` — the head of its origin, its decision as it stands, a required check shown — while no covering record holds another verdict on that origin.
* Or carried into a covering record, where it is decided.
* A carried finding `false-positive` owes an upholding decision review.
* A BLOCKER `fixed` in the state reported is held.
* Each sentence names the missing step.

Pilots: [fixed follow-up](usability/2026-10-26-fixed-followup-pilot.md), [second](usability/2026-10-26-fixed-followup-pilot-2.md).

- **Where:** `followup.release_holds`, `followup.chain`, `report_decisions.followup_findings`, `decision_review.reviewable`
- **Command:** `report-check`; `claude-hook stop`, `.githooks/pre-commit`, `protocol-fill --from-run`
- **Tier:** guaranteed (the binding and the release); agent audit (the verdict)
- **When:** before the number leaves the area

## run → report (a discussed run, the registered report)

A report presents as a result nothing the protocol has not adopted and nothing the audit decisions or the adopted result contradict. This holds for a report discussing a run (a discussion block) and for the report a head registers once its result, handover or reported-through block stands. A report that cites no run is out of its reach.

* A cold reader names the lines as `result` or `contradiction`. The reader gets:
  - the report with line numbers;
  - the adopted run, the discussion blocks and the protocol;
  - the `metrics.json` of the adopted, each discussed and each cited run;
  - every run of the area in one line (state, kind, binding, what the report makes of it, the settings that vary across the protocol's measurements, scalar metrics — the history a silent search shows in);
  - every audit record with its decisions and failed attempts.
* The review is recorded in `audits/report-reviews/` with the fingerprint of exactly the inputs it read and the brief it read them under (`report_hold.review_fingerprint`). Its own folder and the attempt journal are not among them. A corrected brief makes every earlier review stale.
* report-check holds the report, per protocol its discussions name, until a review of its state names no claim. The state is what the reviewer reads, with the report and the protocol as the gate's state holds them:
  - At the stop the gate's state is the working tree.
  - At the commit the gate's state is the index. Only the review records the index holds count, and the area's working tree must equal the index: a difference blocks the commit.
* A committed report discussing a run of an area a change touches is held with the change (`report_hold.discussing_reports`).
* A claim holds the state — an `--again` draw's as well — and a later clean draw (or `--again`) releases nothing.
* A claim the reader got wrong is decided `false-positive` in its record (`limitation` and `fixed` are refused). The decision is bound to the record, the claim's number, the state and the decision's digest. It releases only once a second reviewer, shown the claim, the reason and the first reader's inputs, upholds it. A verdict other than `upheld` is outvoted by no further draw. A revised reason is a new decision with its own confirmation.
* The command prints the draw and the state apart and exits with the state (0 released, 1 held). A changed input (the report, the protocol, a run's metrics, an audit decision) owes a new review. The post-change hook names its command (pilot: [report review](usability/2026-10-25-report-review-pilot.md)).
* The review's record is held three ways, unequally:
  - It is bound to the inputs it read: a changed input owes a new review (guaranteed).
  - Once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed).
  - Its content is compared with no journal line, kept answer or evidence copy, so a claim deleted before the first commit releases the report — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md)).

- **Where:** `report_review_inputs.review_pieces`, `report_review.parse_claims`, `report_reviews.standing`, `report_reviews.upheld`, `claim_review.decide_claim`, `claim_review.review_claims`, `report_hold.report_review_owed`
- **Command:** `labkit-audit --report-review` (with `--decide`: the decision on a claim), `labkit-audit --review --record <report review>`; `claude-hook stop`, `.githooks/pre-commit`, `report-check AREA`, `labkit-next` (`report_hold.discussion_review_findings`, the one finding all of them hold and name, from the state each judges)
- **Tier:** agent audit (the claims); guaranteed (the record's binding to its inputs and its claim count as written); unchecked (the record's origin)
- **When:** when a report discusses a run; ending the turn, committing

## promise → reader

a person who did not build the area can tell what it decides

- **Where:** `audit` in MODE clarity (code-clarity area rules + README, protocol, measure script)
- **Command:** `labkit-audit --mode clarity`
- **Tier:** agent audit (static evidence: never a gate)
- **When:** before freezing

## code → run (refused at the start)

unfrozen full run, unbound run, dangling scope, control leakage: refused before the run dir exists

- **Where:** `runlog.Run`
- **Command:** (every run)
- **Tier:** guaranteed
- **When:** starting the run

## code → run (the preflight record)

a full run's head names the decided preflight record (`preflight_audit = "<minute>-preflight.toml"`), and that record saw the code, the promise block and the registration as they are now — the kind, `[kept]`, the fields the kind owes and the fields read before the run (`protocol_check.registration_stamp` with `AUDITED_FIELDS`), so a step that rewrites one of them owes a new preflight audit before its run, and a repeat or a step that rewrites none starts under the record that stands; an `n/a` or any other text at high repeat cost is refused (nobody waives their own audit)

- **Where:** `runlog.Run`, `audit_gaps.audit_record_gap`
- **Command:** (every full run), `preflight`
- **Tier:** guaranteed
- **When:** starting the run

## promise → run (tier)

the repeat cost is not lower than in the protocol's first commit — a lower tier owes less

- **Where:** `protocol_history.repeat_cost_lowered`
- **Command:** `protocol-check`, `preflight`
- **Tier:** static evidence
- **When:** before the run

## code → run (an unfrozen pilot)

a long pilot's `LABKIT_UNFROZEN=1` rests on a failed audit attempt at the code and promises as they are now (`audits/*-failed.toml`, written by `labkit-audit` when the backend does not answer or answers unproven — `cause`; after an `unproven` attempt `labkit-audit` refuses the same state with the same model, `failed_attempts.stopped_attempt`), else refused; `run_kind`, `unfrozen_ack` and `audit_failed` recorded

- **Where:** `runlog.Run`, `failed_attempts.audit_unavailable`
- **Command:** (every acknowledged full run)
- **Tier:** guaranteed
- **When:** starting the run

## code → run (the recorded state)

block digest, per-promise `declared_scope_sha`, constants, git state, data hashes recorded

- **Where:** `runlog.Run`, `promises.snapshot`
- **Command:** (every run)
- **Tier:** guaranteed
- **When:** starting the run

## code → run (resume across a code change)

the estimator skeleton's rows carry the measuring code, so a resume across a code change is refused, naming the runs, what differs and a new output name; a run that continues a finished run's file is told so (its rows count as its own)

- **Where:** `scope_sha.measured_code_sha`, `batch.Store.pending`, `runlog.Run.output` (`continued_warning`), `runs.next_output_name`
- **Command:** (every run)
- **Tier:** guaranteed
- **When:** registering the output, resuming

## run → report (record)

run completed; declared keys reported; run recorded this block; a block constant not contradicted by the run config

- **Where:** `runs.completion_state`, `intent_check.check_block_against_run`
- **Command:** `intent-check`, `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (model)

The run's call log agrees with the model records: each line of `llm-calls.jsonl` has a record naming its alias.

* The record is the run's own `models_resolved` or, for an answer a run stored (`origin.run`), that run's record, found in the lab's areas.
* A derived run, which by the README's definition makes no model calls and has no record of its own, blocks on a call that asked the model or an answer stored outside any run. It passes only on replayed answers whose storing run names the alias.
* Without a finding there, a run whose metrics show model calls (`model_calls`, `llm_retries`) has a model recorded along its lineage (a warning).
* Stand-ins in the call log (`llm_cache.store_stand_in`, marked in the cache entry and the line) are named in a warning: no model gave them, and the run's numbers show what its processing does with fixed answers.

Not proven: that every answer the run used was logged — answers read past labkit's cache leave no line.

- **Where:** `runs.read_model_calls`, `runs.run_dir_in_lab`, `model_check.call_log_model_findings`, `model_check.model_provenance_findings`, `model_check.stand_in_findings`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (continued rows)

rows that carry their code (`_instrument.code_sha`), continued from a run whose script differs from the answering run's: a blocker — the number is that code's; a model's answers re-read after a parser fix pass

- **Where:** `row_check.row_provenance_findings`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (the null lane)

an output the run kept with a registered and a null lane: the null answers otherwise on some item, gold included — read from the kept rows, not from the editable script

- **Where:** `row_check.null_lane_findings`
- **Command:** `finalize`
- **Tier:** static evidence
- **When:** after the run

## run → delivered file

every output the run registered (`run.output`: its rows, and the deliverable of an external task the stamped script writes from the kept rows, `formats/deliverable`) is the file the run recorded — path and sha256 from outputs.json, never from the tree; gone or changed is a blocker

- **Where:** `run_record_check.output_record_findings`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (input origins)

At every repeat cost, each input whose record names an origin run (`origin_run`, decided at start) is that run's registered output.

* That means, in this order:
  - the origin run under the area's `runs/` reads;
  - it is completed;
  - its `outputs.json` holds the input's path with the sha256 the input's record holds;
  - the file's bytes are those now.
* The first part that fails is a blocker naming the input, the origin and the condition. Its way out restores the bytes or the origin's record from existing evidence, or measures anew; it never rewrites a recorded sha256 or origin.
* At `low` changed bytes are the provenance station's blocker and a note here.
* A plain input and the runs the lookup skipped are notes.
* The analysis audit is shown the same facts as an `INPUT ORIGINS` piece, with a `SOURCE PROTOCOL <run>` piece per origin run: its protocol as that run started under it (`audit_binding.source_protocol_pieces`).
* An origin run bound to a protocol whose text then cannot be read back is a blocker, with the way out restoring that evidence or measuring anew. The text then is commit and patch; a changed tree without its patch counts as lost. An origin run bound to no protocol is a note (`audit_binding.source_protocol_finding`).
* Under a text that reads, the origin run reports every promise that text registered, as intent-check holds an answering run; each promise it does not report is a blocker (`intent_check.origin_intent_findings`). The protocol as it reads now is not asked.
* The exception is a preparation origin, which reports no result and owes none of them; its piece shows the text as context (`audit_binding.SourceProtocolThen.preparation`).
* A stored origin is not decided again. Other protocols of the area are not held.

- **Where:** `origin_check.origin_now`, `origin_check.origin_gap`, `origin_check.origin_finding`, `origin_check.origin_piece`
- **Command:** `finalize`, `report-check`; `claude-hook stop`, `.githooks/pre-commit` through report-check
- **Tier:** guaranteed
- **When:** after the run

## run → report (code)

for the answering run and each run it derives from: the measurement script (the path its command names) unchanged since the run (its recorded `script_sha`), and every module it imports — beside it, under `lib/` or `src/` (`scope_sha.measured_code`) — as the tree the run started from held it (its commit with the part of its `uncommitted.patch` for that module, read in a temporary index); a module in another repository a warning; analysis code and the pin not compared; a change made and undone in between, and code loaded another way, not seen

- **Where:** `run_record_check.code_since_run`, `repo.tree_patch`, `repo.blobs_then`, `repo.blobs_now`
- **Command:** `finalize`, `report-check`
- **Tier:** guaranteed
- **When:** before reporting

## run → report (scopes)

declared scopes unchanged since the run

- **Where:** `promises.scope_drift`
- **Command:** `finalize`, `recheck`
- **Tier:** guaranteed
- **When:** before reporting

## run → report (the registration)

at `low`: the registration the lane owes (`standard_contract.registration_fields`) stood in the protocol as committed at the first measurement — the commit its record names (`git_full`); first is what git's history puts first, the run id (local time) orders only runs at one commit, and on diverged history or beside a run git cannot place each first one is held; the protocol not committed there, a field not written there, a kind changed since, or a commit the clone does not hold, blocks (outside a repository: a warning); a field's value changed after that commit is not compared

- **Where:** `area_state.Measured.firsts`, `runs.recorded_commit`, `repo.earliest_commits`, `protocol_history.registration_in_commit`, `report_check.registration_gaps`
- **Command:** `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (the report a protocol owes)

At both repeat costs, what binds for good is the promise given before the result was known: the report the protocol registered in the commit of a first measurement, read by the id the run recorded (`registered_report.report_duty`, `bound_reports`).

* The duty hangs on the protocol, not on the report's path: the head may name another file, and the new target owes the delivery.
* Held:
  - a head that registers none while that duty stands (restore, name another file, or hand over);
  - a protocol id the area measured under that no protocol of the area carries now, while that id owed a report. One function finds it (`report_check.orphaned_duty_gaps`), and three gate callers hold it: report-check's chain; `report-check AREA` on an area without a protocol; the stop's and the commit's hold, on an area the change touches where no chain ran. `labkit-next` and `labkit-init exp` read the same function to name the duty; they hold nothing. Each gate caller passes the file state it judges (the working tree, or the index at the commit), and the ids carried now are read from the protocol texts of that state.
* A deleted protocol that owed none is passed over.
* A report entered after the first measurement starts no lasting duty. While the head names it, the checks of a registered report hold it. Taking it out ends those and nothing else: an adopted result, a written report and the audit records keep their own holds.
* Where the first measurement's registration does not read, a head without a report is a check not executable, never "no duty". The registration does not read when:
  - its commit is not recorded, not held by the repository or not holding the protocol;
  - a measurement is lost;
  - a run of the area has a record that does not read — it may have been the first.
* The setter previews its proposed head with the same gate.
* Selection reaches a protocol by area or formerly registered report (`formerly_registering`).
* At stop/commit a current protocol-specific handover ends the duty without releasing a result.

- **Where:** `registered_report.bound_reports`, `registered_report.report_binding_gap`, `registered_report.formerly_registering`, `start_check._committed_registration`, `protocol_fill.report_bound`
- **Command:** `report-check`; `claude-hook stop`, `.githooks/pre-commit`; `runlog`, `protocol-fill`
- **Tier:** guaranteed within the stated Git boundary
- **When:** starting the first run; before the number leaves the area

## run → report (the registration as first measured)

every lane: the answering run recorded the promise block its protocol's first measurements recorded (ids, keys, sentences through the block digest, scopes, constants — not the code the scopes name); a change is held, every changed sentence, key, constant and scope named from the protocol texts both runs saw, with the way back (restore and measure again, or register anew); first measurements that recorded different blocks are held too — which one stood cannot be told — with the two ways out (a replacement declared against each, or the handover `ways_out.HANDOVER_WAY`)

- **Where:** `answering_run.first_registrations`, `protocol_then.as_measured`, `protocol_history.promise_differences` (`promises.snapshot_changes` where a text cannot be read back), `registration_hold.registration_changes`
- **Command:** `finalize`, and through it `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (what the number is about, as first measured)

In every lane and at every kind, the protocol the answering run saw holds what the number is about as its first measurements saw it: the question, its terms, the data, the exclusions and the unit (`protocol_history.SCOPE_FIELDS`, whitespace folded, the generated data counts left out) and the head's kind, `[kept]` and `[reference]`.

* A change is held, each field named with its old and new value, with the way back (restore and measure again, or register anew).
* First measurements that saw different texts in a field no correction in place covers (several at one commit, the tree edited between them, a run that stopped without a number among them) are held to each other first. Since which text stood cannot be told, the way out is a new registration or a handover, never a restore.
* The protocol as it stands is held the same way, so a field rewritten after the last measurement is held before any run carries it — unless it is a correction in place.
* A correction in place, at every grade, is all three of:
  - an audit finding that names the field as its place (`<protocol file>:<label>`, the label in full or the one label it begins — `protocol_check.field_at`; no line number; a start several labels share binds nothing, and the decision's line and finalize say so);
  - that finding decided `fixed`;
  - a `resolved` on it bound to that decision in an analysis record that covers the area now (code, promises, registration, the fields read before the run, the run).
* A fresh audit without that verdict, a verdict on another field and a text edited after the verdict release nothing.
* The head's kind, `[kept]` and `[reference]` name no field and are never corrected so. Nor is the question (`protocol_history.UNCORRECTABLE_FIELDS`): it states the requirement, and a different question is a protocol of its own.
* The hold offers the correction route only where it applies (`registration_hold.correction_way`). The decision's line explains the condition (`protocol_history.STANDS_AS_REGISTERED` for the question) and names no way of its own.
* The release names each correction with its old and new value and the verdict's why.
* A code change measured again under the same fields passes: what the run computes is the analysis audit's question.

- **Where:** `answering_run.first_measurement_groups`, `protocol_then.as_measured`, `protocol_history.scope_differences`, `protocol_history.first_measured_differences`, `protocol_history.differences_among_first_measurements`, `protocol_history.correctable`, `finding_decisions.corrected_field`, `registration_hold.scope_changes`, `registration_hold.resolved_corrections`
- **Command:** `finalize`, and through it `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (a declared replacement)

A protocol with `[replaces]` names one predecessor and declares every difference of the registration against the predecessor's.

* One predecessor of the repo, no circle.
* Every difference of the registration is declared as `[[replaces.change]]`, and none is declared that is not one. The registration is the kind, the promises, what the number is about as finalize compares it (`scope_differences`: the question, its terms, the data, the exclusions, the unit, `[kept]`, `[reference]`) and the Data profile.
* The predecessor's registration is read as each first measurement saw it: commit plus its `uncommitted.patch`, held to the recorded block; against each when they differ.
* The predecessor's open BLOCKERs are decided.
* The generated result opens with the predecessor's verdict (`no verdict` where its registration does not stand).
* A report that switched its citations to an undeclared successor is static evidence.

- **Where:** `protocol_block.replaces`, `protocol_history.registrations_as_first_measured`, `protocol_history.registration_differences`, `report_replacement.replacement_gaps`, `result_render.predecessor_verdict`, `report_hold.replacement_hints`
- **Command:** `report-check`
- **Tier:** guaranteed (the hint: static evidence)
- **When:** before the number leaves the area

## run → report (the end)

At every repeat cost, all of these hold at the end.

* Frozen — high repeat cost only; at low repeat cost no freeze and no preflight audit are owed.
* finalize is clean with its blockers named.
* The answering run is a full run (`run_kind="measurement"`, not acknowledged unfrozen); a probe's or an acknowledged run's number is refused.
* An analysis audit record, every finding decided, of these as they are now:
  - the code;
  - the promise block;
  - the registration it judged (`registration`: the kind and the fields the kind owes, `protocol_check.registration_stamp`);
  - the answering run;
  - what the audit was shown of it (`shown_sha`: its rows' excerpts and metrics.json, its declared dependencies, the protocol's declared run when that is another one, and the setup's prose the audit read, `protocol_check.audited_texts`; `audit_binding.run_shown`).
* `02_analyze.py --check --protocol FILE` passes for this protocol: its run is recomputed with the script that run ran. The note carries the numbers and the run_id. Every skeleton stamps the script.

- **Where:** `report_check`, `runs.unreportable`, `audit_gaps.audit_coverage`, `recheck.holds`
- **Command:** `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (the declaration)

A protocol whose TOML head declares a result goes through report-check at the stop and the commit.

* The declaration is `[result] run = "<run_id>"`, written by `protocol-fill --from-run`, never typed — the one declaration that a result is reported.
* With it goes every other protocol of an area a changed, deleted or staged path touches: a path in the area, a file its promises declare in scope, or a shared helper under `lib/`/`src/` its code imports. A script changed or removed under a reported number reopens it; at the commit the protocols are the index's.
* A protocol declaring none owes nothing (an exploration ends with no reported result).
* A `[result]` that does not read (a typed id, a stray key) is a blocker where it stands.
* An Recorded results written under no declaration is a warning.

- **Where:** `report_check.hold_changed_paths`, `report_check.reached_by` (the one reader of the protocols a change reaches, for the gate and for the step printed beside its hold), `report_check.affected_protocols`, `scope_sha.areas_touched`, `protocol_block.declared_run`, `finalize.declared_run_gaps`, `protocol_check.recorded_results_without_run`
- **Command:** `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported --staged`: the answer as the index holds it, the area's tree equal to the index), `protocol-check`
- **Tier:** guaranteed (the warning: static evidence)
- **When:** ending the turn, committing

## run → report (a report outside the protocol)

This check reads a changed or staged Markdown file citing a run (not a protocol, not under `runs/` or `data/`, both tested at its own path).

* A report that is a symbolic link, wherever it points, blocks alone, naming the copy that replaces it (`report_hold.link_gap`); its other checks follow on the copy.
* Every report result block names its protocol, shows the run that protocol declares now and equals what it renders: the registered Question / hypothesis and the Conclusion verbatim, the Recorded results and Limitation lines. That is exact for the block, nothing for the prose beside it.
* `report_blocks.block_body` refuses while the question or the Conclusion is not written, for the writer and the check alike. `protocol-fill --into` writes the block and replaces the protocol's block after a new run is adopted.
* A block shown inside a closed fenced code block outside every block is an example and not read (`comment_blocks.example_lines`).
* Every token that reads as a run id names a run of the repo.
* A cited run that a protocol declares as its result is shown in that protocol's block, else the block is owed.
* The answering run of a protocol that declares no result is not cited undiscussed — the promotion without the adoption.
* A run only looked at stands in a discussion block (`protocol-fill --discuss RUN --why … --into`: protocol, run and why as TOML in its head, its line written from them).
  - A block blocks when it is without its why, has a line that differs from its head, is repeated for one protocol and run, names a run its protocol's area lacks, or discusses a declared run.
  - Any other cited run no protocol declares is a warning.
* The protocol declaring a cited run goes through report-check as well.
* An untouched file's old citations reopen nothing.
* The report a protocol's head registers (`report = "REPORT.md"`, `protocol_block.report_field`), once delivered in the state, carries that protocol's result block of the declared run or its handover block as the record renders it (`handovers.block_mismatch`) — else one blocker with the three ways out (adopt then `--into`, `--discuss` which releases nothing, `--handover`).
* While nothing is adopted, a discussion block of the run the gates hold the protocol to is its progress account: the commit and the stop take it without a report review, an honest interim state, and `labkit-next` names the adoption or the handover (`registered_report.progress_account`). `--into` puts the result block where it stood (`report_blocks.with_block`), run id removed, typed in or discussed alike.
* Before any measurement and with no answering run or adoption, a valid report draft owes no result block.
* A report not yet written owes nothing. A protocol registering none holds no file to this. The protocols registering a file among the paths are selected though it lies in no area.

- **Where:** `report_check.hold_changed_paths`, `report_hold.hold_report`, `report_hold.undeclared_findings`, `report_hold.promotions`, `report_blocks.block_gaps`, `report_blocks.cited_gaps`, `report_blocks.blocks_owed`, `report_blocks.discussions`, `report_blocks.discussion_gaps`, `report_hold.discussion_sources`, `registered_report.report_owed`, `report_hold.registering_protocols`, `report_check.report_findings`, `report_check.hold_registered_report`
- **Command:** `claude-hook stop`, `.githooks/pre-commit` (the report as the index holds it), `report-check` (station 8)
- **Tier:** guaranteed
- **When:** ending the turn, committing, reporting

## run → report (unsourced numbers)

numbers in a changed citing report outside every generated block are named with their line: no source is assigned to them — equal values elsewhere do not show where a number came from

- **Where:** `report_blocks.unsourced_numbers`
- **Command:** `claude-hook stop` (shown only beside a blocker), `.githooks/pre-commit`, `report-check --if-reported`
- **Tier:** static evidence
- **When:** ending the turn, committing

## run → report (the adoption)

the one path that writes the declaration: the lines from the run's metrics.json are written, report-check runs on the written protocol, a blocker puts the file back — a result adopted this way has passed every check

- **Where:** `protocol_fill.adopt`, `report_check.protocol_verdict`
- **Command:** `protocol-fill --from-run`
- **Tier:** guaranteed
- **When:** writing the number back

## run → report (undecided findings)

every finding still `open` in the audit records of the protocol finalize holds (`followup.records_of`), any mode: a BLOCKER blocks, a WARNING warns, each with its file; a finding on another protocol of the area holds nothing here

- **Where:** `finalize.station_open_audit_findings`, `audit_records.area_records`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (a deleted run)

every analysis record of the area names a run it still holds: a record of a run whose directory is gone is a blocker where the record stands — the record is the evidence that the run existed

- **Where:** `audit_binding.check_audited_runs_kept`, `audit_gaps.records_of_gone_runs`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (the gates that run unasked: the stop sends back once, the commit holds)

An area that holds an audit BLOCKER nobody decided is held by both gates: the stop sends the agent back (the records as the tree holds them), the commit is refused (the records and their decisions as the index holds them).

* The areas are those the session touched or a staged file lies in. An area deleted whole with its protocol is found by its journal copy on the branch.
* A lost or unreadable record or journal holds both too, except where a current handover binds that loss (`handovers.acknowledgement`) — an open BLOCKER never.
* Three more findings hold both gates as well, and no handover acknowledges them:
  - Committed evidence changed against git: a record beyond its decision lines, another audit file, a closed run's files. The state the gate checks is compared with HEAD: the working tree at the stop, the index at the commit. Each line names its `git checkout`; where git cannot read what the comparison needs, the comparison did not run, and the line names how to bring the objects back instead (`evidence.unread_finding`).
  - At the stop also: such a change that a commit of the session made against its parent and the working tree has not undone, and a closed run left behind in HEAD's reflog — a commit the reflog names since the session began held it, HEAD no longer holds that commit, and the tree lacks the run's files or holds them changed. Each line names its `git checkout`.
  - A file of labkit's that git ignores, so that no commit can carry it. Its line names `git check-ignore -v`.

- **Where:** `undecided.undecided_blockers`, `evidence.AreaEvidence`, `findings.open_blockers`, `hook_session.committed_in_session`, `evidence.AreaEvidence.change_sentences`, `evidence.ignored`, `agent_hooks.session_evidence`, `evidence.change_blockers`
- **Command:** `claude-hook stop`, `.githooks/pre-commit` (`claude-hook pre-commit`); the change against HEAD also `report-check AREA` and `labkit-next`
- **Tier:** guaranteed
- **When:** ending the turn, committing, before reporting

## audit → evidence (the attempts)

Every model call of `labkit-audit` is an attempt journaled in `audits/attempts.jsonl`.

* The calls are a preflight or analysis audit, a decision review (`review`) and a report review (`report-review`, its record under `audits/report-reviews/`).
* An attempt is started before the call. The model's answer is kept as `audits/answers/<attempt id>.txt` before anything reads it. The attempt is ended with its record, its failed-attempt file or why none, and the kept answer (a kept answer releases nothing).
* A call not made (a state already judged, a refusal before it) is no attempt, and a record older than the journal is named by none.
* An attempt whose process holds no lock and has no end is marked interrupted by the next.
* A file an ended attempt names, a file under `audits/` HEAD holds, or a journal line HEAD holds that is gone blocks the next audit, the stop and the commit, naming the attempt or the file. At the commit they are read as the index holds them, so a commit restoring a record HEAD lost passes; at the stop HEAD's journal is held to HEAD's files.
* The check of the tree (the next audit and the stop) also holds the journal to its copy in the git directory, where every journal line is written too, one file per branch and area:
  - A line the copy keeps that the journal lacks blocks too, and so does each file that the end of an attempt among those lines names and `audits/` lacks.
  - The copy is held as a set of lines: the order of the lines does not count, and a journal line the copy lacks passes.
  - So `audits/` deleted whole before a first commit is noticed.
  - This does not hold on a detached HEAD (no copy is kept there), in a fresh clone, with the git directory gone, or for attempts made before the copy existed.
  - The check at the commit does not compare the journal with the copy; it reads the copy only for the files an attempt's end names.
* A current handover lets the stop and the commit pass on that loss, never the next audit or the adoption (`handovers.missing_paths` keeps its paths owed).
* A running attempt refuses a second; the check and the start stand under one lock.

- **Where:** `attempts.begin`, `attempts.attempt`, `attempts.gaps`, `attempts.area_gaps`, `attempts.journal_copy`, `attempts.copy_gaps`
- **Command:** `labkit-audit`, `claude-hook stop`, `.githooks/pre-commit` (`claude-hook pre-commit`)
- **Tier:** guaranteed
- **When:** auditing, ending the turn, committing

## run → report (denominator)

denominator `criterion_<i>_n` matches a recorded input count

- **Where:** `kept_number_check.criterion_n_input_mismatches`
- **Command:** `finalize`
- **Tier:** static evidence
- **When:** after the run

## report → number

The reported number is recomputed with the code the run ran, from the run's recorded output files or its recorded inputs, as the cases below say.

* Every output file the number is computed from is pinned to the run. Several are named by key and recomputed together (`recheck.holds_outputs`). Each is a row file, one JSON object per line (a stagekit stage output is one JSON document: the area writes the rows it reads into a row file it registers).
* The code here is shown to be the code the run ran. Changed: refused. Not comparable: not verifiable, held by report-check as a check not executed.
* Recomputation agrees.
* The note cites every number and the run id.
* The kept key is read from the protocol as the run saw it.
* The block is unchanged for the answering run (a run named for a recheck is held under the block it recorded).
* An older run is checked apart (`recheck.holds_as_measured`, the script's `--check --run <run_id>`). Its rows are the file as it stands or the bytes a commit holds with the recorded sha256, read into a temporary directory; else the run is not verifiable. No note is read and nothing is released.
* A run that computes from its recorded inputs (`recheck.holds_from_inputs`): first every input is the bytes it read — one with an origin run still that run's registered output (`origin_check.origin_gap`) — and only then its evaluation over them agrees. The source runs are not run again.

- **Where:** `recheck.holds`
- **Command:** (an area's `--check`)
- **Tier:** guaranteed
- **When:** keeping a number

## kind → kept number

Every head names its kept number (`[kept]`: key, unit — `protocol_block.kept`).

* It is owed at every decided kind (`protocol_check.kept_gaps`) and stands in the registration stamp. A fit's or an apply's criterion judges that number.
* Every measure skeleton reads the key (`metric_key`, `KEPT_KEY`).
* finalize blocks an answering run whose metrics.json does not hold it as a finite number, naming what it holds instead (`kept_number_check.kept_number_gaps`). The adoption's check runs finalize on the proposal.
* The Recorded results line names it first with its unit (`result_render.kept_phrase`).

The key is bound by name, not by meaning.

- **Where:** `protocol_block.kept`, `protocol_check.kept_gaps`, `kept_number_check.kept_number_gaps`, `finalize.station_kept_number`, `result_render`
- **Command:** `labkit-init exp --kept --unit`, `protocol-fill kept.key=… kept.unit=…`, `finalize`, `labkit-adopt`
- **Tier:** guaranteed
- **When:** registering, before reporting

## compute → reference comparison

A computation's head may register the stated value its number is compared with (`[reference]`: value, tolerance, relation, source, compared on the `[kept]` key — `protocol_block.reference`).

* The `[reference]` table is refused on a kind with a bar: a fit or an apply, every kind but a computation (`protocol_check.reference_gap`). The refusal names the criterion as the place where such a kind compares its number. The table stands in the registration stamp as a digest (`protocol_check.registration_stamp`).
* The run writes the verdict beside the number (`reference.reference_verdict`, one home; the compute skeleton's `metrics_of`): `compared` with `ref_met` and the distance, or `not comparable` — the key absent or no finite number.
* `--check` recomputes it.
* The Recorded results line and the result block carry it generated (`result_render.comparison_phrase`).
* finalize blocks a verdict the run could not make, a `ref_*` key without a registered reference, and a reference changed after the run (`reference.comparison_gaps`).
* `not met` is a valid outcome. Without the table no `ref_*` key is written and nothing is owed.

- **Where:** `protocol_block.reference`, `reference`, `result_render`, `finalize.station_reference`
- **Command:** `labkit-init exp --reference`, `02_analyze.py --check`, `protocol-fill --from-run`, `finalize`
- **Tier:** guaranteed
- **When:** registering, the run, before reporting
