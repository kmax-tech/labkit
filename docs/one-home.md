# One home per question

Each heading is a question the code asks in more than one place; the paragraph under it names the one function, constant or module that answers it. Part of [the architecture](architecture.md).

A second answer to any of these questions is drift: move the caller to the home, never copy the logic. `tests/test_one_home.py` greps `labkit/*.py` for the shapes a copy takes (a hand-spelled sha256, a `git` run outside `repo`, a `PROTOCOL-*.md` scan, the id letters, a fence regex, …) and fails on a match outside the home — three audits removed the same copies by hand and they came back each time (2026-10-15).

## Is this an intent id / key?

`promises.ID_IN_PROTOCOL`, `promises.ID_KEY`

## What does the promise block say?

`promises.parse_block`, `promises.load`, `promises.constants`

## Which code does a promise rest on, and did it change?

`promises.declared_scope_sha`, `promises.scope_drift`

## What does the protocol's head say (id, type, cost, frozen, audit)?

`protocol_block.head`

## Which number does a computation report, and does its run hold it?

`protocol_block.kept` (the table, `kept_toml` its writer, `kept_key` the key), `protocol_check.kept_gaps` (owed or refused by kind), `kept_number_check.kept_number_gaps` (the run holds it)

## What stated value does a computation compare with, and did the run meet it?

`protocol_block.reference` (the table, `reference_toml` its writer), `reference.reference_verdict` (the verdict; `with_verdict`, `phrase`, `comparison_gaps` its readers)

## How is a string written into TOML — a finding's or a review's field, a promise sentence, the head of a report's discussion block?

`protocol_block.toml_string` (one line that reads back through tomllib unchanged; a lone surrogate refused with its cause)

## Which prompt does a protocol register, and does a sent prompt match it?

`protocol_check.registered_prompt_blocks` (every fence under Prompt but the stamp's unfilled one — `is_stamp_placeholder_block`, never a guess from a leading `<`), `protocol_check.unheld_prompt_lines` (the fixed-line comparison; `prompt_check.check_prompt_drift` reads the scripts' constants statically and warns on one it cannot compute, `lanes.Lanes.prompt_drift` reads the prompts as a run sends them)

## What does a protocol's field say, as every stamp and comparison reads it?

`protocol_check.field_values` (by `field_name` — case, a gloss and † aside — whitespace folded; a field written twice is all its copies, never one of them): `registration_stamp`, `audited_texts`, `protocol_history.scope_differences` and `registration_differences` read it; `protocol_check.repeated_fields` names a bound field (`BOUND_FIELDS`) written twice, told by `repeated_findings` and refused with `REPEATED_WAY_OUT` by protocol-check, preflight, report-check, finalize, the start check, the run hook and `labkit-next` (`FieldReport.repeated`), and at low repeat cost in the committed registration (`protocol_history.registration_missing`)

## Which protocol field does a place name?

