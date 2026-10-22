# The workflow: from a registered question to a kept number

One pass through labkit for one experiment area, step by step: the command,
what it reads and what it changes, what must hold before it, and what a
clean exit means. The rules behind each step are linked, not restated —
the chain of checks is in [architecture](architecture.md), the promise
format in [promise-block](promise-block.md), which run answers in
[protocol-run-binding](protocol-run-binding.md), the lab standard in
`labkit/docs/standard.md` (`python -m labkit.formats.rules show LAB-nnn`).
Terms are the README's glossary. The steps are the `seconds` lane's; where
`minutes`/`hours` owe more, it stands at its place.

An executable walk of these steps on the stamped count task is
[`examples/count-walkthrough.sh`](examples/count-walkthrough.sh) — run it
in an empty directory with a venv that has labkit, read its output beside
this page; `tests/test_workflow_example.py` keeps it true.

## 0. The area

```
labkit-init lab <dir>                       # once per lab repo
labkit-init exp <name> --cost seconds       # one area per question; --model ALIAS with a model in the loop
```

Reads: the templates shipped with labkit. Writes: `experiments/NN-<name>/`
with `PROTOCOL-<name>.md` (its TOML head stamped with a protocol id, the
cost tier, `frozen = false`), `scripts/01_measure.py` and `02_analyze.py`
(the skeleton for the instrument: count, estimator or model), the area
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
the audit's question. At `minutes`/`hours` the model skeleton's `--probe`
checks the instrument on a few items before anything is frozen.

## 2. The registration

```
protocol-fill PROTOCOL-<name>.md "Question / hypothesis=…" "Unit=…" …
protocol-check PROTOCOL-<name>.md
git add -A && git commit
```

Reads and changes: the protocol's prose fields, by exact label
(`protocol-fill --list` names what is still open). Which fields: the cut
of the tier — at `seconds` the question, scope, exclusions and unit; with a
model also criterion, admissibility condition and data profile
(`standard_contract.registration_fields`). The commit matters: the release
holds the registration to the commit of the first measurement, not to the
tree at the time of the run (`report-check` station 1). At `minutes`/`hours`
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
unbound run, a full run under an unfrozen protocol at `minutes`/`hours`
(`labkit/run/start_check.py`). At `seconds` this run is the instrument check
too; rerun it at will. The run id is `runlog`'s, never typed.

## 4. finalize

```
finalize experiments/NN-<name>
```

Reads: the protocol, every run record of the area, the audit records, git.
Changes: nothing. Its first station chooses the **answering run** — the
newest completed run bound to this protocol id that reports an intent key
(`answering_run.bound_answering_run`); every later station holds that run,
and so does every other gate: nobody chooses twice. Then: the declared
run names it (or none yet), its rows come from it, promises against
metrics, declared scopes unchanged, open fields, the source frozen in the
run and tracked in git (`seconds`), the area test, the denominators, the
audit records — an audit record of a deleted run is a blocker. Clean
means the run can carry a number; it does not release one.

## 5. The analysis audit and the decisions

```
labkit-audit experiments/NN-<name> --mode analysis
labkit-audit experiments/NN-<name> --decide N STATUS "REASON" [--effect stands | "C1 not assessable"] --record <file>
```

Reads: the protocol, the scripts and the repo-local modules they import,
the answering run's rows and `metrics.json`, the cited rules of the
standard — one model call. Writes: `audits/<minute>-analysis.toml`, one
`[[finding]]` per line, each `open`, bound to the code (`scope_sha`), the
promise block (`block_sha`), the run and what the auditor was shown of it
(`shown_sha`). The person decides every finding; labkit stores the
decision and never makes one. An accepted BLOCKER says its effect: the
verdicts stand within the limit (`stands`), or the run cannot judge the
named promise (`not assessable`). At `seconds` this is the lane's one
audit (LAB-017 The number of audits follows the cost tier); at
`minutes`/`hours` the preflight audit came before the freeze and this one
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
command refuses a second draw on an unchanged state. An accepted WARNING
with `stands` owes no review yet; `report-check` names it as a warning.

## 7. The adoption

```
protocol-fill PROTOCOL-<name>.md --from-run <run_id>
```

Reads: the run's `metrics.json`, the covering audit records. Changes: **the
protocol file only** — the head's `[result] run = "<run_id>"` (the one
declaration that this protocol reports a number: the **declared run**),
the `Recorded results` line (every metric key and value as recorded, the
run id, a note on the limits), one `Limit (audit <record> #N)` line per
decided limit, and the run's entry in the protocol run list. Before
writing it runs `report-check` on the written text and restores the file
on a blocker: a result adopted this way has passed every check. The
`Conclusion` stays the author's sentence; `--render` writes the generated
lines again after a change.

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
number rightly stays the audit's and the reader's judgement.

## 9. The gate — at the stop and the commit

```
report-check experiments/NN-<name>                       # by hand
report-check --if-reported [--staged] <paths>            # what the stop hook and the pre-commit run
```

Reads: the protocol as the named state holds it (the tree at the stop,
the index at the commit), the runs, the records, the reviews, the citing
reports. Changes: nothing. The stations, every one named in its output:
the freeze (`minutes`/`hours`) or the registration as committed at the
first measurement (`seconds`); finalize clean and the answering run a
full run; a decided analysis record covering code, promises, run and what
was shown; every generated line equal to its rendering, written once;
every BLOCKER's `stands` upheld by a review; `02_analyze.py --check`
passing. A report that cites a declared run owes that protocol's block.
A protocol that declares no result owes nothing: an exploration ends
without a reported number.

## The questions a reader should be able to answer

- *Where is the answering run chosen?* Once, in
  `answering_run.bound_answering_run`, called by finalize's first station;
  every other gate reads that choice (`audit_binding.audited_run`).
- *When is a decision review needed?* When an accepted BLOCKER carries
  `stands`; `report-check` blocks until one upholds it. Not for `not
  assessable`, not (yet) for a WARNING.
- *Which file does `--from-run` change?* The protocol, and only it.
- *What does the report block guarantee, and what remains judgement?* The
  block equals its bound sources and its protocol's chain holds; the
  prose, the reading of the number and whether a limit is enough do not
  follow from it.
