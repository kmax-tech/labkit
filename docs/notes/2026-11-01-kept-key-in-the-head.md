# 2026-11-01 — a computation's kept key is registered in the head

**Problem.** In the reference pilot, trial 2, task 34 asked for a heart-rate
variability value. The compute protocol's Unit field said in prose that the
kept number was HRV_MeanNN in milliseconds. The measure script, stamped from
`labkit/templates/measure-quick-script.py.template`, set
`METRIC_KEY = "hrv_computed"`, and the run was adopted with that flag as its
kept number: the Recorded results line read `hrv_computed = True`. Since
0.107.0, `kept_number()` refuses a bool, but `hrv_computed = 1` would still
pass. Nothing held METRIC_KEY to the key the protocol names. A compute head
registered a key only inside `[reference]`, when the task stated a value,
and otherwise only in prose. The analysis audit did not notice either.

**Decision (the author's).** The protocol registers the primary value
structurally, and every reader takes it from there:

- a compute head carries `[kept]` with `key`, the metrics.json key, and
  `unit`, a short text ("1" for a dimensionless number); a fit or an apply
  refuses the table, since they bind their answer through their promise
  keys;
- `[reference]` loses its own `key` and compares the `[kept]` key, one home
  for the key; a `[reference]` without `[kept]` is refused;
- the compute skeleton reads the key from the head (`metric_key()`); it is
  no longer a constant the agent fills;
- finalize, and the adoption through its check, holds the answering run to
  the key: metrics.json must hold it as a finite number, otherwise a
  guaranteed blocker names the key, the run and what it holds instead. The
  skeleton's own `kept_number()` sits in an agent-editable file. The gate
  reads the head and the run's record, which the agent cannot edit away
  without a new run;
- the Recorded results line names the kept number first, with its unit,
  then `also recorded: …`. The other metrics stay;
- no reference value is invented: without a stated value there is no
  `[reference]`.

Standard 0.24. 0.106.1 is the last release that reads 0.23 heads and
`[reference] key`.

**The limit.** Binding the key does not prove its meaning. A wrong
computation stored under `HRV_MeanNN` passes this check. Whether the number
under the key is the one the Unit field and the question describe is for
the area's test (a hand-checked case) and the analysis audit to judge. The
preflight agent's instructions now say so.