`protocol_check.field_meant` (the label in full first, else the one label it begins; several or none raise `FieldPlaceError`), `field_at` over a protocol's text (a field written twice raises too), `field_or_none` where a place need not name a field (a line number, a section): `protocol-fill`'s label (`protocol_edit.field_for`), the field a `fixed` finding corrects (`finding_decisions.corrected_field`; finalize and the follow-up audit hold an unclear one as an `AuditError`, the decision's line says it could not be read), and the reading-hint filter (`audit_decisions.read_hints`: a hint whose place names no one field is left out, with its reason).

## Which prose fields does a protocol owe, and which are filled?

`protocol_check.FIELDS`, `protocol_check.owed_fields` (by repeat cost, kind and model — `owed`, the result check, the rendered example `example_owed` and `protocol-check PROTOCOL --contract` read it), `protocol_check.check_fields`

## Which template items does a stamped form carry — the low form, the full form?

`protocol_check.in_form` (a field of `FIELDS` by `in_cut` or `full_owed`, a guidance item of `GUIDANCE` in the full form when `needs_met`, an unlabelled part by `LOW_FORM_SECTIONS`; an item without a policy raises); `protocol_cuts.form_cut` lays it out

## What does a repeat cost owe — the freeze or the registration, which audits, which cut, the foreground, the provenance check? What does a reported number owe at its release? Which skeleton does an area get, and what is its check?

`standard_contract.lane` (the release reads its `freeze` and `audits`; `report_check`), `standard_contract.skeleton` and `standard_contract.registration_fields` (both by the head's `kind`: what the kept number asserts — a computation has no bar, a fit or an apply registers one; `standard_contract.has_bar`), `standard_contract.CHECK_SCRIPT` — every consumer reads the field it needs; a `repeat_cost == "low"` or a `kind == "compute"` outside the contract is a copy

## Which protocols does an area hold? Which does the repo?

`repo.area_protocols`; `repo.repo_protocols` (outside `repo.SKIP_DIRS`); per file state `repo.protocols_in` (the index's at the commit); `repo.PROTOCOL_GLOB`, `repo.PROTOCOL_NAME` are the name; a protocol is a regular file in the tree and in the index — a symbolic link, valid or broken, is refused with `repo.protocol_link` (`repo.protocol_links` finds them per state; the protocol choice, report-check, protocol-check and the handover ask it)

## Which area does a bare name name?

`repo.areas_named` (the directory called so and every `NN-<name>` by `repo.AREA_NAME`, `repo.split_area_name`; never a glob); `repo.area_path` for a command's argument (`repo.resolve_area` adds the refusals: several areas, no directory; every area command calls it after reading its line, which `repo.area_parser` builds with argparse — `repo.GivenOnce` refuses a single-value flag given twice), `scaffold.existing_area` for the area `labkit-init exp` promotes or restamps — both refuse a name several areas carry, naming each

## Which number does a new area get? Does one number name two areas?

`area_numbers.next_experiment_number` (one above every number this tree, `_archiv/`, every branch and every other worktree hold — `area_numbers.areas_elsewhere` over `repo.branch_refs` and `repo.worktree_roots`), `area_numbers.shared_numbers`; `labkit-init numbers --staged` in the pre-commit and the pre-merge-commit

## Which areas do changed or staged paths touch?

`scope_sha.areas_touched` (the nearest area above each path — `repo.areas_of` — and every area whose promises declare a changed path, whose adopted run recorded it as an input, or whose code imports a changed shared helper; the stop's reported numbers and the commit's undecided findings read the same answer)

## Where is the repo? Where is the lab?

`repo.git_root` (git), `repo.layout_root` (git, else stamped tree); `repo.lab_root` (the nearest `models.toml`)

## Run git

`repo.git` (output, loud on failure), `repo.git_run` (exit code is the answer); both read an object under its own hash, a replacement (`git replace`) is not followed (`repo.NO_REPLACE_ENV`)

## Keep a git answer for the rest of a command

`console.once_per_command` (the answers kept while `console.exit_with` runs a command's main; with no command running nothing is kept), `repo._once_by_hash` (only a question about an object named by its full hash: `blob_text`, `blob_bytes`, a known commit in `commit_of`, the tree a run saw in `_in_index_then`; never `HEAD`, the index or the working tree)

## Print a `labkit-audit` step a person or agent runs next

`commands.audit_command` (quoted, `--protocol` where the area holds several); a check that does not know the working directory names `labkit-audit <area>` and report-check fills it (`gate.Findings(audit=…)`)

## Ask git about the repository — HEAD, a dirty tree, a path in the git directory, the files a state holds under a folder

`repo.head_sha` (short form, "" outside a repo or unborn), `repo.tree_dirty` (untracked counted or not), `repo.git_dir_path` (this worktree's or the common git dir: locks, stop base, session log), `repo.local_dir` (labkit's local state about a path: in the git dir, else the temp dir — the audit locks, the detached starts), `repo.files_at` (the index's or a revision's files, None where there is no such state — by exit code, not git's words), `repo.branch_refs` (every local and remote-tracking branch), `repo.worktree_roots` (every worktree's directory), `repo.head_before` (the commit HEAD's line stood on before a time, by commit dates)

## Which directories does an area's `runs/` hold, and what does each say?

`runs.run_dirs` (one walk, metadata read once; an unreadable run is data — the caller refuses, reports or skips); per file state `area_state.present_run_dirs`, the reader the area's state and `report_hold.Sources` ask; a run git holds back or only the index lists is told by `area_state.gone_run_restore` and `LOST_RUN_SENTENCE`

## What is the state of an area — its runs, the runs git holds back, what each protocol measured, which measurements were first?

`area_state.state_of` (built once per check from the formats' readers; `area_state.Measured` per protocol: `has_measured`, `firsts`, `first_groups`, `deleted`, `lost_measurements`; `area_state.assemble` for a test that states records instead of files); a deleted run is read back from the last commit that held it (`area_state.committed_runs`), one only the index lists is lost, never invented

## Which runs does an area's run index list, and does the index read?

`run_index.indexed_runs` (by protocol id, deleted runs included); `run_index.read_index` is the one check every reader and writer of `runs.tsv` shares — the current columns (`header_refusal`), every row whole — and raises `RunIndexError`, a refusal naming the line: a short row is never read as no measurement

## Which run started with which protocol, when and as which kind, also when it never finished or its directory is gone?

`run_starts.read_starts` (the start files `run-starts/<run_id>.json`, by run id; `write_start` creates one whole and durably at a run's start and never over one that exists); a file that does not read is that run's incomplete start (`RunStart.unread`), never an error of the area: `RunStartsError` leaves `parse_start` only and `start_of` catches it; the area state is its one reader outside `formats` (`AreaState.starts`, `started_only`, `conflicts`), and `evidence.start_file_changes` holds a committed one against change

## Is this run finished? Which runs are?

`runs.completion_state`, `runs.completed_runs`

## Where is an area's `runs/`, a run's directory, its metrics file?

`runs.runs_path`, `runs.run_path`, `runs.metrics_path` (`RUNS_DIR`, `METRICS_FILE` are the spelling; a message names the path through them too)

## Which files are an area's code?

`scope_sha.area_files` (the scripts and analysis globs; the audit stamp, code-check, prompt-check, import-check and intent-check read the same set)

## How are a JSONL file's lines turned into objects?

`jsonl.objects` (every line, `_meta` skipped, an unreadable line named), `jsonl.data_rows`; `batch.Store` keeps the torn-last-line loop that is its own

## What answers under a models.toml alias today?

`llm.model_entry` (the same lookup as the spec loader, `llm_specs.alias_tables`; the audit's evidence of a bound validation's alias)

## Which configuration served an openai alias, and did it change during the run?

`served_instrument.read_instrument` (each endpoint's vllm-swap `GET /health`: at resolution in `llm._load_spec`, after the first answer, at the end in `llm.served_readings`); `served_instrument.instrument_changes` decides the end of a run (`runlog`); `served_instrument.agreed_value` is the one rule for several endpoints, also for ollama's weights digest; `llm.served_configuration` is the one answer to which configuration a cache key and a resumable row are bound to

## Where do a protocol's `## ` sections begin and end?

`markdown.section_starts`, `markdown.section_end` (outside every fence; the prose count, the Runs list, the cuts, the reading probe)

## Is a labkit block in a report a real block or an example the document shows?

`comment_blocks.example_fences`, `comment_blocks.example_lines` (a block inside a closed fenced code block outside every block is an example; an unclosed fence hides nothing here, unlike `markdown.fence_spans`)

## Which values fill the `<area>` and audit-command slots a check leaves?

`commands.area_slots` (every gate builds its `gate.Findings` with them; a caller handing its own `Findings` fills them as it takes the findings)

## How does a command refuse, tell progress, or print its usage?

`console.refuse` (stderr, the caller exits 2), `console.Refused` (raised where the reason is known, `console.exit_with` prints it), `console.progress` (stderr, no exit code), `console.usage` (0 asked, 2 bare)

## Write a file whole or not at all

`files.write_atomic`, `files.write_atomic_bytes` (every file a run leaves — records, failure, patch, raw artefacts, source snapshots — the lease, a filled protocol, a protocol `labkit-init` promotes or restamps and the stamp files it replaces; the run index is appended under its lock)

## The digest of a file, or of a set of named contents

`digests.file_digest`, `digests.tree_digest` (`DIGEST_CHARS` is the one recorded width of a stamp)

## How is a JSONL text split into its records?

`jsonl.record_lines` (at "\n" only — `str.splitlines` also breaks at U+2028, U+2029, U+0085 inside a record)

## What does a run's metadata say?

`runs.read_run_config`

## Does an output file account for its input, item by item?

`batch.Store.ledger` (missing, duplicate, stray, stale per expected field); `require_complete()` inside the run keeps it from completing

## Which runs wrote a JSONL file's rows?

`batch.row_runs` (per-row `_prov.run`); runlog names the runs a resumed file continues, finalize holds every row to the run

## Is the recording process alive?

`runs.is_alive`

## Is an output lock's writer still writing? Is a detached start running?

`files.lock_held` (the kernel's `flock`, never a pid: `batch.lock_holder_words`, `detached.starts`)

## Is a run still open? Is the area busy?

`runlog.still_open` (`open_runs`; the twin refusal reads the open runs of the same script), `runlog.busy` (the open runs and the detached starts no open run names: `labkit-next`, `runlog --wait`, `runlog AREA`)

## Which protocol does a new run bind to?

`start_check.protocol_binding`

## What refuses a run before its directory exists, in which order?

`runlog.Run.__init__` (the registration, the detach gate where required and not already detached, the index header, data leakage, then for a full run `start_check.freeze_gate`: undecided blockers, the freeze or the registration, the acknowledgement over a failed audit); `start_check.prepare` refuses what cannot be read before any check

## Which run answers for a protocol?

`answering_run.bound_answering_run` (the choice; `intent_check.choose_explicit` takes a named run; `recheck.chosen_run` is the same choice behind `--check` and `--from-run`)

## Is this run a repeat draw, of which, and is it comparable?

`RunConfig.repeat_of`, `answering_run.repeats_of`, `answering_run.repeat_mismatch` (a fit's repeat with `reseed`: its seed held to `answering_run.repeat_seed` of the parent and the draw, the one key a repeat may change; `answering_run.repeat_seed_problem` where draws are read; its own output file `runlog.Run.draw_output`) — a repeat never answers (`bound_runs` leaves it out, `completed_runs(with_repeats=…)` makes every caller decide)

## Which run recorded the model that answered these rows?

`runs.model_provenance_run` (walks `derived_from`; a derived run records none)

## Is a run's `derived_from` chain whole?

`runs.lineage` (every config readable, every parent present, no loop — the whole chain; model provenance, params and row provenance read it)

## Which protocol does a command hold an area to?

`repo.choose_protocol` (the named one — a path, or a bare file name inside the area, `repo.given_or_in` — else the only one; never a guess)

## What does one check hold — which protocol text, which file state, which answering run?

`report_context.checked` (`Checked`: built once, read by every station; the state is named — the working tree at the stop, the index at the commit, the written proposal at the adoption; the run is `answering_run.bound_answering_run`'s choice through `audit_binding.audited_run`)

## How does a registered constant stand against the record?

`promises.constant_records_of` (equal / different / missing, type-strict), over a block's constants (`constant_records`) or a run's promise snapshot (`snapshot_constants`); runlog refuses before mkdir, intent-check/finalize block, `labkit-params` shows all three from the run's own snapshot

## Does a frozen protocol owe a promise block?

`promises.promise_tables_owed` — protocol-check (MUST), preflight and finalize (blocker), runlog (refusal before mkdir)

## Which state of the area does an audit record bind, and does a record bind the state now?

`findings.AuditedState` (`audit_prompt.bound_prompt` binds it, `Record.state` carries it, `covering_records` compares the two)

## Which analysis records cover the area now — code, promises, the answering run and what the audit was shown of it?

`audit_binding.covering_analysis` (`analysis_now` the state, `run_shown` the snapshot; report-check's analysis stage and its Limitation lines, `protocol-fill --from-run`)

## What does the result section say when it says what its sources say — and does it?

`result_render.rendering` (the Recorded results line from the declared run's metrics.json with its note, opened by a stand-in label per alias when the run or a run it rests on read stand-in answers — `result_render.stand_in_label`, counted from the call logs `model_check.stand_in_calls` reads, the same lines finalize's warning counts —, one Limitation line per decided limitation of the covering records), `result_render.render_gaps` (exact equality, each difference named; report-check's analysis stage, `protocol-fill --from-run` and `--render` write it)

## Does a report outside the protocol show a reported number as its sources render it?

`report_blocks.blocks`, `report_blocks.block_body`, `report_blocks.block_gaps` (a report result block shows the run its protocol declares now and equals that protocol's Recorded results and full Limitation lines; `protocol-fill --into` writes it), `report_blocks.cited_gaps` (every token that reads as a run id names a run of the repo), `report_blocks.unsourced_numbers` (numbers outside every block — a hint); `report_check.hold_changed_paths` holds changed citing reports, the protocols their blocks name and the protocols declaring the runs they cite, and the committed reports citing a run a protocol among the paths newly declares against HEAD (`report_hold.newly_declared`, `report_hold.committed_reports` — the two-step commit of the sixth round, t5)

## Which file owes a protocol its result, and what releases it?

the head's `report` (`protocol_block.Head.report`, read by `protocol_block.report_field`: repo-relative, inside the repository, not a protocol, Markdown; stamped by `labkit-init exp --report-file`); `registered_report.report_owed` holds the delivered file to the result block of the declared run, the handover block as its record renders it (`handovers.block_mismatch`) or, while nothing is adopted, the reported-through block as the analysis run's record and adoption say it now (`report_hold.stated_through`, `through_gap`: another protocol of the area adopted the run, and it reads this protocol's runs as inputs), and names the ways out; `report_hold.registering_protocols` finds the protocols a change of that file reaches (pressure pilot 2026-10-29: the run id deleted, the commit passed)

## Does a review uphold a decision as it stands now, under the claim the protocol makes now?

`reviews.upholding` (a review of that record, its code and its run as shown, of the claim's digest `reviews.claim_digest` over `protocol_check.reported_claim`, holding the decision's digest `finding_decisions.decision_digest`, every such draw saying `upheld`), `reviews.contested` (another draw settles nothing) — both by the one rule over the draws on a state, `reviews.released_by` and `reviews.first_not_upheld`, which release a report claim's decision as well (`report_reviews.upheld`, `report_reviews.not_upheld`); `reviews.once_not_upheld` (was a decision on this finding ever not upheld — then closing it owes a review too), `reviews.state` for the gate's sentence

## What does a file say at a git state — the index, HEAD?

`repo.text_at` (the index's or a revision's content, None where that state does not hold the file); `repo.state_text` for "the tree or the index" as a gate reads it — both name the file when its bytes are not UTF-8; `repo.indexed_files` for what the next commit carries; `repo.under_root` for whether a given path is the repo's at all

## What carries a gate finding's sentence — a mechanical check or an indication?

`gate.GateFinding.evidence_kind` (`GUARANTEED` / `STATIC_EVIDENCE`, given at every site, never defaulted; static evidence never blocks, the dotted line names it, the summary counts it; `labkit-params` shows the same constants in its evidence column; the agent audit is the records' kind, `findings.Finding`)

## What does a gate finding say about its check — a breach, a deviation on an unsettled basis, a suspicion, or a check not executed?

`gate.GateFinding.outcome` (`gate.derived_outcome` from the evidence kind and the rule assignment; a site states only `NOT_EXECUTABLE`, through `stated_outcome`; a stated value that contradicts the derived one is refused; the line names a check not executed, the inventory lists the outcome per site)

## Which audit findings are still undecided, and what does each gate make of one?

`findings.open_findings` (every mode, or one; the table of the gates' rules stands in its docstring: preflight warns unfrozen and blocks frozen, runlog refuses on a preflight BLOCKER and tells the rest only on an acknowledged start, finalize every record of its protocol by grade, the hooks, the handover and `labkit-audit --findings` hold BLOCKERs only (`findings.open_blockers`); the one record the head names is a gap on any open grade, `audit_gaps.audit_record_gap` — the differences are intended)

## Which code did an audit see, and is it still that code?

`scope_sha.area_snapshot` (the bytes read once and the sha over them; `area_stamp` its sha); the record carries its `scope_sha`, and `audit_gaps.audit_coverage` holds it to the stamp now (area stamp, not per promise)

## Which package does a requirements line name, and how is labkit pinned?

`requirements.requirement_name`, `requirements.requirement_lines`, the four `*_REQUIREMENT` grammars (stamp pin line, `labkit-check`, lock parser, probe)

## Which requirements file belongs to a repository?

`requirements.PIN_FILES` (the names, the lock before the declared list) and `requirements.requirements_files` (from a directory upwards to the root of its git repository, root included; outside a repository to the filesystem root): the stamp's pin (`scope_sha.find_pin`) and the run's lock (`provenance.env_state`) search with it; `labkit-check` reads both files at the repository root only (`repo_check.read_pins`)

## What is a run id, when did the run start?

`runs.RUN_ID`, `runs.RUN_ID_TIME`, `runs.run_started`; `runs.COMPLETED` is the one state word every consumer compares to

## How is a path shown in a report line, a bundle or a refusal?

`repo.shown(path, base)` — relative to the base when below it, else absolute, both resolved; a repo-relative key as git names it is `repo.rel_posix` (a link by its own name, loud outside the base); a record's path is `runs.recorded_path`, a stamp's hashed key `scope_sha._key`

## How does a record state a time?

`runs.now_stamp()` in `runs.RECORD_TIME` (`2026-10-13T14:00:57`, local) — a run's `started`/`finished`, a lock's or lease's holder, a staged probe, a session's stop

## How does a gate tell what it found, and exit?

`gate.Findings` (`block`, `warn`, `take` for a `GateFinding` built where it was found — `gate.blocker` for a pure check's, `gate.coded` for a code check's, grade, where, rule and fix as fields; `note` for a line counted as nothing, `report`; `Findings(tell=None)` collects the same findings without a console — report-check reads finalize's so, fixes included) — preflight, finalize, report-check, code-check, notes-check

## Does a hold withdraw a declared result first?

`gate.GateFinding.changed_since`, set by the comparison that found a difference — `run_code_check.code_since_run` (the script or a helper of the run or of a run it derives from) and `finalize.station_declared_scopes` (a declared scope) — never where the code could not be compared; `report_check.held_declaration` reads it and `chain_gaps` puts the withdrawal before every later hold — never read off a finding's words

## Which of finalize's findings does report-check's chain hold at a station of its own and tell once?

`gate.GateFinding.known_as`, set where the finding is built — `finalize.UNREPORTABLE_NUMBER` on `finalize.unreportable_warnings`, `finalize.UNREADABLE_RESULT_TABLE` on `finalize.declared_run_gaps`; `report_check.without_unreportable_warnings` and `report_check.without_declaration_blocker` leave finalize's finding out by it — never by comparing a finding's words

## What does a repair decided `fixed` owe next?

`labkit-next` (`next_step.next_step`), the one answer; the line under the decision (`audit_decisions.repair_hint`) explains what `fixed` means for the kind of repair the finding names — a correction of a field in place and its release condition, the question that stands as registered, a repaired Conclusion and its decision review, a repair of code, inputs or configuration — reads no area state, and points to `labkit-next`; it names no action, so it cannot contradict the gates

## What command does a way out name?

`commands.Command` (`name`, `kind` from `COMMAND_KIND`, `line`): every builder in `formats/commands.py` returns one (`fill_command` and `step_command` the `protocol-fill … "<label>=<value>"` and `labkit-next …` lines), and the three that build a line of their own format beside it — `report_blocks.discuss_command`, `registration_hold.restore_step`, `attempts.restore_command`, `str()` is the line a finding's text embeds; a finding carries it as `GateFinding.step`, and the withdrawal a hold names first as `withdraw_first` (told by `GateFinding.way`, set by `gate.withdrawn_first`). Code that decides on a way reads the names — `next_step._refused_measurement` (`MEASURE`), `report_check.adoption_order_note` (`ADOPT`, `RENDER`) — never the words of `fix`

## Which line names a command in the repo's environment (`.venv/bin/…`)?

`commands.VENV_BIN`: the fixed lines `HOOKS_INSTALL`, `PIP_INSTALL`, `LOCK_WRITE`; `pytest_command`, `script_check_command`, `measure_command`, `lab_stamp_command`; labkit's own commands are printed by their bare name (`gate_command`, `wait_command`, `runlog_placeholder_command`)

## What does a hook hold on, and what does it tell?

The hold is the gate's finding: a hook holds by its fixed policy — a BLOCKER among the findings of the state it judges (`GateFinding.grade`; the tree at the stop, the index at the commit), never by the words. What to do is `next_step.next_step`'s choice from the same findings of the same state, by its order (several blockers may stand; it names the first, and places the progress account before some blocks on purpose), printed as `labkit-next` prints it (`next_step.Step.render`, the one spelling). So a hook never composes a "Next:" sentence of its own, and `next` never names a step from a finding the hook's set does not carry: the hold and the action can differ in words (`missing_report`'s three ways are the hold, the discussion with the run id is the action) but never in the finding they rest on. The stop's and the commit's own hold — an audit BLOCKER nobody decided, a record lost or unreadable (`undecided.undecided_state`) — is a row of `next`'s order too (`next_step._undecided_step`, after the chain's gaps), and the stop, the commit's undecided gate and report-check's hook entry (`--if-reported`) print `next`'s step for every protocol touched (`next_step.steps_for`), reading the chain report-check already ran on that protocol in that state (`report_check.hold_changed_paths` → `HoldVerdict.chains`) instead of running it a second time. The commit's hold on an area whose tree differs from the index is one finding too (`report_hold.staged_area_gap`): report-check's declared branch and the report review print it, and `next --staged` has the row (`next_step._staged_area_step`, step `commands.stage_command`). The row also stands when only the tree holds a completed run or the adoption (`report_hold.result_outside_index`): read from the index alone, `next` would ask for a measurement the tree holds. There the hook's finding is the report's citation of that run, named unstaged with the same staging (`report_blocks.cited_gaps`, `report_hold.runs_outside_index`), not the tree-vs-index finding itself (`tests/test_next_step.py`, `RunInTheTreeOnly`). Held by `tests/test_next_step.py` (`DiscussingReport`, `MissingRegisteredReport`), `tests/test_agent_hooks_undecided.py` and `tests/test_report_check.py` (`test_the_commits_tree_vs_index_hold_is_nexts_step`).

## What does finalize say while the protocol declares no result?

One line naming `labkit-next AREA` (`finalize.undeclared_note`): a note, finalize stays clear, and it names no step of its own — finalize is a station of `next`'s chain (`report_check.chain_gaps` → `report_check.finalize_findings`), so the step is `next`'s to print. The decision list's line for an open BLOCKER (`audit_decisions.CAUSE_FIRST`) points the same way; the ways out by cause (`ways_out.WAYS_OUT`) are shown to the analysis auditor and stated in the agent guide

## What is the way out of a BLOCKER?

`gate.GateFinding.fix` — required for a BLOCKER (refused without one, every building site held by `tests/test_ways_out_data.py`), told in every form (`<what is refused>. Next: <fix>`, `gate.with_way_out`; a dotted line's last part `Next: <fix>`) and repeated in the summary; every literal way out names its command — a backticked span or a command builder; after a repair by hand, the check run again (`commands.gate_command`) — held by `tests/test_ways_out_data.py`; built where the cause is known, from the shared command builders (`commands.audit_command`, `commands.decide_command`, `commands.measure_command`, `commands.measure_anew`, `commands.gate_command`, `commands.adopt_command`, `finding_decisions.decide_way`, `audit_records.record_way`, `commands.register_anew`, `ways_out.HANDOVER_WAY`, `ways_out.ANSWER_AGAIN`); the refusals outside the findings carry one the same way — `AuditError` and `AttemptError` take `fix` as a required keyword, runlog's start refusals are `SystemExit(with_way_out(…))`, exemptions listed with their reason in `tests/test_ways_out_data.py`; the ways out by cause, for a person deciding an audit BLOCKER: `ways_out.WAYS_OUT`

## Which rules exist, what do they say, and does a reference name one?

`rules.load_ledger`, `rules.rule_heads`, `rules.check_heads`, `rules.check_ledger`, `rules.check_refs`, `rules.rule_text` (`labkit/docs/standard.md`, `labkit/docs/rules.tsv`)
