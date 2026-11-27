# Gate stations — what each station calls, what it can tell, and the way out

Generated, do not edit: `python -m labkit.tools.gate_stations` writes this page from the source, and `tests/test_gate_stations.py` holds it equal to what the command writes. After a change to a gate's stations or to a finding site run the command again (`just overview`).

How to read it. A gate is a function that numbers its stations in comments; a station's title is that comment, which states when the station runs. *Calls* are the functions the station's code calls that tell a finding or reach one, each with the first sentence of its docstring. *At this station* lists the finding sites in the station's own code (the *Function* column then names the gate itself) and in those functions; *further down* lists the sites these functions reach through the call graph. *Tells* is the constant text of the site's message, every value as `{…}`, on one line and cut to 90 characters (`…` marks the cut). *Next* is the way out the site names as data — its constant text, or in backticks the expression that builds it; `—` where it names none that way (a BLOCKER always names one; a warning's message may still say what to do). *Rule* is the rule assignment the finding records as data: a rule of the standard by id and name, `technical contract` (a condition no rule of the standard covers), `open assignment` (the rule is not decided yet), `variable` (the cause passes the assignment in, so the scan cannot read it) or `not recorded` (an exit records none). *Commands whose code reaches it* counts labkit's console scripts only; a gate none of them reaches is called by an area's own script.

Its limits. The call graph resolves names, not values: *further down* is a static estimate that names sites the station cannot reach at run time (a function named is followed whether or not the branch that calls it runs; a class named counts for each of its `__dunder__` methods; a name given two classes in one function reaches the methods of both). A method called on an object is followed where annotations tell the object's class — a parameter, a return value, a dataclass field; a method called on any other object is missed, and so are a subclass's override of a method its annotated base has and a function found by a computed name; a path back through the gate's own function is not followed. A site under several stations is listed under each. Which condition a site holds is established by reading its function; the tests that reach a site stand in [the checks overview](checks-overview.md). A gate that numbers no stations (`protocol-check`, `code-check`, `labkit-audit`) is not on this page. The order of the gates and what each holds: [The gates in order](architecture.md#the-gates-in-order).

## `finalize.finalize_area` — `labkit/gates/finalize.py`

Run finalize on an area.

Commands whose code reaches it: `claude-hook`, `codex-hook`, `finalize`, `labkit-adopt`, `labkit-init`, `labkit-next`, `report-check`.

### finalize.finalize_area · 0. protocol and settings — the only early end

Calls:

- `finalize._refuse` — Step 0's early end told: on the console (CONSOLE_OUTPUT) a refusal with WHY; in a passed collector a blocker with its way out FIX and RULE, so the caller (report-check) can name it.
- `finalize._inputs` — The area's state and audit evidence for finalize's stations: the caller's when it built them for its check run (report-check), else built here once — finalize on the console is its own entry.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `finalize._refuse` | BLOCKER | GUARANTEED | variable | {…} | `fix` |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |

### finalize.finalize_area · 1. answering run — the run every later step examines

Calls:

- `finalize.station_answering_run` — Station 1: the run every later station holds the protocol to — chosen from STATE (the area's state, `area_state.Measured.answering`), shown, and held to the run the head declares (`[result] run`).

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `run_record_check.single_draw` | WARNING | GUARANTEED | technical contract | the draws of {…} cannot be counted: {…} | — |
| `run_record_check.single_draw` | WARNING | GUARANTEED | LAB-036 Validate, don't trust a single run | {…} is one draw — no spread: `scripts/01_measure.py --repeat-of {…}` draws it again, `02_… | — |
| `run_record_check._own_record_unbacked` | BLOCKER | GUARANTEED | LAB-027 Model discipline | {…}'s call log holds {…} of alias `{…}` ({…}), but its models_resolved does not name `{…}… | `_name_alias_fix(alias)` |
| `run_record_check._derived_run_calls` | BLOCKER | GUARANTEED | LAB-027 Model discipline | {…} — yet its call log holds {…} call{…} of alias `{…}` that asked the model | `_fresh_run_fix(alias, parent)` |
| `run_record_check._derived_run_calls` | BLOCKER | GUARANTEED | LAB-027 Model discipline | {…} — yet its call log holds {…} of alias `{…}` stored outside any run{…}, which no recor… | `_fresh_run_fix(alias, parent)` |
| `run_record_check._stored_answer_unbacked` | BLOCKER | GUARANTEED | LAB-027 Model discipline | {…}'s call log holds {…} of alias `{…}` stored by run {…}, but {…} — no record says which… | `repair + ( _fresh_run_fix(alias, None) if derived_from is not None else _name_alias_fix(alias) )` |
| `run_record_check.stand_in_findings` | WARNING | GUARANTEED | LAB-027 Model discipline | {…}: fixed answers stored with `llm_cache.store_stand_in`, not answers of a model — its n… | — |
| `run_record_check.model_provenance_findings` | BLOCKER | GUARANTEED | technical contract | model provenance: the call log of {…} does not read — {…} | restore the file as the cache wrote it (`{…}` where git holds it), or {…} |
| `run_record_check.model_provenance_findings` | BLOCKER | GUARANTEED | technical contract | model provenance: {…} has no config.json — which model it recorded cannot be read | restore the run record as runlog wrote it (`{…}` where git holds it), or {…} |
| `run_record_check.model_provenance_findings` | WARNING | GUARANTEED | technical contract | model provenance: the stand-ins behind {…} cannot be counted — {…}; the result line canno… | restore the named record as runlog wrote it, or {…} |
| `run_record_check._metrics_model_findings` | WARNING | GUARANTEED | technical contract | model provenance: the lineage of {…} is broken — {…} | — |
| `run_record_check._metrics_model_findings` | WARNING | GUARANTEED | LAB-027 Model discipline | {…} called a model, but no run in its lineage recorded models_resolved — record the alias… | — |
| `run_record_check.row_provenance_findings` | BLOCKER | GUARANTEED | technical contract | row provenance: the lineage of {…} is broken — {…} | `measure_anew(answering_run.parent.parent)` |
| `run_record_check.row_provenance_findings` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | `measure_anew(answering_run.parent.parent)` |
| `run_record_check.row_provenance_findings` | BLOCKER | GUARANTEED | LAB-057 One area per idea | {…}: {…} row(s) from {…} — a run this run neither is, continues nor derives from; a file … | {…}, into an output file of its own — a new name for the output in the measuring script, e.g. `{…}`; keep {…} and its runs, never delete it: those rows are the other runs' evidence |
| `run_record_check._continued_with_other_code` | BLOCKER | GUARANTEED | open assignment | {…}: {…} row(s) come from {…}, which ran other code (script {…}, this run's {…}) — {…}'s … | measure anew into an output file of its own — a new name for the output in the measuring script, e.g. `{…}` — keep {…} and its runs, then audit that run |
| `run_record_check.arm_findings` | WARNING | GUARANTEED | technical contract | arm `{…}`: the protocol names {…}, no such file under {…} | — |
| `run_record_check.arm_findings` | WARNING | GUARANTEED | open assignment | arm `{…}`: the protocol names fingerprint {…}, the answering run recorded no such value —… | — |
| `run_record_check.arm_findings` | WARNING | GUARANTEED | LAB-027 Model discipline | arm `{…}`: the protocol names alias {…}, the answering run recorded no such alias | — |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | variable | {…} | `self.way_out` |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key | `way_out` |
| `finalize.choose_answering_run` | BLOCKER | GUARANTEED | LAB-043 Runs go through `runlog` | no stamped protocol id ([protocol] id) — no run is bound to it | stamp the area with `labkit-init exp <name> --kind …`, which writes a fresh id, and carry the protocol's text over |
| `finalize.choose_answering_run` | WARNING | STATIC_EVIDENCE | open assignment | {…}: bound to this protocol and newer by name than the adopted run {…} — if one of them a… | — |
| `finalize.unreportable_warnings` | WARNING | GUARANTEED | variable | the answering run {…}: {…} — its number cannot be reported (report-check refuses it) | — |
| `finalize.declared_run_gaps` | BLOCKER | GUARANTEED | technical contract | {…} | `{…}` removes it; audit the run that answers, then `{…}` writes the table for it |
| `batch.Store.__enter__` | exit | none | not recorded | {…} exists — another run is writing this output: {…} {…} | — |

### finalize.finalize_area · 2. the registration as the first measurement recorded it — with a run

Calls:

- `registration_station.station_registration` — Hold the answering RUN to its workflow's registration (`workflow_and_holds`, read from STATE, the area's state built once); a note when it holds — what the workflow held —, and one per field a correction released (`corrected_in_place`), so the release names what changed and why.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `run_record_check.code_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: its runs cannot be followed ({…}) | `measure_anew(answering_run.parent.parent)` |
| `run_record_check.code_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | restore {…} as runlog wrote it (`{…}` where git holds it), or {…} |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…} cannot be compared with what {…} ran: the area lies in no git repository now | `measure_anew(area)` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | `measure_anew(area)` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…} cannot be read now: {…} | repair what the error names, then `{…}` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} no longer imports it, so it is not what reads the answers | `measure_anew(area)` |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | {…} recorded no script — the code behind its number cannot be compared | `measure_anew(area)` |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | {…}, with the script where it is now; only when it was moved or deleted by mistake, restore it from {…} |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran it — its number came from other code | {…} (`cp {…} {…}`) |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | the code {…} ran cannot be read now: {…} | repair what the error names, then `{…}` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran it (it was untracked; the run kept it as {…}) | {…} (`cp {…} {…}`) |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-010 Commit before the run | {…}, so the helpers its script imports ({…}) cannot be compared | in the repository, {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…}, so the helpers its script imports ({…}) cannot be compared | in the repository, {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} started from a tree with changes ({…}), and its uncommitted.patch is gone: the commit… | restore {…} from git or a backup, or {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} {…}, so the helpers its script imports ({…}) cannot be compared | `f"{PATCH_CONTRADICTION_WAY}: {measure_anew(run_dir.parent.parent)}"` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} started at commit {…}, which this clone does not hold | fetch it (`git fetch --unshallow` in a shallow clone) or {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | the tree {…} started from cannot be read for {…}: {…} | `measure_anew(run_dir.parent.parent)` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} is in neither {…}'s commit nor its uncommitted.patch, so it cannot be compared with w… | commit {…}, then {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran | {…} (`git -C {…} cat-file blob {…} > {…}`) |
| `area_state.unread_start_warning` | WARNING | GUARANTEED | technical contract | {…} — nothing is taken from a start file that does not read | restore the file from the commit that holds it (`git log --all -- <area>/run-starts/<run_id>.json` names it); where no commit holds it, leave it as it is: no value is written into a start file by hand, the protocol and the kind are read from the run's own record where that reads, and the start stays unknown |
| `area_state.missing_start_warning` | WARNING | GUARANTEED | technical contract | {…} | `START_FILE_BACK` |
| `area_state.unassigned_record_warning` | WARNING | GUARANTEED | technical contract | the record of run {…} does not read, and neither a start file nor the run index names it:… | `RECORD_BACK` |
| `exploration_hold.unknown_step_hold` | BLOCKER | GUARANTEED | technical contract | the step a run was measured under cannot be told: {…}{…} — the comparison with its basis … | make it readable: the run's record or its uncommitted.patch restored from git or a backup, the commit from a clone that holds it (`git fetch`), then `{…}`; where it cannot be read back at all, {…}; or {…} |
| `exploration_hold.step_gap_hold` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | run {…} made the step "{…}" on {…}, and its declared changes are not the differences of t… | write the step as the texts stand (`{…}` computes the changes), measure again and audit that run — {…} keeps the text it ran under; or, {…} |
| `exploration_hold.unstepped_holds` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | run {…} was measured without a step, and its registration differs from the first measurem… | declare the step (`{…}`, or on another run it builds on), measure again and audit that run — {…} keeps the text it ran under; or, {…} |
| `exploration_hold.live_holds` | BLOCKER | GUARANTEED | variable | what the number is about changed after the answering run {…}: {…} (as the protocol stands… | {…}measure the change as a step on {…} (`{…}`, then the run, its audit and its adoption); or restore {…} as {…} saw them{…}{…}; or, {…} |
| `registration_hold.registration_changes` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | the first measurements recorded different registrations: {…} — which one stood before the… | either {…}; or {…} |
| `registration_hold.registration_changes` | BLOCKER | GUARANTEED | variable | the registration changed after the first measurement {…}{…}: {…} (recorded by the answeri… | restore the [[promise]] tables as {…} registered them ({…}){…}, and measure again, then audit that run (the earlier runs stay); or, when the registration cannot be answered as written, {…} — the earlier protocol, its runs and their verdict stay |
| `registration_hold.types_split_hold` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | the first measurements registered different types: {…} — which workflow binds the runs ca… | either {…}; or {…} |
| `registration_hold.type_hold` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | the type changed after the first measurement {…}: "{…}" → "{…}" ({…}) — the workflow that… | put `type = "{…}"` back as {…} registered it{…} — and measure again where a run measured under the change —; or, for the other workflow, {…} — the earlier protocol, its runs and their findings stay |
| `registration_hold.release_unchecked` | BLOCKER | GUARANTEED | technical contract | whether a correction in place releases what the number is about cannot be checked: {…} | `exc.fix or f"repair what the sentence names, then `{gate_command('finalize', area)}`"` |
| `registration_hold.seen_hold` | BLOCKER | GUARANTEED | variable | what the number is about changed after the first measurement {…}{…}: {…} (as the answerin… | `fix` |
| `registration_hold.split_hold` | BLOCKER | GUARANTEED | variable | the first measurements saw different texts of what the number is about: {…} — {…} — which… | either {…}; or {…} |
| `registration_hold.now_hold` | BLOCKER | GUARANTEED | variable | what the number is about changed after the first measurement {…}{…}: {…} (as the protocol… | `fix` |
| `registration_hold.unread_hold` | BLOCKER | GUARANTEED | technical contract | what the number is about cannot be compared with its first measurement: {…} — the compari… | make it readable: the commit from a clone that holds it (`git fetch`), the repository's missing objects restored (`git fsck` names them), a run's uncommitted.patch restored from git or a backup, then `{…}`; where it cannot be read back at all, {…}; or {…} |
| `registration_hold.unread_history_hold` | BLOCKER | GUARANTEED | technical contract | {…} — the runs and start files a commit holds were not read back, so whether a start file… | {…} (`{…}`); where they cannot be restored, {…} |
| `registration_hold.binding_conflict_hold` | BLOCKER | GUARANTEED | technical contract | which protocol a run belongs to is contradicted: {…} — no file is taken over another, so … | make the files agree with what happened: the run's own record back from a commit, a clone or a copy that holds it; a start file a commit holds restored from that commit, never edited; a wrong row of runs.tsv corrected by hand, never deleted; then `{…}`; where that cannot be settled, {…} — the earlier protocol, its runs and their verdict stay; or {…} |
| `registration_hold.missing_start_hold` | BLOCKER | GUARANTEED | technical contract | {…} — which protocol it was bound to at its start and when it started cannot be checked, … | {…}, then `{…}`; where nothing keeps it, {…} — the earlier protocol, its runs and their verdict stay; or {…} |
| `registration_hold.lost_record_hold` | BLOCKER | GUARANTEED | technical contract | what the number is about cannot be compared with its first measurement: {…} — {…} may hav… | bring the record back where something keeps it — the run's directory with its config.json, from a commit, a clone or a copy that holds it (a record written anew from memory settles nothing) —, then `{…}`; where nothing keeps it, {…} — the earlier protocol, its runs and their verdict stay; or {…} |
| `registration_hold.later_record_warning` | WARNING | GUARANTEED | technical contract | {…} — the start files put {…} after that of a measurement of this protocol that reads, an… | `RECORD_BACK` |

### finalize.finalize_area · 3. intent-check — always

Calls:

- `finalize.station_intent_keys_in_metrics` — Station 3: every registered intent id reports as a key of the answering run's metrics.json, a branch as one of its registered outcomes (intent-check).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `finalize.station_intent_keys_in_metrics` | BLOCKER | GUARANTEED | technical contract | intent-check: {…} | repair what the sentence names; `{…}` holds it alone |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `intent_check.hold` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} | `INTENT_FIX` |
| `intent_check.hold` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} | `INTENT_FIX` |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…}: [{…}] declares key '{…}', which the run does not report. | `INTENT_FIX` |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | variable | {…}: {…}. | `INTENT_FIX` |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} | `INTENT_FIX` |
| `intent_check.unregistered_outcomes` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…}: [{…}] records {…} = {…}, which is none of its outcomes' names | record one of {…} — the name of the outcome whose condition holds, as [[promise]] {…} writes it: fix the code, then `{…}` |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | variable | {…} | `self.way_out` |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key | `way_out` |

