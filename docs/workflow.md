# The workflow: from a registered question to a kept number

One pass through labkit for one experiment area, step by step: the command,
what it reads and what it changes, what must hold before it, and what a
clean exit means. The rules behind each step are linked, not restated —
the chain of checks is in [architecture](architecture.md), the promise
format in [promise-block](promise-block.md), which run answers in
[protocol-run-binding](protocol-run-binding.md), the lab standard in
`labkit/docs/standard.md` (`python -m labkit.formats.rules show LAB-nnn`).
Terms are the README's glossary. The steps are the `low` tier's; what
`high` owes on top is said inside the step it belongs to.

Five words the page leans on: a **full run** is one started with
`run_kind="measurement"` (not a probe, not a preparation); a **station** is
one named check of a gate, told in the gate's output in its order; the
**release** is the moment a number leaves the area as a reported result
(the adoption, the stop, the commit); a **hint** is static evidence —
named, never blocking; the **declared run** (`[result] run` in the head)
and the **answering run** (the choice below) must be the same run, or
`report-check` blocks.

An executable walk of these steps on the stamped count task is
[`examples/count-walkthrough.sh`](examples/count-walkthrough.sh) — run it
in an empty directory with a venv that has labkit, read its output beside
this page; `tests/test_workflow_example.py` keeps it true.

## 0. The area

```
labkit-init lab <dir>                       # once per lab repo
labkit-init exp <name> --repeat-cost low --kind compute   # one area per question; --kind fit|apply when the number judges predictions; --model ALIAS with a model in the loop
```

Reads: the templates shipped with labkit. Writes: `experiments/NN-<name>/`
with `PROTOCOL-<name>.md` (its TOML head stamped with a protocol id, the
repeat cost, `frozen = false`), `scripts/01_measure.py` and `02_analyze.py`
(the skeleton for the instrument: compute, estimator or model), the area
test, the README card. Nothing is owed yet; `protocol-check --contract`
prints what the tier will owe and when.

## 1. The measurement code

```
<edit scripts/01_measure.py>                # the TODOs: what is counted, how, the number
code-check experiments/NN-<name>            # after every code change
```

Reads: the scripts, the protocol's promise tables. Changes: nothing.
Clean means: every declared key appears in the code, every `PROMPT`
constant stands in the protocol, the parsers have fixtures — the static
part of the promise → code link. It proves nothing about meaning; that is
the audit's question. At `high` the `--probe` of the model and the
estimator skeletons checks the instrument on a few items before anything
is frozen (a few real calls; a reduced estimator on twelve labelled
items); a computation has none.

## 2. The registration

```
protocol-fill PROTOCOL-<name>.md "Question / hypothesis=…" "Unit=…" …
protocol-check PROTOCOL-<name>.md
git add -A && git commit
```

Reads and changes: the protocol's prose fields, by exact label
(`protocol-fill --list` names what is still open). Which fields follow the
kind, not the tier (`standard_contract.registration_fields(kind, model)`):
every kind the question; a fit or an apply also the success criterion, the
admissibility condition and the null condition / anchors; a `[model]` table
adds the data profile, and a computation with one says in the head what its
number describes (`number_describes`). `protocol-check` says "all must
and should fields filled" once these stand; the Conclusion is not among
them — it is owed after the run (step 7), and `--list` keeps it under
"after the run — yours". The commit matters: the release
holds the registration to the commit of the first measurement, not to the
tree at the time of the run (`report-check` stage 2, the registration): the
fields the kind owes must stand in that commit — the kind included: that
commit is judged by the kind the protocol declares today, so a kind changed
after the measurement holds the report. A field's value changed after that
commit (a bar lowered) is not compared yet. A kind chosen wrong
is corrected before the first measurement (`labkit-init exp NAME --kind KIND
--change-kind`); after it, a new protocol registers the other kind. At `high`
the registration becomes a freeze instead: `preflight` clean, the
preflight audit run and decided, `frozen = true`.

## 3. The run

```
.venv/bin/python experiments/NN-<name>/scripts/01_measure.py
git add -A && git commit
```

Reads: the data the script names (`SOURCE`, `INPUTS`). Writes:
`runs/<run_id>/` (the run record: `config.json` with the protocol binding,
the frozen inputs and the git state; `metrics.json`; `outputs.json`;
`completion.json`), the output file, a row in `runs.tsv`. Before the
directory exists `runlog` refuses: a run without the registration, an
unbound run, a full run under an unfrozen protocol at `high`
(`labkit/run/start_check.py`). At `low` this run is the instrument check
too; rerun it at will. The run id is `runlog`'s, never typed.

## 4. finalize

```
finalize experiments/NN-<name>
```

Reads: the protocol, every run record of the area, the audit records, git.
Changes: nothing. Its first station chooses the **answering run**
(`answering_run.bound_answering_run`): the newest completed run bound to
this protocol id that reports an intent key — a computation registers no ids,
so for a computation it is simply the newest completed bound run. Every later
station holds that run, and so does every other gate: nobody chooses
twice. Then the stations: the head's declared run is the answering run
(or no run is declared yet); the output rows were written by it; the
promises against its metrics; the code it ran — the measurement script
and the modules it imports, not the analysis code or the pin — and the
declared scopes unchanged since it ran (a fix after the run means:
restore the code as it ran, or measure anew and audit that run); no
field left open; at `low` the source frozen in the run and
source and output tracked in git; the area test; the denominators; the
audit records — one of a deleted run is a blocker. Clean means the run
can carry a number; it does not release one.

