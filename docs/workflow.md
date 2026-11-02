# The workflow: from a registered question to a kept number

One pass through labkit for one experiment area, step by step: the command,
what it reads and what it changes, what must hold before it, and what a
clean exit means. The rules behind each step are linked, not restated —
the chain of checks is in [architecture](architecture.md), the promise
format in [promise-block](promise-block.md), which run answers in
[protocol-run-binding](protocol-run-binding.md), the lab standard in
`labkit/docs/standard.md` (`python -m labkit.formats.rules show LAB-nnn`).
Terms are the README's glossary. The steps are those of repeat cost `low`; what
`high` owes on top is said inside the step it belongs to.

Five words the page leans on: a **full run** is one started with
`run_kind="measurement"` (not a probe, not a preparation); a **station** is
one named check of a gate, told in the gate's output in its order; the
**release** is the moment a number leaves the area as a reported result
(the adoption, the stop, the commit); a **hint** is static evidence —
named, never blocking; the **adopted run** (`[result] run` in the head)
and the **answering run** (the choice below) must be the same run, or
`report-check` blocks.

An executable walk of these steps on the stamped count task is
[`examples/count-walkthrough.sh`](examples/count-walkthrough.sh) — run it
in an empty directory with a venv that has labkit, read its output beside
this page; `tests/test_workflow_example.py` keeps it true.

## The steps at a glance

One row per step below: when the area has reached it (read from the
records, never from a status file), what the agent may change there, the
command, what it writes, what ends the step, and the way out when a check
holds. `labkit-next <AREA>` names the step an area stands at today
(`labkit/tools/next_step.py`); the sections below carry the details and
the `high` additions.

| Step | Reached when | The agent may change | Command | Writes | Done when | Held → way out |
|---|---|---|---|---|---|---|
| 0 area | no protocol in the area | — | `labkit-init exp <name> --kind compute\|fit\|apply` (`--report-file REPORT.md` when the task asks for a report) | the area, its protocol, the skeleton, the area test | the area is stamped with its own number | two areas with one number → `labkit-init numbers` names them |
| 1 code | the area exists | the scripts, the area test | `code-check <AREA>` after each change | nothing | every declared key, prompt line and parser fixture found | a missing key or fixture → write it |
| 2 registration | a MUST field is open | the protocol's fields through `protocol-fill`; the kind only before the first measurement (`--change-kind`) | `protocol-fill`, `protocol-check`, commit | the protocol | `protocol-check` finds every field the kind owes, and they are committed (`high`: frozen after preflight and its audit) | an open field → `protocol-fill <PROTOCOL> --list` |
| 3 run | the registration is committed | the code before the run; nothing under `runs/` | `scripts/01_measure.py` (through `runlog`) | `runs/<run_id>/`, the output, `runs.tsv` | the run completed; with a registered report and nothing adopted, `labkit-next` names the progress account next (`--discuss RUN --why …`), before the audit and any gap — it releases nothing | an unregistered or unbound run → refused before it starts |
| 4 finalize | a completed run answers the protocol | nothing (it only reads) | `finalize <AREA>` | nothing | no blocker: the run can carry a number | code or registration changed since the run → measure again, or restore, or register anew |
| 5 analysis audit and decisions | finalize is clean and no analysis record covers the area as it is now | each finding's decision, through `--decide` | `labkit-audit <AREA> --mode analysis`, then `--decide` per finding | `audits/<minute>-analysis.toml` and its decisions | every finding decided, the record covers code, promises, run and what was shown | code changed after the audit → the record is stale, audit again; an earlier BLOCKER undecided → decide it first |
| 6 decision review | a BLOCKER was accepted with `stands`, or a decision a review did not uphold was closed | the Conclusion, the decision | `labkit-audit <AREA> --review` | `audits/<minute>-review.toml` | every such decision `upheld` | `rejected` → decide again (limit, change the effect, fix); `insufficient` → add evidence |
| 7 adoption | nothing but the adoption holds | — | `labkit-adopt <AREA> [RUN_ID]` (or `protocol-fill <PROTOCOL> --from-run`) | the protocol: `[result] run`, Recorded results, Limitation lines, Runs; with a registered report its result block, where the run's progress account stood | `report-check` passes on the written protocol | a blocker → the file is restored and the blocker named |
| 8 report | an adopted run, or a run the report discusses | the report's prose; the blocks only through `protocol-fill` | `protocol-fill <PROTOCOL> --into REPORT.md` (`--discuss RUN --why …` for a run only looked at), then `labkit-audit <AREA> --report-review REPORT.md` | the generated block; `audits/report-reviews/<minute>-review.toml` | the block equals its rendering, and the review of this state names no claim | a registered report without its result or handover block, or a claim → adopt and `--into`, `--discuss` (the progress account before the adoption; releases nothing), or `--handover` |
| 9 stop and commit | the agent ends its turn, or commits | — (the hooks run unasked) | `claude-hook stop`, `.githooks/pre-commit` (`report-check --if-reported`) | nothing | no blocker in the areas touched or staged; a registered report carrying only the progress account passes the commit, the stop names the next step once | the line names its command; no result to be had → `protocol-fill <PROTOCOL> --handover --why … --tried … --into REPORT.md` |

