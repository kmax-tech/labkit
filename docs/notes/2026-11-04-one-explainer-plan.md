# One explainer — gates return data, `labkit-next` explains and does the mechanical steps

2026-11-04. Baseline `35242fc3`. Planned, not ordered: `TODO.md`
("Reihenfolge") puts it after the release gaps of the
[maintainability repair plan](2026-11-03-maintainability-repair-plan.md)
and before the next usage round. This note owns the work order; the
format-and-gate inventory it starts with is the size question's answer,
the phases after it are the cut that inventory prepares.

## The question

Since the simplification started (`76d81f78`) the package grew 6 % and
the suite 12 %; the repairs added contracts faster than the shared rules
removed lines. The size is not additive but multiplicative: every format
is a reader, a writer, a validation and its tests, every gate reads
several formats, and every gate explains its own refusal. The
contradictions of the last weeks (two gates naming different next steps
for one state, a hold that sent an agent to measure a third time, a hint
that disagreed with the stop hook) sat exactly there.

labkit does not own the state: the agent edits protocol, code, report and
runs freely and in any order, so every gate re-derives the state from the
files. That stays — a stored state lies after the next free edit
([derived views copy no truth](../architecture.md)). What changes is who
orders the states and who explains them.

## Review of 2026-11-04 and the first step

A second reading of this note (another session, same day) held: the
direction — one decision, one understandable output — is right; the
note as a whole is not a build order, because it bundles simplification
with new guards (a write ledger) and new functions (`--do`) and could
grow the code first. Accepted, with these consequences, worked into the
sections below:

1. The write ledger is a system of its own (storage, restore, parallel
   sessions, fresh clones). It leaves the plan and becomes a proposal
   with a trigger.
2. Byte equality is not the registration binding. "Equal to what the
   tool last wrote" does not prove "equal to the first measurement" or
   "audited as such"; an allowed write can still change the registered
   question. The historical bindings stay; the allow-list changes who
   writes and what the writer refuses, not what the gates compare.
3. Hooks and `next` must judge the same file state: the index at the
   commit, the working tree otherwise. `next_step` takes the state
   (`Checked.state` exists: TREE, INDEX, PROPOSED); a hook never holds on
   one state and prints a step from another.
4. `--do` is a function of its own, needs structured arguments (paths and
   ids, not a shell line to parse) and is no precondition of the usage
   round. It becomes a proposal with a trigger.
5. A reader does not justify a format, and a merge can breed variants.
   Every *merges* or *goes* needs a before/after proposal of its own.

And: tests do not reduce to transitions wholesale. A shared writer
removes no check at the read: files can be edited by hand, restored or
copied from another clone, so the reader validates what it reads as
long as provenance (the ledger) is deferred. What a shared writer gives
is one validation function for writer and reader — one implementation
to test instead of two that can disagree (V1 and V2 were two comparisons
disagreeing, not one check too many). Corrupted files, missing git
objects and concurrent writes stay real inputs with their tests.

**The first step, limited and measured:** close the known gap — the
review a report owes that only *discusses* a run — by letting the gate
(`report_hold.hold_report`), the hooks and `labkit-next` read the same
findings in the same file state: same state, same hold, the fitting next
step. Remove the competing logic on the way and record the effort
(sessions, lines added and removed, tests changed). Then decide, on that
result, whether Phase 1 continues as written. This is the pilot of the
architecture before its build-out.

Acceptance of the pilot, fixed before it starts:

1. Gate (`report_hold.hold_report`), the stop and pre-commit hooks and
   `labkit-next` name the same owed report review for the same area,
   from the same findings.
2. Working tree and index are tested apart: the pre-commit judges the
   index, the stop and the console the tree, each with its own test.
3. A valid counter-case passes: a report whose discussed run's review
   stands is held by none of the three (no false blocker).
4. The competing logic is gone, not bypassed: the hook's own
   composition of that hold and `next`'s separate path to it do not
   survive as dead code.
5. Measured afterwards: effort, the special cases that remain, and
   usability (the commands an agent needs from the hold to the release).
