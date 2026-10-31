# labkit agent guide — the workflow in full

This guide is the reference behind the stamped `AGENTS.md`: every step,
its conditions and the reason for each rule. Read the part for your
current step only. `labkit-next <area>` names that step.

## When a gate stops you

Run `labkit-audit <area> --findings`. Without a model call, it prints the
open BLOCKERs, the evidence problems and the complete decision and handover
commands. Use those commands. Do not invent flags. If it names a failed
audit call, that call left no findings to decide. A superseded call needs
nothing more, but recorded BLOCKERs still need their follow-up.

Hand over only when a way out needs a prerequisite that is missing (see
"When you are stuck"). This holds with an audit or without one. labkit
gives the mechanical next steps. You decide the cause, and whether a claim is
scientifically justified.

## Deliver an external task's outputs

The run's metrics do not replace the files the task names. The answering
run writes each one:

- `DELIVERABLES` in the measuring script names the path. `labkit-init exp
  --deliverable <path>` stamps it. Else, set it yourself.
- `DELIVERABLE_COLUMNS` names the task's columns in its order
  (`--deliverable-columns`). The write refuses a missing, unnamed or
  misplaced column.
- `deliverable_rows()` gives the rows from the kept rows and the metrics.

A result no longer holds when a gate refuses it, or when an audit BLOCKER
against its code or data stays unfixed. Then remove the output file at
once. Write it again from the next adopted run. Until then, keep the file
away. Say in the report which you did, and why.

A protocol head can register a report (`report = "REPORT.md"`, stamped
by `labkit-init exp --report-file`). Then the stop and the commit hold
that file. They release it when it carries the adopted run's generated result
block or the handover block. A number without its run id, a typed run id
or a discussion block releases nothing. Other notes owe nothing.

## Choose the experiment: three separate decisions

`AGENTS.md` gives the table of `kind`, `repeat_cost` and `type`. These
points add to it:

- Decide `kind` first, by what the reported result claims (`AGENTS.md`):
  a computed quantity is `compute`. A claim about predictions is `fit` if
  this experiment trained, tuned or selected the model, else `apply`. A
  tuning rule registered in advance still tunes. Document and audit a
  training under `compute` like any other code.
- Evaluate a `fit` on held-out labelled rows. Judge a tuned detector on
  rows kept apart from the tuning.
- A RandomForest fitted in seconds is `fit`, usually at `low`. A threshold
  of k times each signal's own noise, with k fixed in advance, tunes
  nothing. Scored against annotations, it is `apply`. A count of its
  detections is `compute`. An unchanged LLM judged against labels is
  `apply`.
- `repeat_cost` is the cost of the measurement, not of the audit or the
  whole task.
- Neither `low` nor `exploratory` removes the criterion or the audits of a
  fit or an apply.
- For `confirmatory`, the plan stood before the results. For a fit or an
  apply, it includes the criterion. For a computation, it is quantity, unit
  and exclusions. A written type does not make a claim valid.

Take the area's obligations from `protocol-check <PROTOCOL> --contract`,
not from an older lab's instructions. The pin is the `labkit` line of
`requirements.lock`, else of `requirements.txt`, for the whole repository.
`labkit-check` prints it beside the installed version. If you raise the
pin, no earlier audit covers any area.

Do not convert old protocols and runs to pass current gates. To reproduce
an old run, use its commit and a venv from its `requirements.lock`. Stamp
a fresh area for new work. A new area does not discard an earlier result.

## One workflow — every kind and both repeat costs

Follow the steps in order. **Additional at `high`** applies only when
`repeat_cost = "high"`. A computation has no prediction criterion. Fill
the fields its contract requests.

### 1. Create the area and register the question

`labkit-init exp <name> --repeat-cost <cost> --kind <kind>` stamps the
protocol, the scripts and the area test. Add `--model <alias>` only if
calls use `models.toml`. If the kind is wrong before the first
measurement, run `labkit-init exp <name> --kind <kind> --change-kind`.
After it, use the replacement route under "When you are stuck".

Fill the before-run fields, including `type` and each promise's sentence:

- For every kind, fill the question, Data / scope, the exclusions and the
  unit. In Data / scope, name the source and the producer script. `protocol-fill <PROTOCOL>
  --data-counts` writes the counts after `scripts/00_prepare.py`.