A repair after an adoption runs the steps again from the withdrawal:
`protocol-fill <PROTOCOL> --withdraw --why "…"` → change the code (step 1)
→ measure again (3) → finalize (4) → the analysis audit follows the
earlier decided BLOCKERs up (5) → adopt the new run (7). The withdrawal
removes the adoption and the result blocks, never a run or an audit record.

## 0. The area

```
labkit-init lab <dir>                       # once per lab repo
labkit-init exp <name> --repeat-cost low --kind compute   # one area per question; --kind fit|apply when the number judges predictions; --model ALIAS with a model in the loop
```

Reads: the templates shipped with labkit. Writes: `experiments/NN-<name>/`
with `PROTOCOL-<name>.md` (its TOML head stamped with a protocol id, the
repeat cost, `frozen = false`), `scripts/01_measure.py` and `02_analyze.py`
(the skeleton for the instrument: compute, estimator or model), the area
test, the README card. Nothing is owed yet; `protocol-check <PROTOCOL>
--contract` prints what its repeat cost and kind will owe and when.
`NN` is one above every number the repository holds — this tree,
`_archiv/`, every branch this clone knows, every other worktree — so two
branches do not both stamp the same next area; `labkit-init numbers`
checks that each area has a number of its own, and the pre-commit and
pre-merge-commit hooks run it on the index.

## 1. The measurement code

```
<edit scripts/01_measure.py>                # the TODOs: what is counted, how, the number
code-check experiments/NN-<name>            # after every code change
```

Reads: the scripts, the protocol's promise tables. Changes: nothing.
Clean means: every declared key appears in the code, every `PROMPT`
constant stands in the protocol, the parsers have fixtures — the static
part of the promise → code link. It proves nothing about meaning; that is
the audit's question. A local `apply` loads the unchanged predictor; it
neither receives labels nor trains, and its null lane scores the same
predictions against labels permuted with the seed (or a registered fixed
null predictor). The author declares the model's files in
`PREDICTOR_FILES`, whose digests are recorded
in the config, run inputs and output fingerprint. A changed artifact cannot
resume old rows or count as an unchanged repeat.
At `high` the `--probe` checks the instrument on a few items before anything
is frozen (real model calls, a reduced fitted estimator, or unchanged local
apply predictors); a computation has none.

## 2. The registration

```
protocol-fill PROTOCOL-<name>.md "Question / hypothesis=…" "Unit=…" …
protocol-check PROTOCOL-<name>.md
git add experiments/NN-<name> tests/test_NN_<name>.py && git commit -m "…" -- experiments/NN-<name> tests/test_NN_<name>.py
```