### finalize.finalize_area · 4. the run's code and the declared scopes — only with a run

Calls:

- `finalize.station_run_code` — Station 4, first half: the code that produced the answering run's number, and that of every run it derives from, is the code here now (`run_record_check.code_since_run`), for every kind — a fix after the run with no new run would leave the old code's number standing.
- `finalize.station_declared_scopes` — Station 4, second half: a promise's declared scope edited after the run: today's code is not the code that produced the number.
- `finalize.station_answer_reading` — Station 4, third part: each run of the answering run's lineage that declares its answer reading (`answer_reading`) is held to its parent beyond the code (`run_record_check.answer_reading_gaps`): the prompts field of PROTOCOL as each run started under it, and the answer file both registered.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `finalize.station_run_code` | WARNING | GUARANTEED | technical contract | {…} | — |
| `finalize.station_answer_reading` | BLOCKER | GUARANTEED | technical contract | the prompts {…} re-reads with cannot be held to {…}'s: {…} | restore what the sentence names, or {…} |
| `finalize.station_declared_scopes` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} recorded no promise block: {…} — a run records the block it was measured under, so th… | a block added after the run is a new registration: {…} |
| `finalize.station_declared_scopes` | BLOCKER | GUARANTEED | variable | declared scope cannot be compared with what {…} recorded: {…} | {…}, then `{…}` |
| `finalize.station_declared_scopes` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | declared scope changed since {…}: {…} | rerun before reporting: `{…}`, then audit that run |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `run_record_check.code_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: its runs cannot be followed ({…}) | `measure_anew(answering_run.parent.parent)` |
| `run_record_check.code_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | restore {…} as runlog wrote it (`{…}` where git holds it), or {…} |
| `run_record_check.answer_reading_gaps` | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | {…} re-reads the answers of {…}, but the prompts field differs from the text {…} was meas… | `anew` |
| `run_record_check.answer_reading_gaps` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} registered none of the files {…} registered as its output — a derived run re-reads it… | register the answer file {…} wrote in the derived run (`r.output(...)`), or {…} |
| `run_record_check.answer_reading_gaps` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…}: {…} registered sha256 {…}, {…} {…} — the answers changed after {…} ran | restore the file as {…} registered it (`git log -- {…}` names its commits), or {…} |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…} cannot be compared with what {…} ran: the area lies in no git repository now | `measure_anew(area)` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | `measure_anew(area)` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…} cannot be read now: {…} | repair what the error names, then `{…}` |
| `run_record_check._reading_since_run` | BLOCKER | GUARANTEED | technical contract | {…}: {…} no longer imports it, so it is not what reads the answers | `measure_anew(area)` |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | {…} recorded no script — the code behind its number cannot be compared | `measure_anew(area)` |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | {…}, with the script where it is now; only when it was moved or deleted by mistake, restore it from {…} |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran it — its number came from other code | {…} (`cp {…} {…}`) |
| `run_record_check._run_code` | BLOCKER | GUARANTEED | technical contract | the code {…} ran cannot be read now: {…} | repair what the error names, then `{…}` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran it (it was untracked; the run kept it as {…}) | {…} (`cp {…} {…}`) |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-010 Commit before the run | {…}, so the helpers its script imports ({…}) cannot be compared | in the repository, {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…}, so the helpers its script imports ({…}) cannot be compared | in the repository, {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} started from a tree with changes ({…}), and its uncommitted.patch is gone: the commit… | restore {…} from git or a backup, or {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} {…}, so the helpers its script imports ({…}) cannot be compared | `f"{PATCH_CONTRADICTION_WAY}: {measure_anew(run_dir.parent.parent)}"` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} started at commit {…}, which this clone does not hold | fetch it (`git fetch --unshallow` in a shallow clone) or {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | the tree {…} started from cannot be read for {…}: {…} | `measure_anew(run_dir.parent.parent)` |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | technical contract | {…} is in neither {…}'s commit nor its uncommitted.patch, so it cannot be compared with w… | commit {…}, then {…} |
| `run_record_check._helpers_since_run` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} changed since {…} ran | {…} (`git -C {…} cat-file blob {…} > {…}`) |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | make the run's files readable (path and permissions), then `{…}` |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | measure anew (`{…}`) and audit that run; the run's own files stay as they are |

