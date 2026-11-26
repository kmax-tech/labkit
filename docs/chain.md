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

the evaluation means the frozen criterion; every earlier decided BLOCKER (`fixed`, `limitation`, `false-positive` in a record not of the state audited; only the head of each carried chain, `followup.chain`) is shown with its decision, and so is every earlier correction of a protocol field at any grade (a finding naming the field as its place, decided `fixed`; `followup.earlier_corrections`), with the field as first registered, in the audited run's own text and as it reads now, each under the name of its text (`audit_prompt.FieldChange`) — once a text of 500 bytes or more would be printed twice, every text stands once in full under `FIELD TEXTS`, named by number, each change to judge once as a word diff (`audit_prompt.field_text_numbers`); a BLOCKER's verdict other than `resolved` carries the finding into the new record (open, origin text, check kept, `carries`, counted in `blockers` and `carried_blockers`); and the auditor writes one `FIX · <record>#<n> · resolved | unresolved | not_assessable · <why>` entry per finding (the why may continue below the line up to a blank line or the next entry, kept whole; an entry naming another shown finding is refused), stored as `[[fix_verdict]]` bound to the decision shown (`finding_decisions.decision_digest`); a FIX line that does not read, names a finding not shown, repeats one or carries another word, or a shown decision changed during the call, records nothing; a finding without a line stays unchecked; a finding may require a diagnostic (`· check: <metrics key>`, or `· check: file:<path>` for a file the run declares as a dependency, optionally ` (<note>)` or ` — <note>` to the line's end, the note kept whole as `check_note`; the auditor's, kept by every decision and bound in the digest), whose whole value from the shown metrics.json — or the file shown whole as a `DEPENDENCY` piece — the prompt carries and whose presence each verdict records (`check_present`, from that snapshot, `audit_binding.check_evidence`, the same lookup report-check makes; absent when none is required) (pilot, no gate yet: eighth round, t3)

- **Where:** `audit` in MODE analysis, `audit_reply.parse_fixes`, `followup.earlier_blockers`, `findings.FixVerdict`
- **Command:** `labkit-audit --mode analysis`
- **Tier:** agent audit (the verdict); guaranteed (its form and binding)
- **When:** after the run

## run → report (the decisions)

a limit whose effect is `stands` claims the verdicts hold within the limit, one whose effect is `<ID> not assessable` that the fault prevents judging each promise it names — only those, a criterion beside a named quality check only when named too (`result_render.left_unjudged`, each with its recorded verdict; one verdict for all, `upheld` only when every one holds); both release the finding, and a `not assessable` no review upholds voids no verdict (`result_render.limits_of`); a second, cold auditor gets the finding, the reason, the finding's required check with its value in the run or that it is missing (`audit_prompt.required_check_line`, the follow-up's wording), the protocol (registration and reported claim), the files the findings name as the auditor read them — when none names a code file, the reviewed run's measuring script as it ran (`run_record_check.script_as_run`: the area's file when its digest is the run's `script_sha`, else the run's own copy, labelled; else a line why none is shown) — and what the auditor was shown of the run, and says per decision `upheld`, `rejected` or `insufficient`; only `upheld` releases, and only when every draw on the decision as decided and claimed now says so (a contested state is settled by deciding again, never by another draw); a changed decision or a rewritten Conclusion makes the review stale (the Recorded results and Limitation lines are generated and bound through the record and the run); report-check blocks on a BLOCKER limitation's `stands` no review upholds and warns on a WARNING limitation's; a `stands` a review of the decision as decided and claimed now did not uphold renders in the Limitation line as "a limit proposed, not confirmed by a second auditor — unresolved", neither standing nor falling (`result_render.limits_of`, `reviews.contested`); a finding a review once did not uphold (`reviews.once_not_upheld`) and that is now `false-positive` or `fixed` (`findings.CLOSING`) is held the same way until a review upholds the new decision — the reviewer is asked whether the reason shows it inapplicable, gone or somebody else's (sixth round, t5: a dismissal after `insufficient` released the state); a BLOCKER on the Conclusion decided `fixed` (`finding_decisions.fixed_claim`) is held the same way — no follow-up audit is shown a rewritten claim, so the review judges the Conclusion as it stands; the review's record (`audits/<minute>-review.toml`) is held three ways, unequally: bound to its inputs — a changed decision or a rewritten Conclusion makes it stale (guaranteed); once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed); its content is compared with no journal line, kept answer or evidence copy, so `rejected` rewritten to `upheld` before the first commit releases the decision — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md))

