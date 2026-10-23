# Changelog

labkit does not carry legacy paths: a format or API change is a break,
announced here with the last version that still has the old behaviour.
Reproduce an old run with the repo's own commit and the labkit version it
pins (`requirements.txt` / `requirements.lock`).

## Unreleased

### Breaking

- **A resume refuses another model behind the same alias.** The judge's
  instrument (`lanes.Lanes.instrument`) held the prompts' digest and the
  alias only: models.toml edited between two processes put another model
  behind the alias, the resume kept the old model's answers and added the
  new one's, and the balance passed (review 2026-10-23). The instrument
  now also carries `model_identity` — backend and model, `name@digest`
  for ollama (`llm.identity`, the spelling `llm.provenance` stamps) — and
  `batch.Store` refuses rows of another (`InstrumentError`, naming both).
  Endpoints are not part of it: a cluster host changes with every
  allocation. An ollama digest that read `unavailable` in one process and
  a digest in the next is refused too — the weights cannot be shown to
  match. `lanes.balance` also refuses a file whose rows carry more than
  one instrument, whichever they are (rows merged by hand, or resumed
  before this). Migration: an output file written before holds rows without
  `model_identity` and is refused on resume; finish it with labkit
  0.103.0, or measure again into a new output file. Kept results are not
  touched: `--eval-only` and the analysis read the rows as they stand.
- **An audit record binds the registration it judged.** `[audit]` carries
  `registration = { kind = "…", "Question / hypothesis" = "<digest>", … }`:
  the head's kind and, per field the kind owes
  (`standard_contract.registration_fields`), the digest of its value,
  whitespace collapsed (`protocol_check.registration_stamp`). A record
  covers the protocol only while they are what the audit judged; the
  refusal names what changed — `the registration changed after the audit
  (Question / hypothesis)` — in the freeze gate, preflight, protocol-check
  and report-check. The report fields written after the run (Conclusion,
  Recorded results, Limits, the run list) are not in it. Why (review
  2026-10-23): the question was rewritten from the mean line count to the
  mean number of causal claims after the number was adopted, and the old
  analysis audit still covered it — report-check exited 0. A record
  without `registration` is no longer read; labkit 0.103.0 is the last
  that reads one. Migration: run the audits again (`labkit-audit <area>
  --mode preflight|analysis`) — a digest of what an old audit saw cannot
  be written by hand.