- For a fit or an apply, also fill the inference criterion, the quality
  check and a null condition in the same run. The criterion decides which
  conclusion the result supports. The quality check tests whether the
  measurement can carry that conclusion.
- If a computation is compared with a value the task states ("0.62 within
  0.01"), run this before the first measurement: `labkit-init exp --kind compute --reference
  KEY=VALUE[±TOL]`, or write the head's `[reference]` table yourself. KEY
  is the skeleton's `METRIC_KEY`.
  Register no criterion. A miss is a result, and the run writes the
  verdict.
- If the head contains a `[model]` table, also fill Data profile. Copy the
  skeleton's `PROMPT` constants with `protocol-fill <PROTOCOL> --prompts`.

A promise id is its kind and a number:

- `criterion-1`: the condition that decides which conclusion the result
  supports.
- `quality-check-1`: what must hold for the measurement to carry that
  conclusion.
- `branch-1`: what follows from each outcome, such as `criterion-1 met →
  supported: reported as meeting the criterion; otherwise → missed:
  reported as a miss`.

Fill values with `protocol-fill <PROTOCOL> "type=exploratory"
"criterion-1 sentence=<value>" "<Label>=<value>"`. A computation without
promises omits the criterion-1 assignment. Set criteria and constants
before you see results.

State each promise value in its sentence before the commit. `margin` is
the smallest lead over the null lane that you call success. `null_band` is
how far the null lane can stray from its target:

- At `apply` with the estimator skeleton, the target is the score against
  randomly assigned labels. After you prepare the data, run
  `.venv/bin/python <area>/scripts/01_measure.py --calibrate-null --write`.
  It registers the band by the registered rule, before the first
  measurement only.
- At `fit`, the null lane refits on permuted labels in every fold: twice
  per fold at `low` (3 folds), five times at `high` (5 folds). The plan is
  in the measurement script's head (`FIT_PLAN`) and in the run's config.
  Give the band a reasoned value. At `high`, you can use the spread of
  those refits over a few `--seed` values of `--probe`.
- Write the Timebox as a duration first (`45 min — then record and ask`).
  A fit times its first fold and stops before the budget when the
  projection exceeds it, with the numbers and the way out.

After the first measurement, these values stay fixed. Decide a finding
about them by the ways under "When you are stuck".

### 2. Implement and test the instrument

For an estimator or prompt skeleton, read `.venv/bin/python
<area>/scripts/01_measure.py --show 3` before you measure. Run `code-check
<area>` after each code change. Use the scripts your area has. The prompt
skeleton's `00_prepare.py --audit` counts are hints for the data profile,
not the judgement.

**Additional at `high`:** for an estimator or prompt skeleton, run
`.venv/bin/python <area>/scripts/01_measure.py --probe` on the real
pipeline. labkit discards its rows. For a computation, test the
calculation. Test the evaluation on synthetic extremes before the freeze.
The probe can correct the instrument. It must not change the hypothesis or
the criteria. At `low`, no probe, no preflight audit and no freeze are owed.
The full measurement checks the instrument.

### 3. Commit and run

**Additional at `high`, before the full run:**

1. Run `preflight <area>`, then `labkit-audit <area> --mode preflight`.
2. Decide its findings as in step 4.
3. Put the record filename into the head's `preflight_audit`.
4. Add the report fields with `labkit-init exp <name> --report`.
5. Fill what the contract requires, then set `frozen = true`.

If you fix code, audit the fixed code before the freeze.

Commit the code and the registration. Keep raw data under `data/raw/`.
Prepare inputs with a script, `scripts/00_prepare.py`, into
`data/prepared/`. Put small inputs into git if you can legally
share them. For large or protected data, commit the source or access route
and the version. To resume a run, use the same measurement command.

### 4. Finalize, audit and decide

Before you report any result, run `finalize <area>`, then `labkit-audit
<area> --mode analysis`. Decide each finding with the command that
`labkit-audit <area> --findings` prints:

`labkit-audit <area> --decide <N> <STATUS> --why "<REASON>" --record <record>`

READ lines are hints, not findings to decide.

| status | what follows |
|---|---|
| `fixed` | The next analysis audit judges the repair. Until it finds the fault resolved, the number is held. |
| `limitation` | The number carries a Limitation line. The verdict holds within the limit. A second auditor must uphold a BLOCKER. |
| `false-positive` | A BLOCKER needs a second auditor (`labkit-audit <area> --review --record <record>`) before the number leaves. A WARNING does not. |

`fixed` means that you corrected the whole named fault. If the finding ends
in `check: <key> — <what it must show>`, also show its diagnostic. The
decision list prints this work order:

> extend the measuring script so that its kept rows carry what `<key>` (what it must show) needs and `evaluate_rows()` computes it from them, writing the value to metrics.json under that key — the check (`02_analyze.py --check`) recomputes every metrics key from the kept rows and refuses one computed beside them; a key written as a constant shows nothing

If the finding ends in `check: file:<path>`, declare that file among the
files the run reads (`PREDICTOR_FILES`, else runlog's `data=`). Then
measure and audit again. Without that value or file, the follow-up judges
the repair not assessable.

After a fix of the measurement code, repeat steps 2 to 4. Give the new
output file a new name in the measuring script. Keep the earlier file and
its runs. Decide the unresolved BLOCKERs that the new audit carries into
its record. Editing code does not repair an old run. At `high`, first set
`frozen = false`. Do not change the question, criteria or constants. Then
take step 3 again.

If a quality check is unmet or not assessable, every criterion is not
assessable. The measured values stay description.

### 5. Write the claim and obtain any decision review

Write the Conclusion before the adoption, not as a list of metric keys.
With a model, Raw output holds one real prompt and answer pair per finding,
from the kept output that the finding names. To change the Conclusion
after the adoption, add `--force`. The adoption and the report block stay
valid. Redo each decision review that is owed. A new measurement is not
owed.

If you decide a BLOCKER `limitation` or `false-positive`, run
`labkit-audit <area> --review --record <record>`. If the review rejects
it, correct the decision, the evidence or the claim. Do not draw again
until a review approves.

- A BLOCKER a review did not uphold, now decided `fixed` or
  `false-positive`, needs an upholding review before release.
- A carried BLOCKER closed as `false-positive` needs an upholding review.
- A changed Conclusion or decision makes its review stale. Review again
  where the decision needs a review.
- `--again` never supplies a missing approval or overrules a rejection.

### 6. Adopt and deliver

`labkit-adopt <area> <run_id>` needs the measurement, a decided covering
analysis audit and a passing `02_analyze.py --check`. An analysis audit
with no findings covers the run if it saw the current code, promises and
run. It re-checks earlier decided BLOCKERs itself. You add nothing to the
record.

If a result is adopted and you fixed something, withdraw the old adoption
first: `protocol-fill <PROTOCOL> --withdraw --why "<why>"`. An audit made
while another run is adopted does not cover the next adoption. Then:

1. Run the new run's analysis audit and decide its findings.
2. Write the Conclusion for it, with `--force` if one is filled.
3. Run `labkit-adopt <area> <new run_id>`.

Adoption is refused while any other blocker stands. Fix those first.
Adoption is the last step, not the fix. A failed criterion under passed
quality checks is a reportable miss.

After you change an audit decision, run `protocol-fill <PROTOCOL>
--render`. Then write the report block again with `protocol-fill
<PROTOCOL> --into REPORT.md`.

To discuss a run without adoption, run `protocol-fill <PROTOCOL> --discuss
<run_id> --why "<what refused adoption, what you found>" --into
REPORT.md`. Say that the question stays open. A discussion owes
`labkit-audit <area> --report-review REPORT.md` of the finished report, in
this order:

1. Write the whole report.
2. Run `--discuss`.
3. Run the review.
4. Commit.

Any later change, a rewrite of the file included, owes a new review. If
the reviewer names a wrong claim, correct it and review again. A clean draw
on the unchanged state releases nothing. If the area's audit evidence is
gone, no review runs. Restore the evidence, or remove the run ids and the
discussion block and keep the handover block.

Stage the required review records with the commit. `runlog reindex <area>`
rebuilds the ignored run index `runs.tsv`.

## When you are stuck — both repeat costs

Name the cause before you change anything. An honest handover without a
result is an admissible end. A refusal alone is no reason to hand over: it
names its next step. Hand over only if a way out needs a prerequisite that
is missing, and name it. `--no-verify` is never a way out. `labkit-audit`
prints these ways out with each decision list:

- **an implementation error** — The code does not do what the
  registration says. If the protocol has adopted a result, withdraw it
  first: `protocol-fill <PROTOCOL> --withdraw --why "<why>"`. Fix the code
  and decide `fixed`, naming the change. Measure again under the unchanged
  registration, and audit the new run. Example: if the code uses an
  excluded feature, remove it from the code, not from the exclusion rule.
- **a missed criterion** — That is the result. Report the miss first.
  Example: held-out performance is below the registered margin. Lowering
  the margin is not a repair.
- **an unjudged promise** — If you cannot fix a fault, decide it
  `limitation` with `--not-assessable <ID>`. Report the values as
  description, not as a pass. A `compute` without promises has none to
  leave unjudged, and `--decide` refuses every id. There, name the limit in
  the Conclusion (`limitation`), or hand the protocol over.
- **an invalid registration** — The question cannot be answered as
  written. Example: the definitions of what the criterion judges conflict.
  Explain the conflict. Then register anew with `labkit-init exp
  <new-name> --kind …`, `type = "exploratory"`, `[replaces] protocol =
  "<id>"` and one `[[replaces.change]]` (what, from, to, why) per change.
  Decide or hand over the predecessor. Its open BLOCKERs stay open. Its
  verdict is rendered first: a new approach never turns an earlier miss
  into a pass. A new question after a valid result, a miss included, is a
  protocol of its own without `[replaces]`. If it builds on an earlier
  protocol, name that protocol in its Question / hypothesis and make it
  `exploratory`. No gate checks this. Use `[replaces]` only for a
  registration that cannot be answered as written, or one incomplete at its
  first measurement.
- **an incomplete registration** — report-check says that the committed
  registration lacked a field at the first measurement. That measurement
  is exploratory. If you can make the missing choice on stated grounds,
  register a successor with `[replaces]` as above. If not, hand over. If a
  setup description disagrees with the unchanged data or code, correct the
  text in the protocol. Examples are a count, a path or a name in Terms,
  Data / scope, Model / tool, Model I/O, Exclusions / filters or Unit. Decide the finding `fixed`, naming the correction, and run
  the analysis audit again. If the data or code changes, measure anew.
  In place, never change a promise, the question, the criterion, the
  quality checks or the null condition.
- **a wrong adoption** — The measurement stands, but the head adopted a
  run that does not answer; the finding names the one that does. Withdraw
  the adoption with `protocol-fill <PROTOCOL> --withdraw --why "<why>"`.
  Decide the BLOCKER `fixed`, naming that, and run the analysis audit
  again. Then adopt the answering run with `labkit-adopt <area> <run_id>`.
  Do not measure again.
- **none of these** — A way out above needs a prerequisite that is
  missing. Name it. First run `labkit-audit <area> --findings`. Decide each
  BLOCKER you can decide. An unresolved one stays `open`, and the handover
  records it. Then run the printed command:
  `protocol-fill <PROTOCOL> --handover --why "<what blocks>" --tried "<what you tried>" --into REPORT.md`.
  The handover leaves no `[result]` table in the protocol. It writes a
  handover block into REPORT.md: the report names the protocol, not its
  runs. Write no run ids in the reason or the tried steps. Remove or discuss each citation in
  other text or reports. The handover names each with its `--discuss`
  command. Stage the report, the protocol, the handover record and the
  remaining audit evidence together. New evidence or a changed block needs
  a new handover. The handover gives no number and no audit approval.

## Keep the evidence

Change a decision only with `--decide`. Update a generated result only with
`protocol-fill`. Keep unsuccessful audits. They show the attempt but give
no analysis coverage. If a later change made an audit outdated, keep it.
Decide its BLOCKERs, `fixed` where the change repaired the fault, and stage
the record with the change. If the change touched the measuring code or
its inputs, measure again and audit the new run. If you delete a record
before you stage it, the commit is held. The hold names how to restore it.

## Setup and layout

Treat prepared data as read-only. Import shared helpers from the pinned
labkit (`from labkit.run import runlog`). Do not copy its modules. In
`notes/`, `theorie/` holds independent knowledge, `messung/` instruments
and protocols, and `results/` what runs showed.