- **Where:** `decision_review.gather_review`, `decision_review.parse_review`, `reviews.upholding`, `reviews.once_not_upheld`, `report_decisions.review_findings`, `report_decisions.check_repaired_claims_upheld`
- **Command:** `labkit-audit --review`, `report-check`
- **Tier:** agent audit (the release condition: guaranteed, on the record as written; the record's origin: unchecked)
- **When:** after the analysis audit is decided

## run → report (the follow-up)

an earlier decided BLOCKER (`fixed`, `limitation`, `false-positive` in a record not of the state reported) is released only by a covering analysis record's valid `resolved` — the head of its origin, its decision as it stands, a required check shown — while no covering record holds another verdict on that origin, or carried into a covering record, where it is decided; a carried finding `false-positive` owes an upholding decision review; a BLOCKER `fixed` in the state reported is held; each sentence names the missing step (pilots: [fixed follow-up](usability/2026-10-26-fixed-followup-pilot.md), [second](usability/2026-10-26-fixed-followup-pilot-2.md))

- **Where:** `followup.release_holds`, `followup.chain`, `report_decisions.followup_findings`, `decision_review.reviewable`
- **Command:** `report-check`; `claude-hook stop`, `.githooks/pre-commit`, `protocol-fill --from-run`
- **Tier:** guaranteed (the binding and the release); agent audit (the verdict)
- **When:** before the number leaves the area

## run → report (a discussed run, the registered report)

a report discussing a run (a discussion block), and the report a head registers once its result, handover or reported-through block stands, present as a result nothing the protocol has not adopted and nothing the audit decisions or the adopted result contradict; a cold reader gets the report with line numbers, the adopted run, the discussion blocks, the protocol, the `metrics.json` of the adopted, each discussed and each cited run, every run of the area in one line (state, kind, binding, what the report makes of it, the settings that vary across the protocol's measurements, scalar metrics — the history a silent search shows in) and every audit record with its decisions and failed attempts, and names the lines as `result` or `contradiction`; recorded in `audits/report-reviews/` with the fingerprint of exactly the inputs it read and the brief it read them under (`report_hold.review_fingerprint`; its own folder and the attempt journal not among them — a corrected brief makes every earlier review stale); report-check holds the report, per protocol its discussions name, until a review of its state — the report and protocol as the gate's state holds them, at the commit only records the index holds and the area's tree equal to the index — names no claim; a committed report discussing a run of an area a change touches is held with the change (`report_hold.discussing_reports`); a claim holds the state — an `--again` draw's as well — and a later clean draw (or `--again`) releases nothing; a claim the reader got wrong is decided `false-positive` in its record (`limitation` and `fixed` are refused), bound to the record, the claim's number, the state and the decision's digest, and releases only once a second reviewer, shown the claim, the reason and the first reader's inputs, upholds it — a verdict other than `upheld` is outvoted by no further draw, a revised reason is a new decision with its own confirmation; the command prints the draw and the state apart and exits with the state (0 released, 1 held), a changed input (the report, the protocol, a run's metrics, an audit decision) owes a new review; the post-change hook names its command (pilot: [report review](usability/2026-10-25-report-review-pilot.md)); a report that cites no run is out of its reach; the review's record is held three ways, unequally: bound to the inputs it read — a changed input owes a new review (guaranteed); once HEAD holds it, a record changed since is refused at the commit and in working-tree release checks, including `labkit-next` and `report-check AREA` (`evidence.change_blockers`, guaranteed); its content is compared with no journal line, kept answer or evidence copy, so a claim deleted before the first commit releases the report — where what the record says came from is unchecked ([limit](notes/2026-11-02-review-record-forgery.md))

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

the run's call log agrees with the model records: each line of `llm-calls.jsonl` has a record naming its alias — the run's own `models_resolved`, or for an answer a run stored (`origin.run`), that run's record, found in the lab's areas; a derived run, which by the README's definition makes no model calls and has no record of its own, blocks on a call that asked the model or an answer stored outside any run, and passes only on replayed answers whose storing run names the alias. Without a finding there, a run whose metrics show model calls (`model_calls`, `llm_retries`) has a model recorded along its lineage (a warning). Stand-ins in the call log (`llm_cache.store_stand_in`, marked in the cache entry and the line) are named in a warning: no model gave them, and the run's numbers show what its processing does with fixed answers. Not proven: that every answer the run used was logged — answers read past labkit's cache leave no line

- **Where:** `runs.read_model_calls`, `runs.run_dir_in_lab`, `run_record_check.call_log_model_findings`, `run_record_check.model_provenance_findings`, `run_record_check.stand_in_findings`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** after the run

## run → report (continued rows)

rows that carry their code (`_instrument.code_sha`), continued from a run whose script differs from the answering run's: a blocker — the number is that code's; a model's answers re-read after a parser fix pass

- **Where:** `run_record_check.row_provenance_findings`
- **Command:** `finalize`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (the null lane)

an output the run kept with a registered and a null lane: the null answers otherwise on some item, gold included — read from the kept rows, not from the editable script

- **Where:** `run_record_check.null_lane_findings`
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

every repeat cost: each input whose record names an origin run (`origin_run`, decided at start) is that run's registered output — the origin run under the area's `runs/` reads, is completed, its `outputs.json` holds the input's path with the sha256 the input's record holds, and the file's bytes are those now; the first part that fails is a blocker naming the input, the origin and the condition, its way out restoring the bytes or the origin's record from existing evidence or measuring anew, never rewriting a recorded sha256 or origin; at `low` changed bytes are the provenance station's blocker and a note here; a plain input and the runs the lookup skipped are notes, and the analysis audit is shown the same facts as an `INPUT ORIGINS` piece, with a `SOURCE PROTOCOL <run>` piece per origin run: its protocol as that run started under it (`audit_binding.source_protocol_pieces`); an origin run bound to a protocol whose text then (commit and patch; a changed tree without its patch counts as lost) cannot be read back is a blocker with the way out restoring that evidence or measuring anew, one bound to none a note (`audit_binding.source_protocol_finding`); under a text that reads, the origin run reports every promise that text registered, as intent-check holds an answering run, a blocker each where it does not (`intent_check.origin_intent_findings`; the protocol as it reads now is not asked), except a preparation origin, which reports no result and owes none of them, its piece showing the text as context (`audit_binding.SourceProtocolThen.preparation`); a stored origin is not decided again; other protocols of the area are not held

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

at both repeat costs: what binds for good is the promise given before the result was known — the report the protocol registered in the commit of a first measurement, read by the id the run recorded (`registered_report.report_duty`, `bound_reports`). The duty hangs on the protocol, not on the report's path: the head may name another file, and the new target owes the delivery. Held: a head that registers none while that duty stands (restore, name another file, or hand over), and a protocol id the area measured under that no protocol of the area carries now while it owed a report — by report-check's chain, by its area form on an area without a protocol, and by the stop's and the commit's hold (`report_check.orphaned_duty_gaps`, one reading in the file state each judges); a deleted protocol that owed none is passed over. A report entered after the first measurement starts no lasting duty: while the head names it, the checks of a registered report hold it, and taking it out ends those and nothing else — an adopted result, a written report and the audit records keep their own holds. Where the first measurement's registration does not read (its commit not recorded, not held by the repository or not holding the protocol; a measurement lost; a run of the area whose record does not read, which may have been the first), a head without a report is a check not executable, never "no duty". The setter previews its proposed head with the same gate. Selection reaches a protocol by area or formerly registered report (`formerly_registering`). At stop/commit a current protocol-specific handover ends the duty without releasing a result

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

every lane and every kind: the protocol the answering run saw holds the question, its terms, the data, the exclusions and the unit (`protocol_history.SCOPE_FIELDS`, whitespace folded, the generated data counts left out) and the head's kind, `[kept]` and `[reference]` as its first measurements saw them; a change is held, each field named with its old and new value, with the way back (restore and measure again, or register anew); first measurements that saw different texts in a field no correction in place covers (several at one commit, the tree edited between them, a run that stopped without a number among them) are held to each other first, and since which text stood cannot be told, the way out is a new registration or a handover, never a restore; the protocol as it stands is held the same way, so a field rewritten after the last measurement is held before any run carries it — unless it is a correction in place: an audit finding that names the field as its place (`<protocol file>:<label>`, the label in full or the one label it begins — `protocol_check.field_at`; no line number; a start several labels share binds nothing, and the decision's line and finalize say so), decided `fixed`, and a `resolved` on it bound to that decision in an analysis record that covers the area now (code, promises, registration, the fields read before the run, the run) — at every grade; a fresh audit without that verdict, a verdict on another field and a text edited after the verdict release nothing; the head's kind, `[kept]` and `[reference]` name no field and are never corrected so, nor is the question (`protocol_history.UNCORRECTABLE_FIELDS`: it states the requirement, a different question is a protocol of its own) — the hold offers the correction route only where it applies (`registration_hold.correction_way`), the decision's line explains the condition (`protocol_history.STANDS_AS_REGISTERED` for the question) and names no way of its own; the release names each correction with its old and new value and the verdict's why; a code change measured again under the same fields passes — what the run computes is the analysis audit's question