The commit names its paths (LAB-077 Own commits, others' state stays with
the user): `git add` makes new files known, and the paths after `--` keep
whatever else is staged — another session's work, the state you found —
out of it.

Reads and changes: the protocol's prose fields, by exact label
(`protocol-fill --list` names what is still open). Which fields follow the
kind, not the repeat cost (`standard_contract.registration_fields(kind, model)`):
every kind the question; a fit or an apply also the success criterion, the
quality check and the null condition / anchors; a `[model]` table
adds the data profile, and a computation with one says in the head what its
number describes (`number_describes`). A computation names its kept
number in the head's `[kept]` table — the metrics key and its unit
(`labkit-init exp --kind compute --kept KEY --unit UNIT` stamps them, else
`protocol-fill <PROTOCOL> "kept.key=…" "kept.unit=…"`); the compute
skeleton reads the key from there, and finalize refuses a run that does
not hold it as a finite number. A computation a task asks to match
a stated value registers it in the head's optional `[reference]` table
(value, tolerance, relation, source — compared on the `[kept]` key;
`labkit-init exp --kind compute --kept KEY --reference VALUE[±TOL]` stamps it,
`docs/promise-block.md`): the run writes the verdict beside the number,
the Recorded results line carries it generated, and a `not met` is a
valid outcome; without the table nothing is compared. `protocol-check`
says "all must and should fields filled" once these stand; the Conclusion is not among
them — it is owed after the run (step 7), and `--list` keeps it under
"after the run — yours". The commit matters: the release
holds the registration to the commit of the first measurement, not to the
tree at the time of the run (`report-check` stage 2, the registration).
Which measurement is first, git's history says — the commit each run
recorded —, not the run id, which is local time; after a rebase or an
amend the first of each branch is held, and so is a run whose commit the
clone does not hold. The
fields the kind owes must stand in that commit — the kind included: that
commit is judged by the kind the protocol declares today, so a kind changed
after the measurement holds the report. The answering run's promise block
is also held to the first measurements' recorded registration: changing a
registered constant after seeing a run does not release its result.
Changing implementation bytes under unchanged promises still allows a
repair, new measurement and audit. The report the head registers
(`report = "REPORT.md"`, step 8) is bound the same way at `low`: the first
measurement starts only with it committed, and dropped or moved after it
the stop and the commit hold it — restore it, or hand the protocol over and
register anew; `high` is unchanged. A kind chosen wrong
is corrected before the first measurement (`labkit-init exp NAME --kind KIND
--change-kind`); after it, a new protocol registers the other kind. At `high`
the registration becomes a freeze instead: `preflight` clean, the
preflight audit run and decided, `frozen = true`.

## 3. The run

```
.venv/bin/python experiments/NN-<name>/scripts/01_measure.py
git add experiments/NN-<name> && git commit -m "…" -- experiments/NN-<name>
```

Reads: the data the script names (`SOURCE`, `INPUTS`). Writes:
`runs/<run_id>/` (the run record: `config.json` with the protocol binding,
the frozen inputs and the git state; `metrics.json`; `outputs.json`;
`completion.json`), the output file, a row in `runs.tsv`. Before the
directory exists `runlog` refuses: a run without the registration, an
unbound run, a full run under an unfrozen protocol at `high`
(`labkit/run/start_check.py`). At `low` this run is the instrument check
too; rerun it at will. The run id is `runlog`'s, never typed. With a
registered report and nothing adopted, `labkit-next` names the progress
account next — `protocol-fill <PROTOCOL> --discuss <run_id> --why "<what was
measured, what is still open>" --into REPORT.md` —, before the audit and
before any gap; it saves the state and releases nothing, and the next call
names the remaining gap as before.

## 4. finalize

```
finalize experiments/NN-<name>
```