## 5. The analysis audit and the decisions

```
labkit-audit experiments/NN-<name> --mode analysis
labkit-audit experiments/NN-<name> --decide N STATUS "REASON" [--effect stands | "C1 not assessable"] --record <file>
```

Reads: the protocol, the scripts and the repo-local modules they import,
the answering run's rows and `metrics.json`, the cited rules of the
standard — one model call. Writes: `audits/<minute>-analysis.toml`, one
`[[finding]]` per line, each `open`, bound to the code (`scope_sha`), the
promise block (`block_sha`), the registration it judged — the kind and the
question with the other fields the kind owes (`registration`; the report
fields written later do not move it) — the run and what the auditor was
shown of it (`shown_sha`). The person decides every finding; labkit stores the
decision and never makes one. An accepted BLOCKER says its effect: the
verdicts stand within the limit (`stands`), or the run cannot judge the
named promise (`not assessable`). At `low` this is the lane's one
audit (LAB-017 The number of audits follows the cost tier); at
`high` the preflight audit came before the freeze and this one
comes before the number leaves (LAB-050 Analysis audit before reporting).

## 6. The decision review — when a BLOCKER was accepted with `stands`

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
command refuses a second draw on an unchanged state. Deciding again is
not closing: once a review did not uphold a decision on a finding, a
`dismissed`, `fixed` or `deferred` on it is under review as well — the
reviewer is asked whether the reason shows the finding inapplicable, the
fault gone in the files as audited, or the task somebody else's — and
`report-check` holds it by the finding's grade until a review upholds
the new decision. The same holds for a carried finding — one a follow-up
audit did not find gone — closed `dismissed` or `deferred`. A reason alone
releases nothing. An accepted WARNING with `stands` owes no review yet;
`report-check` names it as a warning.

## 7. The adoption

```
protocol-fill PROTOCOL-<name>.md --from-run <run_id>
```

Reads: the run's `metrics.json` and the covering audit records (the
analysis records whose code, promise and run stamps are the area's now).
Changes: **the protocol file only** — the head's `[result] run =
"<run_id>"` (the one declaration that this protocol reports a number: the
**declared run**), the `Recorded results` line (every metric key and value
as recorded, the run id, a note on the limits), one `Limit (audit <record>
#N)` line per decided limit, and the run's entry in the protocol run
list; the command names them as "Recorded results, [result] run, Runs".
Before writing it runs `report-check` on the written text and restores
the file on a blocker: a result adopted this way has passed every check.
The `Conclusion` is the author's sentence, written before this step (the
walkthrough does so); `--render` writes the generated lines again after
a change.

## 8. The report block — the number outside the protocol

```
protocol-fill PROTOCOL-<name>.md --into REPORT.md
```

Changes: `REPORT.md` (or any note) gets a generated **report result
block** between two markers: the Recorded results line and the Limit
lines as the protocol renders them, owned by the protocol named in the
opening marker; after a new run is adopted the same command replaces it.
What the block guarantees: it equals what its protocol's bound sources
render — the run's metrics, the records' decided limits — and the
protocol's whole chain holds. What it does not: the prose beside it. A
count or median the run never stored has no source; numbers outside the
block are named as unsourced (a hint), and whether the prose reads the
number rightly, and whether a decided limit is enough, stay the audit's
and the reader's judgement.

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
declares no result is blocked: at `low` the report is the promotion,
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
protocol does declare block (the result block shows that number); numbers
in and beside a discussion are named as a hint. A report with a
discussion block owes a report review of its state: `labkit-audit <AREA>
--report-review REPORT.md` writes `audits/report-reviews/<minute>-review.toml`
with the fingerprint of the inputs it read, and the gate holds the report
until a review of the state it reads names no claim; a claim holds that
state, and only a changed report or source and a review of it release it. A probe's or an older
run's citation stays the warning it was: an exploration's run is looked at.

## 9. The gate — at the stop and the commit

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
passing. A report that cites a declared run owes that protocol's block —
also a committed, untouched report, when the protocol among the paths
declares that run newly against HEAD (a report committed before the
declaration, then the declaration committed alone, left the delivered
state with a blocker no commit saw). A protocol that declares no result
owes nothing: an exploration ends without a reported number.

## The questions a reader should be able to answer

- *Where is the answering run chosen?* Once, in
  `answering_run.bound_answering_run`, called by finalize's first station;
  every other gate reads that choice (`audit_binding.audited_run`).
- *When is a decision review needed?* When an accepted BLOCKER carries
  `stands`; `report-check` blocks until one upholds it. And when a
  finding a review did not uphold is closed instead (`dismissed`,
  `fixed`, `deferred`): the new decision owes its own review. And when a
  carried finding is closed `dismissed` or `deferred`. Not for
  `not assessable`, not (yet) for a WARNING.
- *Which file does `--from-run` change?* The protocol, and only it.
- *What does the report block guarantee, and what remains judgement?* The
  block equals its bound sources and its protocol's chain holds; the
  prose, the reading of the number and whether a limit is enough do not
  follow from it.