- **Where:** `answering_run.first_measurement_groups`, `protocol_then.as_measured`, `protocol_history.scope_differences`, `protocol_history.first_measured_differences`, `protocol_history.differences_among_first_measurements`, `protocol_history.correctable`, `finding_decisions.corrected_field`, `registration_hold.scope_changes`, `registration_hold.resolved_corrections`
- **Command:** `finalize`, and through it `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (a declared replacement)

a protocol with `[replaces]`: one predecessor of the repo, no circle, every difference of the registration — the kind, the promises, what the number is about as finalize compares it (`scope_differences`: the question, its terms, the data, the exclusions, the unit, `[kept]`, `[reference]`) and the Data profile — against the predecessor's (as each first measurement saw it: commit plus its `uncommitted.patch`, held to the recorded block; against each when they differ) declared as `[[replaces.change]]` and none declared that is not one, the predecessor's open BLOCKERs decided; the generated result opens with the predecessor's verdict (`no verdict` where its registration does not stand); a report that switched its citations to an undeclared successor is static evidence

- **Where:** `protocol_block.replaces`, `protocol_history.registrations_as_first_measured`, `protocol_history.registration_differences`, `report_replacement.replacement_gaps`, `result_render.predecessor_verdict`, `report_hold.replacement_hints`
- **Command:** `report-check`
- **Tier:** guaranteed (the hint: static evidence)
- **When:** before the number leaves the area

## run → report (the end)

at every repeat cost: frozen (high repeat cost only — at low repeat cost no freeze and no preflight audit are owed), finalize clean with its blockers named, the answering run a full run (`run_kind="measurement"`, not acknowledged unfrozen — a probe's or an acknowledged run's number is refused), an analysis audit record of the code, the promise block, the registration it judged (`registration`: the kind and the fields the kind owes, `protocol_check.registration_stamp`), the answering run and what the audit was shown of it (`shown_sha`: its rows' excerpts and metrics.json, its declared dependencies, the protocol's declared run when that is another one, and the setup's prose the audit read, `protocol_check.audited_texts`; `audit_binding.run_shown`) as they are now, every finding decided, `02_analyze.py --check --protocol FILE` passes for this protocol (its run recomputed with the script that run ran; the note carries the numbers and the run_id; every skeleton stamps the script, the compute skeleton's since 0.100.0)

- **Where:** `report_check`, `runs.unreportable`, `audit_gaps.audit_coverage`, `recheck.holds`
- **Command:** `report-check`
- **Tier:** guaranteed
- **When:** before the number leaves the area

## run → report (the declaration)

a protocol whose TOML head declares a result (`[result] run = "<run_id>"`, written by `protocol-fill --from-run`, never typed — the one declaration that a result is reported) goes through report-check at the stop and the commit, with every other protocol of an area a changed, deleted or staged path touches — a path in the area, a file its promises declare in scope, or a shared helper under `lib/`/`src/` its code imports (a script changed or removed under a reported number reopens it; at the commit the protocols are the index's); a protocol declaring none owes nothing (an exploration ends with no reported result); a `[result]` that does not read (a typed id, a stray key) is a blocker where it stands; an Recorded results written under no declaration is a warning

- **Where:** `report_check.hold_changed_paths`, `report_check.reached_by` (the one reader of the protocols a change reaches, for the gate and for the step printed beside its hold), `report_check.affected_protocols`, `scope_sha.areas_touched`, `protocol_block.declared_run`, `finalize.declared_run_gaps`, `protocol_check.recorded_results_without_run`
- **Command:** `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported --staged`: the answer as the index holds it, the area's tree equal to the index), `protocol-check`
- **Tier:** guaranteed (the warning: static evidence)
- **When:** ending the turn, committing

## run → report (a report outside the protocol)

a changed or staged Markdown file citing a run (not a protocol, not under `runs/` or `data/`, both tested at its own path): a report that is a symbolic link, wherever it points, blocks alone, naming the copy that replaces it (`report_hold.link_gap`; its other checks follow on the copy); every report result block names its protocol, shows the run that protocol declares now and equals what it renders (the registered Question / hypothesis and the Conclusion verbatim, the Recorded results and Limitation lines; `report_blocks.block_body` refuses while the question or the Conclusion is not written, for the writer and the check alike; `protocol-fill --into` writes it and replaces the protocol's block after a new run is adopted) — exact for the block, nothing for the prose beside it; a block shown inside a closed fenced code block outside every block is an example and not read (`comment_blocks.example_lines`); every token that reads as a run id names a run of the repo; a cited run that a protocol declares as its result is shown in that protocol's block, else the block is owed; the answering run of a protocol that declares no result is not cited undiscussed — the promotion without the adoption (sixth round, t3 and t18) — and a run only looked at stands in a discussion block (`protocol-fill --discuss RUN --why … --into`: protocol, run and why as TOML in its head, its line written from them; a block without its why, with a line that differs from its head, repeated for one protocol and run, naming a run its protocol's area lacks, or discussing a declared run blocks; any other cited run no protocol declares: a warning); the protocol declaring a cited run goes through report-check as well; an untouched file's old citations reopen nothing; the report a protocol's head registers (`report = "REPORT.md"`, `protocol_block.report_field`), once delivered in the state, carries that protocol's result block of the declared run or its handover block as the record renders it (`handovers.block_mismatch`) — else one blocker with the three ways out (adopt then `--into`, `--discuss` which releases nothing, `--handover`); while nothing is adopted, a discussion block of the run the gates hold the protocol to is its progress account: the commit and the stop take it without a report review, an honest interim state, and `labkit-next` names the adoption or the handover (`registered_report.progress_account`), and `--into` puts the result block where it stood (`report_blocks.with_block`), run id removed, typed in or discussed alike; before any measurement and with no answering run or adoption, a valid report draft owes no result block; a report not yet written owes nothing, a protocol registering none holds no file to this, and the protocols registering a file among the paths are selected though it lies in no area

- **Where:** `report_check.hold_changed_paths`, `report_hold.hold_report`, `report_hold.undeclared_findings`, `report_hold.promotions`, `report_blocks.block_gaps`, `report_blocks.cited_gaps`, `report_blocks.blocks_owed`, `report_blocks.discussions`, `report_blocks.discussion_gaps`, `report_hold.discussion_sources`, `registered_report.report_owed`, `report_hold.registering_protocols`, `report_check.report_findings`, `report_check.hold_registered`
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

- **Where:** `finalize.check_open_audit_findings`, `audit_records.area_records`
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

an area the session touched, or a staged file lies in — an area deleted whole with its protocol is found by its journal copy on the branch —, holds an audit BLOCKER nobody decided: the stop sends the agent back (the records as the tree holds them), the commit is refused (the records and their decisions as the index holds them); a lost or unreadable record or journal holds both too, except where a current handover binds that loss (`handovers.acknowledgement`) — an open BLOCKER never; committed evidence changed against git — a record beyond its decision lines, another audit file, a closed run's files — or a file of labkit's that git ignores holds both as well, in the state checked against HEAD, at the stop also by a session commit or left behind in HEAD's reflog, and no handover acknowledges it: each line names its `git checkout`

- **Where:** `undecided.undecided_blockers`, `evidence.AreaEvidence`, `findings.open_blockers`, `hook_session.committed_in_session`, `evidence.AreaEvidence.change_sentences`, `evidence.ignored`, `agent_hooks.session_evidence`, `evidence.change_blockers`
- **Command:** `claude-hook stop`, `.githooks/pre-commit` (`claude-hook pre-commit`); the change against HEAD also `report-check AREA` and `labkit-next`
- **Tier:** guaranteed
- **When:** ending the turn, committing, before reporting

## audit → evidence (the attempts)

every model call of `labkit-audit` is an attempt journaled in `audits/attempts.jsonl` — a preflight or analysis audit, a decision review (`review`), a report review (`report-review`, its record under `audits/report-reviews/`) — started before the call, the model's answer kept as `audits/answers/<attempt id>.txt` before anything reads it, ended with its record, its failed-attempt file or why none, and the kept answer (a kept answer releases nothing); a call not made (a state already judged, a refusal before it) is no attempt, and a record older than the journal is named by none; an attempt whose process holds no lock and has no end is marked interrupted by the next; a file an ended attempt names, a file under `audits/` HEAD holds, or a journal line HEAD holds that is gone blocks the next audit, the stop and the commit (at the commit as the index holds them, so a commit restoring a record HEAD lost passes; at the stop HEAD's journal is held to HEAD's files), naming the attempt or the file; in the tree a journal line its copy in the git directory keeps (one per branch, held as a set of lines) that the journal lacks blocks too, with the files its end names — `audits/` deleted whole before a first commit is noticed (not on a detached HEAD, in a fresh clone or with the git directory gone) — a current handover lets the stop and the commit pass on that loss, never the next audit or the adoption (`handovers.missing_paths` keeps its paths owed); a running attempt refuses a second; the check and the start stand under one lock

- **Where:** `attempts.begin`, `attempts.attempt`, `attempts.gaps`, `attempts.area_gaps`, `attempts.journal_copy`, `attempts.copy_gaps`
- **Command:** `labkit-audit`, `claude-hook stop`, `.githooks/pre-commit` (`claude-hook pre-commit`)
- **Tier:** guaranteed
- **When:** auditing, ending the turn, committing

## run → report (denominator)

denominator `criterion_<i>_n` matches a recorded input count

- **Where:** `run_record_check.criterion_n_input_mismatches`
- **Command:** `finalize`
- **Tier:** static evidence
- **When:** after the run

## report → number

every output file the number is computed from pinned to the run — several named by key and recomputed together (`recheck.holds_outputs`), each a row file, one JSON object per line (a stagekit stage output is one JSON document: the area writes the rows it reads into a row file it registers) —, the code here shown to be the code the run ran (changed: refused; not comparable: not verifiable, held by report-check as a check not executed), recomputation agrees, note cites every number and the run id, the kept key read from the protocol as the run saw it, block unchanged for the answering run (a run named for a recheck is held under the block it recorded); an older run is checked apart (`recheck.holds_as_measured`, the script's `--check --run <run_id>`): its rows are the file as it stands or the bytes a commit holds with the recorded sha256, read into a temporary directory, else the run is not verifiable — no note is read and nothing is released; a run that computes from its recorded inputs (`recheck.holds_from_inputs`): first every input is the bytes it read — one with an origin run still that run's registered output (`origin_check.origin_gap`) — and only then its evaluation over them agrees; the source runs are not run again

- **Where:** `recheck.holds`
- **Command:** (an area's `--check`)
- **Tier:** guaranteed
- **When:** keeping a number

## kind → kept number

every head names its kept number (`[kept]`: key, unit — `protocol_block.kept`, owed at every decided kind, `protocol_check.kept_gaps`; in the registration stamp; a fit's or an apply's criterion judges that number); every measure skeleton reads the key (`metric_key`, `KEPT_KEY`), and finalize blocks an answering run whose metrics.json does not hold it as a finite number, naming what it holds instead (`run_record_check.kept_number_gaps`) — the adoption's check runs finalize on the proposal; the Recorded results line names it first with its unit (`result_render.kept_phrase`). The key is bound by name, not by meaning

- **Where:** `protocol_block.kept`, `protocol_check.kept_gaps`, `run_record_check.kept_number_gaps`, `finalize.check_kept_number`, `result_render`
- **Command:** `labkit-init exp --kept --unit`, `protocol-fill kept.key=… kept.unit=…`, `finalize`, `labkit-adopt`
- **Tier:** guaranteed
- **When:** registering, before reporting

## compute → reference comparison

a computation's head may register the stated value its number is compared with (`[reference]`: value, tolerance, relation, source, compared on the `[kept]` key — `protocol_block.reference`, refused on a kind with a bar naming the criterion, `protocol_check.reference_gap`; in the registration stamp); the run writes the verdict beside the number (`reference.reference_verdict`, one home: `compared` with `ref_met` and the distance, or `not comparable` — the key absent or no finite number; the compute skeleton's `metrics_of`), `--check` recomputes it, the Recorded results line and the result block carry it generated (`result_render.comparison_phrase`), and finalize blocks a verdict the run could not make, a `ref_*` key without a registered reference, and a reference changed after the run (`reference.comparison_gaps`); `not met` is a valid outcome, and without the table no `ref_*` key is written and nothing is owed

- **Where:** `protocol_block.reference`, `reference`, `result_render`, `finalize.check_reference`
- **Command:** `labkit-init exp --reference`, `02_analyze.py --check`, `protocol-fill --from-run`, `finalize`
- **Tier:** guaranteed
- **When:** registering, the run, before reporting