Reads: the protocol, every run record of the area, the audit records, git.
Changes: nothing. Its first station chooses the **answering run**
(`answering_run.bound_answering_run`): the run the head adopted, once
it adopted one; before that the newest completed run bound to this
protocol id that reports an intent key — a computation registers no ids,
so for a computation it is simply the newest completed bound run. Every later
station holds that run, and so does every other gate: nobody chooses
twice. Then the stations: an adopted run that cannot answer blocks with
the withdrawal, and bound runs newer by name than it are a warning; the
output rows were written by it; its
promise block is the one the first measurement registered — a change
after it is held here, every changed sentence, key, constant and scope
named with the way back, and not first at the adoption; the
promises against its metrics; the code it ran — the measurement script
and the modules it imports, not the analysis code or the pin — and the
declared scopes unchanged since it ran (a fix after the run means:
measure anew with the fixed code and audit that run — restoring the old
code removes the difference, not the fault; it is the way out only for a
change not meant); no field left open; at `low` the source frozen in the run and
source and output tracked in git; the area test; every registered
output — the rows, and a deliverable the task names — the file the run
recorded (gone or another sha256 than outputs.json is a blocker); the
denominators; the audit records — one of a deleted run is a blocker; and
a kept output's null lane moved against its registered lane. Clean means
the run can carry a number; it does not release one.

## 5. The analysis audit and the decisions

```
labkit-audit experiments/NN-<name> --mode analysis
labkit-audit experiments/NN-<name> --decide N STATUS --why "REASON" [--not-assessable criterion-1] --record <file>
```

