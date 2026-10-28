# Workflow stages, orientation and unresolved handover

*2026-10-27. Functional review of the low/high and compute/fit/apply routes.*

## Decisions

A computation whose prose registers no promise has no promise tables at
either repeat cost. Freezing it still requires its registration and a
covering preflight audit. Requiring invented tables contradicted the
compute stamp and prevented its high-cost measurement from starting.

A local apply uses the unchanged predictor. The shared estimator template
keeps the evaluation in one place, but only its fit path trains. The
first form required an author-built null predictor; decided the same day
(the lab's choice, not the fix's): the null lane scores the primary's own
predictions against the labelled gold permuted with the seed, each null
row naming whose label it carries (`gold_of`) — the same noise floor as
fit's permuted lane without a second artifact. A protocol that registers
a fixed null predictor returns it from `make_null_predictor()` instead. Every loaded
predictor dependency belongs in `PREDICTOR_FILES`: source digests bind
it to the config, run inputs and output fingerprint. That detects changed
declared artifacts, not omitted dependencies or hidden training in a loader;
those remain audit questions.

Predictor dependencies use the explicit `provenance.BinaryInput` wrapper
when passed as run inputs. They record path, digest and `rows=None` without
text decoding or row-id checks. Ordinary dataset paths retain both checks;
trying to infer binary inputs from decoding failure would silently excuse
corrupt text datasets.

Withdrawing a result also withdraws its generated result blocks in the
chosen handover report. Other protocols' blocks and prose remain. Result
citations in other reports still need removal or explicit discussion; the
handover cannot silently rewrite unrelated reports.

Failed backend calls are evidence, not findings. Recovery lists failures
without a completed audit of the same mode, code and promises and offers
the no-model handover. A preflight record cannot hide an analysis failure.
A matching completed audit makes that failure history, not an outstanding
recovery step; whether the audit covers the current run remains the release
gate's question. With no attempt yet, recovery still names the area's
workflow rather than inventing a decision.

The area README names the analysis audit before adoption. The field
contract places raw examples after the run, as the open-field listing does.
These helpers explain mechanical obligations; none chooses a scientific
interpretation or proves the model's judgement correct.

## Verification

`tests/test_high_compute_workflow.py` exercises the real stamped high-cost
compute route through detached measurement, both audits, adoption, report,
stop and staged release checks. Audit answers are simulated. The test was
red against the parent snapshot and green with the compute fix.

`tests/test_apply_skeleton.py` checks prediction without fitting, the fit
twin, explicit null construction, prediction counts and changed artifacts.
A separate real generated apply subprocess loaded two JSON-backed fixed
predictors; its config and run inputs retained both artifact identities.
`tests/test_binary_inputs.py` also runs a measurement with actual pickle
bytes and checks that corrupt UTF-8 datasets and text split leakage still
raise beside a declared binary artifact.

`tests/test_handovers.py` covers adoption, a result block, handover and
staged release together. A report elsewhere retaining the withdrawn result
still blocks. `tests/test_workflow_orientation.py` covers the route, model
raw output and failed analysis recovery after preflight.

Final checks: Ruff, formatting and Pyright clean. The suite passed 2106
tests and 6466 subtests, with two skips; the two process-budget tests passed
separately outside the sandbox because their `ps` call is forbidden inside
it. The actual failed-audit recovery path also passed through the listing,
handover, stop and staged checks without a model call. Independent review
of the final changed paths reported zero findings; this is static evidence,
not proof of scientific correctness.

## Separate observation

`runlog start` returns after launching its child. An immediate `runlog
--wait` can observe no run before the child creates its directory and
return success too early. The high-compute test waits for the actual child
process before checking its recorded completion; it does not establish
that this launch/wait race is repaired. Repaired the same day: `runlog
start` returns once the run's directory holds its record, reports a
command that ended first (exit 0 without a run, 2 on failure, with the
log's tail) and gives up after `--max-seconds` with exit 3
(`tests/test_runlog_wait.py`, `TestStartWaitsForTheRun`).

That repair covered the first `--max-seconds` only. A stamped script
computes its rows before `runlog.run` opens the record, so a computation
longer than the start's wait fell into the same gap: in round 2 of the
labkit-paper area 15 pilot (t21, 2026-10-28) `runlog start` gave up at
17:23:29 with "pid 1814 is still starting", `runlog --wait` said "no open
runs" (exit 0) at 17:23:32, and the run opened at 17:23:36. Since then
`runlog start` keeps a record of the command it detached
(`labkit/run/detached.py`), and the command inherits the lock on it:
`runlog AREA` lists it and `--wait` waits for it until the command ends,
its run record open or not. A lock, not the pid, because the system
reuses pids (as for the audit attempts, `attempts.py`).

The review of that repair (same day) found the failure half missing: a
command that died while it prepared its rows left only its log, and
`--wait` said "no open runs — no finished runs", exit 0. Only a parent
can learn a process's exit status, so `runlog start` now starts a small
supervisor (`python -P -m labkit.run.detached`) in the new session; the
supervisor starts the command as its child — the pid the run records
stays the command's own —, writes the start record, waits, and writes
the command's exit into it (negative: the signal). A start that ended
without a run record bound to it (one naming its pid, started no earlier)
and not with exit 0 is a failed state: `--wait` exits 2 naming the exit
and the log, `runlog AREA` lists it. It stays until the next `runlog
start` in the area, which prints it once more and removes it: starting
again is the acknowledgement labkit already has (resume is the same
command; acknowledged means the message was seen, not that anything was
repaired or released), and a process that ended can no longer open a
record that would bind it. The start acknowledges what it read and
showed, nothing else: it reads the records once, prints the failures,
and removes exactly the records that read held as ended, each while its
file still holds the text read. A first version listed the records a
second time to clean up, and a command that ended between the two reads
lost its record unseen (an exit 7, reproduced in the review); now it
stays for the next display. Logs are never removed. An exit 0 without a run is a command that opened none,
as `runlog start` says when it sees it end. A wrapper process's run
records another pid; beside an open run the wrapper reads as "started
process still active; matched to no open run by its pid", not as a run
still to come.
