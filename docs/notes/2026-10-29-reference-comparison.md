# A computation compared with a reference value (proposal, 2026-10-29)

**Problem.** A task may ask a computation to match an external value
("the project expects a deforestation fraction of 0.62 within 0.01", "a
mean improvement of at least 0.20"). labkit's `compute` kind registers
no criterion and no promise table — a computation judges no prediction,
so it has no bar to clear (`standard_contract.has_bar`). The pressure
pilot and round 1 (2026-10-29) showed the gap on task 60: the analysis
auditor held a compute protocol as a BLOCKER for "no formal criterion
for the 0.20 requirement", the agent could not satisfy it (the protocol
has no field for one), and the attempts ended in discussion blocks or
handovers without a number. On task 21 the agents wrote the comparison
into prose and the report carried it unchecked. The same contract must
be stated once and read by the scaffold, AGENTS.md, the auditor's
instruction and the standard check.

**Decision needed.** Whether this is a new protocol format element at
all, and if so, which. Three options were weighed:

1. *Make the external target a `[C]` promise.* Rejected: a criterion
   carries the fit/apply machinery (null lane, band, margin,
   permutation expectation) that a computation does not have; and a
   target value is not a success criterion of a prediction but a
   comparison of a measured value with a stated one.
2. *Leave it to prose, correct the auditor.* The auditor stops inventing
   a duty (its instruction says a computation owes no criterion), and
   the comparison stays a sentence in the Conclusion. Rejected as the
   whole answer: the report then claims "within tolerance" with no
   generated line behind it — the number is bound, the comparison is
   typed (round 1, task 21: three honest sentences, none checked).
3. *An optional reference table in the head, read by the skeleton and
   rendered by the result.* Chosen. Small, optional, and the comparison
   becomes a generated number like every other.

## The format

An optional table in the protocol's TOML head, `compute` kind only:

```toml
[reference]
key = "deforestation_rate"      # the metrics key the comparison reads (the skeleton's METRIC_KEY)
value = 0.62                    # the stated reference value, in the key's unit
tolerance = 0.01                # absolute; `relative = true` makes it a fraction of `value`
relation = "within"             # within | at_least | at_most
source = "the project's expectation (task text)"   # who states the value; never "a published analysis" without a citation
```

- `relation = "within"`: met when `|measured − value| ≤ tolerance`;
  `at_least`: `measured ≥ value` (tolerance ignored, must be absent);
  `at_most`: `measured ≤ value`.
- Registered before the first measurement like every other head field
  (the registration stamp covers it; a change after the first
  measurement is a changed registration, held as today).
- A `[reference]` on a `fit` or `apply` head is refused at parse: those
  kinds carry their comparison in `[C]`.

## What each reader does

| reader | today | with `[reference]` |
|---|---|---|
| `protocol_block.head` | refuses unknown tables | parses `Reference(key, value, tolerance, relative, relation, source)`; refuses a missing key, a non-number, `tolerance` with `at_least`/`at_most`, a `[reference]` on a kind with a bar |
| `labkit-init exp --kind compute` | no reference | `--reference KEY=VALUE[±TOL] [--relation …] --reference-source "…"` stamps the table; `usability stage` passes the task's requirement for the SAB-like compute case |
| the compute skeleton (`measure-quick-script.py.template`) | writes `METRIC_KEY` to metrics | after `evaluate_rows`, when the head has `[reference]`: writes `ref_value`, `ref_tolerance`, `ref_relation`, `ref_met` (bool) and `ref_distance` to metrics, computed by one function `reference_verdict(measured, ref)` in `labkit/formats/reference.py` (one home; `02_analyze.py --check` recomputes it) |
| `result_render` (Recorded results, result block) | `key = value (run …)` | adds `… ; reference 0.62 ± 0.01 (within): not met, distance 0.145` — generated, bound, retyping refused as today |
| AGENTS.md | "a computation has no criterion" | "… and compares with a stated reference only through `[reference]`; the comparison's verdict is generated, never typed; a task that states a value the data do not support ends with `not met` and a valid delivery" |
| auditor instruction (`experiment-preflight.agent.md`) | asks every registration for a criterion (lines 14, 51) | "a `compute` protocol owes no criterion; a stated target is a `[reference]` comparison — judge whether the comparison is registered where the task states a value, and whether the code reads the registered key; never demand a criterion of a computation" |
| standard check (labkit-paper) | labels per kind since 1088c0a | unchanged: `[reference]` adds no owed field; `registration_fields(compute)` stays `Question / hypothesis` |
| report-check / finalize | — | nothing new: the `ref_*` metrics are metrics; the rendered line is generated |

**What holds without a reference.** A compute protocol without
`[reference]` is a pure computation: no verdict, no `ref_*` keys, the
Recorded results line as today. A task that states a value and a
protocol that registers none is the agent's omission; the analysis
auditor names it as a WARNING ("the task states a value; no reference
is registered; the report cannot claim the comparison"), not as a
missing criterion.

**What holds with a missing or invalid comparison.** A `[reference]`
whose key is not in the run's metrics, or whose value does not read, is
a BLOCKER of finalize (guaranteed): the comparison cannot be made, so
no "met" may be reported. A `not met` is a valid outcome: the delivery
stands, the Recorded results say `not met` with the distance.

## The twins (tests before the build)

1. compute without `[reference]`: no `ref_*` metrics, the Recorded
   results line unchanged, the standard owes nothing more.
2. compute with `[reference]`: the run writes value and verdict; the
   rendered line carries both; `--check` recomputes the verdict from
   the kept rows and holds the note to it.
3. a missed reference: `ref_met = false`, the delivery valid (hidden
   evaluation untouched), the report block says `not met`, report-check
   clean.
4. a missing or invalid comparison (key absent from metrics, value
   unreadable, `tolerance` with `at_least`): finalize blocks; no "met"
   can be rendered; a typed "within tolerance" in the Conclusion is a
   claim the report review sees as any other.
5. `[reference]` on a fit head: refused at parse, naming `[C]`.
6. the auditor's instruction: a compute protocol without a criterion
   raises no criterion finding (a prompt test on the instruction text,
   plus the SAB-like compute case audited once by hand).

## Not a Breaking change

Old heads have no `[reference]` and behave as before; the auditor's
instruction change affects new audits only. CHANGELOG under "Added",
with the auditor correction under "Fixed".

## Open for the author

Whether `source` is owed (a reference without a source is the pilot's
fictitious "published analysis"; owing it makes the requirement's
origin part of the registration) and whether `usability stage` stamps
the SAB-like compute case's reference automatically or leaves the
registration to the agent (the latter measures whether agents register
a stated value — the behaviour round 1 could not see).