Reads: the protocol, the scripts and the repo-local modules they import,
the answering run's rows and `metrics.json`, the files it declared as
dependencies (a predictor's weights: small text whole, others by digest),
the cited rules of the standard — one model call. Writes: `audits/<minute>-analysis.toml`, one
`[[finding]]` per finding — its grade line and the lines the auditor wrote
below it, up to the next finding or section (a FIX, READ, notes tally,
verdict or scope line, a code fence; a blank line ends none), kept whole
in `text` —, each `open`, bound to the code (`scope_sha`), the
promise block (`block_sha`), the registration it judged — the kind and the
question with the other fields the kind owes (`registration`; the report
fields written later do not move it) — the run and what the auditor was
shown of it (`shown_sha`) — with the run the protocol has adopted when that
is another one, so withdrawing that adoption moves the state and the
next audit follows earlier findings up, while the first adoption of the
run audited moves nothing; and with the setup's prose the audit read
(Terms, Data / scope, Model / tool, Model I/O, Exclusions / filters,
Unit), so a description corrected in place is followed up too. The fields
written after the audit (the Summary, Recorded results, the Limitation lines,
the run list) are not bound. The person decides every finding; labkit stores the
decision and never makes one. An earlier analysis record's BLOCKERs are decided
before the next analysis audit: a follow-up is shown decided BLOCKERs only, so
`labkit-audit --mode analysis` refuses, before the call, while one stands
undecided in a record of another state, naming the `--decide` line of each. An accepted BLOCKER says its effect: the
verdicts stand within the limit (`stands`), or the run cannot judge the
named promise (`not assessable`) — where the protocol registers one: a
computation has no [[promise]] table, `--decide` refuses every id there,
and the printed ways out name `stands`, a fix, or the
handover instead. At `low` this is the lane's one
audit (LAB-017 The number of audits follows the cost tier); at
`high` the preflight audit came before the freeze and this one
comes before the number leaves (LAB-050 Analysis audit before reporting).

## 6. The decision review — when a BLOCKER was decided `limitation` with `stands`

```
protocol-fill PROTOCOL-<name>.md "Conclusion=…"      # the claim, first
labkit-audit experiments/NN-<name> --review [--record <file>]
```

Needed only when an accepted BLOCKER carries `stands`: a severe finding is
not settled by a reason alone. A second, cold auditor gets the decisions,
the Conclusion, the result as it will render, the files the findings name
and the run as shown, and says per decision `upheld`, `rejected` or
`insufficient` (`audits/<minute>-review.toml`). Only `upheld` releases;
it is bound to the decision and the Conclusion as reviewed — change
either and the review is stale. `rejected` means deciding again (limit the
Conclusion, change the effect, fix the fault), not drawing again; the
command refuses a second draw on an unchanged state. `--again` draws
anyway: its verdicts count, and it releases nothing — an `upheld` from
`--again` draws alone releases no decision. The exit says the state, not
the draw: 0 every decision reviewed released, 1 one held. Deciding again is
not closing: once a review did not uphold a decision on a finding, a
`false-positive` or `fixed` on it is under review as well — the
reviewer is asked whether the reason shows the finding inapplicable, the
fault gone in the files as audited, or the task somebody else's — and
`report-check` holds it by the finding's grade until a review upholds
the new decision. The same holds for a carried finding — one a follow-up
audit did not find gone — closed `false-positive`. A reason alone
releases nothing. An accepted WARNING with `stands` owes no review yet;
`report-check` names it as a warning.

## 7. The adoption

```
protocol-fill PROTOCOL-<name>.md --from-run <run_id>
```

Reads: the run's `metrics.json` and the covering audit records (the
analysis records whose code, promise and run stamps are the area's now).
Changes: **the protocol file only** — the head's `[result] run =
"<run_id>"` (the one adoption that this protocol reports a number: the
**adopted run**), the `Recorded results` line (the reportable verdict of
every registered promise — a quality check not assessable or
not met leaves each criterion not assessable —, then the other metric keys
and values as recorded, the run id, a note on the limits), one `Limitation (audit <record>
#N)` line per decided limitation, and the run's entry in the protocol run
list; the command names them as "Recorded results, [result] run, Runs".
Before writing it runs `report-check` on the written text and restores
the file on a blocker: a result adopted this way has passed every check.
The `Conclusion` is the author's sentence, written before this step (the
walkthrough does so); `--render` writes the generated lines again after
a change.

An adopted result is replaced, never overwritten: `protocol-fill
PROTOCOL-<name>.md --withdraw --why "<why>"` removes `[result]`, resets
the generated lines and marks the run's entry in the run list `withdrawn
<date>: <why>` (with `--into REPORT.md` it also withdraws the result
blocks there). It touches no audit record and releases nothing: the
analysis audit of the run that answers comes next — it follows earlier
decided BLOCKERs up —, then this step for that run. An audit made while
another run was adopted does not cover the new adoption. The commit
hook holds the code to an adopted run, so a change of the measuring code
after an adoption starts with the withdrawal.

## 8. The report block — the number outside the protocol

```
protocol-fill PROTOCOL-<name>.md --into REPORT.md
```

Changes: `REPORT.md` (or any note) gets a generated **report result
block** between two markers: the Recorded results line and the Limit
lines as the protocol renders them, owned by the protocol named in the
opening marker; after a new run is adopted the same command replaces it.
What the block guarantees: it equals what its protocol's bound sources
render — the run's metrics, the records' decided limitations — and the
protocol's whole chain holds. What it does not: the prose beside it. A
count or median the run never stored has no source; numbers outside the
block are named as unsourced (a hint), and whether the prose reads the
number rightly, and whether a decided limitation is enough, stay the audit's
and the reader's judgement. The report is a file at its own path: a
report that is a symbolic link, wherever it points, is refused at the
stop and the commit — the file a link points to can lie where no report
is read, as `data/` — and the refusal names the copy that replaces the
link; its other checks follow once the copy is in place.

A number about the inputs — records per split, class sizes, a median or
threshold the code derives — therefore belongs in `metrics.json`: the
measuring code's `evaluate_rows` computes it from the kept rows, and the
block shows it. If the rows cannot give it, the rows must keep what it
needs; writing it by hand into the report is no way out. The estimator
skeleton stores `scored_class_counts` (accuracy and auc): the items per
gold value in the scored rows — not the class distribution of the input
file, which also holds the unlabelled split. `02_analyze.py --check`
holds a stored key that vanished from the recomputation; it does not
notice a number left out of the dict and written in prose.

A report that cites a protocol's **answering run** while that protocol
has adopted no result is blocked: at `low` the report is the promotion,
and this is its shape without the adoption (`report_check.promotions`;
sixth haiku round, t3 and t18: `--from-run` refused, REPORT.md written
from `metrics.json` by hand). The sentence names the adoption
(`protocol-fill <PROTOCOL> --from-run <run_id>`, which says what it still
owes) and the way out for a run only looked at: a discussion block,
`protocol-fill <PROTOCOL> --discuss <run_id> --why "<what refused the
adoption, what you found>" --into REPORT.md` — its head holds the
protocol, the run and the why as TOML, its line is written from them. A
block without its why, one whose line differs from its head, a second
block of the same protocol and run, and a discussion of a run some
protocol has adopted block (the result block shows that number); numbers
in and beside a discussion are named as a hint. A report with a
discussion block owes a report review of its state: `labkit-audit <AREA>
--report-review REPORT.md` writes `audits/report-reviews/<minute>-review.toml`
with the fingerprint of the inputs it read, and the gate holds the report
until a review of the state it reads names no claim; a claim holds that
state, and only a changed report or source and a review of it release it.
The report the head registers (`report = "REPORT.md"`) owes the same
review of its own state once its result or handover block stands —
whether or not it discusses a run: its prose may still present an older
run's verdict as the result. `labkit-adopt` names that review as its
fourth step and does not hold it (the text comes after); the stop and the
commit do. A registered report never written after the area measured
holds the stop as an incomplete delivery; a research note citing a run
owes no review unless it discusses one, and `--report-review` reads any
report on request.
While the area's audit evidence is gone (`attempts.evidence_gaps`) no
review can start, so the hold, the review's refusal, the adoption's and
the handover name the route that works: restore the evidence, or the
report cites no run of the area (`report_hold.lost_evidence`).
`--again` draws once more on a judged state: its claims hold the state
like any review's, and it releases nothing. The command prints this
draw's claims and the state apart, and its exit code is the state's — 0
once the state is released, 1 after a draw while a claim or only
`--again` draws hold it (the commit counts the review records the index
holds); a plain re-run on a claimed state is refused before any call,
exit 2. A probe's or an older run's citation stays the warning it was:
an exploration's run is looked at.

**The registered report owes its result.** A protocol whose head names
its report file (`report = "REPORT.md"`, a path relative to the
repository root, stamped by `labkit-init exp --report-file REPORT.md`, or
on a protocol stamped without it registered by `protocol-fill <PROTOCOL>
report=REPORT.md` — before the first measurement only, another file with
`--force`; once the area measured, no fill moves or drops it;
`usability stage` registers it for the SAB tasks, whose sheet asks for
the file) is owed that result by that file, run id or not: once the
file exists — in the tree at the stop, in the index at the commit — it
carries the protocol's result block of the adopted run or the
protocol's handover block, else the stop, the commit and the plain
`report-check` hold it with the three ways out: adopt the newest kept
run and `--into`; `--discuss`, which releases nothing (the report then
still owes the result or the handover); `--handover`. While nothing is
adopted, a discussion of the run the gates hold the protocol to is the
**progress account**: the commit takes it without a report review, the
stop holds it once naming the audit and the adoption or the handover —
the commit rule for this state is deliberately looser, the release
requirements are not —, and the adoption's `--into` puts the result block
where it stood (`report_hold.progress_account`, `report_blocks.with_block`).
A number with the run id removed, a run id typed in, a discussion of
another run, a handover block typed by hand without its record: all held (`report_hold.report_owed`;
pressure pilot 2026-10-29, tasks 34, 15, 60: the hook refused the
citation, the agents deleted the run id, the commit passed). A report
not yet written owes nothing — the obligation is on what is delivered
—, and a protocol that registers none holds no file to this; general
notes and input descriptions elsewhere stay outside it.

## 9. The gate — at the stop and the commit

To end a protocol without a result (a handover), use `labkit-audit <AREA> --findings`
first: it reads all open BLOCKER records and evidence errors without a
model call and prints complete commands. For a failed audit call — a
`-failed.toml` or an attempt the journal ended without a record (its
answer kept under `audits/answers/`) — it names the call, its error and
its kept answer and offers the handover, exit 2; that call left no
findings to decide. A later completed audit of the same mode and the
same protocol with the same promise block supersedes it, also after a
code change: `--findings` then shows it as superseded, informational.
The old call and its kept answer stay as they are; superseding confirms neither the call's content nor the repair of any finding, and a recorded BLOCKER stays under the follow-up rule. Whether the current result may be adopted is decided
by the checks of the current code and run (the follow-up holds,
report-check), not by the supersession. The protocol is named by its file name in the area, not by the head's `id` (a protocol without an `id` must still be nameable; Max, 2026-10-28): a protocol file renamed since counts as another protocol, so its earlier failed calls stay named until the file is renamed back and audited, or the area is handed over. A historical call (a start of
labkit 0.103.0 or earlier, which names no promise block and protocol, or
a `-failed.toml` no journal attempt names) is named as such with the
audit, run again now in the current format, that supersedes it — an
audit of its mode, of any protocol of the area, since the old start
names none. A readable BLOCKER that stays unresolved stays `open`;
use its `protocol-fill <PROTOCOL>
--handover --why "<what blocks>" --tried "<what you tried>" --into
REPORT.md` command. It withdraws the result's adoption, keeps an
immutable handover record in `audits/handovers/` — with the run the
protocol stands at and what held its adoption, computed, and a warning
when nothing held it (a missed criterion is a result) — and writes its handover
block into the report (one per protocol, replaced in place). The selected
protocol's result blocks in that report are withdrawn; other text and
other protocols' blocks stay. Citations in prose or other reports must
still be removed or explicitly discussed. Only an unchanged block, protocol and audit state can
finish despite documented integrity loss; a changed block or new evidence
needs a new handover, prose beside the block does not. The commit
requires the same files staged together. Normal audit/adoption
still holds missing evidence. See [recovery contract](notes/2026-10-27-handover-recovery.md).