6. The shared-findings invariant of Phase 1, as a test for this one
   hold: the stop, the pre-commit and `next_step(area, state)` read the
   owed review from the same findings of the same state; with no other
   blocker standing, the hooks hold and `next` names this step.

The pilot needs no `Command`: `next` takes the hold as one row in its
order, reads it from `Checked.state`, and the finding's identity is the
`GateFinding` itself. Phase 2 starts after it, not inside it.

Stop or replan — fixed now, so the decision is falsifiable — when any
of these holds after the pilot:

- the hold needs more than one new row in `next`'s order, or a branch
  on the file state inside that row (the state parameter did not carry);
- the package has net more lines than before the pilot after the
  competing logic is removed (tests apart);
- the invariant test needs an exception list (a finding the hooks hold
  on that `next`'s set does not carry, or the reverse);
- the pilot takes more than two sessions.

The forecasts and the two sessions are a budget for a new decision:
exceeding them triggers an explanation and a re-decision, never the
removal of clear code or of a check to meet the number.

Then Phase 1 does not continue as written; the note gets the reason and
the next proposal.

## Target

1. **One ordering, one explainer.** `labkit-next` is the only code that
   turns an area's state into a step. A gate returns findings as data:
   what holds, where, which rule, and the way out as a *command object*,
   not a sentence. No gate, hook or console path composes a "Next:"
   sentence of its own.
2. **Mechanical steps run themselves, if the `--do` proposal is
   triggered.** `labkit-next --do` executes a
   step whose command is one of labkit's own checked writers (adopt,
   block into the report, withdrawal, wait for an open run). It never
   runs git, never a model, never writes content it would have to invent.
3. **Research steps stay with the agent.** Which run answers when several
   could, the Conclusion, a decision on a finding, the `--why` of a
   discussion: `next` names what is expected and stops.
4. **State is derived, from few files, by one reader each.** No format
   gains a second reader; a format no gate reads is a candidate to go.

## The direction: toward an allow-list — step 1 is the writer that refuses

Today labkit is a deny-list: the agent may change any file, and the gates
recognise known violations afterwards. A deny-list grows with every
error observed, and so do its tests (the registration comparison that
broke on whitespace and on a glossed field name, V1 and V2 of the
maintainability review, are errors of recognising a hand-edited head).
The alternative is an allow-list: one way, and what lies beside it is not
forbidden case by case but not provided for. This plan takes its first
step only: the writer refuses what a gate would later hold. The ledger
is deferred and the historical bindings stay, so hand edits before the
first commit stay unrecognised and the test class "semantically
equivalent hand edits" does not fall away yet — it shrinks where a
writer's precondition replaces a gate's recognition, and no earlier.

| Class | Files | Who writes | What labkit checks |
|---|---|---|---|
| machine-led | the protocol head and its tables, the generated protocol sections, `runs.tsv` and the run records, audit records and decisions, attempt journals, reviews, handover records, the result, discussion and handover blocks in reports | labkit's commands only | today: against HEAD once committed (`evidence.change_blockers`). Step 1 (Phase 3, first item): the writer refuses what a gate would later hold. A comparison against what labkit last wrote, before the first commit, is the deferred write-ledger proposal below |
| free | measuring code, report prose, notes, data, `MANIFEST.sha256` | the agent | consequences only: code changed since the run, a report citing a run nothing adopted |

The second row exists and stays: research content must be free. The
first row exists by half — `runlog` writes the runs, `protocol-fill` the
head, `evidence.change_blockers` compares committed evidence against
HEAD. What is missing is the consequence: a hand edit of a machine-led file
is not a case with its own cure but a refusal with one way out, and the
writer refuses what the gates would later hold (a registered field after
the first measurement). The gap between a write and its first commit
(what HEAD cannot compare yet) is a proposal below, not part of this
plan. A writer's refusal removes no check at the read; writer and
reader share one validation, so the rule has one home and one test
instead of two implementations that can disagree. What does not change
are the
bindings across time — the registration to the first measurement's
commit, the record to the run it audited — which compare a present text
with a historical one and stay as they are. What it does not solve
stays with the agent audit: a number that is formally clean and wrong. Deliberate circumvention stays possible (a forged
ledger line); labkit guards against error, not adversaries, as the
[review-record limit](2026-11-02-review-record-forgery.md) already says.