### finalize.finalize_area · 5. open fields — always

Calls:

- `finalize.station_open_fields` — Station 5: fields of the protocol still empty or a placeholder — in a field owed as a must under LAB_011, in any other as an open assignment —, a bound field written twice (a blocker), the README's placeholders (CODE-016 The experiment area reconstructs itself) and route block, and the generated data counts (`station_data_counts`).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `finalize.station_open_fields` | WARNING | GUARANTEED | variable | {…}:{…}: {…} | — |
| `finalize.station_open_fields` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | {…}; then `{…}` |
| `finalize.station_open_fields` | BLOCKER | GUARANTEED | technical contract | {…} | repair README.md as UTF-8 text or remove it, then `{…}` |
| `finalize.station_open_fields` | WARNING | STATIC_EVIDENCE | CODE-016 The experiment area reconstructs itself | {…} — a stamped placeholder, fill or delete the line | — |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `code_scan.unreadable_source` | BLOCKER | GUARANTEED | technical contract | {…} · the code cannot be read, so no check over it holds | repair or remove the file, then `code-check {…}` |
| `readme_check.readme_route` | WARNING | GUARANTEED | technical contract | README.md: no {…} … {…} block — the route (protocol · runlog · labkit-params · evaluate_r… | — |
| `readme_check.readme_route` | WARNING | GUARANTEED | technical contract | README.md route: does not name {…} | — |
| `readme_check.readme_route` | WARNING | GUARANTEED | technical contract | README.md route: does not name {…} | — |
| `readme_check.readme_route` | WARNING | GUARANTEED | CODE-016 The experiment area reconstructs itself | README.md route: scripts/01_measure.py does not exist | — |
| `readme_check.readme_route` | WARNING | GUARANTEED | CODE-016 The experiment area reconstructs itself | README.md route: scripts/01_measure.py defines no evaluate_rows | — |
| `finalize.station_data_counts` | BLOCKER | GUARANTEED | variable | {…} | `{…}` writes them from the run — never typed |

### finalize.finalize_area · 6. provenance — at low repeat cost, and only with a run

Calls:

- `finalize.station_provenance` — Station 6: every source the run read frozen in its record, its bytes the ones the record names, and tracked in git or kept outside it — by an ignore rule, or lying outside the repository; the outputs tracked, an untracked one a warning (`provenance_findings`).

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `run_record_check.provenance_findings` | WARNING | GUARANTEED | technical contract | no outputs.json — the run registered no output file (run.output) | — |
| `run_record_check.provenance_findings` | WARNING | GUARANTEED | technical contract | not a git repository — cannot tell whether source and output are committed | — |
| `run_record_check.provenance_findings` | WARNING | GUARANTEED | LAB-017 The number of audits follows the cost tier | output {…} is not yet tracked — `{…}` before the commit that cites the number | — |
| `run_record_check._recorded_sources` | BLOCKER | GUARANTEED | technical contract | {…} | pass every source in `data=` to runlog.run, then {…} |
| `run_record_check._recorded_sources` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | source not frozen — the run carries no `data=` | pass data={name: path} to runlog.run so sha and rows are recorded, or data=runlog.NO_INPUTS for a run that reads no input file, then {…} |
| `run_record_check.source_finding` | BLOCKER | GUARANTEED | LAB-017 The number of audits follows the cost tier | source {…} is not the bytes the run read: {…}, the run recorded sha256 {…} | restore the bytes the run read (from git where it tracks them, else from the source or access route Data / scope names), or {…} |
| `run_record_check._untracked_source` | BLOCKER | GUARANTEED | LAB-017 The number of audits follows the cost tier | {…} — whether it belongs to the project is left open | if it is small and may legally be shared, commit it (`{…}`); large or protected data stay out of git on purpose: an ignore rule for it (a `.gitignore` or `.git/info/exclude`) and its source or access route and version in the protocol's Data / scope — finalize then holds it to the checksum this run recorded, `sha256 {…}` |
| `run_record_check._gone` | BLOCKER | GUARANTEED | technical contract | {…} is not at its recorded path on this machine — deleted, moved or held elsewhere; the r… | restore it (`{…}` where git holds it; else get it again from the source or access route Data / scope names), or {…} |

### finalize.finalize_area · 7. input origins — on every repeat cost, only with a run

Calls:

- `finalize.station_input_origins` — Station 7: each input of the answering run whose record names an origin run is that run's registered output, its bytes as both records hold them (`origin_check.origin_gap`) — the first part that fails is a blocker naming the input, the origin and the condition, with the way out that restores evidence (`origin_finding`).

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `audit_binding.source_protocol_finding` | BLOCKER | GUARANTEED | technical contract | {…} | restore what holds it — the commit (`git fetch`), the run's uncommitted.patch or the protocol's history, from git or a backup — or, with the right sources, {…}; never show or write today's text in its place |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…}: [{…}] declares key '{…}', which the run does not report. | `INTENT_FIX` |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | variable | {…}: {…}. | `INTENT_FIX` |
| `intent_check.check_block_against_run` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} | `INTENT_FIX` |
| `intent_check.unregistered_outcomes` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…}: [{…}] records {…} = {…}, which is none of its outcomes' names | record one of {…} — the name of the outcome whose condition holds, as [[promise]] {…} writes it: fix the code, then `{…}` |
| `intent_check.origin_intent_findings` | BLOCKER | GUARANTEED | variable | {…}: promise block: {…} | measure the origin anew under its protocol and compute from that run ({…}); the files of origin run {…} and the text it was measured under stay as they are |
| `intent_check.origin_intent_findings` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} | measure the origin anew under its protocol and compute from that run ({…}); the files of origin run {…} and the text it was measured under stay as they are |
| `intent_check.origin_intent_findings` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | measure the origin anew under its protocol and compute from that run ({…}); the files of origin run {…} and the text it was measured under stay as they are |
| `origin_check.origin_finding` | BLOCKER | GUARANTEED | technical contract | {…} | {…}, or, with the right sources, {…}; {…} |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | make the run's files readable (path and permissions), then `{…}` |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | measure anew (`{…}`) and audit that run; the run's own files stay as they are |

### finalize.finalize_area · 8. area tests — always

Calls:

- `finalize.station_area_tests` — Station 8: the area's own tests.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.tell_test_run` | WARNING | GUARANTEED | technical contract | pytest is not installed in this interpreter — tests not run | — |
| `preflight.tell_test_run` | BLOCKER | GUARANTEED | technical contract | {…} did not run{…} — {…} | make them run (a collection or import error, a missing dependency, no test collected) until `{…}` passes |
| `preflight.tell_test_run` | BLOCKER | GUARANTEED | variable | {…} failed{…} — {…} | fix the code (or a test that asks the wrong thing) until `{…}` passes; a test's expected values are found apart from the run under test (by hand or from an independent source), never copied from a run's output, which tests only that the code repeats itself |

### finalize.finalize_area · 9. registered outputs, criterion n, the null lane and the reference comparison — only with a run

Calls:

- `finalize.station_registered_outputs` — Station 9: every output the run registered is the file the run recorded (`output_record_findings`) — the number's rows and the deliverable of an external task, held by path and sha256 from outputs.json, on every lane.
- `finalize.station_criterion_n` — Station 9: a criterion's denominator that matches no recorded input count (`kept_number_check.criterion_n_input_mismatches`).
- `finalize.station_null_lane` — Station 9: the kept rows' null lane moved (`null_lane_findings`) — a gate over the run's own output, not the editable script's guard.
- `finalize.station_kept_number` — Station 9: the kept number — the key the head's `[kept]` names, at every kind — held as a finite number in the answering run's metrics.json (`kept_number_check.kept_number_gaps`, a guaranteed blocker): the check the agent cannot edit away, where the skeleton's own check sits in its script.
- `finalize.station_reference` — Station 9: the comparison with the stated value the head registers (`[reference]`, a computation's), held to the answering run's metrics.json (`reference.comparison_gaps`, each a guaranteed blocker): a table that does not read, or one on a kind with a bar (`reference_gap`), blocks too; metrics that do not read block as the other stations' do.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `finalize.station_reference` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | repair the head as the sentence says, then `{…}` |
| `finalize.station_reference` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | repair the [reference] and [kept] tables as the sentence says; `{…}` shows them |
| `finalize.station_kept_number` | BLOCKER | GUARANTEED | variable | {…}: {…}{…} | `f"`{fill_command(protocol, f'kept.{gap.label.removeprefix("[kept] ")}=<value>')}`" if unfilled else f"repair the head as the sentence says, then " f"`{gate_command('finalize', protocol.parent)}`"` |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `kept_number_check._criterion_n_warning` | WARNING | STATIC_EVIDENCE | open assignment | {…} | — |
| `kept_number_check.kept_number_gaps` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | the kept number: metrics.json of {…} {…} — the head's [kept] names `{…}` as the number th… | write `{…}` as a finite number from evaluate_rows() (the skeleton reads the key from the head's [kept]), then {…}; when [kept] names the wrong number, set it before the first measurement — after it, {…} |
| `run_record_check.null_lane_findings` | WARNING | STATIC_EVIDENCE | LAB-034 Null condition in the same run | {…}: the null lane's answer and gold equal the registered lane's on every item — if the n… | if the null should differ, give the instrument a null of its own, e.g. its predictions against permuted gold, then {…} |
| `run_record_check.output_record_findings` | BLOCKER | GUARANTEED | variable | {…}: not the file run {…} recorded — {…} | `_output_way_out(o, drift, area)` |
| `reference.comparison_gaps` | BLOCKER | GUARANTEED | LAB-035 Thresholds belong to the run, not to the measure | metrics.json carries {…} and the head registers no [reference] — a comparison is register… | register the stated value in the head's [reference] table (value, tolerance, relation, source), or drop the keys from evaluate_rows(); then `{…}` |
| `reference.comparison_gaps` | BLOCKER | GUARANTEED | technical contract | the head registers [reference] on `{…}`, and the run recorded no verdict (no `{…}` in met… | write the verdict from the head after evaluate_rows() — the compute skeleton's `metrics_of()` does (`reference.with_verdict`) — then measure anew and audit that run |
| `reference.comparison_gaps` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | `{…}` {…}, so the registered reference ({…}) cannot be compared and no verdict can be rep… | write `{…}` as a finite number from evaluate_rows() (the key the head's [kept] names, which the compute skeleton reads), measure anew and audit that run; a [kept] key that names the wrong number is a new registration |
| `reference.comparison_gaps` | BLOCKER | GUARANTEED | technical contract | the verdict in metrics.json does not read: `{…}` = {…}, `{…}` = {…} — written beside the … | let the compute skeleton's `metrics_of()` write the verdict, measure anew and audit that run |
| `reference.comparison_gaps` | BLOCKER | GUARANTEED | LAB-035 Thresholds belong to the run, not to the measure | the run compared with {…}, the head registers {…} — the reference changed after the run, … | restore the [reference] the run compared with, or {…} |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | make the run's files readable (path and permissions), then `{…}` |
| `finalize.run_file_unread` | BLOCKER | GUARANTEED | technical contract | {…} | measure anew (`{…}`) and audit that run; the run's own files stay as they are |

### finalize.finalize_area · 10. audit findings — always; a head without an id has no record, and a record that does not read ends the station with that blocker

Calls:

- `finalize.station_open_audit_findings` — Station 10: every finding still `open` in the audit records of PROTOCOL (those that name PROTOCOL_ID, `followup.records_of`), any mode (`findings.open_findings`, with the table of the gates' rules) — a BLOCKER blocks, a WARNING warns, a NOTE is printed — each with its file; a finding on another protocol of the area holds nothing here, and a head without an id (PROTOCOL_ID None) has no record to hold it.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `audit_binding.check_audit_records_read` | BLOCKER | GUARANTEED | technical contract | {…} | `audit_records.record_way(state.area)` |
| `audit_binding.check_audit_findings_decided` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | {…} — {…} | `way_out_of(u)` |
| `audit_binding.check_audit_findings_decided` | WARNING | GUARANTEED | LAB-015 Preflight audit before freezing | {…} — {…} | — |
| `audit_binding.check_audited_runs_kept` | BLOCKER | GUARANTEED | technical contract | {…}: names {…} as the run it read, and there is no runs/{…}/ in this area — the run the r… | `way` |

## `preflight.preflight_area` — `labkit/gates/preflight.py`

The gate before the freeze, on AREA.

Commands whose code reaches it: `claude-hook`, `codex-hook`, `preflight`.

### preflight.preflight_area · 0. protocol — the only exit 2

Reaches no finding site.

### preflight.preflight_area · 1. protocol-check — the one early end: a head nobody can read

Calls:

- `preflight.station_protocol_fields` — Station 1: the field report of protocol-check (REPORT: the owed fields by cut, the graduation at frozen = true), the stamped id against the repo's others and the bound annotation evidence (`check_annotation_validity`), a repeat cost lowered since the first commit.
- `preflight.station_promise_sentences` — Station 1, the sentences the freeze owes: every [[promise]] table of TEXT whose `sentence` is still the stamp's `<…>` placeholder (`promises.placeholder_sentences`), a warning where the kind registers (`protocol_check.kind_registers`) — the freeze refuses them (`promises.promise_tables_owed`, a must gap of the field report once frozen = true), so the gate before the freeze names them first.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.preflight_area` | BLOCKER | GUARANTEED | variable | HEAD (must): {…} | `repair_head_way(protocol)` |
| `preflight.station_protocol_fields` | BLOCKER | GUARANTEED | variable | {…} | {…} in {…}; {…} |
| `preflight.station_protocol_fields` | BLOCKER | GUARANTEED | technical contract | REPEATED (must): {…} | {…}; then `{…}` |
| `preflight.station_protocol_fields` | BLOCKER | GUARANTEED | LAB-011 Required-field check | {…}:{…}: PLACEHOLDER (must): {…} | replace the placeholder with this protocol's own text; {…} |
| `preflight.station_protocol_fields` | WARNING | STATIC_EVIDENCE | LAB-015 Preflight audit before freezing | {…} | — |
| `preflight.station_protocol_fields` | WARNING | GUARANTEED | technical contract | missing (should): {…} | `rename_way(text, label)` |
| `preflight.station_protocol_fields` | WARNING | GUARANTEED | technical contract | {…}:{…}: placeholder (should): {…} | — |
| `preflight.station_promise_sentences` | WARNING | GUARANTEED | LAB-004 Identifiers make the intent addressable | [[promise]] {…} still carries the stamp's `<…>` sentence — frozen = true refuses it | state each promise explicitly in one sentence in its table (`{…}`); {…} |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `protocol_history.check_protocol_id` | BLOCKER | GUARANTEED | technical contract | {…}: DUPLICATE protocol id {…} — also carried by {…}. An id binds runs to ONE protocol | re-stamp the copy: `labkit-init exp <name> --kind …` writes a fresh id, and the copy's text moves into it |
| `protocol_history.check_protocol_id` | WARNING | GUARANTEED | technical contract | {…}: WARNING: protocol id changed against HEAD ({…} -> {…}) — runs bound to the old id st… | — |
| `protocol_history.check_annotation_validity` | BLOCKER | GUARANTEED | variable | {…} — {…} | bind it to one apply protocol of this repo whose head has adopted its result (`[result] run`, adopted there first), or name a DOI |

### preflight.preflight_area · 2. repeat cost — told, never counted

Reaches no finding site.

### preflight.preflight_area · 3. audit findings — the records always; the line's coverage where the lane owes the freeze and a line is stamped; handed over elsewhere always

Calls:

- `preflight.station_audit_records` — Station 3, the records: every finding still `open` in the area's audit records, each with its file — a warning before the freeze, a blocker once FROZEN (frozen = true owes every decision, LAB-015 Preflight audit before freezing).
- `preflight.station_audit_coverage` — Station 3, the record: why the record the head's AUDIT_LINE names does not cover a full run of this code and the promise block TEXT carries now (`audit_gaps.audit_record_gap`, the same answer runlog's freeze gate gives — preflight must not pass a state the run refuses), with the gap's own way out (`RecordGap.fix`: a new audit, or the decisions where the record's findings are still open).
- `preflight.station_handed_over_elsewhere` — Station 3, the reminder: every open finding of another area of the repo that a handover of that area records (`handovers.handed_over`) — set aside there unresolved, it may be this area's ("its own task").

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.station_audit_records` | BLOCKER | GUARANTEED | technical contract | {…} | `audit_records.record_way(area)` |
| `preflight.station_handed_over_elsewhere` | WARNING | GUARANTEED | technical contract | {…} | — |
| `preflight.station_handed_over_elsewhere` | WARNING | GUARANTEED | technical contract | {…} | — |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `preflight._owed` | BLOCKER | GUARANTEED | variable | {…} | `fix` |
| `preflight._owed` | WARNING | GUARANTEED | variable | {…} | `fix` |

### preflight.preflight_area · 4. code-check — always

Calls:

- `preflight.station_code` — Station 4: code-check's automated checks (`code_check.code_findings`: intent ids, parser fixtures, prompt drift, stamp coverage), each with its grade as data and counted once — here, not again by code-check.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `code_check._intent_id_findings` | BLOCKER | GUARANTEED | CODE-016 The experiment area reconstructs itself | [{…}] is registered, but no script names a '{…}'/'{…}_*' key literal (a key assembled at … | report the key in the measure script or drop [{…}] from the block, then `{…}` |
| `code_check._intent_id_findings` | WARNING | GUARANTEED | LAB-004 Identifiers make the intent addressable | key '{…}_*' is in the intent-id namespace, but the protocol registers no [{…}] · a number… | register it or rename the key |
| `code_check.promise_block_findings` | BLOCKER | GUARANTEED | variable | promise block: {…} | repair the [[promise]] tables as the sentence says, then `{…}` |
| `code_check.promise_block_findings` | BLOCKER | GUARANTEED | variable | [{…}] declared scope: {…} · runlog refuses the run | {…}, then `{…}` |
| `code_check.promise_block_findings` | BLOCKER | GUARANTEED | LAB-018 Routine check after every implementation | [{…}] declares key '{…}', which no script names as a literal{…} (an assembled key is not … | report '{…}' in the measure script or correct the key in [{…}], then `{…}` |
| `code_check.quality_check_reads` | WARNING | GUARANTEED | technical contract | quality-check keys: read check not done — {…} | fix the file |
| `code_check.quality_check_reads` | WARNING | STATIC_EVIDENCE | LAB-004 Identifiers make the intent addressable | [{…}] key '{…}' is written but nothing decides on it under its literal name · if no decis… | withhold the verdict when it fails, reading the key by its literal name (`if not m["{…}"]: …`) |
| `code_check.constant_copies` | WARNING | STATIC_EVIDENCE | LAB-004 Identifiers make the intent addressable | [{…}] {…}:{…} sets {…} = {…} itself ({…}) · a copy judges by an unregistered value once t… | read it with promises.constants(PROTOCOL, "{…}")["{…}"] |
| `code_scan.unreadable_source` | BLOCKER | GUARANTEED | technical contract | {…} · the code cannot be read, so no check over it holds | repair or remove the file, then `code-check {…}` |
| `import_check._import_findings` | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | `{…}` resolves to {…}, outside lib/ and src/ · the stamp does not cover it, a change ther… | `fix` |
| `import_check._coverage_in` | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | `sys.path` gains {…} · imports after it may resolve outside lib/ and src/, which the stam… | declare the file as a promise's scope (its declared_scope_sha then sees it) or copy it into the area |
| `import_check._coverage_in` | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | `{…}(…)` loads code at run time · the stamp follows `import` lines only, so it does not c… | declare the file as a promise's scope (its declared_scope_sha then sees it) or copy it into the area |
| `import_check._coverage_in` | WARNING | STATIC_EVIDENCE | LAB-019 The stamp covers everything that determines the number | names area `{…}` · this area's stamp does not follow a path into it | declare the file as a promise's scope (its declared_scope_sha then sees it) or copy it into the area |
| `prompt_check.check_parser_fixtures` | WARNING | GUARANTEED | technical contract | cannot be parsed ({…}) · which parsers it calls cannot be told | repair it until `{…}` collects it |
| `prompt_check.check_parser_fixtures` | WARNING | STATIC_EVIDENCE | LAB-041 Generate numbers, don't retype them | {…}() is called by no test under tests/ · a parser fails silently into a wrong number | give it a test with real raw answers under tests/, then `{…}` |
| `prompt_check.check_prompt_drift` | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | {…} | close the block with a fence line like its opening one, then `{…}` |
| `prompt_check.check_prompt_drift` | WARNING | GUARANTEED | technical contract | {…} is not statically readable (a call or a format spec this check does not compute) · pr… | — |
| `prompt_check.check_prompt_drift` | BLOCKER | GUARANTEED | LAB-067 A prompt has one home, which the run freezes | prompt block drifted from {…}: {…} of {…} fixed line(s) missing, e.g. {…} | paste the rendered `--show` output, not a transcript |

### preflight.preflight_area · 5. scope-sha — always. A stamp that cannot be computed blocks, with one exception: a scope file or promise block that is missing or does not read is only told when an earlier station already blocked (the same cause, said once); git failing or another file always blocks

Calls:

- `preflight.station_scope_stamp` — Station 5: the audit stamp of the area's input scope (`scope_sha.area_stamp`), or why there is none; a way out reruns preflight for PROTOCOL (`commands.preflight_command`).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.station_scope_stamp` | BLOCKER | GUARANTEED | technical contract | cannot stamp the area's scope: {…} | repair the file or promise block the sentence names, then `{…}` |
| `preflight.station_scope_stamp` | BLOCKER | GUARANTEED | technical contract | cannot stamp the area's scope: {…} | make the file readable (or git work on the repository), then `{…}` |

### preflight.preflight_area · 6. working tree — only inside a git repo: outside one no commit holds anything, and `tree_dirty` would answer False for a tree nobody compared

Calls:

- `preflight.station_working_tree` — Station 6: uncommitted changes under REPO, a git repository, warn — the number would rest on code no commit holds.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.station_working_tree` | WARNING | GUARANTEED | LAB-010 Commit before the run | uncommitted changes in {…} (commit or stash before the run) | — |

### preflight.preflight_area · 7. hooks — only inside a git repo

Calls:

- `preflight.station_hooks` — Station 7: the gates that do not depend on the agent remembering — every gap `install_hooks.check` names in GIT_REPO warns: a repo without the hooks (or with an older labkit's) runs on good intentions only.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight.station_hooks` | WARNING | GUARANTEED | LAB-011 Required-field check | {…} | — |

### preflight.preflight_area · 8. area tests — always; frozen = true owes the file

Calls:

- `preflight.station_tests_owed` — Station 8: what running the area's tests found (TESTS, from `area_tests`).

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `preflight._owed` | BLOCKER | GUARANTEED | variable | {…} | `fix` |
| `preflight._owed` | WARNING | GUARANTEED | variable | {…} | `fix` |
| `preflight.tell_test_run` | WARNING | GUARANTEED | technical contract | pytest is not installed in this interpreter — tests not run | — |
| `preflight.tell_test_run` | BLOCKER | GUARANTEED | technical contract | {…} did not run{…} — {…} | make them run (a collection or import error, a missing dependency, no test collected) until `{…}` passes |
| `preflight.tell_test_run` | BLOCKER | GUARANTEED | variable | {…} failed{…} — {…} | fix the code (or a test that asks the wrong thing) until `{…}` passes; a test's expected values are found apart from the run under test (by hand or from an independent source), never copied from a run's output, which tests only that the code repeats itself |

### preflight.preflight_area · 9. summary

Reaches no finding site.

## `report_check.protocol_verdict` — `labkit/gates/report_check.py`

Check AREA before reporting (`ProtocolVerdict`: the exit code and what the chain found), every line through TELL.

Commands whose code reaches it: `claude-hook`, `codex-hook`, `labkit-adopt`, `report-check`.

### report_check.protocol_verdict · 0. protocol and context — the only early end

Calls:

- `report_check.orphaned_duty_gaps` — The report duties of protocols STATE's area measured under and no longer holds, in STATE's file state (`registered_report.orphaned_report_duties`, the ids carried read from the state's protocol texts) — the one reading for report-check's station, its area form on an area without a protocol (`protocol_verdict`), and the stop's and the commit's hold (`hold_changed_paths`).
- `report_context.checked` — The context of one check: TEXT is the protocol as FILE_STATE holds it (read off the area's state when None); AREA_STATE the area's state when the caller built it already (one build per check run), else built here; AREA_EVIDENCE likewise (`evidence.read_evidence`, the index's for INDEX).

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | variable | {…} | `self.way_out` |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key | `way_out` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `registered_report._undetermined_duty` | BLOCKER | GUARANTEED | technical contract | {…}: whether it owes a report cannot be told — {…} | `way_out` |
| `registered_report.orphaned_report_duties` | BLOCKER | GUARANTEED | open assignment | {…}: no protocol of the area carries the id {…}, under which it measured ({…}); that prot… | `back.format(pid=pid)` |

### report_check.protocol_verdict · 1. the chain

Runs another gate of this page: `report_check.chain_gaps`.

### report_check.protocol_verdict · 2. summary — 1 with a blocker, otherwise 0

Reaches no finding site.

## `report_check.chain_gaps` — `labkit/gates/report_check.py`

Every finding report-check holds CTX to, in the order of the chain — the one list `report_check` prints and `next_step` reads (`ReleaseChain`)

Commands whose code reaches it: `claude-hook`, `codex-hook`, `labkit-adopt`, `labkit-init`, `labkit-next`, `report-check`.

### report_check.chain_gaps · 0. evidence — an adoption cut off, then committed evidence changed

Calls:

- `report_check.cut_off_adoption_gaps` — A blocker while an adoption was cut off during its check: the head may hold a proposal no check passed (`repo.pending_adoption`); never on the proposal itself, which that adoption is checking.
- `evidence.AreaEvidence.change_blockers` — CHANGES as blockers with their restore (`change_blockers`).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_check.cut_off_adoption_gaps` | BLOCKER | GUARANTEED | technical contract | {…}: an adoption was cut off during its check — the protocol may hold a proposal no check… | `{…}` puts it back first and adopts again |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |

### report_check.chain_gaps · 1. declaration

Calls:

- `report_check.declaration_gaps` — A blocker when CTX's `[result]` table does not read (`Checked.declaration_gap`).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_check.declaration_gaps` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | `{…}` removes it; audit the run that answers, then `{…}` writes the `[result]` table for it |

### report_check.chain_gaps · 2. registration — the freeze where the lane owes it, else the committed registration where the lane owes that

Calls:

- `report_check.freeze_gaps` — Why the freeze does not hold — the flag unset, or a must gap protocol-check names (the stamp's `<…>` promise sentences among them); REPEATED: a bound field written more than once too (`repeated_gaps`).
- `report_check.registration_gaps` — The committed registration where the lane owes it instead of the freeze (seconds): the registration stood in the protocol as committed at the first measurement — the commit its record names (`runs.recorded_commit`) — at each run `area_state.Measured.firsts` names: git's history orders the measurements, a run id (local time) only those at one commit; on diverged history, or for a run whose commit cannot be placed, more than one is first and each is held.
- `report_replacement.replacement_gaps` — A protocol that declares `[replaces]` (K1, docs/notes/2026-10-27-new-registration-contracts.md) registers anew against a predecessor, and the declaration binds it, exactly: the predecessor is one protocol of the repo, not itself, and the chain of replacements has no circle; every difference of its registration against the predecessor's — each as its first measurements saw it (`protocol_history. registrations_as_first_measured`; against each when they saw several, the way out of K3's registration that cannot be told) — is a `[[replaces.change]]`, and every declared change is one (`registration_differences`); the predecessor's open BLOCKERs are decided first, read from its area's records, so a change of that area's committed evidence against HEAD holds too (`evidence.change_blockers`).
- `report_check.report_binding_gaps` — The report duties of CTX's area that its state drops: the protocol's own, when its head registers no report though it owes one (`registered_report.report_binding_gap`), and those of protocols the area measured under and no longer holds (`registered_report.orphaned_report_duties`).
- `report_exploration.link_gaps` — The hold on a link that names no one protocol, read from CTX: the rule `unresolved_link_hold` over CTX's `[explored_in]`, the protocol ids of the repository as the working tree holds them (`protocol_block.repo_protocol_ids`), whether the area holds a measurement of the protocol (`Measured.has_measured`) and, for an id no file carries, what the history holds of it (`last_held`; not asked otherwise).

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_check.freeze_gaps` | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | {…}: not `frozen = true` — a reported number owes the freeze | freeze it: `{…}` clean, the preflight audit run and decided (`{…}`), then `{…}` |
| `report_check.freeze_gaps` | BLOCKER | GUARANTEED | variable | {…}: {…} | `f"{gap.repair}; {fields}"` |
| `report_check.freeze_gaps` | BLOCKER | GUARANTEED | LAB-011 Required-field check | {…}: line {…}: {…} still a placeholder | replace it with this protocol's own text; {…} |
| `report_check.registration_gaps` | WARNING | GUARANTEED | technical contract | not a git repository — the registration cannot be held to the commit of the first measure… | — |
| `report_replacement.replacement_gaps` | BLOCKER | GUARANTEED | variable | {…}: {…} | write `[replaces]` as the head reads it: `protocol = "<id>"` and one `[[replaces.change]]` (what, from, to, why) per change |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `area_state.unread_start_warning` | WARNING | GUARANTEED | technical contract | {…} — nothing is taken from a start file that does not read | restore the file from the commit that holds it (`git log --all -- <area>/run-starts/<run_id>.json` names it); where no commit holds it, leave it as it is: no value is written into a start file by hand, the protocol and the kind are read from the run's own record where that reads, and the start stays unknown |
| `area_state.missing_start_warning` | WARNING | GUARANTEED | technical contract | {…} | `START_FILE_BACK` |
| `area_state.unassigned_record_warning` | WARNING | GUARANTEED | technical contract | the record of run {…} does not read, and neither a start file nor the run index names it:… | `RECORD_BACK` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `registered_report._undetermined_duty` | BLOCKER | GUARANTEED | technical contract | {…}: whether it owes a report cannot be told — {…} | `way_out` |
| `registered_report.report_binding_gap` | BLOCKER | GUARANTEED | open assignment | {…} registered {…} as its report {…}, and its head now registers none — the report a meas… | restore `report = "{…}"` in the head of {…}, or name another file there (the duty moves with the entry), then `{…}`; or end the protocol with `{…}` and register anew — its earlier runs, results and findings stay |
| `registered_report.orphaned_report_duties` | BLOCKER | GUARANTEED | open assignment | {…}: no protocol of the area carries the id {…}, under which it measured ({…}); that prot… | `back.format(pid=pid)` |
| `registration_hold.unread_history_hold` | BLOCKER | GUARANTEED | technical contract | {…} — the runs and start files a commit holds were not read back, so whether a start file… | {…} (`{…}`); where they cannot be restored, {…} |
| `registration_hold.later_record_warning` | WARNING | GUARANTEED | technical contract | {…} — the start files put {…} after that of a measurement of this protocol that reads, an… | `RECORD_BACK` |
| `report_check.repeated_gaps` | BLOCKER | GUARANTEED | technical contract | {…}: {…} | {…}; then `{…}` |
| `report_check._registration_at` | BLOCKER | GUARANTEED | LAB-010 Commit before the run | {…} recorded no commit ({…}{…}) — it started outside the history, so the registration can… | when the missing choices can be made on grounds the new registration states, {…}; else {…} |
| `report_check._registration_at` | BLOCKER | GUARANTEED | technical contract | {…} recorded no commit ({…}{…}) — what the run started from is unknown, so the registrati… | when the missing choices can be made on grounds the new registration states, {…}; else {…} |
| `report_check._registration_at` | BLOCKER | GUARANTEED | technical contract | {…} ({…}{…}) recorded a commit this repository does not hold (a rewritten history, a shal… | fetch that commit from a clone that has it (`git fetch --unshallow` in a shallow clone) |
| `report_check._registration_at` | BLOCKER | GUARANTEED | technical contract | {…} at {…} ({…}{…}) cannot be read: {…} — the registration that stood before the number c… | {…} (`{…}`); where they are lost, {…} |
| `report_check._registration_at` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | {…} was not committed at {…} ({…}{…}) — nothing stood before the number; the registration… | when the missing choices can be made on grounds the new registration states, {…}; else {…} |
| `report_check._registration_at` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | the registration as committed at {…} ({…}{…}) lacks {…} — the registration is what the co… | when the missing choices can be made on grounds the new registration states, {…}; else {…} |
| `report_exploration.unresolved_link_hold` | BLOCKER | GUARANTEED | technical contract | exploration link: [explored_in] protocol = {…} names {…} — the exploration this confirmat… | make the id name exactly one protocol of the repo: {…}, then `{…}`; {…} |
| `report_replacement._predecessor` | BLOCKER | GUARANTEED | LAB-003 No run without an intent paragraph | [replaces] protocol is its own id | name the protocol it replaces in [replaces] protocol, then `{…}` |
| `report_replacement._predecessor` | BLOCKER | GUARANTEED | variable | [replaces] protocol = {…} names {…} | name the one protocol of this repo it replaces, kept as it is, then `{…}` |
| `report_replacement._predecessor` | BLOCKER | GUARANTEED | technical contract | the replacements run in a circle ({…}) | let each name the one before it, then `{…}` |
| `report_replacement._undeclared_changes` | BLOCKER | GUARANTEED | technical contract | the registrations cannot be compared — {…} | until they can, {…} |
| `report_replacement._undeclared_changes` | BLOCKER | GUARANTEED | technical contract | changed against {…} ({…}) and not declared: {…} {…} → {…} | add under [replaces]: [[replaces.change]] what = {…}, from = {…}, to = {…}, why = "…"; then `{…}` |
| `report_replacement._undeclared_changes` | BLOCKER | GUARANTEED | technical contract | declares a change the registrations do not show: {…} {…} → {…} (the predecessor {…}, this… | remove that [[replaces.change]], then `{…}` |
| `report_replacement._predecessor_open` | BLOCKER | GUARANTEED | technical contract | the predecessor's audit records do not read: {…} | `audit_records.record_way(pred.parent, pred)` |
| `report_replacement._predecessor_open` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | its predecessor's BLOCKER is still open — {…} | decide it (`{…}`), or hand the predecessor over, replaced by {…}: `{…}` |

### report_check.chain_gaps · 3. finalize — always; where it read this text, what this chain's own stations hold is not told again as finalize's: the `[result]` table that does not read (station 1) and the unreportable marks (station 4)

Runs another gate of this page: `finalize.finalize_area`.

### report_check.chain_gaps · 4. full run — only with an answering run

Calls:

- `report_check.unreportable_gaps` — Why the answering run's number cannot be reported (`runs.unreportable`), each a blocker.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_check.unreportable_gaps` | BLOCKER | GUARANTEED | technical contract | {…}: no config.json in this file state — the run's record cannot be checked | measure through runlog: {…} |
| `report_check.unreportable_gaps` | BLOCKER | GUARANTEED | variable | the answering run {…}: {…} — its number cannot be reported; a reported number owes {…} | measure in full{…}: {…}, then audit that run |

### report_check.chain_gaps · 5. analysis — where the lane owes it and an answering run exists; without one, finalize's run-choice station holds it where it reads this text

Calls:

- `report_check.analysis_findings` — Coverage and rendered-result blockers for an analysis stage already due.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `result_render.render_gaps` | BLOCKER | GUARANTEED | LAB-011 Required-field check | the Recorded results line is not written | `{…}` writes it from the run |
| `result_render.render_gaps` | BLOCKER | GUARANTEED | technical contract | the Recorded results line differs from its rendering (the run's metrics.json, the stand-i… | `{…}` writes it again |
| `result_render.render_gaps` | BLOCKER | GUARANTEED | technical contract | "{…}" is written {…} times — one generated line per label | remove the extra line(s) by hand (`--render` rewrites one and leaves the others) |
| `result_render.render_gaps` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | no "{…}" line — the limit's line belongs in the protocol | `{…}` writes it from the record |
| `result_render.render_gaps` | BLOCKER | GUARANTEED | technical contract | "{…}" differs from the record and its decision reviews — a line written before the decisi… | `{…}` writes the record's line |
| `result_render.render_gaps` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | "{…}" names a limit no covering record decides — written by hand or from an older record | `{…}` drops it |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | technical contract | no answering run to hold it to — {…} | measure: `{…}`, then audit that run |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | technical contract | the analysis audit cannot be held to the run: {…} | `exc.fix or audit` |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | technical contract | the analysis audit cannot be held to the area: {…} | repair what the sentence names (a refused file: make it readable), then {…} |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | technical contract | no analysis audit covers the area as it is now, and none can run — {…} | (a) bring the evidence back — the line names the first restore, `{…}` lists every loss with its restore —, then {…}; (b) where nothing restores it, no audit covers the area and no number leaves it: {…} |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | variable | no analysis audit covers the area as it is now, and none can until the exploration link r… | resolve the exploration link first, as its blocker names; then `{…}` names the audit where one is still owed. No audit before that: it would be held to the area without the exploration and cover nothing once the link resolves |
| `report_check.analysis_audit_gap` | BLOCKER | GUARANTEED | variable | {…} | audit the answering run as it stands: `{…}`, then decide its findings |
| `report_decisions.limit_gaps` | BLOCKER | GUARANTEED | technical contract | the result cannot be rendered from {…}: {…} | repair what the sentence names, then `{…}` writes the result section |
| `report_decisions.check_limit_effects_decided` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | {…}: a BLOCKER decided limitation owes its effect on the verdicts | decide it again: `{…}` |
| `report_exploration.later_use_findings` | WARNING | STATIC_EVIDENCE | LAB-050 Analysis audit before reporting | data use after the audit: run {…} of {…} recorded {…} — {…}. The run is taken as not show… | have the auditor judge it: `{…}` shows every input digest a run of that area shares with a run of this protocol |

### report_check.chain_gaps · 6. recomputation — always, unless `undeclared`

Calls:

- `report_check.recomputation_findings` — Run the analysis script's check for PROTOCOL and return its failure as a blocker; a check that did not end (`CheckUnfinished`) and one that ended "not verifiable" (`recheck.NOT_VERIFIABLE`: nothing shows that the code here is the code the run ran) as a check not executed — no number was compared, and the release waits all the same.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_check.recomputation_findings` | BLOCKER | GUARANTEED | technical contract | {…} — no result, the numbers are not held to the run | run {…} by hand and make it end, then `{…}` |
| `report_check.recomputation_findings` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} | restore the code and its record as the check names them, or measure anew, audit and adopt that run; then `{…}` — the recalculation is owed for the adopted result, another run is not held by it |
| `report_check.recomputation_findings` | BLOCKER | GUARANTEED | LAB-041 Generate numbers, don't retype them | {…} | fix what the check names until {…} exits 0; a number in the protocol comes from `protocol-fill`, never typed |

### report_check.chain_gaps · 7. decisions — where the lane owes the analysis

Calls:

- `report_decisions.review_findings` — The decision reviews: every effect among the limits of the covering analysis records — `stands`, `<ID> not assessable` — is upheld by a decision review (`reviews.upholding`: a review of that record, its code and its run as shown, under the claim the protocol makes now, of the decision as it stands now, every draw saying `upheld`).
- `report_decisions.followup_findings` — The follow-up of earlier decided BLOCKERs (`followup.release_holds`): each one not released by a valid `resolved` of the state reported now, and a BLOCKER `fixed` in that state itself, is a BLOCKER naming the missing step.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_decisions.followup_findings` | BLOCKER | GUARANTEED | technical contract | the carried findings of {…} do not form a chain: {…} | `audit_records.record_way(ctx.area, ctx.protocol)` |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `report_decisions.check_decision_reviews_read` | WARNING | GUARANTEED | technical contract | a review nobody can read: {…} | — |
| `report_decisions.check_limits_upheld` | variable | GUARANTEED | LAB-015 Preflight audit before freezing | {…}: `{…}` on a {…} decided limitation {…} — no decision review upholds that {…} | `fix` |
| `report_decisions.check_contested_closings_upheld` | variable | GUARANTEED | LAB-015 Preflight audit before freezing | audit {…} #{…}: `{…}` on a {…} a review said {…} on ({…}) — closing a finding a reviewer … | {…} asks a second auditor whether the reason shows it {…} |
| `report_decisions.check_repaired_claims_upheld` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | audit {…} #{…}: `fixed` on a BLOCKER on the Conclusion {…} — no follow-up audit is shown … | {…} asks a second auditor whether the Conclusion as it stands no longer makes the claim the finding names; no new measurement and no analysis audit |
| `report_decisions.check_first_dismissals_upheld` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | audit {…} #{…}: `false-positive` on a BLOCKER {…} — a blocking finding is not released by… | {…} asks a second auditor whether the reason shows it {…} |
| `report_decisions.check_earlier_blockers_released` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | audit {…}: {…} | `h.step` |
| `report_decisions.check_carried_closings_upheld` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | audit {…} #{…}: a carried finding (from {…}) `{…}` — the follow-up did not find the fault… | {…} asks a second auditor whether the reason shows it {…} |

### report_check.chain_gaps · 8. report — unless `undeclared`; its review not on the proposal: its text is in every review's fingerprint, so the adoption would hold itself (`report_findings` says why)

Calls:

- `report_check.report_findings` — The registered report's obligation (`registered_report.report_owed`): the file the head's `report` names, as the state holds it, carries the result block of the declared run or the protocol's handover block — else one blocker; nothing registered: [].
- `report_hold.discussion_review_findings` — The report reviews the reports of REPO owe for discussing a run of PROTOCOL (its TEXT as the state holds it): the findings `hold_report` holds each such report with (`report_review_owed`), read here per protocol so that `report_check.chain_gaps` — and through it `report-check AREA` and `labkit-next` — holds and names exactly what the stop and the commit hold (`report_check.hold_changed_paths`), one function for both.

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | variable | {…} | `self.way_out` |
| `answering_run.AnsweringRun.explain` | BLOCKER | GUARANTEED | LAB-004 Identifiers make the intent addressable | {…} {…} — no answer: a probe or producer run, or a script that reports no registered key | `way_out` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `registered_report.result_owed` | BLOCKER | GUARANTEED | variable | {…} registers {…} as its report, and {…} carries neither {…} nor the protocol's handover … | {…}; `{…}` writes the progress account of the run the gates hold it to — the commit takes it, it releases nothing and the result or the handover stays owed; `{…}` ends the protocol without a result{…} |
| `registered_report.missing_report` | BLOCKER | GUARANTEED | variable | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… | restore it (`{…}` where the last commit holds it), or `{…}` writes its result block of {…} again; then the report review it owes |
| `registered_report.missing_report` | BLOCKER | GUARANTEED | variable | {…} registers {…} as its report; the report is missing ({…}), and its area holds a measur… | `{…}` writes the progress account (the commit takes it, it releases nothing); `{…}` adopts a run and writes its result block into {…}; `{…}` ends the protocol without a result and writes that into it; then the report review it owes |
| `registered_report.registered_review` | BLOCKER | GUARANTEED | technical contract | {…}: its discussion blocks do not read — {…} | `report_blocks.DISCUSSION_RESTORE_WAY` |
| `report_hold.staged_area_gap` | BLOCKER | GUARANTEED | technical contract | {…}: the working tree differs from the index ({…}) — {…} the tree, the commit holds the i… | `{…}` stages the whole area{…} ({…} file(s), listed above); stash what the commit must not hold |
| `report_hold.through_gap` | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | {…}: {…} | remove the block, or repair what the sentence names and write it again: `{…}` |
| `report_hold.through_gap` | BLOCKER | GUARANTEED | technical contract | {…} differs from what the analysis run's record and adoption say now — a stale rendering … | `{…}` writes it again |
| `report_hold.review_gap` | BLOCKER | GUARANTEED | technical contract | {…}: its report review cannot be told — {…} | repair what the sentence names, then review this state: {…} |
| `report_hold.review_hold` | BLOCKER | GUARANTEED | technical contract | {…}: {…} and has no clean report review of this state — and none can run: {…} | `lost.fix` |
| `report_hold.review_hold` | BLOCKER | GUARANTEED | LAB-015 Preflight audit before freezing | {…}: the report review holds this state ({…}) — {…} | {…} (another draw on this state, `--again` included, releases nothing) |
| `report_hold.review_hold` | BLOCKER | GUARANTEED | LAB-104 A number leaves the area only through its adoption | {…}: {…} and has no clean report review of this state (one naming no claim){…} — a cold r… | {…} (one model call) — last, after the report's text and its blocks are final: a change after it owes another |

## `runlog.Run.__init__` — `labkit/run/runlog.py`

—

Commands whose code reaches it: no console script.

### runlog.Run.__init__ · 1. preparation — what the run is held to, read once

Calls:

- `start_check.prepare` — Phase 1 — preparation.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `start_check.prepare` | exit | none | not recorded | runlog: run_kind='probe' is not allowed at repeat_cost='low' — this repeat cost has no se… | run the full measurement with run_kind='measurement' |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `start_check.protocol_binding` | exit | none | not recorded | runlog: protocol={…} is not one of the PROTOCOL-*.md in the run's area ({…}): {…} | name one of these: `runlog.run(..., protocol=PROTOCOL)` |
| `start_check.protocol_binding` | exit | none | not recorded | runlog: {…} protocols in {…} — nothing would say which one this run belongs to: {…} | name it: `runlog.run(..., protocol=PROTOCOL)` |
| `start_check.protocol_binding` | exit | none | not recorded | runlog: {…}: {…} | `repair_head_way(path)` |
| `start_check._promise_snapshot` | exit | none | not recorded | runlog: promise block: {…} | `PROMISE_BLOCK_WAY` |
| `start_check.completed_parent` | exit | none | not recorded | runlog: {…}={…}: {…} | restore the run record the sentence names as runlog wrote it (`{…}` where git holds it) |
| `start_check.completed_parent` | exit | none | not recorded | runlog: {…}={…} names no completed run under {…} ({…}){…} | name a completed run of this area by its id (its folder under {…} holds a completion.json) |
| `start_check._derived_parent` | exit | none | not recorded | runlog: derived_from={…} is not a run id | name a run of {…} by its id, never a path |
| `start_check._derived_parent` | exit | none | not recorded | runlog: derived_from={…} is a repeat of {…} — supporting evidence, never the answer | derive from {…} |
| `start_check.require_step_basis` | exit | none | not recorded | runlog: {…} | write the step with `protocol-fill <PROTOCOL> --builds-on <run_id> --step-id <step> --occasion <occasion> --why "…"` |
| `start_check.require_step_basis` | exit | none | not recorded | runlog: [builds_on] run = {…} is a repeat of {…} — supporting evidence, never a step's ba… | build on {…} |
| `start_check.require_step_basis` | exit | none | not recorded | runlog: [builds_on] run = {…} is bound to {…}, not to this protocol ({…}) | build on a run of this protocol; a run of another protocol is read as an input (its origin), not built on |

### runlog.Run.__init__ · 2. the start check — the order and every skip are visible here; helpers check the facts without reading a partly built Run

Calls:

- `start_check.require_registration` — Refuse a run that breaks the registration's contract, before any gate that can be acknowledged and before mkdir: a frozen protocol and every full run carry the promises as data (`promises.promise_tables_owed`), and a run under a block records every registered constant unchanged — otherwise the number is held to a threshold nobody registered.
- `start_check.require_valid_reseed` — Refuse a run whose seed is drawn anew (RESEED) against the rules: a reseed goes with REPEAT_OF; the config must hold an integer REPEAT_SEED_KEY; and a seed the protocol registers as a constant is not drawn — a repeat may not change a registered value.
- `start_check.require_answer_reading` — The path under the repository root of MODULE, the module a derived run declares as its answer reading (`answer_reading`), or a refusal: no `derived_from` beside it, the area in no git repository, MODULE no file, outside the repository, or not among the modules SCRIPT imports (`scope_sha.measured_code`) — a module the script does not import reads none of its answers.
- `runlog._declared_under` — The installed labkit's version, which a run's declared answer reading records (`AnswerReading.labkit`).
- `start_check.foreground_timeout` — The foreground limit of the shell this process runs in, and who named it; None when no harness limits it.
- `start_check.require_detached` — Refuse a foreground start under the harness LIMIT, before mkdir.
- `runlog._require_no_open_twin` — Refuse a measurement while a run of the same script is still open in the area: a low-cost run that outlasts the agent's tool limit goes to the background, and the next start would resume into its rows — overlapping runs write rows another run made.
- `runlog._decide_origins_and_warn` — The origin of every input in DATA (`input_origins`), DESCRIBED as `describe_data` made it; the automatic decisions made without the area's unreadable runs are warned of once (`unreadable_warning`).
- `start_check.freeze_gate` — The freeze gate for a full run, before mkdir: a full run on a protocol not ready for one is a refusal, not a run with a warning.
- `code_repos.require_recordable` — Refuse a measurement whose imported code cannot all be recorded: an untracked file above `COPY_CAP` is in no commit and would not be copied.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `code_repos.require_recordable` | exit | none | not recorded | runlog: the run imports untracked code it cannot record (above {…} MB, in no commit): {…} | commit these files in their repository, then start the run again |
| `runlog._declared_under` | exit | none | not recorded | runlog: labkit runs from a source tree that is not installed, so the version this run's a… | install labkit (`pip install -e .` in its checkout, or the lab's pinned requirements), then start the run again |
| `runlog._decide_origins_and_warn` | exit | none | not recorded | {…} | — |
| `runlog._require_no_open_twin` | exit | none | not recorded | runlog: {…} is still measuring in {…}: {…} — a second measurement beside it would read an… | wait for it (`{…}`), then read its result |
| `start_check.foreground_timeout` | exit | none | not recorded | runlog: {…}={…} is not a number of seconds >= 0 | set {…} to the shell's limit in seconds (0: the shell has no limit) |
| `start_check.require_valid_reseed` | exit | none | not recorded | runlog: reseed draws a repeat's seed anew — it goes with repeat_of | pass `repeat_of=<the primary run>` with `reseed=True`, or drop reseed |
| `start_check.require_valid_reseed` | exit | none | not recorded | runlog: reseed: the config holds no integer `{…}` to draw anew ({…}) | give the config an integer `{…}` |
| `start_check.require_valid_reseed` | exit | none | not recorded | runlog: reseed: the protocol registers `{…}` = {…} — a spread over seeds needs a seed the… | repeat without reseed, or register a spread over seeds in a protocol of its own |
| `start_check.require_registration` | exit | none | not recorded | runlog: {…}: {…} | write the [[promise]] tables in the protocol and commit them before the run (`protocol-check <PROTOCOL> --contract` names what the kind owes) |
| `start_check.require_registration` | exit | none | not recorded | runlog: {…}: {…} | read them with promises.all_constants(), not a second copy |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading declares what a derived run re-reads its parent's answers with — i… | pass `derived_from=<the run whose answers are read>`, or drop answer_reading |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading: {…} lies in no git repository, so the module cannot be compared w… | measure in the repository, or drop answer_reading |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading = {…}: no such file | name the module that reads an answer, absolute or under the repository root |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading = {…} lies outside the repository {…} | declare a module of this repository |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading: the code {…} imports cannot be read: {…} | repair what the sentence names, then start the run again |
| `start_check.require_answer_reading` | exit | none | not recorded | runlog: answer_reading = {…}: {…} does not import it, so it reads none of the answers | declare the module the script imports to read an answer |
| `start_check.require_detached` | exit | none | not recorded | runlog: this run declares run_kind='measurement' and sits in a foreground shell an agent … | start it detached: `{…}`; or, if the caller already detached it (run_in_background, nohup+setsid), acknowledge with LABKIT_DETACHED=1 |
| `start_check.freeze_gate` | exit | none | not recorded | runlog: {…}, and a preflight audit found BLOCKER(s) nobody decided — not an unfrozen prot… | decide each ({…}) with the command `{…}` prints per finding |
| `start_check.freeze_gate` | exit | none | not recorded | runlog: {…}, but its protocol is not ready for one: {…} | {…} No other run yields a reported number: a probe (run_kind='probe') and a run acknowledged with LABKIT_UNFROZEN=1 (at high repeat cost only over an audit the backend refused, audits/*{…} written by labkit-audit) are recorded as such, and report-check refuses their numbers. |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `area_state.unread_start_warning` | WARNING | GUARANTEED | technical contract | {…} — nothing is taken from a start file that does not read | restore the file from the commit that holds it (`git log --all -- <area>/run-starts/<run_id>.json` names it); where no commit holds it, leave it as it is: no value is written into a start file by hand, the protocol and the kind are read from the run's own record where that reads, and the start stays unknown |
| `area_state.missing_start_warning` | WARNING | GUARANTEED | technical contract | {…} | `START_FILE_BACK` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `evidence.change_blockers` | BLOCKER | GUARANTEED | variable | {…} | `c.fix` |
| `start_check._undecided_findings` | exit | none | not recorded | runlog: {…} | `audit_records.record_way(base_dir)` |
| `start_check._audit_unavailable` | exit | none | not recorded | runlog: LABKIT_UNFROZEN=1 — the area cannot be stamped ({…}), so no failed audit attempt … | repair what the sentence names, then start the run again |
| `start_check._audit_unavailable` | exit | none | not recorded | runlog: promise block: {…} | `PROMISE_BLOCK_WAY` |
| `start_check._audit_unavailable` | exit | none | not recorded | runlog: {…} | `audit_records.record_way(base_dir)` |
| `start_check._audit_unavailable` | exit | none | not recorded | runlog: this run declares run_kind='measurement' (a full run) on a protocol not ready for… | run the audit: `{…}`; when the backend does not answer, it writes audits/<date>-preflight{…}, and this acknowledgement rests on that file — and its number cannot be reported either (report-check refuses it) |
| `start_check.require_exploration_link` | exit | none | not recorded | runlog: {…} | write the link with `{…}`: it names the run that protocol has adopted and refuses with the reason where the link cannot hold |
| `start_check.require_exploration_link` | exit | none | not recorded | runlog: this is the first measurement of {…}, and its [explored_in] is no valid link to a… | {…}; or remove the table: a confirmation without an exploration of this repo names none |

### runlog.Run.__init__ · 3. creation — the record, whole or not at all; the id and the directory are drawn together under the guard below

Calls:

- `runlog._repeat_draw` — (repeat_of, draw, config) for config.json, before mkdir and under the index lock the caller holds: a repeat draws a completed primary run of this area again, comparable in protocol, promise block, config and inputs (`answering_run.repeat_mismatch`) — else a refusal.
- `runlog.Run._write_start_file` — The run's start file (`run_starts`): its id, the protocol id it is bound to ("" unbound), the time now in UTC and RUN_KIND, whole and synced to disk, outside the run's directory.

**At this station:**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `runlog._repeat_draw` | exit | none | not recorded | runlog: repeat_of and derived_from exclude each other — a repeat asks the model again, a … | pass the one this run is: `repeat_of=` to ask again, `derived_from=` to re-read |
| `runlog._repeat_draw` | exit | none | not recorded | runlog: repeat_of={…}: the next draw number cannot be counted — {…} | restore the run record the sentence names as runlog wrote it (`{…}` where git holds it) |
| `runlog._repeat_draw` | exit | none | not recorded | runlog: repeat_of={…}: {…} | restore the run record the sentence names as runlog wrote it (`{…}` where git holds it) |
| `runlog._repeat_draw` | exit | none | not recorded | runlog: this run is no repeat of {…} — it measures something else: {…} | run it as the same measurement, or as a run of its own without `repeat_of` |
| `runlog.Run._write_start_file` | exit | none | not recorded | runlog: {…} exists — a run with the id {…} started before, and its start file is never ov… | start the run again: it draws a new id; the earlier start file stays as it is |
| `runlog.Run._write_start_file` | exit | none | not recorded | runlog: the start of {…} could not be recorded in {…}: {…} — the run did not start, and n… | make the area's run-starts/ writable, then start the run again |

**Further down (static estimate):**

| Function | Grade | Evidence kind | Rule | Tells | Next |
|---|---|---|---|---|---|
| `runlog._repeat_parent` | exit | none | not recorded | runlog: {…} is itself a repeat of {…} | repeat the primary run: `repeat_of={…}` |
| `start_check.completed_parent` | exit | none | not recorded | runlog: {…}={…}: {…} | restore the run record the sentence names as runlog wrote it (`{…}` where git holds it) |
| `start_check.completed_parent` | exit | none | not recorded | runlog: {…}={…} names no completed run under {…} ({…}){…} | name a completed run of this area by its id (its folder under {…} holds a completion.json) |