```
report-check experiments/NN-<name>                       # by hand
report-check --if-reported [--staged] <paths>            # what the stop hook and the pre-commit run
```

Reads: the protocol as the named state holds it (the tree at the stop,
the index at the commit), the runs, the records, the reviews, the citing
reports. Changes: nothing. The stations, every one named in its output:
the freeze (`high`) or the registration as committed at the
first measurement (`low`); finalize clean and the answering run a
full run; a decided analysis record covering code, promises, run and what
was shown; every generated line equal to its rendering, written once;
every BLOCKER's `stands` upheld by a review; `02_analyze.py --check`
passing. A report that cites an adopted run owes that protocol's block —
also a committed, untouched report, when the protocol among the paths
adopts that run newly against HEAD (a report committed before the
adoption, then the adoption committed alone, left the delivered
state with a blocker no commit saw). A protocol that has adopted no result
owes nothing but its registered report: an exploration ends without a
reported number, and a REPORT.md its head registers, once delivered,
carries its handover block or its result block (section 8; the
protocols registering a file among the paths are held too, the report
at the repository root lying in no area).

## The questions a reader should be able to answer

- *Where is the answering run chosen?* Once, in
  `answering_run.bound_answering_run`, called by finalize's first station;
  every other gate reads that choice (`audit_binding.audited_run`).
- *When is a decision review needed?* When an accepted BLOCKER carries
  `stands`; `report-check` blocks until one upholds it. And when a
  finding a review did not uphold is closed instead (`false-positive`,
  `fixed`): the new decision owes its own review. And when a
  carried finding is closed `false-positive`. Not for
  `not assessable`, not (yet) for a WARNING.
- *Which file does `--from-run` change?* The protocol, and only it.
- *What does the report block guarantee, and what remains judgement?* The
  block equals its bound sources and its protocol's chain holds; the
  prose, the reading of the number and whether a limit is enough do not
  follow from it.