- **A failed audit attempt names its cause, and an unproven one stops
  the auditing of that state.** `audits/*-failed.toml` carries `cause =
  "unavailable" | "unproven"`: the backend gave no answer, or the
  requested model did not write it whole (`llm_backends.UnprovenAnswer`).
  After an `unproven` attempt `labkit-audit` refuses another try on the
  same code, promises and model before any call
  (`findings.stopped_attempt`) — in the fit probes a safety classifier
  stopped the auditor again on almost every try, and each try cost
  minutes and about a dollar. Another alias (`--model`) may try. A failed
  record without `cause` is not read; labkit 0.103.0 is the last that
  reads one. Migration: add `cause = "unavailable"` to each
  `audits/*-failed.toml` written before. Where no audit covers the state
  and an unproven attempt exists, the refusal of `report-check` and the
  freeze says so — the model, the count, the record — instead of only "no
  audit" (`findings.audit_coverage`); `usability score` shows `audit
  attempts failed · N (K unproven)`.
- **Protocol standard 0.22: the head says what the kept number asserts
  (`kind`).** `kind = "compute" | "fit" | "apply"` below `cost`: a
  computation judges no prediction (a measurement that cannot pass trivially), a fit
  judges a model trained or adjusted in the experiment, an apply a model
  used unchanged. The registration and the skeleton follow the kind, not
  the model technology (`standard_contract.registration_fields(kind,
  model)`, `skeleton(cost, kind, model)`, `has_bar`): a computation owes its
  question; a fit or an apply also the success criterion, the
  admissibility condition and the null condition / anchors, and carries
  promise tables at every tier; a `[model]` table adds the data profile
  and the prompt. `labkit-init exp` takes `--kind` and stamps nothing
  without it; `--kind compute --model` stamps the claim keys below; a fit at `seconds` gets
  the estimator skeleton (until now the compute's, now the fit skeleton). The template marks the
  fields a bar owes with `<!-- sb -->` (`protocol_cuts.SECONDS_BAR_TAG`),
  and the seconds cut carries them for a fit without a model. Loud, never
  a fallback: an unknown kind does not read (`protocol_block.head`), a
  placeholder stands among the head's placeholders and refuses a full run,
  a `compute` with a `[model]` table says what its number describes,
  `[model] number_describes = "model_outputs" | "target_property"`: the
  model's outputs, or a property of the data with the model as annotator;
  the latter owes `[model] annotation_validity = { protocol = "p-…" }` (an
  apply of this repo with a declared result, bound by protocol-check and
  preflight, `protocol_history.check_annotation_validity`) or `{ doi =
  "10.…" }` (its form only); evidence with `model_outputs`, and either key
  with a fit or an apply, is a must finding (`protocol_check.kind_gap`).
  Neither form proves the annotator suits — that stays the audit's, which
  is shown the bound protocol, its result, the model its run recorded
  (`answering_run.recorded_models`) and its prompt, today's models.toml
  entry and prompt sources marked as today's; the area stamp
  (`scope_sha.validation_basis`) covers the protocol, the result, the run
  records and the scripts — not today's models.toml — so
  an audit record goes stale when the bound validation changes (a DOI by
  its string only — the cited content is bound by nothing). Areas without
  `annotation_validity` keep their stamp. An
  intermediate commit refused `compute` with a `[model]` table outright
  (and the usability staging rewrote it to `apply` in silence): a share
  of model labels judges no prediction, but its claim about the data needs
  the annotator's evidence. Migration, said in the refusal of a 0.21
  head (`protocol_block.MIGRATION`): set `standard = "0.22"` and add the
  `kind` line (`protocol-fill PROTOCOL kind=…`); 0.103.0 is the last
  version reading standard 0.21, and no code reads it here. Why: a
  RandomForest at `seconds` had no `[model]` alias, got the count's
  skeleton and owed no criterion — t5 and t18 of the fifth haiku round;
  the writing probe (`docs/notes/2026-10-22-kind-writing-probe.md`)
  registered a count, two fits and an apply under the schema without a
  special rule. The kind was first stamped `count` and renamed `compute`
  before this release: it names what the number asserts — a descriptive
  or inferential statistic of fixed data, no prediction judged (ML
  lecture, ML:VII-1) — and not the one operation of counting. Migration
  for repos pinned to an intermediate commit: `kind = "count"` →
  `kind = "compute"` in the head (the refusal says so,
  `protocol_block.COUNT_RENAMED`), `labkit-init exp --kind count` →
  `--kind compute`; the skeleton `standard_contract.COUNT` is
  `COMPUTE`.

- **`preflight_audit` names the decided record, not a line.** The head
  field is the file name of the decided preflight record under the area's
  `audits/` (`preflight_audit = "2026-09-08T14-12-preflight.toml"`, as
  `labkit-audit --mode preflight` prints it when it writes one); `""`
  until then and at `seconds`. The gates read the record it names
  (`findings.audit_record_gap`: no such record, another mode, other code
  or another promise block than the area carries now, a finding still
  open — each a refusal at the run and a blocker in `preflight` once
  frozen; `n/a` or any other text names no record and is refused as
  before). A line of the old form (`<date> · scope sha <12 hex> · N
  findings`) is read as naming no record: 0.103.0 is the last version
  that reads it; a frozen protocol moves by writing its record's name
  into the field. `scope_sha.AUDIT_SHA`, `scope_sha.audit_stamp_drift`,
  `findings.waived_audit_gap` and `findings.audit_line_gap` are gone. Why:
  the last machine-read text inside a TOML value (review 2026-10-22) —
  the record carries its stamp, its date and its decisions, so the head
  copied a sha a regex had to find again.

### Fixed

- **Every file a run leaves is written whole or not at all.** `failure.json`,
  `uncommitted.patch`, `Run.save_raw` artefacts, the script and source
  snapshots, and four of protocol-fill's own writes (a field, `--prompts`,
  `--render`, the report's result block) took the plain path while
  `docs/architecture.md` said every record file and every filled protocol
  goes through `files.write_atomic` (audit 2026-10-23, B2). They do now;
  the snapshots through the new `files.write_atomic_bytes`.

- **finalize's reasons reach report-check.** Inside report-check finalize
  runs on a silent collector, and three of its stations put the reason
  into a note beside the blocker: intent-check's lines ("intent-check
  failed (see its lines above)" — nothing was above), the runs excluded
  from the answering-run choice, and the exit-2 reason (no protocol to
  hold), which report-check turned into "run it to see why" (audit
  2026-10-23, B1). Now each line intent-check prints is a blocker of its
  own, the excluded runs travel in the completion blocker, the test
  station's blocker carries pytest's count line, and a protocol finalize
  cannot choose or read is a blocker in a passed collector (a refusal on
  the console, as before). A non-zero finalize without a blocker is a
  `RuntimeError` in `report_check.finalize_gaps`, not a hint.

- **A changed validation reopens the computation that rests on it.** The
  area stamp of a `compute` with `annotation_validity = { protocol = … }`
  covers the bound validation, but the choice of what to recheck — the
  stop, the commit's `report-check --if-reported --staged`, report-check
  (`scope_sha.areas_touched`) — picked only the validation's own area, so
  a changed validation metric never reached the stale audit of the
  computation (review 2026-10-23). `areas_touched` now follows
  `scope_sha.validation_sources`: the bound protocol, its declared
  `metrics.json`, its scripts and the lab's `models.toml`. A DOI ties the
  area to no file.
- **A JSONL record holding U+2028, U+2029 or U+0085 reads as one record.**
  `json.dumps(..., ensure_ascii=False)` leaves these three raw inside a
  string, and `str.splitlines()` broke there: `batch.Store` and
  `write_dataset` wrote files their own reader called damaged
  ("unparseable line before the end of the file"), and cutting a torn
  last line could split a whole record. Every JSONL reader now splits at
  "\n" only through `jsonl.record_lines` — the Store, `recheck.rows_of`,
  the leakage check in `provenance`, the usability recount and the
  Claude Code transcript readers (`JSON.stringify` leaves them raw too).
  The writers are unchanged; their output was valid JSON Lines.
- **A claude-cli reply another model wrote is no answer.** A safety
  classifier stopped `claude-opus-5-5` mid-audit; the CLI let
  `claude-opus-4-8` continue, `--output-format json` returned the
  continuation alone as `result`, and the audit record named
  `claude-opus-5-5` (fit probes on `3e9784c` and `de663ed`). The reply now
  has to show the requested model alone in `modelUsage` and `num_turns =
  1` (both required; a missing one is a `ReplyError`), and no safety stop
  where the CLI counts them (`safety_stops`, absent in CLI 2.1.285, so
  optional); otherwise `llm_backends.UnprovenAnswer`, raised at once, not
  retried. Observed on CLI 2.1.285 (fit probe on `97e6470`): a stopped
  reply is `subtype = "success"`, `is_error = false`, `num_turns = 2`,
  both models in `modelUsage`, no `safety_stops`. A reply whose
  `stop_reason` is `refusal` is unproven too — a stop nothing continued
  would show one turn and one model; not yet observed, so a guard, and
  `stop_reason` is named in every failure message. An audit that meets it records a failed audit, no
  findings. Standard: LAB-029. The stop and a foreign model are checked
  before `is_error`: in the fit probe on `4f4f238` every audit try was
  stopped and continued and the call was retried — a stopped answer
  flagged as an error took the retryable path. An error without a stop
  or another model stays retryable. Every claude-cli failure names
  `subtype`, `is_error`, `safety_stops`, `num_turns` and the models, and
  the retry line keeps 300 characters of it (60 before).
- **`02_analyze.py --draws` reads the estimator's criterion key.** The
  analysis skeleton is shared by the model and the estimator skeleton
  and read `c1_accuracy`, the model's key; the estimator reports
  `c1_score`, so a fit's draws printed `c1_accuracy None`. Each measure
  skeleton names its key (`C1_VALUE_KEY`), the analysis reads that name
  and fails loud on a missing key. Found by the analysis audit of the
  cold fit probe on `3e9784c`.
- **finalize runs intent-check whenever the promise block declares an
  id.** The station asked the prose alone (`[C1]`); a protocol with three
  [[promise]] tables and `C1:` in the prose read "no intent ids
  registered" and passed, so neither the prose/block match nor the
  metrics keys were checked. Prose and block now register together
  (`promises.registered_ids`), for the intent station, the choice of the
  answering run and the declared-scopes station; the mismatch is the
  blocker intent-check already names. Found by the cold fit probe on
  `d549696`.
- **The estimator's `00_prepare.py --audit` prints the yields and no
  text profile.** The estimator skeleton (a fit, or an apply without a
  model) stamped the text prepare step, whose `--audit` calls
  `labkit.run.profile`; on numeric features it ended in `item m0 has no
  'text'`. The skeleton now stamps `prepare-estimator-script.py.template`:
  fields `id`, `features`, `gold` (the names `01_measure.py` reads),
  `--audit` the yield of every filter. The model skeleton keeps the
  profile.
- **A fit or an apply is stamped with its promise ids in the prose.**
  The shortened placeholder of the criterion lost the template's `[C…]`
  hint, and the cold fit probe wrote `C1:`. `labkit-init exp` now writes
  `[C1]`, `[A1]`, `[A2]` before the placeholders of the criterion, the
  admissibility condition and the null condition
  (`protocol_cuts.name_promise_ids`) — only the ids the stamped block
  declares, and only for a kind with a bar; a compute's prose names none.
  A field holding only the id and a placeholder (`[C1] <…>`) or the id
  alone is still open (`FieldLine.placeholder`), and `protocol-fill`
  keeps the stamped id when the value names none.
- **A generated result line written twice is a blocker.** `report-check`
  held the Recorded results line and the Limit lines through a dict of
  the protocol's fields, so of two lines with one label only the last
  was compared: a wrong Limit line above the record's correct one, or a
  retyped Recorded results below the generated one, passed
  (`result_render.render_gaps`; review 2026-10-22). Every line of a
  generated label is held now; a label written more than once is named,
  and the extra line is removed by hand (`--render` rewrites one and
  leaves the others).

### Changed

- **One lookup of a models.toml alias.** `repo.model_entry`, what the
  audit is shown of a bound validation's alias, looked the alias up with
  its own error text and search start; it is `llm.model_entry` now and
  reads the table as `llm` loads a spec (`llm_specs.alias_tables`), so a
  file shape refused for a run is refused with the same sentence here
  (audit 2026-10-23).

- **Where an area's code is has one spelling.** `scope_sha.area_files`
  (with `SCRIPT_GLOB`, `ANALYSIS_GLOB`) is read by the audit bundle, the
  producer/consumer split and the prompt check, which globbed
  `scripts/*.py` by hand (audit 2026-10-23); the one-home test holds it.

- **One reader turns JSONL lines into objects.** `jsonl.objects(text,
  where)` gives (line number, object) and names file and line for a line
  that is not JSON; `jsonl.data_rows` drops the `_meta` header
  (`jsonl.is_meta`). The leakage check, `recheck.rows_of`, the session
  log, the transcript reader and the usability recount parsed lines
  themselves, each with its own error sentence (audit 2026-10-23);
  `batch` keeps the one loop that is its own — a torn last line of an
  interrupted write is cut, not refused. Two deliberate peeks (the first
  record of a transcript, the first five lines of a data file) stay
  streamed and say so.

- **A run's directory and its metrics file have one spelling.**
  `runs.run_path(area, run_id)`, `runs.runs_path(area)` and
  `runs.metrics_path(run_dir)` replace about twenty hand-spelled
  `area / "runs" / id` and `run / "metrics.json"` (audit 2026-10-23); the
  one-home test refuses the next copy. The two remaining hand walks over
  `runs/` — the session record's and report-check's — go through
  `runs.run_dirs`; the session record finds an area's runs where its
  protocol is (`repo.repo_protocols`), not by a glob on the folder name.

- **The gates in order stand in one place, and every `--help` states the
  exit contract.** The order (protocol-check → code-check → preflight →
  preflight audit → runlog → finalize → analysis audit → review →
  report-check → undecided), what each holds, where the area tests run
  with which missing-test rule, and which hook runs it unasked is a table
  in `docs/architecture.md`, "The gates in order" (audit 2026-10-23, C3).
  `gate.EXIT_CONTRACT` is the one line every mechanical gate's `--help`
  ends with; report-check's `--help` names `--if-reported [--staged]`, the
  hooks' form parsed before argparse (C2). `labkit-audit` keeps exiting 1
  on a warning, by intent — its findings are a person's to decide — and
  says so (`audit.AUDIT_EXIT_CONTRACT`, C6). protocol-check's `--contract`
  help no longer breaks off mid-sentence.

- **"Is an audit finding still undecided" has one home.** Four gates
  walked the records for `open` findings themselves — preflight blocking
  any grade once frozen, finalize by grade, the hooks BLOCKERs only,
  runlog's start check preflight records only — and nothing said whether
  the four readings were meant (audit 2026-10-23, C1). They are:
  `findings.open_findings(records, mode=…)` is the walk, its docstring the
  table of the gates' rules side by side, and the gates grade what it
  returns; a change to one row is a change to that gate's rule. The
  one-home test holds the walk (`for … in ….open`).

- **A compute owes no bar at any tier, and is stamped so.** At `minutes`
  and `hours` a compute was still stamped with the success criterion, the
  admissibility condition, Model / tool, the null condition and three
  placeholder promise tables, and `protocol-check` owed those fields —
  against standard 0.22 (a compute owes its question). Since `finalize`
  holds the block to the prose, a compute that left the stamped tables was
  blocked by its own stamp. `protocol_cuts.bar_cut` now drops the fields a
  bar owes (`<!-- sb -->`) and the tables for a compute at every tier, and
  `protocol_check.owed` asks them of a fit or an apply only
  (`bar_owed`). A compute stamped earlier keeps its fields; nothing reads
  them as owed.
- **The release-check flow is explicit at its entry point.** `report_check`
  lists the declaration, registration/freeze, finalize, full-run check,
  analysis and rendered results, recomputation and decision reviews with
  their conditions. The `station_one` and `later_gaps` wrappers are gone;
  stages hand typed findings to the shared `Findings.take_all` collector.
  Check order, diagnostics and exit codes are unchanged. Its context
  documentation distinguishes the gate's shared inputs from the nested
  finalize and analysis script, which read their own inputs.

- **A report that cites a declared result owes its generated block.**
  `report-check --if-reported` (the stop, the pre-commit) now blocks a
  changed or staged citing report for every run it cites that a protocol
  declares as its result and whose block the report does not carry
  (`report_blocks.blocks_owed`); the sentence names the protocol as the
  report names it and the `protocol-fill <PROTOCOL> --into <REPORT>` that
  writes it. 0.103.0 warned once per report without a block. A cited run
  no protocol declares owes no block: the warning now says that nothing
  is declared there. `path_from_report` moved from `protocol_fill` to
  `report_blocks` (the gate names the path the same way). Why: fifth
  haiku round, all three labkit reports retyped the declared number in
  prose beside invented ones; the block is the one number a report shows
  that its sources hold.

### Added

- **A crashed run keeps why it broke off.** When the block of
  `runlog.run` raises, the run directory gets `failure.json` — the
  exception's type, message and time (`runs.write_failure`,
  `runs.read_failure`) — and `runlog --wait` names it beside CRASHED.
  Until now the reason stood on stderr alone; a claude-cli answer another
  model wrote ends a run this way. A failure to write the file is said on
  stderr and never masks the exception.
- **A fit probe for the usability harness.** `usability stage <dir> --task
  fit --data <train.csv>` stamps a `kind = "fit"` area at seconds with the
  estimator skeleton and plants the DILI molecules the operator hands in
  (columns `standardised_smiles`, `vDILIConcern`; the package ships no
  benchmark data) with a task sheet asking for the registered lane's
  out-of-fold accuracy under `c1_score`; the score reads it as a model's
  number (present, within [0, 1], the null lane reported). The first cold
  probe of the fit lane after standard 0.22.
- **`docs/workflow.md` and an executable count walkthrough.** The steps
  from a registered question to a kept number, one section each: the
  command, what it reads and changes, what must hold before it, what a
  clean exit means; the `minutes`/`hours` extras at their place; the
  decision review's conditional step. `docs/examples/count-walkthrough.sh
  <dir> [VENV]` walks them on the stamped count task (registration, run,
  finalize, the analysis record as a marked stand-in for the model call,
  adoption, report block, gate), then retypes a generated number in the
  report and in the protocol and shows the refusal each time;
  `tests/test_workflow_example.py` runs it. A cold reading probe answered
  the page's four acceptance questions rightly
  (`docs/usability/2026-10-22-workflow-reading-probe.md`); its stumbles are
  worked in, and the skeletons' hint after a run names what `--from-run`
  writes as the command does ("Recorded results, [result] run and the run
  entry", not "Answer, Result and Runs").
- **A decision review: `labkit-audit AREA --review [--record FILE]`.** A
  second, cold auditor gets every accepted finding of one analysis record
  whose effect is `stands`, with the person's reason, the protocol (the
  registration and the reported claim — Conclusion, Recorded results,
  Limit lines), the files the findings name as the record's auditor read
  them (the area snapshot, held to the record's `scope_sha`) and what the
  auditor was shown of the run (held to `shown_sha`), and answers per
  decision `upheld`, `rejected` or `insufficient` with one sentence
  (`decision-review.agent.md`, `gates/decision_review`). The verdicts are
  written beside the records as `audits/<minute>-review.toml`
  (`formats/reviews`), bound to the record, its code, its run as shown,
  the claim as judged (`claim_sha`: the Conclusion,
  `protocol_check.reported_claim`; the Recorded results and Limit lines
  are shown to the reviewer as they render and are bound through the
  record and the run) and each
  decision as it stood (`findings.decision_digest`): only `upheld`
  releases a `stands`; `rejected`, `insufficient`, a review of a decision
  since changed and one of a claim since rewritten do not. Every draw on
  one state counts (`reviews.contested`): once a review of the decision
  as decided and claimed now said `rejected` or `insufficient`, no later
  draw releases it, and `--review` refuses another draw on that state
  unless `--again` asks for one as a measurement (it never releases).
  After `rejected` the person decides again first (limits the claim,
  changes the effect, fixes the fault); a new audit does not by itself
  settle it. `--review` refuses while the Conclusion is a placeholder
  (the claim it judges; a review made before it goes stale when it is
  written), and `--record` takes a record's bare file name for
  `--review`, `--decide` and `--findings`, resolved under the area's
  `audits/` — both from the fresh round on 86e38bc (judge-2 paid a
  second review and was refused once on the name;
  `docs/usability/2026-10-22-sandbox-86e38bc.md`). Replayed on the fifth round (two passes, 1.77 USD) and every
  decision assessed from its sources (`docs/usability/2026-10-22-decision-review-*.md`). `report-check` names every `stands` of
  the covering records that no review upholds, with the review's state:
  a **blocker** for an accepted BLOCKER (a severe finding is not settled
  by a reason alone; `protocol-fill --from-run` refuses the adoption the
  same way), a warning for an accepted WARNING for now. A `--from-run`
  that passed before is refused when an accepted BLOCKER with `stands` has
  no upholding review. A report whose decision lines
  and closing counts disagree, or that decides on a finding not asked
  about, records nothing (exit 2); the review is refused when the code or
  the run is no longer what the record's auditor saw. Why: labkit-paper
  area 09, fifth haiku round — 28 findings, 15 accepted with no action,
  six with the reason "Finding noted"; of four findings at decision
  points, one was fixed.
- **The seconds release holds the registration to the commit of the first
  measurement.** `report-check` (station 1, where the lane owes the
  registration instead of the freeze) reads the oldest full run bound to
  the protocol (`answering_run.first_measurement`), the commit its record
  names (`runs.recorded_commit`) and the protocol as that commit holds it
  (`protocol_history.registration_in_commit`): the protocol not committed
  there, or the fields the lane owes not written there, blocks; outside a
  repository a warning, as the provenance station's. runlog's start gate
  reads the tree, which a line written a minute before the run passes;
  what stood before the number is what the commit holds. The fields are
  the lane's (`standard_contract.registration_fields`): the question, with
  a `[model]` table also criterion, admissibility condition and data
  profile. Why: labkit-paper area 09, fifth haiku round — none of the
  three labkit agents had committed criterion and admissibility condition
  before the first measurement.
- **finalize blocks on an audit record of a deleted run.** Station 8 now
  also holds every analysis record to the area's runs: a record naming a
  run that has no `runs/<id>/` any more is a blocker where the record
  stands (`findings.records_of_gone_runs`). A run an audit read is a kept
  run; the record is the evidence that it existed. Why: labkit-paper area
  09, fifth haiku round (labkit 0.102.0), t18 removed two measured runs
  with `rm -rf runs/…` after their analysis audits, `runs.tsv` still
  listed them, and finalize read the three records left behind as "every
  finding decided".

## 0.103.0 — 2026-10-22

### Breaking

- **Protocol standard 0.21 gives the two result fields distinct names.**
  The Summary's prose answer is `Conclusion` (formerly `Result`); the
  generated metrics, run id and limits note are `Recorded results`
  (formerly `Answer to the question`). `[result].run` still declares the
  reported result and must name the answering run. Templates, field checks,
  rendering, CLI guidance and the field guide use the new labels. Standard
  0.20 is refused rather than read through compatibility paths. labkit
  0.102.0 is the last published version reading the old labels; reproduce
  existing protocols with their original repo commit and package pin.
  For new work, stamp a fresh area. Internal helpers follow the vocabulary:
  `affected_protocols` replaces `reported_protocols` (selection includes
  explorations), `recorded_results_field` and `recorded_results_without_run`
  replace `answer_field` and `answer_without_run`; `Rendering.recorded_results`
  and `recorded_results_line` replace `Rendering.answer` and `answer_line`.

### Added

- **A report outside the protocol is held at the stop and the commit.**
  `report-check --if-reported` (the stop hook, the pre-commit) now also
  holds every changed or staged Markdown file among its paths that cites a
  run — `REPORT.md`, a results note; not a protocol, nothing under `runs/`
  or `data/`. Blockers: a generated result block that differs from what the
  protocol it names renders (Answer and Limit lines), a block showing a run
  its protocol no longer declares, a token that reads as a run id and names no run
  of the repo; the protocol declaring a cited run goes through the stations
  as well, so a report cannot show a result whose chain fails. A warning
  lists the numbers outside every block — no source is assigned to them;
  the check does not compare values, since an equal value elsewhere does
  not show where a number came from. The guarantee covers the block, never
  the prose beside it. Only the paths given are read: an old citation in
  a file nobody touched reopens nothing. New: `protocol-fill <PROTOCOL>
  --into <FILE>` writes the declared result into FILE as a generated block
  (`checks/report_blocks`); the block names its protocol (the path
  relative to the report), so after a new run is adopted the same command
  replaces it instead of adding a second; idempotent. A
  commit that passed before can now be refused when a staged report cites
  a run id that names no run. Why: labkit-paper area 09, fifth haiku round
  (labkit 0.102.0) — the protocol's Answer was held exactly while
  REPORT.md at the repository root stated counts and a median no run
  produced, and no gate read the file.

## 0.102.0 — 2026-10-21

### Breaking

- **The result section is held to equality with its rendering.** The
  Answer line and the Limit lines are generated — from the declared run's
  `metrics.json` and the covering analysis records (`checks/result_render`)
  — and report-check's limit station compares what the protocol says with
  that rendering exactly: a retyped number, a changed Limit line, a Limit
  line no covering record decides, a missing one — each a blocker that
  names the line, whatever the line says. Until now the station checked
  that each record's limit had a line opening with its effect and that
  the Answer carried the note's parts; a stale line from an older record
  passed. Consequences: a re-decided finding owes a write-back
  (`protocol-fill <PROTOCOL> --from-run <run_id> --force`, or `--render`);
  `--from-run` drops a Limit line of a record that covers the run no
  longer. The Result sentence and the rest of the prose stay the author's
  and are not compared. New: `protocol-fill --render` writes the result
  section again from its sources (Answer, Limit lines with stray ones
  dropped, the Prompt block where the constants read statically),
  idempotent; `protocol_fill.answer_line` and `accepted_limits` moved to
  `result_render.answer_line` and `limits_of`; `limit_lines` takes (label,
  value) pairs. 0.101.0 is the last version that checks the Limit lines by
  their opening words instead of their rendering.

- **The declaration makes the result due.** The after-run fields (Answer,
  Result, Raw output, Limits, Next step) and a frozen protocol's report
  fields are owed once the head declares `[result] run`
  (`protocol_check.result_due`); until now a run id in the prose Runs list
  — minus the words "prepare", "probe", "wegwerf", "trockenlauf" and "dry
  run" — stood for a measure run (`measure_runs`, `SETUP_RUN`, gone). A run
  listed and never adopted is an exploration and owes nothing; a declared
  one owes the fields the moment the declaration stands. `protocol-check`
  says "the head declares run <id> but <fields> empty". Phase 5 of the 1.0
  line (2026-10-21); the remaining prose readers — the label parser, the
  Answer field as a generated section, its warning, the Prompt block's
  drift check — stay at their grades, each decided
  (`tests/test_migration_bar.py`). 0.101.0 is the last version that reads
  a measure run from the prose Runs list. The bar after this phase:
  [docs/usability/2026-10-21-sandbox-42f0ec8.md](docs/usability/2026-10-21-sandbox-42f0ec8.md).

## 0.101.0 — 2026-10-21

### Breaking

- **Head format `standard = "0.20"`.** The three new tables (`[result]`,
  `[model]`, `[gate]`) are the format's change; a protocol that still says
  `"0.19"` is refused by `protocol_block.head` with the release that reads
  it ("use the labkit release the protocol was written for, or update the
  protocol") instead of being read as an exploration without a model —
  the silent misreading a review named (2026-10-21). To migrate a 0.19
  protocol: write `standard = "0.20"`, add `[model] alias` where a model
  is in the loop (and the arm tables where arms are compared), then
  `protocol-fill <PROTOCOL> --from-run <run_id> --force` where a number
  was reported.

- **The model in the loop, its arms and the gate labels are declared in
  the TOML head.** `labkit-init exp --model <alias>` writes `[model] alias`
  (a bare `--model` its placeholder, which `protocol-fill "model alias=…"`
  fills); `[model.arms.<arm>]` tables carry profile, fingerprint and alias
  of a compared arm; `[gate] labels` the labels the gate accepts
  (`protocol_block.model`, `declared_labels`). The table decides whether a
  model is named — for the seconds cut, the registration and `--report` —
  where the prose `Model / tool` line did, read with a pattern for "n/a",
  "none" and dashes; `finalize` holds the arm tables to the run where it
  parsed `Arm \`x\`: … @ … model=…` lines; the code-check bundle lists the
  declared labels beside the extracted comparisons, data for the agent,
  no gate compares them. The prose `Model / tool` field stays and asks for
  the instrument's sentence, not the alias; the `Gate labels (expected)`
  field is gone. Phase 4 of the 1.0 line; 0.100.0 is the last version that
  reads model, arms and labels from the prose. A protocol stamped before
  declares no model to this version: add `[model] alias = "<alias>"` to
  its head (and the arm tables where it compared arms). Gone:
  `protocol_check.model_named_in`, `_NO_MODEL`, `run_record_check.ARM_LINE`;
  `protocol_check.model_named` reads the head; `protocol_fill.HEAD_KEYS`
  replaces `HEAD_CHOICES` as the table of head placeholders.

- **The declaration that a number is reported is `[result] run` in the
  TOML head, not a run id in the Answer line.** `protocol-fill --from-run`
  writes a `[result]` table right after `[protocol]` naming the run
  (`protocol_block.declared_run`), then the Answer and Runs lines as before;
  `finalize`, `report-check`, the stop hook and the pre-commit read the
  head: a protocol without the table is an exploration and owes nothing;
  one whose table does not read — a typed `…_final`, a stray key — is a
  blocker where it stands, not a citation the gates chase; one naming
  another run than the one the checks hold blocks; none yet is a note with
  the adopt command, so a clean `finalize` before adoption stays clear. The
  template's `Answering run` line is gone (the head's comment says where the
  declaration stands), and `protocol-check`'s warning now reads "Answer
  written but the head declares no `[result] run`". Why: three cold
  judge probes carried the declaration in a prose line the gates parsed
  with 21 patterns, and a typed id there passed as a citation (labkit-paper
  area 08, 2026-10-21); phase 3 of the 1.0 line (`TODO.md`, "Reihenfolge").
  0.100.0 is the last version that reads the declaration from the prose.
  A protocol adopted under 0.100.0 declares nothing to this version: adopt
  it again with `protocol-fill <PROTOCOL> --from-run <run_id> --force`.
  Gone: `protocol_check.answering_run_field`, `answering_run_open`,
  `finalize.cited_runs`, `cited_run_gaps`, `cited_run_mismatch`,
  `answering_run_field_mismatch`; new: `protocol_block.declared_run`,
  `protocol_fill.fill_result_run`, `finalize.declared_run_gaps`,
  `declared_run_mismatch`, `undeclared_hint`; `report_check.Checked.cited`
  is `declared` and `declaration_gap`.

## 0.100.0 — 2026-10-21

### Breaking

- **With a model, the judged data profile is part of the registration.**
  The stamped `00_prepare.py --audit` prints the data profile per gold
  class (`labkit.run.profile`): items and mean words always; optionally,
  the cue words in `MARKERS` counted per class with the union of them,
  and the numeric fields in `CONFOUNDS` averaged. `None` prints "none
  counted", `()` prints "none applies", and a listed marker found in no
  item prints "checked, no hit". The profile is static evidence: an aid
  for the judgement and the audit, never proof that the data fit the
  question; a marker in one class only is a shortcut candidate, not proof
  the model uses it. The protocol has a new field, Data profile (must,
  model only), for the judgement of the data — what is owed is the
  judgement, not a word list. At `seconds` with a model, a
  full run is refused until that field is written; at minutes/hours the
  freeze holds it. Before, `audit()` was a stamped TODO, and two of three
  judge probes left it alone while the data carried a cue only one class
  had; the analysis audit found it after the run (sandbox, 2026-10-21). A
  protocol registered under 0.99.0 without the field writes it before its
  next full run.

- **An accepted BLOCKER owes its effect on the verdicts, an accepted
  WARNING may name one, and the reported protocol carries it.**
  `labkit-audit AREA --decide N accepted REASON` on a BLOCKER now needs
  `--effect stands` (the verdicts hold, read within it) or `--effect "C1
  not assessable"` (the run does not judge C1); on a WARNING the same
  `--effect` is optional, for a finding that limits what the result
  allows. The record stores it as `effect`, and its ids are held to the
  protocol's promises. `protocol-fill --from-run` writes each finding
  with an effect below the Answer as `Limit (audit <record> #N): <effect>
  — <reason>`, and the Answer carries one note counting them ("; subject
  to N recorded limitations (the Limit lines below)") and names each
  promise left "not assessable with this run (Limit (…))"; the number
  stays reported. report-check refuses a report whose covering analysis record
  holds an accepted BLOCKER without an effect, or a named effect without
  its Limit line or its note in the Answer. Before, a judge probe accepted a BLOCKER — its
  prompt asked more than the gold scores — and "C1 not met" passed with
  the limit only in the record (sandbox, 2026-10-21). Whether a limit
  is enough stays the reader's judgement. A reported protocol resting
  on a BLOCKER accepted under 0.99.0 is decided again with `--effect`
  and adopted again with `--from-run --force`.

- **`runlog.active()` returns `ActiveRun` objects, not dicts.** Each open
  run is `run_id`, `dir`, `state`, `alive`, `config` (its `RunConfig`, None
  for an unreadable record) and `error`; the record is no longer merged
  into the same dict as the computed state, where a record key could
  overwrite a computed one. A script that read `r["state"]` reads
  `r.state`; one that read a recorded field such as `r["script"]` reads
  `r.config.script`. 0.99.0 is the last release that returns dicts.

- **A run's config.json is read into `runs.RunConfig`.** `read_run_config`
  returns a frozen `RunConfig` instead of a dict: labkit's own fields typed
  (`cfg.run_kind`, `cfg.protocol.id`, `cfg.derived_from`, …), the
  experiment's settings free JSON in `cfg.config`, nested values (`config`,
  `data`, `promises`, `models_resolved`, `command`) handed out as fresh
  copies; `cfg.as_record()` gives the whole record as stored. The record
  is complete or unreadable: every field the writer writes must be present
  (missing is no null and no default — deleting `"unfrozen_ack": true` made
  an acknowledged run reportable), null only where the writer writes null
  (`derived_from`, `repeat_of`, `draw`, `audit_failed`, `cost_tier`,
  `promises`), and a key labkit does not write, a field of another type, a
  `protocol` table without both `id` and `path` or with more, or bytes that
  are no UTF-8 text make it unreadable. The experiment config keeps its
  key order. `runs.repeat_parent` is gone
  (`cfg.repeat_of`); `run_state(run_dir, alive)`, `unreportable` and
  `summarize` take the `RunConfig`; `answering_run.repeat_mismatch` takes the
  parent's `RunConfig` and the new run's keys. 0.99.0 is the last release
  that returns the dict.

- **`llm.complete(max_tokens=...)` is refused where a backend has no cap.**
  claude-cli has no token flag, and an explicit `max_tokens` was dropped
  without a word. `max_tokens` now defaults to `None`: ollama and openai
  still send 512 (`llm.DEFAULT_MAX_TOKENS`), claude-cli its own limit; a
  value given to a claude-cli alias raises `ValueError`, as a temperature
  does. `llm.takes_max_tokens(alias)` says which backends take a cap;
  `labkit-audit` asks it before giving a report 4096 tokens.

- **An analysis audit record names what it was shown of the run.** The
  record bound the run id only, so a `metrics.json` or output rows changed
  after the audit still read as audited. `labkit-audit --mode analysis`
  writes `shown_sha`, the digest of the rows' excerpts and the metrics.json
  the prompt showed (one snapshot for prompt and record), and report-check
  recomputes it for the answering run. An analysis record without
  `shown_sha` is no longer read: run the analysis audit again. 0.99.0 is the
  last release that reads it.

- **Runs declare their purpose through `run_kind`, not `long`.** Pass
  `run_kind="probe"` for an instrument check or `run_kind="measurement"`
  for the registered measurement; `run_kind="preparation"` preserves the
  separate data-preparation record. Only measurements can supply results.
  The default remains an instrument probe.
  Seconds retains data preparation but has no separate probe: a probe,
  including a template's `--probe`, is refused before work starts.
  Minutes/hours keeps
  the probe stage; only measurements undergo freeze/audit and detachment
  checks and can supply a reported result. Result release still requires
  finalize, a decided analysis audit and the recomputation check.
  Run schema 3 records the validated string as `run_kind`; missing or
  unknown kinds and schema 2 records are unreadable. No `long` argument or
  record fallback remains. 0.99.0 is the last release that reads the old
  record format and accepts `long`. Update scripts and raise their pin
  together; reproduce old runs with their original commit and pin.

- **The modules live in layer packages; imports name the package.** The
  layers of `docs/architecture.md` are folders now, and the package root
  holds only `__init__.py`, the packages and the shipped assets
  (`templates/`, `agents/`, `docs/`, read through `labkit.PACKAGE_DIR`):

  | Package | Modules |
  |---|---|
  | `labkit.formats` | `protocol_block`, `promises`, `protocol_check`, `standard_contract`, `runs`, `repo`, `scope_sha`, `rules`, `findings`, `console`, `gate` |
  | `labkit.run` | `runlog`, `batch`, `llm`, `endpoint_lease` |
  | `labkit.checks` | `intent_check`, `code_check`, `recheck`, `notes_check` |
  | `labkit.gates` | `preflight`, `finalize`, `report_check`, `claude_hooks`, `audit`, `install_hooks` |
  | `labkit.tools` | `protocol_fill`, `scaffold`, `repo_check`, `params`, `calltree` |
  | `labkit.probes` | `usability`, `agent_transcript`, `cold_reader`, `protocol_reading`, `code_navigation` |

  An experiment script writes `from labkit.run import runlog, batch, llm`,
  `from labkit.formats import promises, runs`, `from labkit.checks import
  recheck`; the templates `labkit-init` stamps do so. `python -m
  labkit.rules` is `python -m labkit.formats.rules`; the template
  `experiment-protocol.md.template` sits in `labkit/templates/`, the
  field guide in `labkit/docs/`, the audit agents' instructions in
  `labkit/agents/`. The console commands keep their names. 0.99.0 is the
  last version with the flat `from labkit import runlog`; a repo moves by
  rewriting its imports with its pin.
- **Eight large modules are split inside their layer; private names that
  crossed are public in their new module.** No behaviour changed.
  `runlog` keeps the run writer; `provenance` (git, environment, data,
  snapshots), `start_check` (binding, preparation, the refusals before
  mkdir) and `runlog_command` (the `runlog` command) moved out.
  `protocol_check` keeps the field catalogue; `protocol_history` (what git
  knows of a protocol) and `protocol_report` (the file report and the
  `protocol-check` command) moved out. `code_check` keeps the id and
  promise checks and the bundle; `code_scan`, `gate_label_scan`,
  `import_check` and `prompt_check` moved out. `usability` keeps the
  staging; `usability_score` and `usability_command` moved out. `runs`
  keeps reading a run directory; `answering_run` (which run answers,
  repeats, the same-second tie) moved out — the analyze skeleton calls
  `answering_run.draws`. `scaffold` keeps stamping; `protocol_cuts` (the
  template cut to a tier) moved out. `llm` keeps resolve, complete and the
  retries; `llm_backends` (the call per backend, the endpoint choice,
  `PromptTruncated`) moved out — `llm.BackendError` still resolves.
  `finalize` keeps its stations and the answering run's citation;
  `checks/run_record_check` (what a run's record must show) and
  `checks/readme_check` (placeholders, the route block) moved out. A script
  that imports only the public helpers is unaffected; one that reached
  into `runlog._git_state` finds `provenance.git_state`.
- **`report-check` is the release check at every cost tier.** At
  `cost = "seconds"` it exited 0 with "nothing owed here"; a probe's number
  written back there passed as a reported one. Now only station 1 (the
  freeze, the preflight audit) is skipped at seconds, and the rest holds as
  at minutes/hours: finalize clean — so the answering run is bound to this
  protocol and the answer cites it — and that run a full run (`long=True`,
  not acknowledged unfrozen; `runs.unreportable`), a decided analysis
  record of code, promises and that run (`findings.audit_coverage`),
  `02_analyze.py --check` passing. finalize's blockers are named in
  report-check's list ("run it to see them" was a round trip inside a
  hook); `finalize_area` takes a `Findings` collector for that. LAB-017 is
  read as: at seconds the one analysis audit is owed when the number is
  written back, which is its promotion. 0.99.0 is the last version that
  passes a seconds area unchecked.
- **The stop hook and the pre-commit run `report-check --if-reported`;
  `finalize --if-reported` is gone.** The declaration that a result is
  reported is the run_id in the protocol's "Answer to the question"
  (`protocol-fill --from-run` writes it, `finalize.cited_runs` reads it) —
  the binding already expressed the occasion, so nothing new is declared.
  Every protocol of an area a changed (stop) or staged (commit) path
  touches whose answer cites a run goes through the whole check above
  (`report_check.reported_protocols` — a script edited under a reported
  number reopens it, with the protocol untouched both hooks passed it,
  audit 2026-10-19); a protocol whose answer is still
  open owes nothing, so an exploration ends with "no reported result",
  probes in `runs/` or not. Third haiku round on 0.99.0 (labkit-paper
  area 09): t3 and t5 reported a probe's number and no agent called
  report-check; a gate the agent must call is no gate. Reinstall the hooks
  (`labkit-hooks install`): the pre-commit is stamped anew. An answer
  written without a run_id is neither a reported result nor an open field:
  `protocol-check` warns (`answer_without_run`, static evidence — the hint
  Max asked for where the declaration is not unambiguous), the gates stay
  silent. The shipped standard's LAB-011 paragraph and the stamped
  `AGENTS.md` lanes say so.
- **`protocol-fill --from-run` is the one path by which a number becomes
  the result.** It writes the Answer, Answering run and Runs lines
  as before, then runs `report-check` on the written protocol and puts the
  file back as it was on a blocker (`protocol_fill.adopt`). Writing the
  number back declares it reported; the declaration is not what makes it
  sound, the check is — a declaration the check refuses is no weaker kind
  of result, it is none. So every result adopted this way has passed every
  check labkit prescribes, and the hooks hold a hand-written or later-changed
  answer to the same; a provisional number stays a sketch in `runs/` and
  `output/`. Until 0.99.0 `--from-run` wrote unconditionally.
- **Without `--model`, `labkit-init exp` at minutes/hours stamps the
  estimator skeleton** (until 0.99.0: the prompt skeleton with
  `TODO-alias`). A bare `--model` still stamps the prompt skeleton; at
  seconds without a model the counting skeleton stays.
- **The check is one command at every tier: `scripts/02_analyze.py
  --check`.** The counting skeleton (`labkit-init exp --cost seconds`
  without a model) stamps `02_analyze.py` beside `01_measure.py`
  (`analyze-quick-script.py.template`): it loads the measure script and
  holds metrics.json and the protocol's Answer line to the kept rows
  through `recheck.holds` — the one recheck logic, no second formula.
  Until 0.99.0 the count carried the check inside `01_measure.py --check`
  and stamped no `02_analyze.py`; report-check's station 4 demanded the
  analysis script and refused every correct count, so `protocol-fill
  --from-run` never adopted one (audit 2026-10-19). Now station 4, the
  stop hook, the pre-commit, the README route and the stamped `AGENTS.md`
  name the same command for every skeleton, and the standard's own
  wording (LAB-041 Generate numbers, don't retype them: one analysis
  script per area) holds at seconds as well. An area stamped at seconds
  by 0.99.0 or earlier owes the script: the gap names the template to
  stamp beside its measure script. A check that prints a byte no codec
  reads is a named gap, not a traceback.
- **An import through `lib`/`src` stamps the root's `__init__.py`.**
  `from lib import x` runs `lib/__init__.py` first, and the audit stamp
  left it out. In a repo with such a file every area that imports through
  the root's name has a new stamp: its audit line no longer matches and
  owes a new audit (`labkit-audit`).
- **The stamped pre-commit changed; `labkit-hooks check` names it stale
  until `labkit-hooks install`.** It hands every staged path to
  report-check and the undecided gate, deletions included (`--no-renames`),
  and refuses the commit by name when `.venv/bin/report-check` or
  `.venv/bin/claude-hook` is missing — before, both gates were skipped in
  silence.
- **`protocol_check`, `runs`, `usability`: ten shared names are public.**
  `HTML_COMMENT` (was `_MARKER`), `DASHES_ONLY` (`_DASHES`),
  `STAMPED_ITEM`, `in_cut`, `field_label` (`_label`), `model_named_in`
  (`_model_named`), `runs.read_run_dir` (`_run_dir`),
  `usability.read_answer` (`_answer_text`), `read_probe`, `sidecar`.

### Added

- **Probes share less, and the score shows what they shared.** `usability
  stage` gives each probe its own `.tmp/` (git-ignored) and its prompt
  says temporary files go there — never `/tmp`, a harness scratchpad or
  anywhere outside the probe; an editable staging labkit is refused when
  the probe's venv is built (it would install from GitHub at HEAD, not the
  working tree) and warned when `--venv` links one (the probe would follow
  the working tree). `usability score` lists the paths a probe used
  outside its directory, its own files and its venv
  (`agent_transcript.outside_paths`, static evidence). judge-2 of
  2026-10-20 read an earlier probe's `/tmp` file and wrote into the
  operator's scratchpad; a subagent inherits the operator's environment,
  so no per-probe TMPDIR can be set for it.

- **`labkit-audit AREA --decide N STATUS REASON` stores a decision on a
  finding.** The person gives status and reason explicitly; the command
  checks the number, the status and the owed reason, writes both as TOML
  strings into finding N of the newest record (or `--record FILE`), reads
  the result back — only that finding may change — and replaces the file
  whole. It decides nothing. Editing the file by hand stays possible. Two
  count probes of 2026-10-20 broke a record with a hand-written reason;
  the reason-form hint eased the repair but did not prevent it.
  `labkit-audit` now takes `--mode` or `--decide`, exactly one.

- **`standard_contract` — one home for what each tier owes, of which run,
  at which occasion.** The obligations the standard puts on a number were
  spelled by every component for itself (`head.cost == "seconds"` in
  seven modules, the registration's labels in one, the check's script in
  two), and the audit of 2026-10-19 found them disagreeing. The module
  states them once, as data read off facts a caller holds: the lane of a
  tier (`lane`: freeze or registration, the audits, the cut, the
  foreground, the provenance check; the release's freeze follows it), the
  skeleton an area gets (`skeleton`) and the one check every skeleton
  stamps (`CHECK_SCRIPT`, `check_command`). It reads no file, runs nothing, writes nothing; the
  checks stay with their modules, the contract says when each is due.
  Every consumer reads it (scaffold, report-check, protocol-check,
  runlog, preflight, finalize, the hooks, audit, code-check); a tier
  compared by hand outside the contract is a copy the one-home test
  names, in labkit and in the stamped script templates (the model
  skeleton's test reads `lane(cost).probe_allowed`). The usability
  probe's `scaffold sha` pins the contract and every template a skeleton
  stamps (it missed the counting skeleton's `02_analyze.py`). `protocol-check --contract` prints the contract by tier and
  occasion (`describe`). No rule changed: the table is the standard's own
  (LAB-017, LAB-003, LAB-015, LAB-050, LAB-041), held to the template's
  labels and the shipped templates by its tests. Two core modules
  (`runlog`, `code_check`) import it where they had copied the rule; the
  architecture test records the crossing by name.
- **Every skeleton end to end on the real chain** (`tests/test_end_to_end.py`):
  the count at seconds, the prompt skeleton at seconds with the model
  faked, the estimator at minutes through the freeze — stamped, filled,
  registered, run under the interpreter, held by finalize, audited,
  adopted, held again by the stop hook and the pre-commit. The four
  findings of the 2026-10-19 audit are pinned there, not on fixtures.
- **A report field written before any run is named.** `protocol-check`
  warns per report field (Did, Outcome, Result, Rival check, …) filled
  while "Answering run" is still the stamp's and no completed run is bound
  to the protocol (`written_before_run`); `n/a — …` claims nothing. Exact
  in what it says (no run exists), silent on whether the text claims one:
  Sonnet t18 (labkit-paper area 09, 2026-10-16) described a grid run that
  `runs/` never held (plan P, B1).
- **A registered constant no sentence names and no scope file reads is
  named.** `promises.unmentioned_constants`, printed by `protocol-check` as
  a warning (static evidence, never a blocker): the stamp's `margin`,
  `max_empty` and `null_band_items` stood under three Haiku protocols whose
  sentences never used them, one re-read as a threshold (plan P, C3).
  `promises.scope_sources` is the one resolution of a declared scope that
  `declared_scope_sha` and this check share.
- **The estimator skeleton.** `measure-estimator-script.py.template` and
  `test-estimator.py.template`: the instrument is an estimator (fit,
  predict) in `make_estimator()`, scored out of fold over the labelled
  items; the null lane fits labels permuted inside each fitting fold; the
  test lane predicts the unlabelled split and is never scored (a withheld
  label stored as 0 or -999 is no label — the prepare step writes null);
  [C1] registered score ≥ null score + `margin`, [A1] at most `max_empty`
  items without a prediction, [A2] the null lane within `null_band` of a
  derived chance (`chance_of`); accuracy, r2 and auc in the stdlib, exact
  where the data is; `--probe` runs a reduced estimator, `--seed` a run of
  its own. The stamped protocol answers the model-shaped fields
  (`scaffold.estimator_placeholders`) and carries the promise sentences in
  the estimator's words; the area's test checks the resolution on
  synthetic rows without any estimator library. Both measure skeletons
  expose `answer_of(row)` for `02_analyze.py --draws`. Evidence: nine of
  nine pilot attempts (labkit-paper area 09, 2026-10-16) were classical ML
  and got the prompt skeleton; three agents rebuilt it, one kept its
  leftovers (plan P, C2).

### Fixed

- **The stamped prepare run records its raw file.** `00_prepare.py` passes
  `data={"source": SOURCE}` to `runlog.run`, so the run holds the raw
  file's path, sha256 and row count; the stamp's own comment promised it
  ("record sha256 via runlog data=") and the call passed none — the
  analysis audit of a finished judge protocol found the prepare run
  without it (2026-10-21). A `build()` that reads several files lists each
  under its own key.

- **`protocol-fill` lists and sets the head's `cost` as it does `type`.**
  `labkit-init exp` without `--cost` leaves `cost = "<seconds | minutes |
  hours>"` in the TOML head; `--list` named only `type` among the head's
  fields, and the hook's "MISSING (must): [protocol] cost" sent the agent
  into the head by hand. `protocol-fill <PROTOCOL> cost=seconds` sets it,
  held to the three tiers; `--list` names both open choices first.
  `head_type_open`/`fill_head_type` are `head_open(text, key)` and
  `fill_head(text, key, value)`.

- **A dataset header still reading the stamp's `TODO` is refused.**
  `batch.write_dataset` raises ValueError naming `about` or the legend
  value (`fields['gold']`) that still starts with `TODO`, and writes
  nothing; the prepare template stamps both as `TODO: …`, and the header
  — what a reader opens first — went into the frozen dataset unchanged
  (review, 2026-10-21). A prepare script that kept the stamp fills the two
  lines and runs again.

- **A field that still holds the stamp's phrase is a placeholder, whatever
  stands around it.** `protocol-check`, `protocol-fill --list` and the
  gates read a value as unfilled when it holds one of the template's own
  `<…>` phrases (two words or more, whitespace collapsed:
  `protocol_check.stamp_placeholders`), not only when the whole value is
  `<…>`. An alias written before the Model / tool arm lines left the
  stamp's `<two arms (profiles) compared? …>` in the field, and it read as
  filled (sandbox, 2026-10-21). A one-word `<alias>` and a placeholder an
  author coins in their own prose stay unrecognised; `<10% unparsed` stays
  content. The template's path has one home, `protocol_check.PROTOCOL_TEMPLATE`.

- **The Limit lines stand in record order.** `--from-run` inserted each
  one right below the Answer, so three limits read #3, #2, #1; all three
  audits of the finished judge protocols named it (2026-10-21). Each now
  goes below the Limit lines already there.

- **A data-profile marker padded with spaces is refused.** Two cold
  agents wrote `" so "` to keep the marker out of longer words. The
  whole-word match then needed a non-word character outside each space,
  so `…cut, so the…` went uncounted and the profile showed 5/6 where
  6/6 was true (sandbox, 2026-10-21). Markers match as whole words
  already. `profile.profile` now refuses a padded marker and names the
  form to write, and the stamped `MARKERS` comment says so.

- **A cited run id must name a run of the area.** The gates read a
  citation only in the exact shape runlog writes, so an Answer that cited
  a typed `(run 2026-10-21T12-48-00_final)` counted as citing nothing:
  the stop hook and the pre-commit skipped the protocol, and the commit
  went through (labkit-paper area 08, 2026-10-21). Every token that reads
  as a run id (`runs.RUN_ID_LIKE`) is now a citation, and finalize, and
  report-check through it, block each one that is not in runlog's shape
  or has no `runs/<id>/` in the area.

- **Raw output is listed as an after-run field, and `--from-run` names
  it.** `protocol-fill --list` listed Raw output among the fields owed
  before the run. Two of three cold judge agents filled it at
  registration: one with "filled after the run", which `--from-run` then
  could not overwrite without `--force`, and one only after the post hook
  asked for it (sandbox, 2026-10-21). `--list` now sets the after-run
  fields the author writes (Raw output, and Limits and Next step on the
  full form) apart, under their own line. After an adopted write-back,
  `--from-run` names those still open together with the run's output
  files. It does not write Raw output: which prompt+answer pair shows a
  finding is a choice no run record makes.

- **`labkit-audit`'s decision list survives a pipe, and can be shown
  again without a new audit.** The list went to stderr while the report
  went to buffered stdout; in a pipe it came out first, and `2>&1 | tail`
  cut it off — one sandbox agent re-ran the paid audit only to see it,
  which wrote a second record and doubled its decisions (judge probes,
  2026-10-21). The list now comes last, on stdout, after the report.
  `labkit-audit AREA --findings [--record FILE]` shows a record's list
  (the newest by default) with no model call and no new record;
  `--mode`, `--decide` and `--findings` take exactly one.

- **The standard states the count's exemption.** A plain count at
  `seconds` whose prose names no `[C]`/`[A]`/`[B]` id owes no promise
  table and no success criterion — so the code has decided since 0.87.1
  (`promises.promise_tables_owed`), while the standard the auditor reads
  and `docs/promise-block.md` said the tables are owed at `seconds`
  always; an analysis audit asked a count for a criterion (sandbox probe,
  2026-10-21). Both now say it, with what stays owed: the `[protocol]`
  head and the release of the number. A test holds code, the auditor's
  excerpt and the contract together.

- **The count skeleton names every blank it stamps.** Its docstring said
  "the constants and the three TODOs" while `INPUTS` was a fourth place to
  fill, and an agent left its TODO behind (sandbox probe, 2026-10-21). It
  now names the four constants and the three functions; a test holds the
  list to the TODOs the template carries.
- **The count skeleton reads its items under the frozen `INPUTS`.** It
  froze `INPUTS` while every cold agent took each case's directory from a
  path the record named; the number followed a value the run did not
  freeze, and the analysis audit warned in each of three sandbox probes
  (2026-10-21). The stamped `01_measure.py` now has `input_dir(record,
  id)`: the directory under `INPUTS`, and a refusal for a record that
  names another path; `rows()` says to use it. Areas stamped before keep
  their script.

- **`labkit-audit` lists what there is to decide, numbered from the
  record.** After recording it prints the record's path and each stored
  finding with the number `--decide` takes and the command that decides it
  (`--record` named), then the auditor's READ lines apart — printed, not
  recorded, nothing to decide — or "no findings to decide". The numbers
  come from the stored record, not from the model's text: five of six
  sandbox probes (2026-10-21) numbered the printed lines, READ hints
  included, and ten `--decide` calls named findings the record does not
  hold.

- **`usability score` takes a transcript whose working directory is the
  probe.** It refused every transcript that named the probe's path in no
  call; an agent whose shell starts in the probe needs no `cd` and may
  name none (count-2 in the sandbox, 2026-10-21). A record's `cwd` equal
  to the probe now proves it as well; another one without a mention is
  still refused.
- **`usability score` reads a Claude Code 2.1.285 transcript.** That
  version writes session bookkeeping records without a timestamp
  (`atis-latch`, `last-prompt`, `cost-state`), and the reader refused the
  whole transcript. A record without timestamp and message is skipped now;
  a message without a timestamp is still refused.

- **A count stamped at `seconds` closes its TOML block.** The cut removed
  the promise tables with a pattern that took the block's closing fence
  along: every such protocol ended inside its ```toml block (parsed all
  the same, raised by the audit in every count probe of 2026-10-20). The
  tables are now removed by the block's structure (`protocol_cuts.
  without_promise_tables`: the fence walker, then table headers), read
  back, and refused unless `[protocol]` is unchanged and the block closed.
  A test stamps a lab at every tier, with and without a model, and holds
  every fence of every stamped Markdown file closed. Areas stamped before
  keep the open block; closing it by hand is safe.
- **`labkit-init exp` reads back the head it stamped.** The id and the
  tier are written by replacing template tokens; a token the template no
  longer carried left the placeholder without a word. The stamp is now
  refused unless the head carries an id and the asked tier. The blank line
  the stamp puts before a `## ` heading is no longer put inside a fenced
  block (a verbatim prompt with a `##` line).

- **The printed `protocol-fill … --from-run` line names the protocol's
  path.** The measure scripts, `labkit-init exp`, `protocol-check` and
  `--check` printed the bare file name, which failed "no such file" from
  the repo root, where agents run the scripts (count probe, 2026-10-20).
  They now print `repo.adopt_command`: the protocol as the working
  directory reaches it. So do `finalize`'s "Answering run not written yet"
  and `protocol-check`'s "written before any run", which named no protocol
  at all (`protocol-fill --from-run <run>` exits 2); the run-less hint of
  `protocol-check` names `<PROTOCOL>`. Stamped measure scripts import it;
  areas stamped before keep the old line.
- **`code-check` at `seconds` no longer calls the protocol's open fields
  not owed.** Its closing line read "schema, gate labels, placeholders: not
  checked — not owed at cost seconds"; only the agent's review of schema
  and gate labels is not owed there. The line now says so and points at
  `protocol-fill <PROTOCOL> --list` for the fields the pre-commit holds
  (judge probe, 2026-10-20).
- **`protocol-fill` lists and fills the promise sentences.** `--list` names
  each [[promise]] sentence still holding the stamp's `<…>` as `<id>
  sentence`, after the head's `type`; `"C1 sentence=..."` fills it, in the
  same one call as the prose fields, written as a TOML string and read
  back. Every judge probe of 2026-10-20 found the sentences only by
  reading the file, and the pre-commit refused one that was left open.
  Every valid spelling of the id is read (a comment after it, single
  quotes, a quoted key); a sentence the table walk cannot place is listed
  with `?` for its line, never left out. `<word> sentence` is a promise's
  only when the word is a promise id — a prose field "Key sentence" stays
  a prose field — and `--line` is refused for it. `--list` on a protocol
  whose promise block is malformed now prints the block's error and exits
  1 instead of listing the prose fields (it used to exit 0; with two TOML
  blocks it raised a traceback).
- **Every TOML string labkit writes reads back** (`protocol_block.toml_string`,
  the one writer for findings files and promise sentences). json left DEL,
  U+0085, U+2028 and U+2029 raw: a finding text from the auditor or a
  sentence carrying one of them made the file unreadable. They are escaped
  now; a lone surrogate is refused by name.
- **An area name two areas carry is refused with both.** `x` for
  `01-x` and `02-x` was refused as "no such area … give its name" by every
  command that takes an area; `repo.area_path` now raises `AmbiguousArea`
  naming the candidates, and `code-check`, `finalize`, `preflight`,
  `labkit-params`, `runlog`, `labkit-audit` and `report-check` refuse with
  it on stderr, exit 2. A unique name and a missing one behave as before
  (review of the probe fixes, 2026-10-20).
- **`labkit-audit` and `report-check` take the area's name.** `01-<name>`
  or `<name>`, as `labkit-init exp` prints it, resolves as it already did
  for `code-check`, `finalize`, `preflight`, `runlog` and `params`; both
  took a plain path and refused the name with a sentence suggesting it
  (four of seven cold probes, 2026-10-20, one paid audit run twice).
- **`usability log TAG TEXT --log FILE -- CMD` writes to FILE and runs
  CMD.** In the order the task sheet stamps, the trailing command argument
  swallowed `--log FILE`: the line went to `./log.md` and `--log` ran as
  the command, a traceback (all three count probes, 2026-10-20). The
  command is now everything after the first `--`; `--log` may stand
  anywhere before it, and stray words without `--` are refused under the
  log usage, saying the command goes after `--`. Two lines that ran before
  no longer do: a TEXT beginning with `-` and a TEXT that is `--` itself
  (`log read -- -x -- true` is refused, "required: text").
- **A server reply of the wrong shape fails by name.** The ollama, openai
  and claude-cli parsers read replies field by field without checking
  them: a missing or mistyped field raised KeyError, AttributeError or
  TypeError deep in the parser, an HTML error page or a reply cut in
  transit a JSONDecodeError (a ValueError, which labkit-audit read as an
  area it could not stamp), and a count sent as text was stored as a
  token number. One reading (`llm_backends.json_reply`, `reply_field`)
  now holds every reply: each departure is a `ReplyError` naming the
  backend, the route and the field. It is a `BackendError`, so it is
  retried and, in labkit-audit, recorded as an audit that could not run.
- **An audit's counts are non-negative.** `blockers = -1` could be written,
  was read, and passed the coverage check. Writer and reader now hold
  `blockers`, `warnings` and `notes` to one rule (`findings.count_problem`):
  a non-negative integer.
- **Audit records and failed attempts are read in the order written.**
  Sorted by name, a minute's second and third file (`-2`, `-3`) came before
  its first, and the newest failed attempt — what a run's acknowledgement
  of an unavailable audit names — was the oldest. They now sort by minute
  and then by that number; a file under `audits/` of another name is
  refused by name instead of placed somewhere.
- **An audit whose verdict and finding lines disagree is no audit.** A
  BLOCKER line followed by "Correction: no finding" and a zero verdict
  exited 0, while the record kept the blocker open and the next gate
  refused the coverage. `labkit-audit` now records only a report whose
  verdict counts exactly its BLOCKER and WARNING lines; otherwise it exits
  2 and writes nothing. The auditor's prompt says a written finding line
  counts.
- **A probe answers the items as they are now.** The judge skeleton's
  `--probe` resumed its `_probe.jsonl`: an item edited since the last probe
  made no new call and showed its old answer, beside rows of earlier
  probes. Both skeletons now start each probe in a fresh file (the judge's
  as `probe(cfg, items, n)`); the estimator's no longer refuses a re-probe
  after a data edit. Existing `01_measure.py` files keep the old probe —
  re-stamp, or delete the probe file before each probe.
- **Ids compare as the file stores them.** The ledger, the resume, the
  status and the duplicate count held ids in Python sets and dicts, where
  `True == 1`: an output row with id `true` balanced an input id `1`, and a
  resume skipped item 1. Ids now compare by their stored JSON
  (`runs.as_stored`): `1`, `true`, `1.0` and `"1"` are four ids. Any JSON
  value stays a valid id. `Store.done_ids()` returns a list in file order
  instead of a set, which could not hold `1` and `true` apart.
- **A Store's instrument is fixed when the Store is built.** It was copied
  one level deep: a caller changing an inner dict afterwards gave later
  rows another `_instrument` than earlier ones, while the resume compared
  against the first. The comparison and every row's stamp now come from
  one snapshot taken at construction; `Store.instrument` returns a copy of
  it.
- **`derived_from` names a run, never a path.** `./<own run>` slipped
  past the loop check by its spelling and hung every lineage reader;
  `../../<elsewhere>` was accepted as a parent outside the area. runlog
  refuses such a value at the start, a config.json holding one is
  unreadable (`RunConfigError`, like a damaged `repeat_of`), and the walk
  compares resolved paths. A record written with such a value no longer
  reads; it was never a run of this area's chain.
- **`runlog <area>` names each finished run's kind.** Preparation, probe
  and measurement all read "fresh run of the script"; each line now starts
  with its `run_kind` (`RunSummary.run_kind`), and the listing reads each
  run's config.json once instead of three times.
- **A parser counts as tested only when a test calls it.** code-check's
  parser-fixture check (a blocker) passed when the parser's name stood
  anywhere in a test file — a comment, a string, an import. It now looks
  for a call in the syntax tree (`parse_x(…)`, `measure.parse_x(…)`); a
  test file that cannot be parsed is said. Whether the test asserts on the
  result is still not checked.
- **protocol-check says OK only when it found nothing.** A doubled id, an
  audit line that no longer covers the code, a lowered cost tier or an
  answer without a run stood above "OK — must fields filled"; the OK now
  needs all of them absent too.
- **A file name no longer grades a finding.** protocol-check and preflight
  read the grade of a protocol-id finding from its text, which carries the
  path: in `PROTOCOL-WARNING.md` a doubled id passed as a warning. The id
  findings now carry their grade as data (`GateFinding`), and `grade_of`
  reads only a line's first word (`BLOCKER · …`, `WARNING · …`).
- **A run's `script_sha` is the hash of the script copy it keeps.** The
  record hashed a second read of the script after copying it; a save in
  between left a `script-source.py` the recorded hash did not match. Copy
  and hash now come from the same bytes.
- **The pre-run hook no longer takes a mention for a run.** It cut a shell
  line at whitespace and read a heredoc's body and a quoted `-c` string as
  commands: writing a note that names `scripts/01_measure.py`, or a
  `python -c '…; python scripts/01_measure.py'`, was gated as running it.
  The hook now reads the line as the transcript reader does
  (`shell.segments`: quote-aware, heredoc bodies cut); running the script
  is held as before.
- **The stamped scripts pair each item with exactly one answer.** The
  judge and estimator skeletons (and the explore notebook) zip items and
  answers with `strict=True`: a `fit_predict` or a model batch that
  returns fewer answers than items raises `ValueError` instead of
  dropping the unanswered items from the output. Re-stamp or edit
  existing `01_measure.py` files by hand; the check is the length only,
  not which item an answer belongs to.
- **The stamped scripts hold their rows to the source before a number.**
  `evaluate()` in the judge and estimator skeletons balances the output
  file first (`balance`, `batch.Store.ledger`) and stops with every gap
  named: a missing, doubled or stray row, or a row made from an item as it
  was before an edit. The judge stamps each job with `item_sha`
  (`batch.content_sha` of the item), so a resumed run that skipped an
  edited item stops here; the estimator's instrument carries `items_sha`,
  since an edited item changes every fit, and a resume refuses the file.
  The complete, unchanged file passes, and its counts are counts of the
  source. Counted from rows alone, six of twelve items could be missing
  and every check still passed. `evaluate(out, cfg)` became
  `evaluate(out, cfg, jobs)` (judge) and `evaluate(out, cfg, items)`
  (estimator); re-stamp, or copy `balance` into an existing script.
- **Resume compares the instrument as JSON stores it.** `Store.pending`
  uses `runs.as_stored`: `true` differs from `1`, while a tuple and its
  stored list representation describe the same instrument. An instrument
  JSON cannot hold raises `TypeError` when the `Store` is built, not at the
  first append. `Store.ledger(expect=...)` compares the same way: a row
  stored with `1` is stale against an expected `True`.
- **Every lineage reader uses one fully validated chain.**
  `answering_run.lineage` checks every ancestor, including those beyond
  the first recorded model. Missing parents and cycles are errors in
  model provenance, parameter display and row-provenance checks alike;
  finalize blocks on a broken chain instead of ending the walk silently.
- **A declared scope file reopens its area even without an import.** The
  stop hook and staged release check include files named in promises,
  including data or rubrics outside `lib/` and `src/`. A damaged promise
  block conservatively marks its area touched without preventing the
  independent selection of other areas.
- **An audit prompt and its stamp use one snapshot.** The stamp includes
  declared scope files; every stamped file is shown to the auditor, and
  a changed file listing between collection and snapshot refuses the
  call. Audit records use exclusive creation instead of overwriting a
  previous record with the same name.
- **Malformed metadata and model tables fail at their boundaries.** Owned
  run-record tables are objects or null, never silently read as empty
  objects when damaged. `models.toml` validates its outer tables and the
  selected alias before backend-specific parsing, with field-named errors.
- **Scope and result comparisons refuse ambiguous evidence.** A function
  scope rejects a name bound more than once. Recomputed values use the
  shared type-strict stored comparison; cited numbers must be whole
  tokens, including the correct sign and exponent.

- **Gates and records found in the review of 2026-10-19.** preflight's
  code station runs code-check's whole list (parser fixtures and prompt
  drift were skipped). `llm.resolve` hands out deep copies and freezes each
  alias once under a lock. A repeat is compared as config.json stores it
  (a tuple config no longer refuses its identical repeat; `1` is not
  `true`, a missing key not `null`). The stop hook and the commit reopen an
  area when a file in it is deleted or moved away, and when a shared helper
  under `lib/`/`src/` its code imports changes (`scope_sha.areas_touched`);
  at the commit the protocols are read from the index. A run continues
  only the rows its output held at `r.output()`; rows of another run
  written meanwhile block at finalize. `batch.Store` completes a last line
  without newline before appending, and a failed open releases its lock.
  `labkit-hooks install` keeps a foreign command that shares an entry with
  a labkit hook.

- **`protocol-fill --from-run` puts the protocol back on any failed check.**
  `adopt` restored the file only on report-check's blocker exit; an
  exception out of the check left the unchecked declaration standing. Now
  every unsuccessful end restores it, and the exception is re-raised.
- **The pre-commit holds the commit, not the working tree.** `report-check
  --if-reported` read the protocol from disk: a reported answer staged,
  then reopened in the tree, passed the commit with the answer in it
  (audit 2026-10-19). The pre-commit now runs `--if-reported --staged`:
  the answer is read from the index (`report_check.index_text` — an answer
  only the tree carries is not in the commit), and an area whose tree
  differs from the index (a file modified and not staged, or untracked;
  `tree_differs`) is a blocker before any station runs, since the
  stations read the tree and the commit holds the index. Reinstall the
  hooks (`labkit-hooks install`).
- **runlog holds measurements at seconds to the registration.** A
  measurement under registered ids requires its promise tables and written
  question, criterion and admissibility condition before the run directory
  exists. `run_kind="preparation"` preserves the separate data-preparation
  record; a separate probe is refused at seconds. The registration check
  and the declared purpose no longer classify the same run differently.
- **`labkit-init exp` prints the lane with its gates.** At minutes/hours
  the next steps skipped the preflight and its audit, the analysis audit
  and the adoption while the stamped `AGENTS.md` named them; an agent
  following the console met the refusal at the run's start. The steps read
  the contract (`scaffold.next_steps`): the preflight where the lane owes
  the freeze, each audit where `Lane.audits` names it, `code-check` after
  every change, the adoption at the end of every lane.
- **report-check's station 3 reads `Lane.audits`.** The release read only
  the freeze off the contract and owed the analysis audit on its own; now
  `later_gaps` takes the lane and reads both. No behaviour changes: every
  lane of the standard owes the analysis audit. `docs/architecture.md`
  named a `standard_contract.release` that never existed; the home of the
  release's obligations is `lane` (`freeze`, `audits`).

### Changed

- **A code check's finding is data up to the console: `gate.coded`.** The
  nine checks behind `code-check` and preflight's code station (intent ids,
  the promise block, declared scopes and keys, `[A]` reads, constant
  copies, parser fixtures, prompt drift, stamp coverage, unreadable source)
  and the audit's tier note returned `BLOCKER · …` strings, and the gate
  read the grade back from the first word (`gate.grade_of`). Each now
  returns a `GateFinding` with grade, where, text, rule and fix as fields;
  the gates `take` it. `grade_of` and `Findings.add` are gone, and an
  ungraded finding is refused when it is built. The lines read as before,
  except that the parser-fixture and prompt-drift blockers name their rule
  in its own place instead of in a dated parenthesis.

- **What an analysis audit is held to has one home below the gates:
  `labkit.checks.audit_binding`.** The run choice (`audited_run`), the
  snapshot of what the audit was shown (`run_shown`, `run_rows`,
  `rows_excerpt`) and the question which records cover the area now
  (`covering_analysis`, `analysis_now`) lived in `gates/audit` and
  `gates/report_check`, so `protocol-fill --from-run` imported a gate to
  ask it and moving the selection into `formats` would have imported
  upward. `labkit-audit`, report-check and `--from-run` now ask the one
  module; `AuditError` moved with it. Behaviour unchanged; the adoption
  still runs report-check and restores the protocol on a refusal.

- **`protocol-fill --from-run` no longer writes the Summary's Result; the
  author does.** The Result is "the answer to the question above, in at
  most two plain sentences"; `--from-run` filled it with the Answer line —
  a dump of every metric key with the "read within Limit" tails — and in
  three of three finished judge protocols nobody replaced it, so the one
  field meant to say whether the question is answered held machine text
  (final-answer audit, 2026-10-21). `--from-run` writes the Answer and
  Runs lines and names Result among the fields still yours; `protocol-check`
  holds an empty Result after a measure run as before, now saying who
  writes what. A protocol adopted under 0.99.0 keeps its Result.

- **The judge skeleton keeps the experiment; its run mechanics are
  `labkit.run.lanes`.** The stamped `01_measure.py` of a model area was 436
  lines for about six edits (every judge probe of 2026-10-21 said so). It
  now holds one block of what to fill (items, text field, answer words,
  both prompts, the case-class file), then what decides the number —
  `MeasureConfig`, `parse_answer`, the counting functions and
  `evaluate_rows` with its null band — where the audit reads them and the
  stamp covers them, and hands the run to `lanes.Lanes`: jobs per item and
  lane, batches, resume, the instrument, the probe, the balance, the
  command line. The mechanics are tested once in labkit (answers stay with
  their jobs whatever order the calls finish in, a break resumes to every
  job once, `--eval-only` gives the run's numbers) and pinned with labkit;
  a test holds that the audit's prompt still carries the prompts, the null
  lane, the config and the formulas. The names `02_analyze.py` and the
  area test read stay (`plan`, `measure`, `evaluate`, `probe`,
  `read_jsonl`, `read_case_classes`, `one_per_class`, `main`). Areas
  stamped before keep their script; the estimator skeleton is unchanged.

- **`runs.tsv` is a local index, git-ignored by the lab stamp.** The
  versioned run directories under `runs/<run_id>/` are the truth; no gate
  reads the index, and `runlog reindex AREA` writes it back with the same
  rows (a test holds that). Two runs of one second may come back in the
  other order — no record holds a finer start time. The rule stands in the
  stamped `.gitignore` and AGENTS.md and in `docs/protocol-run-binding.md`.
  A lab stamped before keeps tracking it: add `runs.tsv` to its
  `.gitignore` and `git rm --cached` each index (a commit of its own).

- **A findings file says how a reason is written, and so does its
  refusal** — an aid, not a fix: it lowers the risk of a hand-written
  reason breaking the TOML and does not prevent it. The file's head names
  the TOML string forms (`"…"` with `\"`, or `'…'`), and a file that does
  not parse is refused with the same sentence after the parser's line and
  column. A reason with an unescaped quote had made the record unreadable,
  refused only as "not TOML" (count probe, 2026-10-20). A command that
  validates and stores a decision the person typed stays deferred.
- **`runs.write_atomic` is `files.write_atomic`.** Writing a file whole or
  not at all serves every format (run records, the lease, a filled
  protocol), not runs alone; it moved to `labkit/formats/files.py`. No alias
  stays: code that imported it from `runs` imports it from `files`.
- **Every command refuses on stderr with exit 2.** intent-check,
  protocol-check, scope-sha, report-check, labkit-params, labkit-hooks,
  `claude-hook sessions`, the run index of runlog and labkit-check sent
  some refusals to stdout or wrote stderr by hand; each now goes through
  `console.refuse`, and stdout carries only what a check found. labkit-init
  and usability refused with `SystemExit` (exit 1) and now exit 2; labkit-calltree
  leaves its own exit for `console.exit_with`. A refusal raised as
  `console.Refused(tool, why)` reaches `exit_with` from any depth, so a
  command that stamps through labkit-init's functions (`usability stage`)
  shows the refusal, not a traceback. A command called without arguments
  prints its usage as such a refusal (`console.usage`); asked with `-h` or
  `--help`, the usage stays on stdout with exit 0. Inside `finalize`
  intent-check's reason still stands above its blocker in the terminal.
- **The README introduces labkit and walks through using it.** Installation,
  the measurement lifecycle, cost tiers and result adoption precede the
  command reference. Internal records and enforcement live in
  `docs/architecture.md`; TODO holds remaining work, decisions and triggers
  instead of a chronological list of completed changes.

- **A gate's findings are data; the console is one channel for them.**
  `gate.Findings` keeps every finding as `GateFinding` (grade, text) and
  tells each line through `tell` — `print` by default, `None` for a gate
  run inside another gate; `note` and `header` carry the uncounted lines,
  `summary` and `exit_code` are readable without printing. finalize's
  stations, including protocol-choice errors, tell everything through the
  collector they are handed (the standalone command keeps usage errors
  on stderr), and `report_check.finalize_gaps` hands over a silent one instead of
  redirecting stdout. `preflight_area` shows its stations and every skip
  condition at the entry point, each station a named function
  (`check_protocol_fields`, `check_audit_records`, `check_audit_coverage`,
  `check_deferred_elsewhere`, `check_code`, `check_working_tree`,
  `check_hooks`, `check_tests_owed`; `cost_tier_lines`, `scope_stamp_line`
  told); `runlog.Run.__init__` is three phases — preparation, the start
  check, creation — with the detach and full-run conditions visible in
  the constructor and every refusal before mkdir in its unchanged order.
  Same grades, messages, summaries and exit codes; no obligation changed.
- **`report-check` builds one context per check and names the state it
  held.** The stations read `report_check.Checked` (`checked`): the
  protocol text as the named file state holds it — the working tree at
  the stop, the index at the commit (`--staged`), the written proposal at
  the adoption — its head, the runs the answer cites, and the answering
  run chosen once (`audit.audited_run`, through
  `runs.bound_answering_run`); no station reads the file or chooses the
  run for itself, and the output says "read from the index". Which areas
  changed or staged paths touch is one answer, `repo.areas_of`, for the
  stop's reported numbers and the commit's undecided findings.
  `protocol-fill --from-run` writes the proposal and its restore through
  `runs.write_atomic`, whole or not at all. Same gates, same blockers.
- **`labkit-init --report` no longer declares a model-free protocol
  deterministic.** It fills only "Parser cases harvested"; "Randomness
  controls" and "Noise ceiling → threshold" come back as placeholders for
  an area without a model, because a seeded estimator, a fold shuffle and a
  permutation are sources of randomness. Sonnet v2 t5 got "no seed,
  repetition spread 0" auto-filled while naming seed 0 under "Free knobs";
  v3 measured a null-AUC spread of 0.116 over ten seeds (plan P, C1).
- **The standard's scar table names the registered number seen before the
  freeze** (LAB-015, audited at preflight): the registered lane run over
  all items before `frozen = true` — ad hoc seeds, a "calibration", an
  instrument check that was the full measurement. The field guide and the
  template's noise-ceiling placeholder say to calibrate bands on the null
  lane or a subset (`--probe`) and where a peek is disclosed; the
  instrument-check entry says what the check is without a model. No rule
  changed; the standard stays 0.19. Evidence: Sonnet v3 t3 and t5
  (labkit-paper area 09, 2026-10-16); v3 t18 is the twin (plan P, D1, D2).

## 0.99.0 — 2026-10-19

### Breaking

- **`n/a` in `preflight_audit` no longer waives the audit at `minutes`/`hours`.**
  Third haiku round on 0.99.0 (labkit-paper area 09, t18): the agent set
  `frozen = true` with `preflight_audit = "n/a — RF model training does not
  require external audit"`, and runlog took it as a visible decision. Now
  a full run at `minutes`/`hours` is refused on such a line; `preflight`
  blocks it when frozen and `protocol-check` warns. The refusal names the
  honest ways — run `labkit-audit`, or let it record the failed attempt
  when the backend does not answer — and says that whoever owes no audit
  has the wrong cost tier; it offers no word to write. One home for the
  line's reading: `findings.audit_line_gap` (runlog and preflight had two
  copies). The shipped standard's paragraph says so (its stamp 0.20 is the
  release's). `n/a` keeps its place at `seconds`. 0.98.0 is the last version
  that passes it.
- **A cost tier lowered since the protocol's first commit is a warning.**
  The next way round, once `n/a` is refused, is `cost = "seconds"`, where
  nothing is owed before the run — the same move as rewriting the promises
  until no check is due. `protocol_check.cost_lowered` reads the head as
  the adding commit has it (`git log --diff-filter=A`, `git show`) against
  the head now; a lower tier is a WARNING in `protocol-check` (so in the
  post-change hook) and `preflight`, naming commit and both tiers. Static
  evidence: a legitimate correction says why in the protocol.

- **The stop hook and the pre-commit hold a touched area to its audit
  records.** An area the session changed a file in (git status), or a
  staged file lies in, that holds an audit BLOCKER nobody decided: `claude-hook
  stop` sends the agent back (exit 2, once), the stamped pre-commit refuses
  the commit through the new `claude-hook undecided <paths…>` (exit 1).
  Third haiku round on 0.99.0 (labkit-paper area 09, t5): the agent ran
  the audit, read its four BLOCKERs, left all twelve findings `open`,
  measured with long=False and reported — report-check would have refused
  the number, but no gate the agent has to call is a gate. Deciding is
  cheap and visible (`accepted` with a reason is a documented deviation);
  the whole repo is not held, so old areas do not block every stop (A4,
  2026-10-17). Reinstall the hooks (`labkit-hooks install`).

- **`LABKIT_UNFROZEN=1` acknowledges an audit that could not run, not one
  nobody ran.** Second haiku round on 0.98.0 (labkit-paper area 09): no
  labkit agent started an audit, so the refusal over an open BLOCKER never
  fired, and t5 measured with `long=True` and the acknowledgement over
  nothing. At `minutes`/`hours` the freeze gate now asks for the failed
  attempt `labkit-audit` writes when the backend does not answer
  (`audits/<date>-<mode>-failed.toml`, `findings.write_failed`: the
  backend's error, the code and promise block it would have read, the time
  the call had, the command) — at the code as it stamps now, the promises
  as they read now, in mode preflight, with the default timeout at least
  (`findings.ATTEMPT_TIMEOUT_S`; `--timeout 1` is not an attempt). The run
  records which attempt it rests on (`audit_failed` in `config.json`). A
  usage error of `labkit-audit` (an unknown alias, an area that cannot be
  stamped) writes no attempt. At `cost = "seconds"` nothing changes: no
  audit is owed before the run. 0.98.0 is the last version whose
  acknowledgement passes without an attempt. `findings.area_records`
  reads the records only; `failed_attempts` the attempts.
- **A probe's or an acknowledged run's number is never a reported number
  (plan 2026-10-17, A3).** Every run records `long` in `config.json` (the
  script's declaration of a full run); `runs.unreportable` is the one
  telling of why a run's number cannot be reported — `long=False` (a
  probe), `unfrozen_ack = true` (a full run acknowledged over an unfrozen
  protocol), or a record without `long` (written before 0.99.0: it cannot
  say, and is not read as a full run). `finalize` warns about such an
  answering run; `report-check` refuses it ("a reported number owes a full
  run (long=True) on a frozen protocol"). Haiku t3 and t18 on 0.98.0
  measured without `long=True` — a probe for labkit, so neither freeze nor
  audit was owed — and reported the probe's number through both gates. The
  freeze gate's refusal now names that consequence instead of offering the
  way round ("Pilot it with long=False … A long PILOT acknowledges …"): the
  agents took the offered way and the offered word, and called their run a
  pilot (transcripts of both haiku rounds). The gate's messages no longer
  use the word; labkit's term for a `long=False` run is "probe" (`--probe`).
  `finalize` also names every finding still `open` in `audits/` (any mode),
  with its file: a BLOCKER blocks, a WARNING warns — a finding nobody
  decided is an ignored finding (LAB-015 Preflight audit before freezing).

## 0.98.0 — 2026-10-18

### Breaking

- **An audit record binds what the auditor read.** `audits/*.toml` carries
  `block_sha` (the promise block, `promises.block_stamp`; `none` when the
  protocol declares no tables) and, in mode analysis, `run_id` (the
  answering run whose rows the auditor read; `none` when there was none).
  `findings.audit_coverage` holds all three, so the freeze gate, `preflight`
  and `report-check` refuse an audit of other promises or of an earlier
  run — until now a record named the code's stamp only, and a promise
  rewritten after the audit, or a later run under the same code, kept the
  old audit valid (review 2026-10-18). `labkit-audit` fixes block and run
  before the model call, like the stamp. A record without `block_sha` is
  refused; 0.97.1 is the last version that reads one. `findings.write` and
  `audit_coverage` take the new arguments. `report-check` holds the record
  to the same run choice as the audit (`audit.audited_run`).
- **`code-check` exits 0 on warnings only**, as `gate.py` promises for
  every gate: a warning is static evidence to read, a blocker stops. Until
  0.97.1 it exited 1 on a warning too (audit 2026-10-18).

### Fixed

- **runlog refuses a full run over an undecided audit BLOCKER, acknowledged
  or not.** `LABKIT_UNFROZEN=1` acknowledged an unfrozen protocol and passed
  a preflight record with an open BLOCKER too (labkit-paper area 09, haiku
  round: the record lay in `audits/` before the first run, four full runs
  went past it). Now the full run names the undecided BLOCKER(s) and
  stops; open WARNINGs ride in the acknowledgement's line; a probe
  (`long=False`) still runs so the finding can be examined.
- **The findings reader holds the counts to the tables, as the writer
  does.** A hand-edited record with `blockers = 2` and no `[[finding]]`
  table read as covered with nothing open; `findings.read` refuses it
  (`counts_outrun`, one home for both).
- The `llm` module's `models.toml` example wrote `endpoint = "gamma2"`, the
  string form `resolve` refuses since 0.89.0; it writes `endpoints = [...]`.
  The `lib/runlog.py` shim recipe is gone from `labkit/__init__.py` and the
  README: labkit carries no legacy bridge, a repo with flat imports is
  reproduced with its own commit and pinned labkit.

## 0.97.1 — 2026-10-18

### Fixed

- **A broken scope file is one blocker in every repo, not only one with a
  `lib/`.** Audit 2026-10-15 bug 11 was closed through the import walk,
  which parses the area's files only when the repo has a `lib/` or `src/`;
  without one a script that does not parse reached a bare `ast.parse` in
  code-check's constant check — the traceback in preflight again, exit 1
  and so not blocking in the pre-run hook. `scope_sha.parse_source` is the
  one parse of a scope file (`SourceError` naming the file); the constant
  check and the admissibility read check go through it (audit 2026-10-18).
- **Fences are read once, also by the readers that walk lines.** Seven
  readers still toggled a flag on a line starting with three backticks
  (`protocol_check.prose_lines` behind `OVERSIZED (must)`,
  `protocol_reading.form`, two in `scaffold`, two in `rules`, the audit's
  scope list): a `~~~` fence or a fence nested in a fence turned code into
  prose for them while the protocol parser read it right.
  `protocol_block.fenced_lines` is the one answer to "is this line inside a
  fence"; `tests/test_one_home.py` now greps the hand-toggled shape too.
- **The tag test skips in a shallow clone without tags, as promised.** Its
  `--is-shallow-repository` check compared against `"true"` with the
  trailing newline still on, so the skip of 0.96.1 never fired and a cloud
  clone's suite was red on one test.

### Changed

- **One rule for a tie in the start second.** `runs.same_second` is the
  one reading of "two runs the ids cannot order", and
  `runs.newest_completed` the one reading of "the newest run" (refusing the
  tie): the usability scorer had compared the seconds itself a second time
  in 0.97.0, and runlog's "last finished" line took the newest by name.
  `tests/test_one_home.py` keeps `start_second` inside `runs`.
- **The standard: "Trivial solution passes" is a scar** (pilots 06 and 07:
  the null probe was measured but held to no expected value), in the scar
  table of LAB-015 and so in the audit. The row orders the thing before
  the bookkeeping: a trivial probe's expected value is 0 or chance; a
  number above that is a finding first, a target only where the protocol
  says why doing nothing is correct — a first audit with the row took the
  easy half and proposed the predictable number as the target. **Section 8, a base layer from the
  literature** (31 error classes with source and check, from Kapoor,
  REFORMS, Biderman, ABC, Wicherts, Makin and Lones) stands outside every
  rule and is not read by the audit until the benchmark has been drawn
  again with it; its rows are prior knowledge, not scars, and a row without
  a house case that produces false alarms is removed, the legend never
  sharpened. The standard carries its version in its head (0.19, the one a
  protocol names) and a dated "Changes" list at its end.

## 0.97.0 — 2026-10-15

### Fixed

- **Two runs started in one second no longer answer by chance.** A run id
  is the start second plus a random suffix, so `runs.bound_answering_run`
  took whichever of two such runs had the larger suffix as "newest". Now a
  second bound run of the same standing started in the same second blocks
  the choice, and an unreadable run in the same second blocks it like a
  newer one. Every check that holds a protocol to its run (finalize,
  intent-check, recheck, params, the audit) reads this choice.
- **A draw cannot vanish or be counted twice.** `runs.draws` (the spread
  `02_analyze.py --draws` shows) and `runs.next_draw` (the number a new
  repeat reserves) skipped a run whose config.json could not be read — it
  may be a draw, so the spread was shown over fewer draws than were taken,
  and its number could be handed out again. Both now refuse; so does a
  repeat whose `draw` is no integer (`next_draw` skipped it), and two
  completed repeats recording one draw number (`draws` listed both).
  `runlog` refuses the repeat with a sentence, finalize's single-draw
  warning says the draws cannot be counted.
- **A derived run cannot be drawn from a repeat.** A derived run is no
  repeat, so it may answer; `runlog` took a repeat as its parent, and the
  best of several draws could answer through it. Now a refusal naming the
  primary run to derive from.
- `tests/test_answering_run_exhaustive.py` holds the choice to an oracle
  over every area of up to three runs from nine kinds, on different days
  and in one second (1640 areas); the code before this fix fails 90. On
  the same areas finalize, intent-check, recheck, params and the audit
  are held to name one run; the draws are checked the same way over seven
  kinds (800 areas, the code before fails 544), and `runs.completed_runs`
  over the nine.
- `usability.latest_run` (the scorer's run) refuses when the last two
  completed runs started in one second, like the answering-run choice.

## 0.96.1 — 2026-10-15

Phase D of the audit of 2026-10-15: docs and hygiene.

### Changed

- **A refusal to run goes to stderr, a finding to stdout.** `console.refuse`
  is the one place a command says it could not run (a bad argument, no
  such area, no protocol to choose, no such file); 44 such lines went to
  stdout and 25 to stderr before, so a caller reading stdout for a gate's
  findings read "no such area" as one.
- Docs: the README counts preflight's eight stations and finalize's seven
  steps as listed (it said seven and eight); the tag test skips on a
  shallow clone without tags instead of failing, and CLAUDE.md says so.

## 0.96.0 — 2026-10-15

Phase C of the audit of 2026-10-15: one home per question, and a test that
keeps the copies from coming back.

### Changed

- **Digests and git through their homes.** `runlog` hashed the script by
  hand and ran `git rev-parse` outside `repo.git_run` (no timeout, no
  `GitError`); `usability` ran its eight git calls the same way. The width
  of a run's recorded digest has a name, `runs.RECORD_SHA_CHARS` (16) beside
  `scope_sha.DIGEST_CHARS` (12), instead of literals in three modules.
- **One repo-wide protocol scan.** `repo.repo_protocols` reads the repo
  outside `repo.SKIP_DIRS` (`.git`, `.venv`, `runs/`, `data/`, …); four
  scans did it themselves and three read a protocol copied under `runs/`
  as a second one (a false "two protocols carry id" blocker). The name has
  one spelling (`repo.PROTOCOL_GLOB`, `repo.PROTOCOL_NAME`), the lab root
  one rule (`repo.lab_root`: the nearest `models.toml`, for `labkit-init`
  and `llm`); `notes_check` no longer carries its own `git_root`.
- **The id alphabet is asked, never re-spelled.** `promises.key_kind` says
  which kind a metrics key belongs to; `usability` and `protocol_reading`
  had their own `^a\d+_` and `[ca]`, which the next change of the alphabet
  would have silenced. The area name `NN-<slug>` has one pattern,
  `repo.AREA_NAME` / `repo.split_area_name`, instead of four.
- **One telling of the answering choice.** `runs.AnsweringRun.explain`
  renders the choice for finalize, intent-check, recheck, `labkit-params`
  and the audit, which did it four ways with four semantics: a chosen run
  that reports no intent key while the protocol registers ids is a blocker
  everywhere now (intent-check warned and read every promise as
  unimplemented; params showed the probe's values as the answer).
- **Fences and labels are parsed once.** `protocol_block.fence_spans` is
  the one fence walker (`protocol-fill --prompts` closed a block on any
  line starting with the marker; the prompt-drift check knew no `~~~` and
  no nesting), `protocol_check.fields` the one label parser (the prompt
  check had its own, blind to a wrapped label), `protocol_check.model_named`
  the one reading of `Model / tool` (`labkit-init --report` matched the
  raw text and read `—` as a model). `protocol-fill` reads the head's
  `type` inside the TOML block, not in a fenced example.
- **`labkit.gate`: what a gate found, told once.** `gate.Findings` holds the
  blockers and warnings of preflight, finalize, report-check, code-check and
  notes-check, prints one spelling (`BLOCKER:` / `WARNING:`), one summary
  and one exit contract (1 with a blocker). Five shapes and three
  spellings before; preflight counted code-check's lines a second time by
  `startswith`, and a protocol-id line graded `WARNING` counted as a
  blocker. preflight's station lines carry the grade now
  (`BLOCKER: MISSING (must): …`); notes-check ends with the same summary.
- **`tests/test_one_home.py` keeps the copies from coming back.** It greps
  `labkit/*.py` for the shapes a copy takes — a hand-spelled sha256, a `git`
  run outside `repo`, a `PROTOCOL-*.md` scan, pip's name normalisation, a
  fence regex, the id letters, the area name, a temp-and-rename write, the
  run-id shape, a pin line spelled by hand — and fails on a match outside
  the home; a line that must stay says why with `# home:`. On the way:
  `scope_sha.digest` for bytes (promises, endpoint_lease), `repo.pip_name`,
  `runlog._parse_lock` and the probe's pin line read through
  `repo.requirement_name`.

## 0.95.0 — 2026-10-15

Phase B of the audit of 2026-10-15: the audit chain and the hooks.

### Fixed

- **`labkit-audit` stamps the code before the model call.** The stamp was
  taken after the answer (up to 900 s later): a lib module edited meanwhile
  gave a record whose sha no auditor had read, and the freeze gate took it
  as covered. The stamp is taken once, recorded as taken, and a change
  during the call is said (`stamp NOTE`).
- **An audit whose finding lines the parser could not read was recorded as
  covered.** `BLOCKER — …` and `BLOCKER: …` parsed as no finding while the
  verdict counted two; the record then had nothing open and passed the
  freeze gate. The parser reads a dash or colon after the grade too, and
  `findings.write` refuses a verdict that counts more blockers or warnings
  than lines it can record — exit 2, nothing written.
- **preflight holds the audit line's `scope sha` to the code's stamp.** At
  `frozen = true` it never compared them (only protocol-check warned and
  runlog refused at the run), so the pre-freeze gate passed exactly the
  state the freeze gate refuses. A stale sha is a blocker once frozen, a
  warning before.
- **The pre-run hook follows a `cd` and judges throwaway flags per
  command.** `cd AREA && python scripts/01_measure.py` resolved the script
  against the event's cwd and found nothing; one `--probe` anywhere in a
  line freed every command in it. The line is cut at `;`, `&&`, `||`, `|`
  and line breaks (`claude_hooks.command_segments`); each segment is judged
  on its own.
- **Hooks, small:** post-change and stop read `git status -z`, so a file
  name with an umlaut (quoted and escaped in the text form) is checked;
  a `notes/messung/` pair anywhere in the path counts, not only the first
  `notes`; `labkit-hooks install` recognises its own hooks by the command
  as a word, so a foreign `./bin/my-protocol-checker` stays; `claude-hook
  sessions --run` without a value is a usage error, not a traceback.
- **A gate's subprocess has a time limit.** An area test or `02_analyze.py
  --check` that hangs hung preflight, finalize and report-check until the
  hook's own timeout killed them, wordless; after 300 s it is a failing
  test or check, said in the finding (`preflight.AREA_TEST_TIMEOUT_S`,
  `report_check.CHECK_TIMEOUT_S`).

## 0.94.0 — 2026-10-15

Phase A of the audit of 2026-10-15 (`docs/audit-2026-10-15.md`): the bugs
of the guaranteed tier.

### Fixed

- **`protocol-fill --from-run` and `--check` chose the run without its
  binding.** `recheck.run_dir` took the area's newest completed run; in an
  area holding two protocols the number of a run bound to protocol B was
  written into A, and a newer producer run made `--check` of a correct
  area block. The choice is `runs.bound_answering_run` now — the same one
  finalize and intent-check make (`recheck.chosen_run`); a run named
  with `--from-run RUN_ID` must be bound to the protocol.
- **`runlog <typo>` read as idle.** A misspelt area printed "no open runs"
  with exit 0, and `--wait` reported it as finished. Status, `--wait` and
  `--follow` resolve the area like `reindex` and refuse one that is not a
  directory (exit 2).
- **A server's 4xx was retried as an outage.** `HTTPError` is a `URLError`:
  a wrong model id (404) or a missing key (401) went through six attempts
  and 13 minutes of backoff. A status below 500 is now a `BackendError` at
  once, with the sentence naming the alias; 5xx keeps the retry.
- **`claude -p` reads the prompt from stdin.** As one argv entry a 200 kB
  audit prompt was `OSError: Argument list too long` on Linux (128 kB per
  entry); only macOS let it through.
- **Every record file of a run is written whole or not at all.** config,
  outputs and metrics went through `write_text`; only completion.json was
  atomic, while `docs/architecture.md` claimed the whole record was
  (CODE-013).
- **A number inside the run id counted as cited.** `recheck.cited` found
  `10` in `…T10-22-33_ab12` and `12` in `12.7`; the run id is mandatory in
  every note, so a count equal to a date or time part passed. Run ids,
  dates and times are masked before a number is looked for, and a number
  followed by `.<digit>` is another number.
- **report-check passed a must field still holding its placeholder.**
  Station 1 read protocol-check's missing fields only; the `<…>` holes
  count now, as in protocol-check and preflight.
- **A scope file that is not Python is one blocker, not a traceback.** With
  a `lib/` or `src/` in the repo, preflight station 3 and code-check raised
  from the import walk on a stale `analysis/old.py` with a syntax error —
  exit 1, and so not blocking in the pre-run hook. `scope_sha.SourceError`
  names the file; code-check and preflight report it as `BLOCKER`.
- Small: a split file with a damaged line names file and line instead of a
  bare `JSONDecodeError`; `recheck.agree` compares the recomputation as JSON
  (a tuple is the list the run recorded); `finalize` looks for the area's
  tests under the layout root like preflight (a stamped tree before `git
  init` read "none"); `runlog` no longer passes `maxsplit` positionally
  (a DeprecationWarning on 3.13).

### Breaking

- `recheck.run_dir(area, protocol, run_id=None)` takes the protocol; an
  area stamped before 0.94.0 calls `recheck.run_dir(AREA, NOTE)` in
  `02_analyze.py --draws`. `recheck.holds(..., protocol=)` names the
  protocol when `note` is a results note without a head. Last version with
  the newest-run choice: 0.93.0.

## 0.93.0 — 2026-10-15

### Added — repeat draws: the spread of a model's number

- **`runlog.run(..., repeat_of=RUN_ID)`** — the same measurement asked
  again: new model calls, its own model record, `repeat_of` and `draw` (2,
  3, …) in config.json. Refused before mkdir unless RUN_ID is a completed
  primary run with the same protocol, the same promise snapshot (block and
  every declared scope's digest), the same measure script and resolved
  model, the same experiment config and inputs (`runs.repeat_mismatch`), and
  never with `derived_from` (which re-reads old rows without a model call).
  The draw number is reserved once, under runlog's index lock, and exposed
  as `run.draw`; a crashed draw keeps its number. Damaged `repeat_of` or
  `draw` values make the run unreadable, not a primary.
- **A repeat never answers** — not by default, not by name: `runs.bound_runs`
  leaves it out of the answering choice, and `recheck.run_dir` (behind
  `--from-run` and `--check`) refuses a repeat named explicitly, with no
  `--force` past it. `runs.completed_runs` takes a required `with_repeats=`.
- **The skeleton:** `01_measure.py --repeat-of RUN_ID` writes
  `<name>_draw<N>.jsonl` by `run.draw`; `02_analyze.py --draws` holds every
  draw like the kept number (`recheck.verified`: output pinned, scopes and
  block unchanged, metrics recomputed) and then prints c1 per draw, its
  range and the items that flip. `runs.next_draw`, `runs.draws`.
- **finalize warns** "one draw — no spread" for a run that asked a model
  and has no repeat (static evidence).

### Breaking

- `runs.completed_runs(area)` needs `with_repeats=True|False`.

### Fixed

- **A judge area stamped at `seconds` failed its first run** (TypeError in
  MeasureConfig): the seconds cut commented out the constants the full
  measure skeleton reads. Broken since 0.87.0; the stamp keeps them now.

## 0.92.0 — 2026-10-14

### Added

- **`batch.Store(..., instrument={...})`** — what makes two answers
  comparable (the prompt's digest, the model alias). Every appended row
  carries it as `_instrument`, and `pending()` raises `InstrumentError` when
  the file holds a row of another instrument (or none): a changed prompt or
  model is a new measurement, a new output file. Resume by id alone let a
  new prompt keep the old prompt's answers (found by the cloud judge
  probe's analysis audit).

### Changed

- **The measure skeleton** passes `{prompt_sha, model}` to the Store;
  `measure(cfg, jobs, out, prov)` takes the config instead of the model
  alias (`instrument(cfg)` builds the dict). Areas stamped earlier keep
  their `measure`; a re-stamp brings the new one.
- **The probe's print names the area's real test file and `PROBE_CASES`**
  (it said `tests/test_<NN>_<name>.py PARSER_CASES`), and the `max_empty`
  comment no longer derives the value from "2 of 96".

## 0.91.2 — 2026-10-14

### Fixed

- **A frozen head carried the stamp's `<…>` promise sentences** and passed
  every gate (only an empty sentence was refused). At the freeze or a full
  run a `[[promise]]` sentence that is one `<…>` placeholder is a must gap
  now (`promises.promise_tables_owed`, `placeholder_sentences`) — in
  protocol-check, preflight and runlog alike; an unfrozen pilot may carry
  it. `report-check` holds the freeze to protocol-check's must gaps, not to
  the flag alone. The template's hint says to state the promise explicitly
  instead of "the same as the Intent field".

## 0.91.1 — 2026-10-14

### Fixed

- **`data=` inputs recorded absolute paths too** (0.91.0 fixed only the
  outputs): after a checkout moved, finalize found the frozen source
  "gone" — a blocker at `seconds` — and a relative `data=` path was kept
  relative to whatever the working directory was. One pair for both,
  `runs.recorded_path` / `runs.resolve_recorded`; `recorded_output_path`
  (0.91.0) is gone.
- **The analysis script has one name:** LAB-041, the field guide and the
  protocol template said `analysis/<note>.py --check`; the stamp writes,
  and `report-check` holds, `scripts/02_analyze.py`.

## 0.91.0 — 2026-10-14

### Added — the lane has an end gate

- **`report-check <AREA>`** — the last gate at `minutes`/`hours`, after the
  analysis audit: `frozen = true`, finalize clean, an analysis audit record
  of the code as it is now with every finding decided, and
  `scripts/02_analyze.py --check` passing. At `seconds` nothing is owed
  there. finalize could not ask for these without a circle (it comes before
  the analysis audit); in the cloud judge probe an agent skipped the check
  and the note with finalize green. The AGENTS.md template's step 11 ends
  with it.
- **`findings.audit_coverage(area, sha, mode)`** replaces
  `preflight_coverage` (0.90.0): one answer for the freeze and the report.

### Changed

- **The measure skeleton's accuracy is over every item of the lane**; an
  empty or unreadable answer is not correct (and still counted as
  `*_empty`). Over readable answers only, a model gained accuracy by not
  answering, and both cloud preflight audits flagged it. The stamped [C1]
  sentence and the area test say the same.
- **`protocol-fill --list`** prints the fields `--from-run` writes (Result,
  Answer to the question) last, under "after the run".
- **`labkit-init exp`** finds the lab repo above the working directory.

### Fixed

- **outputs.json recorded absolute paths**, so `02_analyze.py --check`
  failed in every checkout but the one that measured (a cloud run's
  `/home/user/...`). A path inside the repo is recorded relative to its
  root and resolved on read; records written before keep their absolute
  paths.

## 0.90.0 — 2026-10-14

### Breaking — the frozen code is the audited code; `runlog start` names its area

Both from the cloud judge probe at `minutes` (`docs/usability/2026-10-14-judge-minutes.md`).
Last version with the old behaviour: 0.89.0.

- **A full run's audit stamp must be one a preflight audit record saw.**
  runlog's freeze gate (and `preflight`, a blocker once `frozen = true`)
  now needs a record `audits/*-preflight.toml` whose `scope_sha` is the
  code's stamp now, every finding decided (`findings.preflight_coverage`).
  Writing a new `scope sha` into the head after fixing the findings, without
  a second audit, is refused; `n/a — <reason>` stays a visible waiver.
  Every frozen area audited before `labkit-audit` wrote records (all 21 in
  uniagent) owes a fresh preflight audit before its next full run under a
  raised pin.
- **`runlog start AREA [--log FILE] -- <cmd>`.** The area is a required
  argument; the default log is `AREA/output/start-<ts>.log` (was `output/`
  under the working directory) and the printed wait command names AREA.
  `runlog start -- <cmd>` is a usage error.

### Fixed

- **[C1] in the measure skeleton compared floats:** a registered lane
  exactly at null + margin failed (5/12 + 0.25 > 8/12 by one ulp). It is
  computed in fractions now — found by the probe's opus preflight audit.
- **The AGENTS.md template** says an audit takes minutes: start it in the
  background and wait for that task, not with a `pgrep` loop (which finds
  its own command line; about 14 of the probe's 22 minutes).

## 0.89.0 — 2026-10-14

### Breaking — the legacy paths are out, one home per question

A repo audit (2026-10-13: the seven largest modules, the drift between
modules, the docs against the code) found the readers of old formats
still in place and a dozen second answers to questions
`docs/architecture.md` gives one home. Last version with every old
path: 0.88.8.

- **No `legacy` run state.** A `config.json` without `schema_version >= 2`
  (a run of labkit before 0.21) is unreadable run metadata like a damaged
  file: `runs.read_run_config` raises naming the file and the version that
  reads it (0.47); listings show `unreadable` with the reason, `runlog
  --wait` exits 2 on it, `reindex` reports it and exits 2, no choice ever
  takes it. `runs.completion_state` raises for a directory without
  `config.json` (not a run) instead of answering `legacy`.
- **`endpoint = "<url>"` in `models.toml` is not read.** `llm.resolve`
  refuses it with the list spelling to write (`endpoints = ["..."]`); the
  stamped `models.toml` documents only the list.
- **`promises.DIGEST_CHARS` is gone** — it shadowed `scope_sha.DIGEST_CHARS`
  (the comment said so). The digests themselves are unchanged.
- **The probe's scaffold sha changes shape:** `usability.scaffold_sha`
  computes through `scope_sha.tree_digest` (name + content digest per file)
  instead of raw bytes. Only new probes record it; a score compares a
  probe with its own record.
- **`llm.complete(keep_alive=)` is gone** — no caller ever passed it;
  `llm.OLLAMA_KEEP_ALIVE` (10m) is the one value.
- Smaller: the documented-runs heading no longer matches `ledger` (the word
  left the vocabulary 2026-09-26); the usability source-read pattern no
  longer matches `arbeitsstandard`; `runlog <area>` prints `(not recorded)`
  for a run without a command instead of naming labkit 0.69.

### Changed — one home for what was answered twice

- **`repo.the_protocol(area, protocol)`** raises `ProtocolChoiceError`
  (the candidates in the message); `repo.choose_protocol` prints it.
  `preflight`, `code-check` and `labkit-audit` carried their own copies of
  the rule — three wordings of one refusal.
- **`protocol_block.id_of(text)`** is the one tolerant reader of a head's
  id (`protocol_check`, scaffold's uniqueness scan); scaffold reads `cost`
  through `protocol_block.head`, the area's protocols through
  `repo.area_protocols`, the tiers from `protocol_block.COST_TIERS`.
- **`scope_sha.area_files`** sorts and is the one list of an area's scripts
  (`intent-check`, `labkit-audit` had their own globs).
- **`runs.run_dirs(area)`** walks `runs/` once with every directory's
  metadata read once; `completed_runs`, `bound_runs`, `runlog.active`, the
  finished listing and `reindex` go through it (six loops, six decisions
  before). **`runs.write_atomic`** replaces two private copies (`runlog`,
  `endpoint_lease`). **`scope_sha.file_digest`** and
  **`scope_sha.tree_digest`** are the one file digest and the one stamp
  shape (area stamp, declared scope, directory source — byte-identical).
- **`protocol_check.check_protocol(path, text, tmpl)`** returns a
  `FileReport` with every finding as data (`clean`, `musts`, `blocks`);
  `print_report` renders it, `main` loops. Fields parsed once per file;
  `prose_lines` is the one walk behind the whole-protocol budget
  (`PROSE_LINE_BUDGET`) and the section budgets. Output unchanged.
- **`scaffold.stamp_area` returns `(area, report)`** and prints nothing;
  `labkit-init` prints. `runlog` reads the bound protocol once at binding
  (text and head travel with the record; before: three reads, three
  parses per run start). `usability` writes its probe commit, probe
  record, answer-file and venv helpers once instead of four times.
- **README's command list comes from `--help`** and is held by
  `tests/test_readme_commands.py`; the hook JSON, the gates' stations and
  `Develop` describe the current code; `protocol-fill --from-run` is
  documented to write `Answering run` too (template, finalize's hint).
  The field guide places `Answering run` and `Deviations after freeze`
  under Result, as the template does, and knows the `deferred` status.
- **One grammar for a requirement line** (`repo.VCS_REQUIREMENT`,
  `EDITABLE_REQUIREMENT`, `EDITABLE_PATH_REQUIREMENT`, `VERSION_REQUIREMENT`,
  `repo.requirement_name` / `requirement_lines`): the stamp's pin line,
  `labkit-check`, runlog's lock parser and the probe's pip-freeze line read
  through it (four spellings before). **One shape for a run id**
  (`runs.RUN_ID`, `RUN_ID_TIME`, `run_started`): runlog writes with it,
  protocol-check and finalize find a cited run, the stop hook reads the
  start time. `runs.COMPLETED` replaces nine string comparisons.
- `protocol_check.fields` parses a text once (seven readers before);
  `code_check` reads a bare name and a string literal in one place each;
  `llm` builds the ollama options and the empty-content notice once.

### Added

- **The detach gate holds under any agent.** `runlog` refused a long run in
  a foreground shell only under Claude Code (`CLAUDECODE`); under Codex or
  another agent the run died with that harness's timeout.
  `LABKIT_FOREGROUND_TIMEOUT_S` (seconds, `0` = no limit), set in the
  environment the harness gives its shell, names the limit for any agent;
  `CLAUDECODE` alone still counts as 600 s. `runlog.foreground_timeout()`
  answers which limit applies and who named it.
- **`code-check` warns on an [A] key nothing decides on.** An
  admissibility key the code writes but never tests (`if`, `and`/`or`/
  `not`, `all()`/`any()`, a loop over a key tuple) permits nothing: the C
  verdict is reported either way. Static evidence — a WARNING, and code
  this reader does not follow stays silent.

### Fixed

- **`code-check` crashed on an empty prompt fence** (`IndexError` reading
  the first line of an empty block) instead of reporting the drift as a
  blocker.
- **`labkit-params` missed a script copy in upper case:** `MIN_F1` for the
  registered `min_f1` stood as a separate evidence row and the registered
  row said only "not recorded". The copy now stands in the registered row.
- **`labkit-check` called a tag pin and its lock STALE:** the lock from
  `pip freeze` names the commit the requirements tag points at. The pin
  line resolves the tag at the source and compares commits.
- **The usability task sheets** say that every `.venv/bin/…` path holds
  from the repo root (Haiku H8 called it from the area: exit 127).
- **The stamped skeleton tripped its own gates** (a cold Sonnet agent, judge
  at `minutes`): `00_prepare.py` passed no registered constants, so runlog
  refused the first step of every area with a model; `02_analyze.py
  --check` looked for `:.4f` numbers while `--from-run` writes them as
  Python prints them; `--from-run` skipped the stamped `Answering run: none
  yet` line silently (another run's id is now refused, not skipped); and
  `code-check` warned on `02_analyze.py` loading its own `01_measure.py`.
- **`usability stage`:** the task sheet names the stamped cost tier, and
  says AGENTS.md (not CLAUDE.md) is in the agent's context.
- **A dead run held "running" by a namesake:** `runs.is_alive` matched the
  recorded script as a substring (`not_01_measure.py` for `01_measure.py`);
  `runs.runs_script` now bounds the name.
- **The Stop hook crashed on a run-id-shaped name with no date**
  (`2026-02-30T…`): `runs.run_started` answers None for it.
- **`read_outputs` coerced `rows_from` with `int()`**; a count that is not
  an integer is now an `ArtefactError` naming the entry.
- **Endpoint leases:** the lease directory is named by the canonical URL
  (lower-case scheme and host, no trailing slash) and its digest instead
  of a slug, so `a-b`/`a_b` are two slots and `Host`/`host` one; two
  writers in the same second no longer both yield. A process of an
  earlier labkit leases under the old directory name and does not see a
  0.89.0 lease on the same slot — let running stages finish before
  switching.
- **`protocol-check` cached the repo's protocol ids for the process**;
  `check_protocol` and `check_protocol_id` now take the index
  (`repo_protocol_ids`) as an argument, so an API caller sees a duplicate
  made after its first check.

## 0.88.8 — 2026-10-13

### Fixed — the stamper refuses a version its templates do not belong to

- **`labkit_pin()` compares the installed metadata with the source
  checkout** and refuses when they differ: an editable install keeps the
  version of its last `pip install -e` while the templates are read live,
  and the first `usability stage --restamp` after the 0.88.7 release pinned
  `v0.88.5` under 0.88.7 templates. A wheel install has no source beside
  the package and is unaffected. The release recipe (`just release`)
  reinstalls the editable labkit before the commit, so the two never drift on
  the author's machine.

## 0.88.7 — 2026-10-13

### Added — four cuts from the Haiku series on 0.88.5 (H5–H7, median 1m00s)

- **`protocol-fill PROTOCOL "LABEL=VALUE" ...`** fills several fields in one
  call, all or nothing (`type=exploratory` sets the head). Every cold agent
  filled six fields in six calls and named it the largest sink. The one-field
  form `FIELD VALUE...` stays; the stamped `AGENTS.md` names the one-call
  form.
- **The seconds cut without a model says what a count owes** in its
  placeholders: `Terms of this protocol` → "one line per coined house word —
  or n/a — no coinage" (the check allowed n/a, the stamp never said so;
  three agents wrote a Terms sentence for a plain count), `Question /
  hypothesis` → "what is counted, over which items — a count tests no
  hypothesis" (H7 invented an expectation, then reworded it with `--force`).
  The labels stay: one name per field, in the standard, the check and every
  reader.
- **The counting skeleton freezes what the rows read:** `INPUTS` names the
  directory beyond `SOURCE` (a count of documents per case reads the case
  directories), and `data=` carries both. Before, `data=` froze the case
  list only and a changed document went unnoticed by `--check` (all three
  draws).
- **`usability log TAG TEXT [--log FILE] [-- CMD ...]`** writes the agent's
  step line with the current time and then runs the command. Logging by hand
  tempted every draw to batch: three wrote their first lines after the reads
  they describe. The task sheets name it.

### Changed

- **`protocol-check`: the stamped Runs entry is not a leftover before the
  run.** It is written by `--from-run`; counted as "still verbatim template
  text", it made every registration read as unfinished and two agents
  stopped to see whether it blocks. The check now says so in one line; a
  frozen protocol with the stamped entry is still a leftover (the scar of
  uniagent area 08). The pattern has one home, `protocol_check.RUNS_PLACEHOLDER`.

### Decided, not built

- The area test stays in the seconds lane (H6 would skip it): a
  number-producing function gets a test, three seconds.
- A pre-filled counting skeleton for the directory-per-item source (every
  draw's other sink) is open — not to be cut to the weakest model.

## 0.88.6 — 2026-10-13

### Added — `usability stage --restamp`: the probe stamped again, by the tool

- **`usability stage DIR --restamp [--keep PATH ...]`** lays a fresh stamp
  (task and flags from `<dir>.probe.json`) over an existing probe file by
  file: a stamped file whose bytes changed is overwritten, a new one added,
  a `--keep` path (the probe's hand edits: `TASK.md`, `.gitignore`, the
  cloud's `.claude/settings.json`) left alone and remembered in
  `probe.json` (`kept`, `restamped`). The venv is rebuilt from the stamped
  pin (or linked with `--venv`), `requirements.lock` comes from it, the
  change is committed past the hook; the push stays with the operator. A
  `--keep` path the stamp does not produce and a dirty tree are refused.
  Why: eight re-stamps of `labkit-probe` were done by hand from memory, and
  on 2026-10-13 two sessions reconstructed the recipe differently — one
  would have copied the task sheet and lost the cloud edits.

### Fixed

- The stamped `.gitignore` ignored `.venv/` — a directory only. With
  `--venv` the probe's `.venv` is a symlink, and `git add -A` committed it
  (the first `--restamp` found the link in the fresh stamp's tracked
  files). The pattern is `.venv` now: directory or link.

## 0.88.5 — 2026-10-13

### Fixed — three things a cold agent tripped over (Haiku 5.5, draw H4)

- **A reader that closes the pipe is not a crash.** `protocol-check
  --contract P | head` ended in a BrokenPipe traceback and exit 120. Every
  console command now exits through `labkit.console.exit_with`: a closed
  pipe is exit 0, nothing printed — one home for the one exit.
- **`protocol-check PROTOCOL --contract`** read the flag as a file name
  ("not readable: '--contract'"). `--contract` and `--guide` are flags
  anywhere on the line.
- **`--check` before the write-back** said "numbers not in PROTOCOL", which
  read as a failed check. When the Answer line still holds the stamp's
  placeholder, `recheck` now says so and names the command:
  `protocol-fill PROTOCOL --from-run <run_id>`.

The code landed in `16d7510`; this entry, the version and the draw's notes
follow in the next commit, and the tag was moved onto it.

## 0.88.4 — 2026-10-13

### Changed — a run's own products no longer make it `+dirty`

- **`completion.json` and the `runs.tsv` git column** record the state at
  the end of the run over tracked files only. The run's own products
  (`runs/<id>/`, `output/`, `runs.tsv`) are untracked until committed, so
  every finished run read `+dirty` whatever the tree looked like — 74 of
  74 index rows in one lab repo, and a cloud agent reported
  "`beae3bf+dirty` but `uncommitted.patch` is empty" (Haiku 5.5,
  2026-10-13). `config.json`'s `git` (the state at start) still counts
  untracked files: a file git does not know may have been run. Rows
  written by labkit up to 0.88.3 carry the old flag; `reindex` does not
  rewrite rows.

## 0.88.3 — 2026-10-13

### Added — `protocol-fill` knows the head's `type`

- **`protocol-fill PROTOCOL --list`** names the TOML head's `type` first
  while it is still the stamped placeholder, and **`protocol-fill PROTOCOL
  type exploratory`** (or `confirmatory`) sets it. Before, `--list` showed
  only the prose fields: an agent filled those, the post-edit hook answered
  "MISSING (must): [protocol] type", and the head was edited by hand (cloud
  probe, Haiku 5.5, 2026-10-13).

### Fixed

- The stamped `AGENTS.md`'s seconds lane still asked for a success
  criterion and an admissibility condition at a count — the 0.87.0 cut had
  dropped both from the contract, and the agent logged the contradiction.
  Step 2 now follows `--list` and says what a count owes and what only a
  model adds.

## 0.88.2 — 2026-10-13

### Added — the score names the model

- **`usability score --agent M`** writes the model that drew into
  `<dir>.score.json` (`"agent": "fable-5.1"`) and the table's first row. A
  cloud session leaves no transcript, so the operator states it; without
  the flag the field is `null`, never guessed. The twelve cloud score files
  under `docs/usability/` carry it now, taken from their file names.

## 0.88.1 — 2026-10-13

### Changed — a count's README carries no blank

- **`labkit-init exp --cost seconds` (no model)** stamps the area README
  without a placeholder: the one-question line points to the protocol's
  Question field, the contract paragraph names `METRIC_KEY` and the
  write-back gate. The question and the contract live once, in the
  protocol; the README's blank was the one gate line left in the cloud
  probe (draw 11, `docs/usability/2026-10-12-cloud-fable.md`), reported by
  `finalize` only after the run. Skeleton stamps (a model, or
  minutes/hours) keep their placeholders.

### Fixed

- The README's state box named the area test with the slug's hyphens
  (`tests/test_01_docs-per-case.py`); the stamped file has underscores. The
  line now names the file that exists.

## 0.88.0 — 2026-10-12

### Added — `protocol-fill --from-run`: the number is written back, never retyped

- **`protocol-fill PROTOCOL --from-run [RUN_ID]`** writes the Answer line,
  the Summary's Result line and the Runs entry from the run's
  `metrics.json` (the area's newest completed run by default): every
  reported key and value as recorded, plus the run_id — exactly what
  `--check` (`recheck.cited`) holds the protocol to. labkit's own keys
  (`duration_s`, `llm_retries`) stay out; a filled line is refused without
  `--force`; the stamped `<run_id>` placeholder becomes the entry.
- The counting and the full measure skeleton print that command after the
  run; the seconds lane and the area README name it. Why: twelve cold
  agents in the cloud (Fable, Sonnet, Haiku; 2026-10-12) typed the number
  into three lines by hand, every one named it as the retyping LAB-041
  Generate numbers, don't retype them forbids, and one `--check` failed on
  it.

## 0.87.1 — 2026-10-12

### Fixed — the gates agree with the 0.87.0 stamp: a count registers nothing and owes no table

The sixth cloud probe ran on the 0.87.0 stamp and hit two gates the cut had
not been told about (3m36s, one read of labkit source "because the gate
forced it"): `protocol-check` demanded `[[promise]]` tables the stamp
leaves out, and `runlog` refused the run for the criterion and the
admissibility condition the cut no longer carries.

- **`promises.promise_tables_owed` takes `registers`**: a protocol whose
  prose names no [C]/[A]/[B] id owes no tables unless it is frozen —
  there is nothing to hold (`promises.registers_ids`). protocol-check,
  runlog and finalize pass it; finalize says "n/a — the protocol registers
  no promise id" instead of blocking a count's run for a missing block.
- **The seconds gate of runlog is the question** — with a model named also
  criterion and admissibility condition (`protocol_check.seconds_registration_missing`).
- The seconds lane names the Result line as the summary; Limits and Next
  step belong to the full form.

## 0.87.0 — 2026-10-12

### Breaking — the seconds cut is what a count owes, and the stamp carries hints, not the guide

Three decisions after five cold-agent probes in the cloud (count task,
Fable, 0.85.0 → 0.86.2, 4m27s → ~2m10s; every agent named the same
cuts). Last version with the old seconds cut: 0.86.2.

- **A count registers no promise.** At `cost = "seconds"` without a model
  the stamp has no `[[promise]]` tables, and `Success / failure criterion`
  and `Admissibility condition` are not owed (`sm` fields: with a model
  they are, together with the C1/A1/A2 tables). Five agents each invented a
  tautological [C1] for a mean; the number is held by `--check` and
  `finalize` — `intent-check` has nothing to hold without ids.
- **The Summary at seconds is the Result line.** `Limits` and `Next step`
  belong to the full form; the after-run check and the cut agree
  (`protocol_check.unreported` takes the tier).
- **Every stamped placeholder is one line.** The template's placeholders
  carry the field guide's prose — a third of every probe's reading time;
  `scaffold.short_placeholders` keeps the label and a one-line hint,
  `protocol-check --guide` is the long form. The seconds stamp went from
  102 to 40 lines, the full form from 182 to 120.

## 0.86.2 — 2026-10-12

### Fixed — a path example in a code span is not a README placeholder

- **`finalize.readme_placeholders` ignores code spans and fenced blocks.**
  `` `<inputs>/<case_id>/` `` in an area README was read as a stamped
  blank; the fourth cloud probe (0.86.1, 2m09s, right and bound) spent a
  gate line, a reword and a second finalize on it.

## 0.86.1 — 2026-10-12

### Fixed — what the second cloud probe found (0.86.0: 2m28s, right and bound)

- **The counting skeleton writes its rows inside the run, each with
  `_prov.run`.** It wrote the file before opening the run, so finalize noted
  twelve rows without provenance on every seconds area.
- **`usability stage` installs the stamped requirements beyond labkit into
  the probe venv before freezing the lock** (`other_requirements`). The lock
  knew only labkit, the cloud venv came from requirements.txt with pytest,
  and runlog reported a drift on the first run — in both draws.
- **`Raw output` is owed only with a model** (`sm` in the template and the
  checker): a count has no prompt+answer pair to show; the probe filled the
  field with n/a.
- **`code-check` says at cost seconds that schema, gate labels and
  placeholders are not owed** instead of pointing at `--bundle`; the probe
  never found out what the bundle was or whether it mattered.
- **The seconds lane names `--show 2` only with a model, and the area README's
  state box names `--probe` only where the skeleton has one.** The counting
  skeleton has neither flag; the probe skipped both and said so.

## 0.86.0 — 2026-10-12

### Fixed — three defects of the seconds stamp, found by the first cloud probe

The first cold-agent probe in a claude.ai/code cloud session (count task,
labkit 0.85.0, no house directory, no skills): number right and bound in
4m27s, 0 reads of labkit source — and three of its five "what I would cut"
items were template bugs, not agent trouble
(`docs/usability/2026-10-12-cloud-fable-count-1.score.json`).

- **`labkit-init lab` stamps `pytest` into `requirements.txt`.** The
  stamped area test needs it, preflight and finalize run it, AGENTS.md
  names it — and the lab's requirements listed only labkit. The probe
  installed it by hand, which made runlog record a lock drift and cost a
  second run.
- **The seconds skeleton's function is `evaluate_rows`**, as in the full
  skeleton, the analysis script and the README route the stamp writes.
  It was `evaluate`, so finalize warned twice on every seconds area that
  the route names a function the script does not define.
- **The seconds cut without a model stamps no null-lane table.** `[[promise]]`
  A2 (the null condition) stood in every seconds protocol; without a model
  there is no null lane, and the probe deleted the table by hand. The
  example `constants = {…}` lines become one commented hint instead of
  vanishing: a count registers no threshold, but a criterion that names
  one must register it, and the probe read the promises docstring to learn
  the field.
- The protocol template's Terms field names the lab glossary by its new
  name, `notes/theorie/terms.md`.

## 0.85.0 — 2026-10-12

Four levers from reading uniagent's 23 preflight and 21 analysis audits
(2026-10-12): what the audits found is now data, what the stamp cannot
follow is a mechanical warning, a criterion that noise can fail is a scar,
and an audit at cost `seconds` before the first run says it is early.

### Changed — the scar table knows a criterion that noise can fail

- **New row in LAB-015's scar table, "Criterion fails on noise"**: a
  criterion on model output that one vote of a component the change does
  not touch can fail — every rejection counts, no majority over draws, no
  restriction to the component under test (uniagent area 26: [C3] fell to a
  single vote of an unchanged rule; the preflight audit, working the table,
  had no row for it). Audit column `preflight`, rules LAB-036 and LAB-016.
- **LAB-015 says what no audit sees**: model behaviour on the cases. In
  uniagent four criteria fell to it and no audit had flagged one; the probe
  for that is the instrument check on the boundary cases (LAB-008, LAB-014),
  not a second audit.

### Changed — `labkit-audit --mode preflight` says when it is early

- **At `cost = "seconds"` with no completed run** the command prints one
  WARNING on stderr and goes on: the first run is the cheaper probe, one
  audit in mode analysis after it covers the preflight rows (LAB-017 The
  number of audits follows the cost tier). uniagent area 01 had two
  preflight audits and an analysis audit at seconds; its protocol says one
  after the first run would have done.

### Added — `labkit-init lab` stamps the lab's glossary

- **`notes/theorie/terms.md`**, empty, with the four columns the
  standard's chapter 5 names (everyday word · lab term · code word · field
  term) and the pointer to LAB-084 Double-coinage check. The standard has
  said since 0.77.0 that this file is the one home of a lab term; nothing
  stamped it, and the house template still carried a "core glossary" table
  inside its inherited block — "fill this in" next to "edit the master, not
  here", empty in all nine labs (2026-10-12). The house block now points
  here; the table moves out of it.

### Added — static evidence: code the stamp cannot follow (`code-check` 1d)

- **`code_check.stamp_coverage_findings`**, run by `code-check` and by
  `preflight` station 3: a WARNING naming the line for a `sys.path` edit
  that does not point at `lib/` or `src/`, a dynamic loader (`importlib`,
  `runpy`, `exec`, `__import__`), a path string naming another area
  (`experiments/14-…/scripts/01_measure.py`) and an import that resolves to
  a repo file outside `lib/` and `src/` — code that determines the number
  and that the audit stamp does not see (LAB-019 The stamp covers
  everything that determines the number). Never a blocker. The stamped
  template's own `sys.path.insert(0, REPO / "lib")` is silent, and a
  loader inside a shared helper is not charged to every area that imports
  it. Why: in uniagent five audits (areas 15, 16, 17, 22, 23) found a
  script loaded from another area by reading; on the same areas the check
  now names the lines (15 and 16 load area 14, 16 and 22 load area 05).

### Added — audit findings as data (`labkit.findings`)

- **`labkit-audit --mode preflight|analysis` writes its findings into the
  area**: `audits/<date>-<mode>.toml`, an `[audit]` table (date, mode,
  model, scope sha, counts) and one `[[finding]]` per BLOCKER/WARNING/NOTE
  line, every one `status = "open"`. The person sets the status — fixed,
  accepted, deferred, dismissed — and a reason; `accepted`, `deferred` and
  `dismissed` without a reason do not read.
- **`preflight` has a station for it**: a finding still `open` is a
  warning before the freeze and a blocker once `frozen = true`; a
  `deferred` finding in any other area of the repo is printed as a
  reminder and never counted; an unreadable findings file is a blocker.
- Why: in uniagent a finding deferred in area 16 as "its own task" bit in
  area 17; the same finding was accepted three times; 13 of 44 audit lines
  end in accepted/dismissed and what they decided sits in a 400-character
  protocol line. Now the deferred ones stay visible and an audit's yield
  can be counted instead of read.

## 0.84.0 — 2026-10-12

### Added — `labkit-check`: is this repo current?

- **One command, five lines**: the pin (`requirements.txt` / `.lock`), the
  installed labkit against it, the newest release tag at the pin's source
  (a local checkout with `git tag`, a remote with `git ls-remote`;
  `--offline` skips the remote), the hook (`labkit-hooks check`) and every
  rule reference in the repo's `.md` and `.py` files (`labkit.rules
  check_refs`). Each line ends OK, STALE or UNDECIDED; exit 0 / 1 / 2. It
  reports and changes nothing: the pin is raised on purpose.
- Why: the three checks existed apart and were forgotten; nothing compared
  installed with pinned, and on 2026-10-12 the installed labkit lagged the
  pin in all four active lab repos. A commit pin is STALE — the house sync
  refuses it, and only a tag says which release a run used.

## 0.83.0 — 2026-10-11

### Changed — a cut ollama prompt fails loud

- **`num_ctx` in `models.toml`** for an ollama alias: the context window
  ollama allots, sent with every call (chat and raw). Unset, the server's
  default applies. On any other backend, or as anything but a positive
  integer, `resolve` raises — an OpenAI-compatible server sets its window
  at start and refuses longer prompts itself.
- **`llm.PromptTruncated`**: ollama fits a prompt longer than its window
  by dropping tokens and answers with HTTP 200 (0.23.1 on leguin: a
  25,272-character prompt at `num_ctx` 2048 read exactly 2,048 tokens).
  `complete` now raises when `prompt_eval_count` reaches `num_ctx`, or lies
  far below the prompt's length (more than 10 characters per token on a
  prompt of 4,000 characters or more). Not retried. A call that 0.82.0
  answered from a cut prompt raises under 0.83.0 — that answer was never a
  reading of the whole prompt.
- `labkit-audit` reports it as "no audit" (exit 2), like a backend failure.

## 0.82.0 — 2026-10-11

### Breaking — rule identifiers: `LAB` / `LOCAL` / `CODE` instead of `AS` / `HS` / `CS`

- **Three families, named by scope, not origin.** `LAB-nnn` is the shipped
  lab standard (was `AS-nnn`, for *Arbeitsstandard*), `LOCAL-nnn` a lab's
  own rules in its own ledger (was `HS-nnn`), `CODE-nnn` the coding style
  (was `CS-nnn`). Number for number: `AS-015 Preflight audit before
  freezing` is `LAB-015 Preflight audit before freezing`.
- **Hard cut, no alias, no reader of the old families.** `labkit.rules`
  knows only the new prefixes; `python -m labkit.rules show AS-015` fails
  under 0.82.0. 0.81.0 is the last version that reads `AS`/`HS`/`CS`;
  material written before the cut (frozen protocols, run snapshots,
  reports, this changelog) keeps its old identifiers and is reproduced with
  its commit and pin. The standard carries the one-time note in its
  *Identifiers* paragraph; identifier rule 3 (an id never changes) holds for
  the published families from here on.
- **The seven house numbers left the shipped ledger**: AS-002, -070, -073,
  -078, -080, -081, -099 live on as `LOCAL-002` … `LOCAL-099` in the
  authoring lab's ledger; `rules.tsv` keeps them as gaps (a new id is the
  highest ever given + 1, so they are never reused). The status `house` is
  gone with them.
- Every living file of the package follows: standard, ledger, code,
  templates, agent instructions, docs, tests. `docs/coding-style.md` is
  re-vendored from its master with `CODE-nnn`.

## 0.81.0 — 2026-10-11

### Added — what a call cost

- **`llm.last_usage()`**: the token counts of this thread's most recent
  completion as the backend reported them (`Usage`: prompt tokens with
  cache hits included, output tokens, the cached part, USD where the
  backend prices the call), `NO_USAGE` where it reported none; reset per
  attempt like `last_thinking()`. Every backend fills it: claude-cli from
  its JSON reply, ollama from `prompt_eval_count`/`eval_count`,
  OpenAI-style servers from `usage`.
- **`labkit-audit` prints it** on stderr beside the prompt size
  (`labkit-audit: tokens · prompt 61,234 (8,671 cached) · output 1,902 ·
  0.41 USD`) in every mode — the stamp's facts can carry what the audit
  cost. Why (2026-10-11): 30 Claude Code transcripts of labkit and
  uniagent summed to seven billion cache-read tokens, the old subagent
  audits at 3.65 M per audit, and no labkit line said what one call cost.
- **`agent_transcript.tokens`** reads the `usage` blocks of a Claude Code
  transcript (`Tokens`: calls, input, output, cache read, cache creation,
  the largest context one call read); `TranscriptTrace.tokens` carries
  it, `usability score --transcript` shows a `transcript · tokens` row and
  `usability trace` ends with a `tokens:` line.

### Breaking

- **claude-cli runs `claude -p --output-format json`** and reads the
  answer from the reply's `result` field; plain text on stdout, a reply
  without `result` or one with `is_error` is a `BackendError`. Callers
  see the same answer text as before. A test that fakes
  `subprocess.run` for this backend returns `{"result": "…"}` now
  (0.80.0 was the last version that took plain stdout).

## 0.80.0 — 2026-10-11

### Added — AS-103 The audit reads by declared scope, not by import graph

- **New rule in the standard, chapter 2A** (ledger row AS-103). The stamp
  covers everything that determines the number (AS-019); the audit reads
  what its question needs: the scripts, the files the `[[promise]]` tables
  declare as scope, and the repo-local modules those import directly.
  Deeper modules are the instrument's internals: an index, read on
  assignment.
- **`labkit-audit` builds the prompt that way.** `audit.gather` returns a
  `Reading`: code in full (scripts, analysis files, declared scopes,
  direct imports via `scope_sha.repo_imports`) and the indexed rest of
  `imported_repo_helpers`; `audit.module_index` renders path, line count,
  top-level signatures and the first docstring line under one
  `===== INDEX: … =====` piece. The auditor's `scope:` list names what it
  read in full; the command adds the indexed modules before holding the
  list to the stamp. A declared scope file that does not exist refuses
  the audit (exit 2). uniagent area 22: 444 kB → the scripts, one declared
  function's file, five direct imports and an index of the other ~30
  modules.

## 0.79.0 — 2026-10-10

### Breaking — `labkit-audit` is the one runner of the experiment-preflight audit

- **The Claude subagent copy of the instructions is gone.** AS-015 named two
  ways, the subagent `experiment-preflight` and the command; the standard
  now names the command only. The subagent read on its own (uniagent,
  50 audits: median 295k fresh tokens and 33 tool calls each, the standard
  read 88 times) and its copy drifted from the shipped text once
  (2026-10-07). Last version whose standard names the subagent: 0.78.0.
- **The auditor gets the rules its instructions cite, not the whole
  standard.** `audit.cited_rules` reads the `AS-nnn` ids from
  `experiment-preflight.agent.md` (AS-015 Preflight audit before freezing
  with the scar table and the severity legend, AS-017 The number of audits
  follows the cost tier, AS-004 Identifiers make the intent addressable,
  AS-050 Analysis audit before reporting) and inlines their blocks — about
  18 kB instead of 117 kB. A finding no rule names is "new class".
- **MODE analysis inlines the answering run's rows.** The instructions told
  the auditor to read the first 50 and last 20 output rows; the command
  never gave them (an auditor without tools read code alone). Now every
  output the run registered comes as `===== ROWS <path> … =====` with
  numbered rows (a row over 2000 chars cut and marked), plus the run's
  `metrics.json`; a protocol without an id or a run says so in one line.
- `labkit/templates/models.toml.template` stamps the alias `opus` the
  command calls by default (`claude-cli`, `claude-opus-5-5`).

### Fixed

- **`claude-hook pre-run` fires only on a file the command RUNS.** It
  matched every `.py` path in the command and read it for `runlog.run(`;
  in uniagent 85 of 272 hook lines in one session said a lib module
  "opens a run" because someone was reading it with `sed`, `cat` or a path
  in a heredoc. `claude_hooks.executed_py` now wants an interpreter before
  the file (flags allowed), a command-segment start, or `./x.py`.
- **`labkit-hooks` replaces every hook an earlier labkit wrote, under any
  event.** A jq one-liner running `protocol-check` on each PROTOCOL write
  (an install before `claude-hook post-change`) survived three installs in
  uniagent and doubled every report; `check` saw nothing because it looked
  for missing entries only. A hook command naming `claude-hook`,
  `protocol-check` or `notes-check` is labkit's: `check` names it with its
  event, `install` drops it (`install_hooks.stale_entries`).

## 0.78.0 — 2026-10-10

### Added — `labkit-init`: a lab repo and its areas from labkit's own templates

- **`labkit-init lab [DIR]`** lays out a lab repo: `AGENTS.md` (with
  `CLAUDE.md` pointing at it), `requirements.txt` pinning this labkit at its
  release tag on GitHub (`--labkit-ref` for a pushed commit), `models.toml`,
  editor and type-checker settings, `experiments/`, `data/raw` →
  `data/prepared`, `lib/`, `notes/{theorie,messung,results}`, and the guard
  test that the shared helpers resolve to the package. The lab standard is
  not copied; it comes with the pin.
- **`labkit-init exp <NAME>`** stamps an area — protocol (pilot part,
  `--report` for the † fields, `--cost seconds` for the seconds cut), script
  skeletons, README, the area's test — and `--explore` the entry before an
  area exists. Ported from the house scaffolder; its `sync`, thread and
  legacy-copy detection stay out.
- The templates ship in `labkit/templates/`; none names a house path.

### Changed

- **`usability stage`** stamps its probe repo with `labkit.scaffold`, not
  the house scaffolder under `~/.claude/resources`: the probe runs without
  the author's machine, and the stamped condition is labkit's own (English
  `AGENTS.md`, no copy of the standard). `scaffold_sha` hashes the scaffold
  and its templates.
- Messages and docs name `labkit-init exp` where they said `lib exp`.

## 0.77.0 — 2026-10-10

### Breaking — the lab standard ships with labkit, in English

- **`labkit/docs/standard.md` is the lab standard; `labkit/docs/rules.tsv`
  its ledger.** Both are package data. The German standard was translated
  block by block, reviewed and adapted for labs outside the author's house
  (`docs/standard-translation.md`). A lab refers to the standard through its
  pin, never a copy.
- **`labkit-audit` reads the packaged standard**, not the repo's
  `docs/arbeitsstandard.md`; the code-check bundle quotes the severity
  legend from it. Last version that reads `docs/arbeitsstandard.md`: 0.76.0.
- **Rule names in messages and docstrings are English** (`AS-015 Preflight
  audit before freezing`, was `AS-015 Preflight-Audit vor dem Einfrieren`);
  ids are unchanged. Last version with the German names: 0.76.0.

### Added — `labkit.rules`

- **The one home of the rule ledger, the head parser and three checks**:
  `check_registry` (heads against ledger), `check_ledger` (the ledger only
  grows), `check_refs` (every reference exists and names its rule).
  `python -m labkit.rules check | ledger | refs | show`; a house rule's
  number is listed with status `house`, and `show` says its text is not
  distributed; a row marked `moved:<where>` is left to the ledger it moved
  to. `tests/test_rules.py` holds every living reference in labkit to the
  ledger.

## 0.76.0 — 2026-10-09

### Added — `batch.Store.ledger`: the balance of an item-by-item run

- **Every input item on exactly one row, or the run does not complete.**
  `store.ledger(records, expect={...})` returns a `Ledger`: missing,
  duplicate, stray ids, rows without an id, and per expected field the
  rows that carry another value (`expect` takes a constant — a prompt
  hash — or a function of the row's input record — an item hash).
  `ledger.counts()` goes into `run.metrics`; `ledger.require_complete()`
  raises SystemExit naming every gap, and raised inside
  `with runlog.run(...)` it keeps the run from writing completion.json and
  its runs.tsv row. Guaranteed tier: exact, by id. Whether a row's answer
  is valid stays the experiment's. Before, scripts hand-rolled this
  (fallacy-dataset-generation, area 01) because `status` only reported.

## 0.75.1 — 2026-10-09

### Fixed — `batch.Store.status` names duplicate ids

- **A doubled row no longer hides a missing one.** `status` counted the
  output's ids as a set, so a file with one item missing and another on
  two lines looked whole. It now lists ids on more than one row under
  `duplicate` (absent when there are none). Found in
  fallacy-dataset-generation, area 01, whose script had hand-rolled the
  balance for exactly this case.

## 0.75.0 — 2026-10-09

### Added — `labkit-calltree`

- **The call tree of one real run, cut to the command's package.**
  `labkit-calltree labkit-audit -- <args>` (or `module:function`) runs the
  command under a profiler and prints, per call path, `module.qualname
  path:line ×N` — only functions of the target's top-level package; one
  called through the stdlib hangs under the nearest package function. The
  editor's call hierarchy says what code could call; this says what one
  run did, from the entry point down. Stdlib `trace --trackcalls` gave a
  flat edge list across every module. A reading aid, not a check: no tier.

## 0.74.4 — 2026-10-09

### Changed — Terms before the question

- **The Terms field is the first field of the Intent**, in three parts per
  word — *everyday word · house term · code word*. Four cold readers met
  every house term 60–90 lines before its definition while the field sat
  under Context, after Result. Template and field guide; the checker reads
  the field by label, so protocols written before keep theirs where it is
  (no standard bump). The README names the home of each kind of word:
  tool (this README), method (the lab standard), lab (`notes/theorie/
  begriffe.md`), protocol (Terms).

## 0.74.3 — 2026-10-09

### Fixed

- **`preflight .` / `finalize .` find the area's test.** A relative area
  path has no `.name`; the test pattern read `tests/test_.py` and the
  area's own test counted as absent ("no tests/test_.py — the resolution
  check has no permanent form"). `area_tests` resolves the path first.
  Found on a thesis repo, 2026-10-09.

## 0.74.2 — 2026-10-09

### Changed — entry points and docstrings (part 3 of the cold reading)

- README: the Terms table now defines promise, criterion, admissibility,
  branch, binding, answering run, derived run, scope hash vs stamp, and
  freezing; "five layers; the first and the last cannot be forgotten";
  `runlog`, `preflight`, `usability`, `labkit-audit` lines say what they
  list or are not (`labkit-audit --mode preflight` is the agent audit, not
  the `preflight` gate).
- architecture: six links, one row per check, each row named by what it
  checks; `intent-check` placed at both stages it runs.
- runlog: the file list carries outputs.json and completion.json; the
  index refers to `RUN_INDEX_COLS`; `_prov` / `continues` / `derived_from`
  contrasted in one table; `Run.__init__` lists its ten refusals in order
  with their exception types; `_finalize` says output problems are notes
  and `completed` vouches for the record, not the outputs.
- batch.Store names its two modes; finalize names station 1's checks with
  their grades and station 5 as "frozen source and tracked files", the
  summary line says "review the warnings above"; preflight's stations are
  numbered 1–7 flat, the printed-never-counted lines marked, the early end
  on an unparseable head named; scope_sha says exactly what the stamp
  covers and what not; intent-check's exit codes 0/1/2 documented.

## 0.74.1 — 2026-10-09

### Changed — names (part 2 of the cold reading)

One word, one thing. Every reader in the package, its tests and docs
renamed with it; no alias kept.

| was | is | because |
|---|---|---|
| `protocol_check.id_in_head` | `id_in_git_head` | it reads git HEAD, not the protocol head |
| `promises.PromiseBlock` | `PromiseTables` | "block" is also the whole ```toml block |
| `promises.block_owed` | `promise_tables_owed` | same; the docstring now holds the owed table |
| `promises.registered_ids` | `ids_in_prose` | "registered" is also the data side |
| `protocol_check.intent_missing` | `seconds_registration_missing` | "intent" is also the promise ids |

`protocol_check` no longer repeats the owed condition around the call;
`finalize` no longer shadows `dataclasses.field` with a local.

## 0.74.0 — 2026-10-09

Four cold readers over the package (code-clarity, one per layer, 38
findings): what a newcomer gets wrong. This release fixes what was
behaviour, 0.74.1 the names, 0.74.2 the entry points and docstrings.

### Breaking

- **Run state `unreadable`.** A run whose config.json cannot be read was
  listed as `corrupt` — the word for completion.json without
  metrics.json. It is now `unreadable` (`runs.run_facts`,
  `runlog.active`, `runlog` listings, `FAILED_STATES`); a reader of the
  state no longer has two meanings for one word. Last version with the
  shared word: 0.73.1.

### Changed

- **`AnsweringRun.run_dir` is None whenever `blocker` is set.** A newer
  run with an unreadable binding returned the older run's directory next
  to the blocker; a caller reading only `run_dir` took a run the function
  forbade. `reports_intent_keys` (new) is False when no bound run reports
  an intent key and the newest was taken anyway: `finalize` blocks (a
  probe or producer run is not an answer — only when the protocol
  registers ids), `intent-check` says so.
- **A run directory exists only with its config.json.** Git, environment
  and model alias are read before mkdir; a failure while writing the
  record removes the directory. Before, the leftover read as `legacy`.
- **`protocol-check` names the should-fields** a pilot still owes in its
  pilot note; the `missing (should)` loop that never printed is gone.
- **`labkit-audit`** prints a NOTE when the report lists BLOCKER/WARNING
  lines while the verdict line sums to zero; the verdict line still
  decides (an auditor may correct itself).

## 0.73.1 — 2026-10-09

### Added

- **Arm lines in `Model / tool`, held by finalize.** A protocol that
  compares two profiles names them — `Arm \`before\`: register/profiles/x.toml
  @ <fingerprint>, model=<alias>` — and `finalize` warns when the profile
  file is missing, or the fingerprint or alias is not in the answering
  run's config.json (the profile changed after the stamp, or the run did
  not record it). Optional: no arm line, nothing checked. Template and
  field guide say the form; the diff between the profiles goes verbatim
  under Prompt. Asked 2026-10-09: "what are before and after?" — the
  answer sat 60 lines below the criterion and the fingerprint only in
  the run.

## 0.73.0 — 2026-10-09

### Added

- **`labkit-audit --mode clarity` — a newcomer's reading of an area.** The
  code-clarity agent's area mode ships with the package
  (`code-clarity.agent.md`): README, protocol and `scripts/01_measure.py`
  read in the order a person opens them, findings only where that reader
  would get the behaviour wrong (template residue, a term before its
  definition, a docstring that omits a conjunct, a case id without its
  kind, two languages with no shared word), each with its line and the
  smallest fix; `verdict: N findings (M would be answered wrong)`. Exit 1
  on findings, 0 on none, 2 on no reading. Static evidence: it stamps
  nothing and never blocks; `preflight` names it as due before freezing.
  Measured first on uniagent area 18 (10 findings, 6 wrong readings; the
  README's template residue on top).

## 0.72.3 — 2026-10-09

### Added

- **A resumed output file names the run it continues.** `batch.row_runs`
  reads which runs wrote a JSONL file's rows (`_prov.run` per row);
  runlog records per output `rows_from` (run_id → rows) and `continues`
  (the runs whose rows the file already held), and `completion.json`
  carries `continues` — "this run continues that one" stands in the
  record, not only in the rows. `finalize` holds every JSONL output to
  the run: rows may come from the run itself, from the runs it continues,
  or — for a derived run — from its derived_from lineage; rows from any
  other run are a blocker (a file of two measurements), rows without
  `_prov` a note. Additive keys; older records read as before.

## 0.72.2 — 2026-10-08

### Added

- `finalize` warns when the answering run called a model (`llm_retries`
  recorded or `model_calls` > 0) and no run in its lineage recorded
  `models_resolved` — the alias was not under `model`/`*_model`
  (`finalize.model_provenance_gap`). `labkit-params` marks a resolved
  model spec recorded under another key (`judge`) as static evidence:
  recorded, not provenance labkit holds. Neither reads the old key.

## 0.72.1 — 2026-10-08

### Added

- **`Answering run` field** in the protocol's Result block: one run_id a
  person reads instead of deriving it from the answer line (round 15: the
  fresh run was named, not the derived one that answers). A projection of
  `runs.bound_answering_run`, never a second binding: `finalize` refuses
  the line when it names another run, warns while it still says "none
  yet"; `protocol-fill` writes it. Protocols without the line are unaffected.
- Template: the Summary opens with `Question †`, the Result is its answer;
  `Deviations after freeze` beside the pre-freeze `Changed`; the head's
  legend points to `protocol-check --contract` for what a tier owes.

## 0.72.0 — 2026-10-08

### Breaking

**Protocol standard 0.19: this labkit reads standard 0.19 only.** What
the standard changes: **every reportable run is held to a registration
that is data** — a frozen protocol and every full run (`long=True`; at
`cost = "seconds"` every run) owe the `[[promise]]` tables, and a run
records every registered constant unchanged. Only an unfrozen pilot
(`long=False`) runs without tables; `finalize` blocks an answering run
that recorded none. The seconds cut is a registration in prose AND in
tables, so the machine chain (block digest, scope hashes, constants)
holds for every run a number is reported from.

Versions, two statements kept apart: the last version that *reads*
`standard = "0.18"` is 0.71.0; the last version that *runs the 0.18
contract* is **0.70.0** — 0.71.0 enforced the new rule on 0.18 protocols
and is a transitional release, not one to reproduce an old registration
with. A protocol stamped under 0.18 stays unchanged and is checked, run
and reproduced with the repo's commit and labkit ≤ 0.70.0. A repo may
raise its pin regardless, since the hooks check only staged protocols —
only an edit to an old protocol at the new pin is refused (`[protocol]
standard = "0.18", this labkit reads "0.19"`). Two standards in one
labkit would be a legacy path; `standard` is stamped and never edited.

## 0.71.0 — 2026-10-08

### Breaking

**Frozen protocols require promises, and every promised constant must be
present and equal in the run config.** Last permissive version: 0.70.0.

- `frozen = true` without a `[[promise]]` table is a MUST failure in
  `protocol-check`, a blocker in `preflight` and `finalize`, and `runlog`
  refuses every run bound to such a protocol before `mkdir` — not
  acknowledgeable (`promises.promise_tables_owed`, the one home of the rule).
- `runlog.run(config=...)` under a block refuses the run before `mkdir`
  when a registered constant is missing from `config` or carries another
  value — type-strict (`True` is not `1`, `1` is not `1.0`). The record
  therefore guarantees: every registered constant, unchanged. Whether the
  formula uses it right stays the agent audit's question.
- A constant is named like the config key it is recorded under —
  `^[a-z][a-z0-9_]*$` — and stands in exactly one promise;
  `promises.parse_block` refuses `MIN_F1` and a name declared twice.
  `promises.all_constants(block)` is what a script passes to its config
  object. `constant_records` moved from `intent_check` to `promises`.
- `intent-check`/`finalize`: a registered constant absent from the record
  is a finding (it was invisible); the message names the last permissive
  version for old runs.
- The protocol template stamps the tables (`[C1]` margin, `[A1]`
  max_empty, `[A2]` null_band_items, scope `scripts/01_measure.py`); the
  measure template builds its `MeasureConfig` from them
  (`promises.all_constants(promises.load(PROTOCOL))`), the stamped test
  holds every registered constant to a field. A `--quick` stamp keeps the
  tables without constants.

### Rollout

Only forward: an existing frozen protocol is a registration — adding
tables to it is a new registration, not a migration. Repos with frozen
protocols without tables (uniagent 01–14) stay on their pin (0.70.0) and
raise it when a new area starts there; `finalize` would otherwise block
their frozen areas.

## 0.70.0 — 2026-10-08

### Breaking

- **A derived run records no model resolution.** `runlog.run(...,
  derived_from=...)` leaves `models_resolved` empty: its rows are the
  parent's, and resolving the alias under today's `models.toml` recorded a
  provenance the rows never had. `runs.model_provenance_run(run_dir)` walks
  `derived_from` to the run that recorded the model (None when none did,
  loud on a missing ancestor or a loop). Last version resolving on derived
  runs: 0.69.1.

### Added

- **`labkit-params <AREA> [--run ID] [--protocol FILE]`** — the values the
  answering run ran with, one table: the protocol's registered constants
  against the record (equal / different / missing), every recorded config
  key, the model that answered (from the `models_resolved` of the run that
  recorded it, walking `derived_from`), and UPPER_CASE module constants
  the record does not carry. Each row names its home and its tier; the
  view claims nothing about the record's completeness (round 13: "where
  to start" between protocol, script and runs).
- `intent_check.constant_records` (states equal / different / missing);
  `promised_constant_mismatches` reads `different` from it, unchanged.
- `repo.choose_protocol(area, protocol, tool)` — finalize's choice of the
  area's protocol, now shared.
- `finalize` step 4 warns when the area's README has no
  `<!-- labkit:route -->` block, or the block does not name the protocol,
  `runlog`, `labkit-params`, `scripts/01_measure.py:evaluate_rows` and
  `config.json`, or the script defines no `evaluate_rows`
  (`finalize.readme_route`). The README points; it copies no question,
  answer, run id or threshold — a hand-written formula pointer went stale
  within a day (area 08, 2026-10-08). The stamp writes the block.

### Changed

- **One choice of the run that answers**: `runs.bound_answering_run(area,
  pid)` → `AnsweringRun(run_dir, skipped_newer, exclusions, blocker)`;
  `intent-check` and `finalize` present its outcome instead of choosing
  twice (`run_facts`, `bound_runs`, `newest_with_intent_keys`,
  `newer_unreadable` moved from `intent_check` to `runs`).

## 0.69.1 — 2026-10-08

### Added

- `finalize` step 4 warns on stamped `<…>` placeholders left in the area's
  README (`finalize.readme_placeholders`): a README that still carries the
  stamp's blanks tells a reader nothing and looks as if it did (round 11).

## 0.69.0 — 2026-10-08

### Added

- **A run records the command that started it** (`command` in
  config.json, `sys.argv`), and **`runlog <area>` lists the finished runs**
  after the open ones: one line per run — a fresh run of the script or
  derived from which run (its rows re-evaluated), the commit and whether
  there were uncommitted changes (and how large the patch is), and the
  command — the facts a person returning to an area collected from
  config.json keys and a patch file and got wrong (code-navigation
  round 11: 1 of 8). `runs.run_summary` is the one reader of those facts.
  Runs from before 0.69 show "(not recorded)" for the command.

## 0.68.2 — 2026-10-08

### Changed

Found by the new `code-clarity` agent (dotfiles) on finalize:

- The module docstring numbers the steps like `finalize_area`, 0 to 7,
  flat (it still said "2b" and "4b").
- One word, one thing: the measurement run is `measurement_run` in every
  station, not `run_dir` beside it; the collector of blockers and warnings
  is `Findings`, not `Gate` (the gate is the whole command).
- The provenance step says "n/a — protocol cost is not 'seconds'" instead
  of "not a run of seconds", which used "run" for the protocol's cost tier
  three lines from the measurement run. The only output change; exit codes
  unchanged on five areas.

## 0.68.1 — 2026-10-08

### Changed

- Every run artefact has one loader in `runs.py`, each refusing a wrong
  shape with a sentence naming the file (`ArtefactError`): `read_metrics`
  (an object), `read_outputs` (typed `OutputEntry` rows as `runlog` writes
  them, None when the run registered none), `read_completion` (an object).
  finalize, recheck and runlog read through them instead of parsing the
  JSON in place; `completion_state` still decides a run's state by its
  markers. finalize output unchanged on four real areas.

## 0.68.0 — 2026-10-08

### Breaking

Last version with the old names: **v0.67.1**. Python names only.

- One public name, one thing: `preflight.run` is `preflight_area` (beside
  `finalize_area`; `runlog.run` stays the run writer experiments call),
  `protocol_block.load` is `parse_toml_block` (`promises.load` stays the
  script API), `notes_check.collect` / `protocol_check.collect` are
  `collect_notes` / `collect_protocols`.

### Added

- `tests/test_architecture.py` holds the code to the map: it reads the
  layer table of `docs/architecture.md`, fails when a module is missing
  from it or imports upward, and when a public name other than `main` /
  `cli` stands in two modules. The table now lists `cold_reader`,
  `protocol_reading` and `code_navigation` as tools and `install_hooks` as
  a gate (preflight checks the hooks are there).

### Changed

- ruff: every signature annotated (`ANN`, tests exempt), every public
  module, class and function documented (`D1xx`), complexity capped
  (`C901`, 19 functions carry a visible baseline marker); pyright strict
  for `cold_reader`, `code_navigation`, `protocol_reading`.
  `runs.is_alive` answers None for a script name that is not text instead
  of crashing.

## 0.67.1 — 2026-10-08

### Fixed

- **A metrics.json that is not a JSON object could pass the guaranteed
  intent check:** `["c1_pass"]` read as metrics reported `c1`. One loader,
  `runs.read_metrics`, refuses anything but an object with a sentence
  naming the file (`MetricsError`); intent-check, finalize, recheck, runlog
  and usability all read metrics through it (intent-check's own copy and
  its second, direct read are gone).
- `criterion_n_input_mismatches` no longer takes `true` for a count of 1.
- The test fixture for a dead run no longer uses pid 1, which lives in
  many containers; it takes the pid of a process that has ended.

## 0.67.0 — 2026-10-08

### Breaking

Last version with the old names: **v0.66.1**. Python names only.

- `finalize.run` is `finalize_area`; its `run_dir` is `measurement_run`,
  and its plan says once what a measurement run is. A person reading the
  function took "no run" for "the protocol is missing": the function, the
  experiment's run and the variable all said "run".
- `finalize.provenance_owed` is gone: the condition stands where it
  decides, `if head.cost != "seconds"`. Behind a negated helper name the
  same person read that provenance is checked for cost = hours.

### Changed

- The last line of `finalize_area` says what `report` returns (1 if any
  step found a blocker, else 0). Output and exit codes unchanged on six
  areas, two without a run.

## 0.66.1 — 2026-10-08

### Changed

- `finalize.run` shows the whole flow and every condition that decides
  whether a step runs: its docstring is a flat-numbered plan (0 to 7, each
  with its condition, and that a blocker never stops a step), and the body
  carries the `if`s — skip without a run, provenance only for seconds, the
  only early end at step 0. The stations print no header and check no
  `None` any more; a station that needs a run takes `run_dir: Path`. Why:
  a person answering behaviour questions (code-navigation round 8) missed
  exactly the conditions that sat one level down, in both earlier
  versions; sub-numbers like "2b" confused. Output and exit codes
  unchanged — compared on seven real areas and on two areas without a run
  (cost seconds and hours).

## 0.66.0 — 2026-10-08

### Added

- **`usability human`** — a person answers behaviour questions about a
  repo at the keyboard: one question at a time with numbered choices, the
  time per question, optionally how many questions went to an assistant
  meanwhile (`--count-help`); the verdict (right, missed, invented) only at
  the end, written to `<out>.human.json`. The logic (`human_session`,
  `parse_picks`) takes its input and clock as arguments and is tested.

## 0.65.1 — 2026-10-07

### Added

- Behaviour answers are scored beyond right/wrong: the right choices an
  answer **missed** and the ones it **invented** (a dependency or a path
  the code does not have).
- `usability nav --shuffle SEED` draws the question order from a seed, so
  agents compared across two versions of the code do not all meet the
  questions in one order.

## 0.65.0 — 2026-10-07

### Added

- **`usability nav`: behaviour questions** (`[[choice]]`). A question about
  how the code behaves — what still runs when a step fails, which step a
  later one depends on, which condition yields which exit code — answered
  by picking from a fixed set of choices and scored by exact set match;
  a truth outside its choices refuses at load, an answer outside them at
  scoring. Built to test whether an orchestrator that reads as named steps
  is understood better, not only found faster. A question file may now
  hold only flows or choices.

## 0.64.1 — 2026-10-07

### Changed

- `usability.load_probe_run` reads a staged probe and its latest run once
  (`ProbeRun`: probe, run, config, metrics, the protocol it names, whether
  it is bound by id, the cost tier); `score` and the reading probes use it
  instead of each reading probe.json, config.json and metrics.json
  themselves (the last open finding of the 0.64.0 audit). Scores of the
  round-9 probes recomputed: identical.

## 0.64.0 — 2026-10-07

Worked off a code audit of everything changed since 0.58.1 (two fresh
reviewers, correctness and structure; every finding checked in the code).

### Breaking

Last version with the old names: **v0.63.2**. Python names only; no file
format changes.

- `protocol_reading.score_answer` is `score_reader_answer`, `score_glance`
  is `score_glance_answer`; `code_navigation.score` is `score_nav_answer`,
  `prompt` is `nav_prompt`; the usability handlers are `cmd_reader`,
  `cmd_read_score`, `cmd_glance`, `cmd_glance_score`, `cmd_terms`,
  `cmd_nav`, `cmd_nav_score` (the console commands are unchanged).
- `finalize.check_intent_ids` is `check_intent_keys_in_metrics` — it was a
  second function of the same name as `code_check.check_intent_ids`, doing
  something else.
- The scorers refuse instead of scoring wrong: a yes/no given as a string
  ("true"), a pass flag in metrics.json that is not true/false, a named
  number missing from metrics.json, a place that is not "path:line", a
  flow answer that is not a list of strings, a line-range truth outside
  its file, a flow step pattern that does not compile (refused at load,
  before the agent runs).

### Fixed

- Terms coverage matches a term as a word of its own ("RAG" no longer
  occurs in "paragraph") and keeps short abbreviations (CI, N), which were
  dropped; a Terms link with an anchor (`g.md#x`) is read. Today's
  measurements were rechecked: none changed.
- `nav-score` finds an absolute path inside the repo; two flow steps named
  in one answer item both count.
- `finalize`: every blocker and warning goes through `Gate.block` /
  `Gate.warn` — blockers of the completion station and open fields now
  print with the same `BLOCKER:` / `warning:` prefix as the others.

### Changed

- New module `labkit/cold_reader.py`: what every cold-reader probe shares
  (the newcomer persona, the answer hand-off, loading and reading the
  answer) — it was copied three and four times.
- Module docstrings of `protocol_reading` and `usability` name everything
  they hold; docstrings for the finalize stations and the new dataclasses.

## 0.63.2 — 2026-10-07

### Changed

- `finalize.run` reads as its seven stations, one call each
  (`check_completion` … `check_criterion_n`), over a `Gate` that collects
  blockers and warnings; the decisions inside got names and tests of their
  own — `choose_protocol`, `answering_run`, `cited_run_mismatch`,
  `provenance_owed`. Output and exit codes are unchanged, checked line by
  line on six real uniagent areas. Why: CS-006 One function, one thing —
  and keep I/O at the edges (210 lines of stations separated by section
  comments, the data each station depends on hidden in shared variables),
  not findability — code-navigation round 5 found the inline version
  followed without a miss.

## 0.63.1 — 2026-10-07

### Changed

- `usability nav-score` counts an answer whose path names a file by its
  tail alone (`runlog.py` for `labkit/runlog.py`) when that tail names
  exactly one file in the repo; an ambiguous tail does not count. Round 6:
  one agent found all five places and dropped the package folder from
  every path, scoring 0/5.

## 0.63.0 — 2026-10-07

### Added

- **`usability nav`: line ranges and flow questions.** A truth may be a
  line range (`path:L120-L135`) for logic that has no name of its own — a
  range holds for the commit it was read on. A `[[flow]]` question asks for
  an entry point's steps in order and is scored by how many registered
  steps the answer names in the registered order. Built to test whether an
  entry point that reads as a sequence of named steps is easier to follow.

## 0.62.0 — 2026-10-07

### Breaking

Last version with the old names: **v0.61.0**. Run records and protocols do
not change (the recorded key `declared_scope_sha` stays); only Python
names do.

- `protocol_block.HEAD_FIELDS` is `PROTOCOL_HEAD_KEYS` — the settings at
  the end of every protocol, told apart from the run's `config.json`.
- `scope_sha.imported_lib` is `imported_repo_helpers` — the helper files
  the area's scripts import, told apart from one promise's declared-scope
  digest (`promises.declared_scope_sha`, whose docstring now says so).
- `intent_check.constant_findings` is `promised_constant_mismatches`;
  `finalize.criterion_n_findings` is `criterion_n_input_mismatches` — two
  checks against what a run recorded, named for what they compare.

### Added

- `preflight.area_test_python` — the interpreter that runs an area's tests
  has a name of its own (was four lines inside `area_tests`).

Why: in code-navigation round 3 a weaker reader (Haiku) found 5 of 10 in
labkit against 9 of 10 in uniagent; every labkit miss sat at one of these
pairs or at the unnamed interpreter choice (CS-015 Make the code findable
by name; `docs/usability/2026-10-07-code-navigation.md`).

## 0.61.0 — 2026-10-07

### Added

- **`usability nav` / `nav-score`** (`labkit/code_navigation.py`) — how
  fast a newcomer finds their way in a repo's code. A cold agent gets
  questions that describe a behaviour, never a name, and answers each with
  `path:line`; the truth is a function, class or module-level name in a
  TOML question file, resolved from the source with `ast` (a truth that no
  longer exists refuses to score). Effort comes from the agent's
  transcript: calls by tool, files opened, seconds. Built to measure before
  a navigation rule enters the coding style.

## 0.60.1 — 2026-10-07

### Changed

- The Summary's Result says whether the bar set before the run was met:
  four readers of the first ten lines took the number and the limit away
  from the 0.59 probes but not the verdict (the uniagent Summaries, which
  said it, were read right).

### Fixed

- `protocol_reading.entry_for` returned the first line that mentioned a
  term — often a protocol's pointer to the glossary — so the explanation
  judge saw no definition. It now splits the glossary into entries (a
  bullet with its continuation, each `*term* — …` inside a Terms line) and
  takes the one whose label names the term; a shorter label inside the
  term ("Position" in "Positions-Zuordner") no longer wins.

## 0.60.0 — 2026-10-07

### Added

- **`usability glance` / `glance-score`** — a reader who sees only the first
  ten lines of the file, as they are (head or form text using them up is
  the finding). `protocol_reading.glance` reports the excerpt's characters
  beside its lines (one field per long line holds more than a wrapped one)
  and, mechanically, which Summary fields begin inside it. Round 9 showed
  that asking a whole-protocol reader what it knew at line ten is
  self-report.
- **`usability terms`** — the reader's unclear terms against two layers: a
  term in the Summary must be plain there; a term elsewhere may occur in
  Terms or in a glossary note Terms links. Occurrence is static evidence;
  `terms_judge_prompt` asks a reader whether the entry explains the term.
  Ids match as patterns (digit runs → NN).

## 0.59.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.58.1**.

- **A protocol with a documented run owes a Summary for a person:**
  `Result` (at most two plain sentences carrying the question, no ids, keys
  or run_ids), `Limits` and `Next step` — on every tier, seconds included
  (they are in the seconds cut). `Status` is gone; `Next step` moved from
  Follow-up into the Summary (protocols that have it in Follow-up keep it
  valid). A protocol with a run but no `Limits` fails protocol-check, and
  the message names the missing field instead of "Result/Raw output".
- **The stamped protocol opens with the Summary;** the pointer to the
  field guide and the toml head stand at the end under `## Head`.
  protocol-check reads the head anywhere; the Head section counts neither
  as template text nor as form before the first field.

### Changed

- The criterion's placeholder shows how an id is written (`[C…]` with its
  number, C1 → `c1_pass`); a writer missed it in round 8.
- The cold reader (`usability reader`) is a newcomer, not a colleague, and
  answers checkable questions — the number, whether the criterion held,
  whether admissibility held — that `read-score` holds to the run
  (`protocol_reading.Truth`), plus what it understood after ten lines.

## 0.58.1 — 2026-10-07

### Added

- **`llm.last_thinking()`** — the reasoning trace of this thread's most
  recent completion (ollama `thinking`, OpenAI-style `reasoning_content` /
  `reasoning`), "" when the backend returns none; reset before every
  attempt, so a call never shows a previous call's trace. labkit read the
  field and dropped it; uniagent could not explain a false classifier answer
  afterwards because only the answer was kept.

## 0.58.0 — 2026-10-07

### Changed

- **Less form in front of a reader.** The stamped toml head carries keys
  only — what each key means is in the field guide. `Analysis audit †` is
  no longer stamped at `cost = "seconds"`: there the audit comes when the
  number is promoted or steers a decision, and the field is added then.
- **Terms of this protocol asks for the writer's own coinages**: constants,
  lanes or arms, item and case ids, the model alias.

Cold readers of round 7 (`docs/usability/2026-10-07-protocol-reading.md`)
could place the writers' results; most of what they could not place came
from the stamped form, the rest from unglossed coinages.

## 0.57.0 — 2026-10-07

### Changed

- **Protocols open with the answer for a person.** The stamped protocol
  starts with a three-line pointer and the toml head; the legend (cuts,
  † fields, intent ids, rule references, budgets) moved into
  `protocol-field-guide.md`. The Summary lists **Result** first: at most
  three plain sentences, result not procedure, the limit inside the
  sentence, no ids, keys or run_ids. "One field, one line" became "one
  field, one statement": more than two items as a list or a small table
  under the label; the Answer field gives the verdict per id, the run_id
  and the numbers as a table. Labels are unchanged; existing protocols
  stay valid.
- The auditor's MODE analysis adds two `READ` points: a Summary that does
  not open with the result (or carries ids and keys), and a `·` chain of
  more than two items.

From a reader's assessment of uniagent's protocols ("strong in content,
read like audit papers for the system"): about 65 lines of form came
before the first sentence for a person.

## 0.56.0 — 2026-10-07

### Changed — may block where 0.55.0 passed

- **A frozen protocol owes its area test.** `preflight` turns a missing
  `tests/test_<NN>_<name>.py` from a warning into a blocker once
  `frozen = true` — the permanent resolution check (AS-016) is a gap like
  any other at the freeze.
- **`finalize` runs the area's tests, on every tier.** A failing test is a
  blocker before a number is reported; a missing one is no finding there.
  At `cost = "seconds"`, where preflight is not owed, this is the only
  place they run.

### Fixed

- Area tests are found by the stamped name (`test_<NN>_<name>.py`, split
  files `test_<NN>_<name>_*.py`), no longer by `test_*<name>*.py`: area 08
  of uniagent ran area 09's test, whose name extends its own.
- Area tests run with the repo's interpreter (`.venv/bin/python`), not the
  caller's: a gate started from another venv failed them on a missing
  package.

## 0.55.0 — 2026-10-07

### Added

- **A session log, for debugging what an agent did before a run.** Every
  `claude-hook stop` appends one line to the repo's
  `.git/labkit-sessions.jsonl` (inside .git: local, never committed):
  session id, transcript path, time, and the runs made since that
  session's previous stop. `claude-hook sessions --run RUN_ID` finds the
  session — and so the transcript — a run came from.
- `usability score --archive DIR` keeps a probe's transcript (gzip),
  timeline and score; `usability trace` reads a `.jsonl.gz` as well.
  Claude Code deletes transcripts after `cleanupPeriodDays` (30 by default).

## 0.54.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.53.1**.

- **`src/` is a repo-local root beside `lib/`, and imports resolve to the
  module, not the package.** The audit stamp and the key search follow
  `import a.b`, `from a import b` and `from a.b import c` to the module and
  the `__init__.py` files on the way — no longer every file of a package.
  A repo whose measured code lives in `src/` (uniagent) gets a stamp that
  finally covers it; any repo importing from a package gets a narrower,
  exact one. Either way an existing `preflight_audit` stamp reads as
  changed: restamp after looking, or re-audit.

### Fixed

- **`code-check` finds registered keys in imported repo code.** It read
  only the area's scripts, so a key written in `src/measure/comparison.py`
  made four promises "absent" — blockers against correct code, found on
  the first real upgrade (uniagent 0.45 → 0.53).

## 0.53.1 — 2026-10-07

### Fixed

- **`labkit-hooks install` no longer erases a repo's own hook.** A
  `.githooks/pre-commit` that labkit-hooks did not write is kept as
  `pre-commit.before-labkit` (a second one refuses), and the versioned hook
  runs the repo's own `.githooks/pre-commit.local` when it is executable —
  the repo owns that file, labkit-hooks never writes it. Found on the first
  real upgrade (uniagent): its hook ran a replay test of runs 07/08.

## 0.53.0 — 2026-10-07

What six rounds of cold-agent probes (`docs/usability/2026-10-07-remeasure.md`)
and one reader's feedback on a frozen protocol turned up.

### Changed — may block where 0.52.0 passed

- **The prompt drift check runs on stamped areas.** `PROMPT` constants are
  computed statically (names, `+`, f-strings, `str.join` over a constant);
  the skeleton's `PROMPT = "..." + ANSWER_LINE` used to be unreadable, so the
  check never ran on a stamped area. Every fenced block under the Prompt
  field counts (one block per variant is a written form). A prompt it
  cannot compute is a WARNING, never a silent pass.

### Added

- `protocol-fill PROTOCOL --prompts` writes the Prompt block from the area
  scripts' `PROMPT` / `PROMPT_<VARIANT>` constants.
- `protocol-check` names stamped list placeholders left behind (`- <run_id>
  — <…>`, `- <…>`) and warns on a field that references another area
  without a link ("wie Bereich 07").
- `code-check`, `finalize`, `preflight` and `runlog reindex` take an area
  by its bare name as `lib exp` prints it (`01-<name>` or `<name>`).
- `usability score --transcript F` and `usability trace F`: what a probe
  agent did, measured from its session transcript (`agent_transcript`);
  `usability stage` stamps each task as the house route does and writes
  `<dir>.prompt.md` (the repo's CLAUDE.md first, as a session loads it).
- The auditor agent's MODE analysis adds `READ` lines on the protocol's
  readability; they enter no verdict.
- Field guide rule 8 (write for the reader who opens only this file) and a
  legend line in the template; the template names `protocol-fill` and the
  safest placebo for a null lane.

### Fixed

- `runlog`'s lock check reads an editable install's freeze line (`-e
  git+…#egg=labkit`) and compares it with the checkout's HEAD; a lock
  written by `pip freeze` no longer reports drift against itself.
- At `cost = "seconds"` only the cut's fields count as open placeholders,
  and fields written after the run only once a run is documented.
- `finalize` and `protocol-check` repeat their blockers in the last lines.
- `protocol-fill` reads fields through `protocol_check.fields` (one parser;
  `protocol_fill.open_fields` is gone — use
  `protocol_check.placeholder_fields`).
- "no such area" names the directory a relative path resolved against.
- `--contract` opens with the seconds cut and marks its lists as the full
  form.


### Changed (rule references)

- **Rule references are AS-/CS- code + name.** Messages, the shipped
  protocol template, the field guide and the auditor agent cite rules of the
  Arbeitsstandard as `AS-015 Preflight-Audit vor dem Einfrieren` instead of
  `§2.A12` (the ledger is `~/.claude/resources/rule-registry.tsv`; every old
  §-id stays resolvable as an alias in the register). A finding line's rule
  field reads `AS-nnn <title>`; `labkit-audit` never parsed that field, so
  nothing breaks. Dated records in `docs/usability/` keep their §-ids.

## 0.52.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.51.0**.

- **The audit stamp follows every import form, transitively.** `from lib
  import x`, `import lib.x`, `from lib.x import y`, relative imports inside
  `lib/` and packages are resolved from the syntax tree, and a lib module's
  own imports are followed; `from lib import scoring` used to be read as a
  module `lib`, so lib/scoring.py could change under an unchanged stamp.
  Stamps of areas importing that way move. Code that does not parse refuses
  the stamp instead of a guess.
- **A function scope includes its decorators**: `@cache` → `@retry` moves
  `declared_scope_sha`. Runs recorded with a decorated scope function show
  that scope as changed.
- **batch** raises on an unparseable line anywhere but the last (file and
  line named); a torn last line is cut before a resume appends.
- **Run metadata is checked for shape** in `read_run_config`: not an
  object, a non-integer `schema_version` or a malformed `protocol` binding is
  a `RunConfigError`, not a later AttributeError.

### Added

- `labkit-audit` holds the auditor's `scope:` list against the stamp and
  warns on every file only one side names.
- The `dev` extra carries the coding style's tools: `pytest`, `ruff`,
  `pyright`; a one-off usability script is excluded from ruff.

### Fixed

- The suite writes no lease into `~/.labkit` (`tests/conftest.py`), and the
  `ps` integration test skips where `ps` is missing.

## 0.51.0 — 2026-10-07

### Added

- `labkit-hooks install|check`: the hooks come with the pinned labkit —
  `.githooks/pre-commit` (protocol-check, finalize --if-reported, guard
  test), `git core.hooksPath` (a manual step per clone before, so the hook
  silently did nothing) and the claude-hook entries in
  `.claude/settings.json` (foreign hooks and keys kept). Each hook names the
  labkit version that wrote it; rerun `install` after a pin raise.
  `preflight` warns when hooks are missing or from another version.
- `claude-hook stop`: before the agent ends its turn, every protocol
  changed in the session whose answer cites a run goes through `finalize`;
  blockers send the agent back (exit 2), once per stop.

## 0.50.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.49.1**.

- **A full run checks its audit line.** At minutes/hours `preflight_audit`
  must name the `scope sha` the area's code has now (`labkit-audit` and
  `scope-sha` print it), or say `n/a — <reason>`; a line without a stamp,
  or with the stamp of code that changed since, refuses the run. The line
  was written by hand and never checked — an invented or stale audit looked
  like a real one. `protocol-check` warns on the same drift (after the run
  analysis scripts change legitimately). `scope_sha` moved to layer 1.

### Added

- `finalize --if-reported PROTOCOL...` — the commit gate: every protocol
  whose "Answer to the question" cites a run goes through finalize; the
  house pre-commit hook calls it. `finalize` also blocks when the answer
  cites another run than the one the checks hold. Nothing showed whether
  finalize ever ran before a number entered the history.

## 0.49.1 — 2026-10-07

### Changed

- A promise scope given as an absolute path is refused: scopes are relative
  to the protocol's directory (`../../lib/x.py` stays allowed).

### Added

- `code-check` warns (static evidence) when a declared scope sets a promise
  constant itself as a literal — `MIN_MEAN = 1.4` against 1.5 in the block —
  instead of reading `promises.constants()`.

### Fixed

- Field labels in numbered lists (`1. **Unit:**`) are read; fields inside a
  multi-line HTML comment are not.
- A bare label with sub-bullets or an indented paragraph below it is filled,
  not a placeholder (found migrating the thesis starter's example).
- `usability score` on an unreadable run, `intent-check --metrics` on a legacy
  run and a numeric `standard` end in a sentence that says what to do.
- `protocol-check` scans the repo's protocol ids once per invocation.
- The type checker reads the repo's own `.venv` (`[tool.pyright]`); the 19
  errors it then showed are fixed — two test classes overwrote
  `TestCase.run` with a path.

## 0.49.0 — 2026-10-07

### Breaking

Last version with the old behaviour: **v0.48.1**.

- **Stricter fields.** A placeholder is `<…>` (opened and closed), `TODO`,
  a bare `n/a — <why>` or an empty label without a code block; `TODO`
  used to count as filled. Every † field is owed: Intent/Setup ones at
  freeze, Summary/Result ones once frozen and a run is documented (new
  level `report`, Analysis audit included). `Data / scope`, `Unit` and
  `Model / tool` are musts in the full form. `frozen = true` at cost
  seconds is a must finding.
- **A full run on an unstamped protocol id is refused** before the run dir
  exists.
- **The promise digest** is over the promises as read (normalized) and
  recorded with its format; a run from 0.46/0.47 is reported as such, not as
  "the promises changed".
- **One audit stamp**: `scope_sha.area_stamp` (scripts, imported `lib/`,
  extra files, pin; paths relative to the repo root) feeds `scope-sha`,
  `preflight` and `labkit-audit`. Stamps from earlier versions differ.
- **Vendored flat copies are gone**: the `except ImportError` fallbacks for
  student repos had stopped working (modules they needed were never
  copied) and are removed. A student repo pins labkit or stays on its copy.

### Fixed

- A newer run with an unreadable `config.json` is no longer passed over
  silently: `intent-check` and `finalize` refuse the older choice.
- A deleted or unparsable declared scope, a renamed protocol (recheck now
  finds it by id), a non-table `[[promise]]` entry, an unreadable head in
  `usability score` and a broken parent in `derived_from` end in a
  sentence, not a traceback.
- `LABKIT_UNFROZEN`, `LABKIT_DETACHED` and `LABKIT_NO_ENDPOINT_LEASE` act on
  `1` only; `0` used to count as set.
- A ```toml example inside a prompt's code block is no second head; fences
  nest by marker length.
- runlog freezes a directory source (digest over visible files, rows =
  files); `repo.layout_root(".")` climbs.
- `protocol-check` no longer reports comment lines or open placeholders as
  left-over template text.

## 0.48.1 — 2026-10-07

### Fixed (audit of 0.48.0)

- `finalize` judged a different run than its own intent-check: intent-check
  skips newer runs without intent keys (a probe), the other stations took
  the newest bound run. One choice now feeds every station — scope drift,
  provenance and the `c1_n` check ran on the probe and said all clear.
- Ids in the letters K/S/W/N passed `intent-check` as "no intent ids
  registered" with exit 0, every promise unchecked. They are now refused:
  a MUST finding in `protocol-check`, exit 2 in `intent-check` — detected,
  never read.
- A field value written on the line below its label (`- **Question /
  hypothesis:**` + indented text) read as unwritten, so the seconds gate
  refused a written registration. Field values now include their
  continuation lines.

## 0.48.0 — 2026-10-07

### Breaking

Last version that reads the old formats: **v0.47.0**. A repo with frozen
protocols in the old head, runs without `schema_version` or an old run
index stays on its pin until new work starts there.

- **The protocol head is data** (TODO 8). `Standard`, `Protocol id`, `Type`,
  `Cost`, `Frozen before run` and `Preflight audit` moved from prose lines
  into the `[protocol]` table of the protocol's one ```toml block (Standard
  0.18), read by the new `labkit.protocol_block` — `tomllib`, exact keys,
  typed values. A typo is an error naming the field: `Cost: second` used to
  read as undeclared and so as `hours`. A protocol without the table is
  refused by every command.
- **Prose fields by exact template label.** `protocol-check` holds each
  field by its label (`protocol_check.FIELDS`), not by keywords searched in
  the whole file: a word anywhere satisfied a field (`prompt` in a sentence
  covered "Model I/O"), a narrow word failed a filled one (`**Terms:**`). A
  test binds `FIELDS` to the template and the seconds cut to its markers.
  "Answer to the question", "Raw output" and "Analysis audit" are owed after
  the run (the run-unreported check), no longer before it. Removed:
  `check_text`, `graduate`, `severity_of`, `cost_tier_of`, `FROZEN_YES`,
  `TYPE_MEASUREMENT`, `protocol_identity`, `protocol_check.protocol_id_of`
  (`intent_check.protocol_id_of` stays, reading the head), `criterion_present`; new: `check_fields`, `fields`, `owed`.
- **The promise digest covers the `[[promise]]` tables only** (canonical
  JSON), not the block text: freezing or stamping the audit line in the
  head must not read as a changed promise. Runs recorded under 0.46/0.47
  carry the old digest; `recheck` against them reports a changed block.
- **Legacy paths removed:** the intent letters K/S/W/N (only C/A/B are
  ids); protocols below Standard 0.16 and the area-based run choice
  (`choose_legacy`, `gate_metrics`, `latest_metrics`, `runs_by_intent_keys`);
  runs without `schema_version` (state `legacy`, never `completed`);
  `runlog migrate-index`; the measurement short form (`Type: measurement`
  — the seconds cut replaced it); the old admissibility words (`stop
  rule`, `kill`, `Abbruch`); `intent_check.ledger_ids`.
- An unstamped protocol id binds nothing: `intent-check` needs `--metrics`,
  `finalize` reports a blocker.

## 0.47.0 — 2026-10-07

### Changed

- **Template and field guide speak C/A/B** (TODO 7): the protocol template
  stamps `[C]` criterion, `[A]` admissibility condition, `[B]` registered
  branch, with keys `c1_pass`, `a1_pass`, `b1_branch`. The field "Stop rule"
  is now "Admissibility condition", "Registered fork" is "Registered
  branch"; null conditions and anchors carry `[A]` ids. `protocol-check`
  accepts the new label; the old labels (`stop rule`, `kill`, `Abbruch`) and
  the letters K/S/W/N are still read and go with the legacy release (TODO 8).

### Added

- `labkit-audit <AREA> --mode preflight|analysis`: the experiment-preflight
  audit as a command through `labkit.llm` (any `models.toml` alias, default
  `opus`), synchronous with a timeout; the instructions ship with the
  package (`experiment-preflight.agent.md`). Exit 1 on a blocker OR a
  warning, 2 when no audit could be made.

## 0.46.0 — 2026-10-06

### Breaking

Last version with the old names: **v0.45.0**.

- **Run read side moved to `labkit.runs`.** `is_alive`, `run_state`,
  `read_run_config`, `RunConfigError`, `completion_state`,
  `completed_runs`, `FAILED_STATES` are no longer in `labkit.runlog`.
  `runlog._is_alive` and `runlog.is_alive` are one name: `runs.is_alive`.
- **`promises.scope_sha` is `promises.declared_scope_sha`.** Runs record
  `config.json → promises.ids.<id>.declared_scope_sha` (was `scope_sha`).
  The area audit stamp `scope-sha` is unchanged.
- **`code_check.find_protocols` / `find_repo` are `repo.area_protocols` /
  `repo.layout_root`.**

### Stricter (correct inputs pass as before; these now fail loud)

- A v2 run with `metrics.json` but no `completion.json` is no longer
  chosen or accepted by `recheck`, `runlog.Run(derived_from=…)`,
  intent-check's choice for protocols without an id, or `usability score`.
- An unreadable `config.json` shows as `corrupt` in `runlog`, makes
  `runlog --wait` and `runlog reindex` exit 2, and is listed, never chosen,
  by intent-check. An unreadable `metrics.json` ends intent-check with exit
  2 instead of falling back to an older run.
- A git failure inside a repository raises `repo.GitError`; it used to read
  as an empty answer ("clean tree").
- `runlog` no longer swallows an unreadable protocol and names a malformed
  `Protocol id:` in its warning.
- Promise block (protocols that carry one):
  - `code-check` / `preflight` block a malformed block, a declared scope that
    does not resolve, and a declared key that appears nowhere in the code.
  - `finalize` blocks a declared scope changed since the run.
  - `recheck` refuses a note whose promise block or declared scope changed
    since the run.
  - `intent-check` / `finalize` report a block constant the run recorded
    under the same name with another value.
- `finalize` holds `c<i>_n` to the recorded inputs like `k<i>_n`.
- `llm` calls `claude -p` with `--tools ""`: a judgement runs without the
  CLI's built-in tools, so a prompt that says "read <file>" cannot send the
  model to its working directory instead of the inlined text.

### Added

- `labkit.promises`: the promise block — one fenced TOML block of
  `[[promise]]` entries (id `C`/`A`/`B`, key, sentence, declared scope,
  constants); `runlog` records its digest and a hash per declared scope.
  Contract: `docs/promise-block.md`.
- `labkit.runs` (read a run), `labkit.repo` (area protocols, repo root,
  git), `protocol_check.protocol_identity` (one reading of `Protocol id:`).
- `code-check` reads intent keys passed as keyword arguments
  (`r.metrics(c1_pass=…)` drew a false blocker before).
- `endpoint_lease`: atomic record writes under a directory `flock`; an
  unreadable record counts as busy for `UNREADABLE_GRACE_S`, then is
  removed with a message.
- `AGENTS.md` (with `CLAUDE.md` as a symlink), `docs/architecture.md`,
  `docs/coding-style.md` (vendored), `pip install -e '.[dev]'` for tests.

### Unchanged behaviour, new structure

- `intent_check._main` dispatches to `choose_explicit` / `choose_bound` /
  `choose_legacy`; `llm._complete_once` dispatches to one adapter per
  backend.