## What already exists

- `labkit-next` (`labkit/tools/next_step.py`) is the ordering: field
  report → evidence restore → handover → open run → progress account →
  report-check's chain gaps → adoption → report block → nothing. It adds
  no check; it reads what the gates compute.
- `GateFinding.fix` (`labkit/formats/gate.py:85`) is required for every
  BLOCKER and is what `next` prints as the step (`first.fix`). The way
  out is already data in the sense of a field — but a prose field.
- `GateFinding.changed_since` is the precedent for the rule: "callers
  order their advice by it, never by the words".
- `audit_decisions.repair_hint` is the precedent for an explanation that
  names no action and points to `labkit-next`
  (`docs/architecture.md`, "What does a repair decided `fixed` owe next?").
- `labkit-adopt` is the precedent for a mechanical step that runs
  labkit's own writers in order and stops at the first refusal.
- The command builders in `labkit/formats/repo.py` (`withdraw_command`,
  `into_command`, `measure_command`, `audit_command`,
  `report_blocks.discuss_command`) are the one spelling of each command.

## What stands in the way

Counted at the baseline (`grep` over `labkit/`, tests excluded).

| Finding | Where | Count |
|---|---|---:|
| `fix=` sites composing a way out as prose | 31 modules | 245 |
| of these naming a command in backticks | | 64 |
| of these prose only ("decide the finding", "fill the field") | | 180 |
| code reading a `fix` string as text to decide | `next_step._refused_measurement` (`measure_command(...) in fix`), `ways_out.declared_first` (prepends to `fix`) | 2 |
| the withdraw-first rule in two homes | `ways_out.declared_first` via `report_check.chain_gaps`, and `next_step._held_step` composing its own withdrawal sentence | 2 |
| step-naming code outside `next_step` | `finalize.undeclared_hint` (adopt command and the steps owed), `agent_hooks._report_hint` + `report_review.review_hint` (the post-change hook's step), `agent_hooks.stop` composing `"{gap.text}. Next: {gap.fix}"` per touched area, `scaffold.next_steps` (the lane after `labkit-init exp`), `ways_out.blocker_routes` (nine routes printed with every decision list and shown to the auditor) | 5 homes |
| the register-a-report hint in two homes | `next_step._report_hint`, `agent_hooks._report_hint` (a different hint under the same name) | 2 |
| hooks that do not call `next_step` | `agent_hooks.stop`, the pre-commit path | 2 |

Not in the way, named so they are not counted twice: `report_hold.report_hints`,
`report_hold.replacement_hints`, `audit_decisions.read_hints` and
`audit_decisions.stands_check_hint` are static-evidence warnings or
reading aids, not step namers; `preflight.contract_hint` and
`protocol_edit.field_address_hint` explain a refused input's spelling,
which is a refusal's way out and stays with the refusal.

(The TODO entry of 2026-11-04 counted "14 hint functions in 9 modules";
that count took the static-evidence hints for step namers. The table
above is the corrected inventory.)

## Phase 0 — Inventory and verdicts (no code)

Status: tables done 2026-11-04; the verdicts are proposals and open.

Deliverable: the two tables below, one row per format and per gate, each
with the chain link it secures (intent → promise → code → run → number),
its readers, and a verdict: *stays*, *merges into X*, *goes*. A format no
gate or check reads, and a gate that only repeats what another checks,
are the candidates; their tests go with them. Each row also says its
class under the principle above, machine-led or free. Periphery
(`tools/`, `probes/`) is judged apart and does not count against the
guards.

### Table A — formats

Readers from an AST scan of direct read calls outside `labkit/formats/`
and outside tests (2026-11-04; spot-checked: `deliverable`,
`criterion_bar`, `timebox`, `promises.load` are read by templates and
their own tests only). Chain link: I intent, P promise, C code, R run,
N reported number. Class as the principle above names it; *derived*
means no file of its own. Verdicts are proposals; each *goes*, *moves*
or *merges* needs a before/after proposal of its own (what the files,
readers and tests look like on both sides) before it is a Breaking
entry (Phase 3). A reader does not justify a format: it may be part of
the same unnecessary construction.

| Format | File | Link | Class | Readers (g gates · c checks · r run · t tools · p probes · tpl templates) | Proposed verdict |
|---|---|---|---|---|---|
| `protocol_block` | PROTOCOL-*.md, the toml block | I P | machine-led | g 9 · c 8 · r 2 · t 8 · p 1 · tpl 3 | stays; the head's writers are `protocol_fill`, `protocol_edit`, `scaffold` — one writer, Phase 3's first item |
| `protocol_check` | PROTOCOL-*.md prose fields, prompt blocks | I P | machine-led (content free, structure labkit's) | g 8 · c 4 · r 2 · t 5 · p 1 | stays; `repeated_fields` and the MUST checks become the writer's preconditions once the fields are written only through it |
| `promises` | `[[promise]]` tables | P | machine-led | parse: g 4 · c 6 · r 1 · t 4; `load`, `write_constant`: tpl only | stays; `load`/`write_constant` are the scripts' API and move to the script-helper home (below) |
| `protocol_history` | the protocol as git holds it | P→R | derived (git) | g 6 · c 1 · r 1 | stays: the binding to the first measurement's commit compares a present with a historical text and is not replaced by "as last written"; with one writer that refuses a registered field after the first measurement it fires rarely, but it stays |
| `runs` | `runs/<id>/*.json` | R | machine-led | g 7 · c 6 · r 3 · t 2 · p 1 · tpl 1 | stays |
| runs index | `runs.tsv` (`run/runlog.indexed_runs`) | R | machine-led | g 3 · r 1 | moves into `formats/` (a format read by gates lives outside the formats layer) |
| `answering_run` | none | R→N | derived | g 4 · c 5 · r 2 · t 1 · p 1 | merges into the state reader (Phase 4) |
| `attempts` | `audits/attempts.jsonl` | R→N | machine-led | g 4 · t 1 | stays; merge candidate with `failed_attempts` (two journals of audit attempts) — decide in Phase 3 |
| `failed_attempts` | `audits/<min>-<mode>-failed.toml` | R→N | machine-led | g 2 · c 1 · r 1 · p 1 | merge candidate into `attempts` |
| `findings` | `audits/<min>-{preflight,analysis}.toml` with decisions | P→N | machine-led | g 8 · c 2 · r 1 | stays |
| `audit_gaps` | none | P→N | derived | g 2 · c 1 · r 1 | merges into the state reader |
| `followup` | none | N | derived | g 4 | merges into the state reader |
| `handovers` | `audits/handovers/*.json` + report block | N | machine-led | g 5 · t 1 · c 1 (block) | stays |
| `reviews` | `audits/<min>-review.toml` | N | machine-led | g 2 | merge candidate with `report_reviews`: one review record with a kind |
| `report_reviews` | `audits/report-reviews/*.toml` | N | machine-led | g 2 | merge candidate with `reviews` |
| `evidence` | audits/ and runs/ against HEAD | all | derived (git) | g 4 · t 1 | stays; the write-to-commit gap is the deferred write-ledger proposal, not a change to this module |
| `comment_blocks` | `<!-- labkit … -->` in reports | N | machine-led inside free files | c 1 (gates through `report_blocks`) | stays |
| `data_manifest` | `MANIFEST.sha256` | C→R | free | c 1 | stays |
| `deliverable` | `pred_results/*.csv` | R | free | nobody; tpl writes it | goes from `formats/`: a write-only helper is the scripts', not a format |
| `criterion_bar` | none | P | script helper | tpl 2 | moves to the script-helper home |
| `timebox` | none (Timebox field) | P | script helper | tpl 1 | moves to the script-helper home |
| `rules` | `docs/standard.md`, `docs/rules.tsv` | — | repo-level | g 1 · c 1 · t 1 | stays |

Script-helper home: the functions a stamped measuring script imports
(`promises.load`, `write_constant`, `criterion_bar.bar_of`,
`timebox.seconds_of`, `deliverable.write_csv`) are the area code's API,
not formats the gates read; they belong under `labkit/run/` beside
`runlog`, `llm` and `batch`, where the public API already lives, and in
the Public API table once a lab imports them. Without area record files
and so not formats either: `standard_contract`, `scope_sha`, `repo`,
`jsonl`, `files`, `console`, `shell`, `gate`, `prompts`, `reference`.

### Table B — gates

Transitive reads from a static call graph (branch-dependent reads
counted). A gate is one of the five that decide; a hook is a surface
that should call a gate and `next` (Phase 1), listed here because today
it reads on its own.

| Entry | Decides | Formats read | Proposed verdict |
|---|---|---|---|
| `preflight_area` | the registration may freeze | protocol_block, protocol_check, promises, protocol_history, findings, audit_gaps, handovers; runs and answering_run through the scope basis | stays |
| `finalize_area` | the run is what the registration promised | the protocol four, runs, answering_run, findings, followup, data_manifest | stays |
| `report_check` | the number may be released | everything finalize reads, plus attempts, failed_attempts, handovers, reviews, report_reviews, evidence, comment_blocks, runs.tsv | stays, the release gate |
| `hold_report` | a report may stand as it is | comment_blocks, handovers, runs, answering_run, protocol_block, promises, attempts, report_reviews, findings | merges into `report_check`'s chain: called from its command path and the hooks today, outside `chain_gaps`, so `next` does not see its holds |
| `measurement_refusal` / `freeze_gate` | a measurement may start | the protocol four, runs, answering_run, one preflight record; `freeze_gate` also area_records, failed_attempts | stays as the start gate; its registration reads (`registration_missing`, `registration_in_commit`) duplicate preflight's and get one home |
| hook `pre_run` | — | head; low lane one check, else preflight_area | surface: keeps calling preflight, prints `next` |
| hook `post_change` | — | attempts, evidence, runs.tsv, protocol_report on a changed protocol, comment_blocks on a changed report | surface: `protocol_report` here is a sixth reader of the protocol state; after Phase 4 it reads the state once |
| hook `stop` | — | handovers, attempts, evidence, report_hold, report_check with all it reads, runs.tsv | surface: prints `next` per touched area (Phase 1) |
| hook `undecided` | — | handovers, attempts, evidence, protocol_block, promises, comment_blocks | surface: the pre-commit's gate call; prints `next` |

Reading of the two tables: every record format is read by a gate, so
nothing goes for want of a reader; what goes or moves is the
script-helper group misfiled under formats. The size sits in the
*readers*: the protocol state has six independent reader paths
(preflight, finalize, start check, report_check, `protocol_report` in
the hook, `next`), and three derived views (answering_run, audit_gaps,
followup) are recomputed by each. That is Phase 4's case.

## Phase 1 — One mouth: every console path prints `labkit-next`'s step

Change: the stop hook and the pre-commit path hold on the findings
`next_step` derives for the same state and print its step; they compose
no line and judge no fact of their own. The shared findings are the
truth; `next` chooses one action from them. So the invariant is not
"the hook holds exactly when `next` names a blocking step" — several
blockers can stand at once and `next` names the first, and `next`
places the progress account before some blocks on purpose. The
invariant, held by a test over every hold the hooks know: gate, hook and
`next` read the same applicable findings of the same file state; the
hook holds by its fixed policy (a BLOCKER among them, grade decides, the
words never); `next` names its step from that same set, by its order. A
hook that holds on a finding `next`'s set does not contain, or `next`
naming a step from a finding the hook's set does not contain, is the
contradiction this plan exists to remove. For the isolated report case
the test may then demand the same hold and the same action.
`finalize.undeclared_hint` becomes one line naming `labkit-next AREA`.
`scaffold.next_steps` prints `next_step` for the stamped area instead of
its own lane. `blocker_routes` leaves the decision list (one line names
`labkit-next`); the nine routes stay in `labkit-next --guide` and the
stamped `AGENTS.md`, where `tests/test_ways_out.py` already holds them
to real commands. `agent_hooks._report_hint` and `report_review.review_hint`
go where `next` names the review. Today it names the *registered*
report's review (`report_hold.report_owed`, reached through
`report_check.chain_gaps` and `_handed_over`) but not the review a report
that merely *discusses* a run owes: that hold lives in
`report_hold.hold_report`, called from the command path of `report-check`
(`report_check.py:1005`) and the hooks, outside `chain_gaps`. This is the
first known state `next` does not name; it becomes a row in `next`'s
order, with a test, before the hook's own line goes.

Requirement: `next_step` takes the file state the caller judges
(`Checked.state`: TREE for the stop and the console, INDEX for the
pre-commit) and reads every finding from it; a hook holds and names the
step from one state.

Files: `labkit/gates/agent_hooks.py`, `labkit/gates/finalize.py`,
`labkit/tools/scaffold.py`, `labkit/gates/audit_decisions.py`,
`labkit/gates/audit_prompt.py`, `labkit/tools/next_step.py`.
Tests: `tests/test_agent_hooks*.py` (63 tests today) and
`tests/test_next_step.py` (17) — each hook assertion on a composed line
becomes an assertion on the step; the six-case repair probe
(`labkit-evidence`, `usability/2026-11-02-repair-paths/`) records per
case the sequence of steps `next` names, as the regression oracle.
CHANGELOG: Breaking (hook output changes; `blocker_routes` no longer
printed with decisions).
Done when: the invariant test above passes for the stop and the
pre-commit over the probe cases; `grep -rn "Next: " labkit
--include='*.py'` outside `formats/gate.py` and `tools/next_step.py` is
empty (a necessary sign, not the proof — it is met by rewording); and
every hint named in the table above either is gone or names no action.
Forecast: package −300 to −500 lines (the hooks' own composition,
`undeclared_hint`, `scaffold.next_steps`, the routes' printing), tests
±0 (assertions move from lines to steps); measured afterwards.

## Phase 2 — The way out as data

Change: a `Command` (frozen dataclass in `labkit/formats/repo.py`, the
builders' home): `name` (one of a small enum: `adopt`, `into`,
`withdraw`, `discuss`, `measure`, `audit`, `review`, `wait`, `restore`,
`fill`, `init`), `kind` (`MECHANICAL`, `CONTENT`, `RESEARCH`,
`DESTRUCTIVE`), its arguments as fields (protocol, run id, report,
record — paths resolved, not shell text), and `line` rendered from them
(the shell line as today). Every builder returns one;
`GateFinding` gains `step: Command | None`; `fix` keeps its type and is
rendered from `step` by `with_way_out` where a step is given, so the 180
prose-only sites do not change and the 64 command sites pass the object.
Then `next_step._refused_measurement` tests `step.name == measure`,
`_held_step` and `report_check.chain_gaps` share one withdraw-first rule
(it moves into `next`; `ways_out.declared_first` goes), and no code
reads `fix` as text.

Kinds, fixed here so the `--do` proposal has nothing to decide:

| Kind | Commands | Why |
|---|---|---|
| MECHANICAL | `adopt` (only when `next` names one run; several candidates make the choice RESEARCH, and `next` must then hand out that kind, never `adopt`), `into`, `withdraw`, `wait` | labkit's own checked writers; each refuses on its own and leaves the files as they were |
| CONTENT | `fill` (a MUST field's value), `discuss` (the `--why`), the Conclusion | the agent writes words labkit cannot know |
| RESEARCH | `audit`, `review`, a decision, choosing among several runs | a model call or a judgement |
| DESTRUCTIVE | `restore` (`git checkout -- <evidence>`), `init` on a tree that has files | discards or overwrites work; printed, never run |

Files: `labkit/formats/repo.py`, `labkit/formats/gate.py`,
`labkit/checks/report_blocks.py`, the 64 command sites (31 modules, list
by `grep -rn 'fix=' labkit | grep '\``'`), `labkit/gates/ways_out.py`,
`labkit/tools/next_step.py`.
Tests: `tests/test_gate.py` (a BLOCKER with a `step` renders the same
`fix` as before — the twin: the rendered line is byte-equal for every
builder), `tests/test_next_step.py` (the measurement refusal found by
name, not text).
CHANGELOG: internal change; `GateFinding` is not in the public API
(`docs/architecture.md`, "Public API"), so one Breaking entry suffices.
Done when: `grep -rn '\.fix' labkit --include='*.py'` shows only
rendering (`with_way_out`, `line`) and no comparison.
Forecast: package +100 to +150 (`Command`, its builders) and −100
(`declared_first`, the text matching, the second withdraw-first home):
about even, honestly; it pays in Phase 4 and in the `--do` proposal,
not by itself. Measured afterwards.

## Proposal — `labkit-next --do` (trigger: the usage round counts the typed commands as a cost)

Not a phase (the former Phase 3; the phases are renumbered). Not part
of the work order; kept here because Phase 2's `Command` is its
precondition. Change: `labkit-next AREA --do` prints the step as today, then: a
MECHANICAL step is run in-process through the writer's function (not a
subprocess), its refusal line printed as the writer prints it; then the
next step is printed again. One step per call — no loop, so a wrong
derivation runs one checked writer at most. CONTENT and RESEARCH steps
exit 3 with the step as without `--do`; DESTRUCTIVE steps print the
command and exit 3. `--do` on "nothing" exits 0 and runs nothing.

Files: `labkit/tools/next_step.py` (the dispatch by `step.name`),
`labkit/tools/adopt.py`, `labkit/tools/protocol_fill.py` (into,
withdraw), `labkit/run/runlog.py` (wait).
Tests: one per kind (ran, refused by the writer, exit 3, nothing), and
the repair probe's six cases driven by `--do` until the first CONTENT or
RESEARCH step: the recorded step sequence of Phase 1 must be reproduced.
The dispatch reads `Command`'s fields, never its `line`.
Docs: `labkit/templates/AGENTS.md.template` ("Run `labkit-next <area>`"
becomes "Run `labkit-next <area> --do`; it runs the mechanical steps and
stops where you have to write or decide"), `labkit/docs/agent-guide.md`,
`docs/workflow.md` (the steps at a glance).
CHANGELOG: feature, with the kinds table.
Done when: in the six probe cases the number of commands an agent must
type is counted before and after, and recorded in this note.

## Phase 3 — The verdicts of Phase 0, executed

First item, and step 1 of the allow-list direction: one writer of the
protocol head. `protocol_fill`, `protocol_edit` and `scaffold` write it
today; one home writes it, and that writer refuses what a gate would
later hold (a registered field after the first measurement, a bound
field twice), through the same validation function the readers use.
The reader's checks stay — a file may be edited by hand, restored or
copied from another clone — but they call one implementation, not a
second one. Before/after proposal like every other row.

Each *goes* or *merges* row of the inventory is first a before/after
proposal (one section in this note or a note of its own), then one
commit with one Breaking entry naming the last version that read the
format; tests go with the format. The two merge candidates (`attempts`
with `failed_attempts`, `reviews` with `report_reviews`) are separate
proposals: a merge that adds a kind field and branches on it has bred
variants, not removed a format. The rule "existing legacy paths go in
one Breaking release" holds — collect the rows, release once.

## Phase 4 — The state model

Change: one reader builds `AreaState` from the files (the seed is
`report_context.Checked`, built today by `next` alone): area, repo,
protocol text and head, promises, the runs and the index, the answering
and the declared run, the records with their decisions, attempts,
reviews, handovers, the evidence comparison. Gates become pure
functions `AreaState → findings`; the twelve gate and check modules that
open files today (`agent_hooks` 9 sites, `audit_decisions` 6,
`audit_prompt` 5, `finalize` 4, `decision_review` 4, …) read none. The
derived views (`answering_run`, `audit_gaps`, `followup`) become fields
of the state, computed once. Tests build a state with a builder instead
of writing twenty files (`tests/protocol_fixture.py` is the start).

Why after Phase 1: only
when `next` is the single explainer is it visible which state fields
the gates need; before, every hook's own path would claim fields of its
own. `--do` is no precondition.
Files: new `labkit/gates/area_state.py` (or `report_context` grown),
every gate module, `tests/conftest.py`.
CHANGELOG: Breaking (gate signatures).
Done when: `grep -c "read_text\|open(" labkit/gates/*.py labkit/checks/*.py`
is zero outside the state reader, and the architecture test
(`tests/test_architecture.py`) holds the new layer.
Forecast: package +400 (the reader and the state) and −600 to −900
(file access and the recomputed views in twelve modules); tests −10 %
by lines where a builder replaces file setups. The most uncertain
forecast here; it is the one to check hardest.

## Two tasks apart from the phases

Both are mechanical, both can run per module beside other work.

- **The command table.** 21 console commands are named in
  `pyproject.toml`, the AGENTS template, the agent guide, `ways_out` and
  in strings; `tests/test_ways_out.py` holds the template to the routes
  by hand. One table in code (name, entry function, kind as Phase 2
  defines it), from which the template, the guide, `next` and the test
  read. Phase 2's `Command.name` is its key.
- **History into notes.** 585 dated incidents stand in 85 package files
  (`grep -rhoE "20(25|26)-[0-9]{2}-[0-9]{2}" labkit --include='*.py'`),
  a quarter of the 11,800 docstring lines, against the repo's own rule
  (the current rule in the docstring, the history in a note). Per module
  touched: the sentence that names a present limit stays with a short
  why; the incident moves to the topic's note under `docs/notes/` and
  the docstring links it. This is the cheapest real reduction in this
  note and runs module by module beside the pilot; its delta is
  reported apart, so it does not mask the pilot's.

## Then: the usage round

The size is measured by use, not by lines: the next round of agents on
real tasks counts, per task, the commands typed, the refusals met and
whether the correct number was reported. The round needs the first
step above, not `--do`; it decides whether Phase 1 continues and whether
the proposals get their trigger and whether the work continues from
Phase 2. Whether Phase 1 continues is the pilot's decision alone, by
its stop criteria above.

## Proposal — the write ledger (deferred; the gap is shown, the decision is whether its protection is worth a system)

What HEAD cannot compare: a file labkit wrote and the agent edited
before the first commit. The gap is demonstrated: the
[review-record forgery note](2026-11-02-review-record-forgery.md) shows
`rejected` rewritten to `upheld` before the first commit releasing the
decision. That case is a deliberate rewrite, and labkit guards against
error, not adversaries — so it shows the gap but is not this proposal's
trigger. The trigger is an *accidental* edit of a machine-led file
before its first commit that releases a wrong number, seen in a probe
or a lab. Until then the open question stays open: which protection,
at what cost. A ledger of what labkit last wrote (per area,
content hashes) would close it, and is a system of its own: where it
lives (the git dir, like the attempt journal's copy), what a fresh clone
does without it (falls back to HEAD), two sessions writing the same area
(the lock the journal already uses), and restore.

## Out of reach here

Rollout to the labs' pinned labkit and their `AGENTS.md`; the house
doctrine; new static-evidence checks (they wait for the benchmark).

## Risks

- `--do` executes on a wrong step derivation. Held by: only labkit's own
  writers, each with its own refusal; one step per call; the probe cases
  as oracle; git never.
- Phase 1 reveals states `next` does not name (the hooks named them on
  their own). That is the point: each becomes a row in `next`'s order,
  with a test, before the hook's line goes.
- The 64 command sites are spread over 31 modules; a site missed keeps a
  prose `fix` and simply yields no `--do` — visible, not wrong.
