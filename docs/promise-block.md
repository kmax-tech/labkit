# Promise block

What a protocol promises the code, as data instead of prose, and what the
checks built on it may claim. Code: `labkit/formats/promises.py`; tests:
`tests/test_promises.py`. Terms (`protocol`, `run`, `metrics`, `intent id`)
are coined in the README.

## Claim and check tiers

labkit's claim: **it detects violations of explicitly encoded scientific
intent across implementation, execution and reporting.** The chain:

    scientific intent → explicit promise → code realization → execution → reported result

The three evidence kinds describe what supports a check's statement:

| Tier | Claims | Examples |
|---|---|---|
| **guaranteed** | exact and mechanical; silent on a correct input | block parses, prose and block name the same ids, the declared key is reported exactly, the run recorded this block, the declared scope is unchanged |
| **static evidence** | an indication; warns, never blocks | a key is written but never read; planned, not built: a scope function calls repo code outside the declared scope (the table below) |
| **agent audit** | semantic agreement of intent and code | `labkit-audit` (the experiment-preflight instructions, one model call); outside labkit, an agent the lab runs on a `code-check --bundle` |

A static check is never presented as proof of semantics. Everything in
`promises.py` is the guaranteed tier.

A mechanical gate finding carries `evidence_kind` as required data
(`gate.GateFinding`): `guaranteed` or `static evidence`. It classifies the
statement in `text`, not its subject: checking that an audit record holds
an undecided BLOCKER is a guaranteed register check; the agent's judgement
remains in the audit record (`findings.Finding`). Static evidence cannot
have grade BLOCKER. The dotted code-check output labels static evidence;
prefixed lines stay `WARNING: …`, and the summary counts static evidence
among the warnings. Individual messages do not always print the kind.

## Three kinds of promise

An id is the kind and a number — `[criterion-1]`, `[quality-check-2]`,
`[interpretation-1]` — and its metrics key is the id with underscores and
a suffix (`criterion_1_pass`), so a person reading a protocol, a report or
a run's metrics.json needs no legend.

| Kind | One sentence |
|---|---|
| `criterion` | constrains the reported outcome: which value of which metric counts as support for the hypothesis |
| `quality-check` | determines whether any criterion's verdict may be issued, conditional on an outcome-neutral check (control, anchor, yield, coverage, resolution) passing in the same run |
| `interpretation` | binds a pre-specified condition on the results to the reading or follow-up analysis it licenses |

**Separation rule: a criterion judges, a quality check releases the
judgement, an interpretation says what follows from it.** Whether
something is a quality check: does it depend on the outcome of the
hypothesis? No → quality check (an outcome-neutral condition in the sense
of Registered Reports); yes → criterion. A comparator without a target
value (a baseline the traces are read against) is no promise; it belongs
in the text of the criterion it serves.

Two refinements (review 2026-10-08). A quality check names *why* its
failure makes the measurement uninterpretable — the instrument's yield, an
anchor, a control at its expected value — never a value the hypothesis
needs: that threshold is a criterion, and filed as a quality check it
would turn a clean negative result into "no verdict". A failed quality
check withholds the verdict, not the data: descriptive readings may
follow, labelled as such. An interpretation is decided on its own
condition, not on the verdict: a stop rule fires during the run or on an
inadmissible one too (`verdict()` sets the criterion keys to None, never
the interpretation's). "n/a — only one outcome" is the honest
interpretation when the answer to "and if [criterion-…] fails?" is not
known before the run; a decision taken afterwards is reported as taken
afterwards.

**Earlier letters.** The letters `C`, `A`, `B` (labkit 0.48 to 0.103.0)
and, before them, `K`, `S`, `W`, `N` (up to 0.47) are not read: a protocol
carrying them is refused with a sentence naming the version that reads
it. Nothing translates them — K/S/W/N did not even map one-to-one onto
C/A/B (tested against 16 earlier protocols, the separation rule assigned
six ids differently from their letter). Frozen protocols are registrations
and are not rewritten; they are read with the labkit they were written
for.

**Not a kind:** a descriptive quantity reported in every branch, without a
criterion. It is a report line, not a promise — until a second case shows
it needs its own kind.

## The block

The protocol's one fenced TOML block holds the head (`[protocol]`, see
`labkit/formats/protocol_block.py` and `docs/protocol-run-binding.md`;
its optional `report = "REPORT.md"` names the report file, relative to
the repository root, that owes this protocol's result once it exists —
`labkit-init exp --report-file` stamps it, `docs/workflow.md` section 8
says what releases it), the
`[[promise]]` tables and — once a number is reported — the `[result]` table
naming the run (`protocol_block.declared_run`, written by `protocol-fill
--from-run`; the binding document says what the gates hold it to). A
computation (`kind = "compute"`) may carry one more optional table,
`[reference]` — the stated value its kept number is compared with:

```toml
[reference]
key = "deforestation_rate"   # the metrics key compared (the compute skeleton's METRIC_KEY)
value = 0.62                 # the stated value, in the key's unit
tolerance = 0.01             # within: |measured − value| ≤ tolerance; `relative = true` makes it a fraction of value
relation = "within"          # within | at_least | at_most (the last two carry no tolerance)
source = "the project's expectation (task text)"   # who states the value; optional
```

`protocol_block.reference` reads it exactly or refuses it by name; on a
fit or an apply it is refused naming the criterion — those kinds compare in a
criterion (`protocol_check.reference_gap`). It is no promise and no bar:
the compute skeleton writes the verdict (`ref_state`, `ref_met`,
`ref_distance`, …; `formats/reference`) beside the number, `02_analyze.py
--check` recomputes it, the Recorded results line carries it generated,
and finalize blocks a reference the run cannot compare (the key absent
from metrics.json, or no finite number) — a `not met` is a valid outcome.
The registration stamp digests the table: a value changed after the audit
is drift (docs/notes/2026-10-29-reference-comparison.md).

The head and the tables:

```toml
[protocol]
standard = "0.23"
id = "p-9e2341c0390948dc"
type = "confirmatory"
repeat_cost = "high"
kind = "apply"
frozen = true
preflight_audit = "2026-10-07T09-12-preflight.toml"

[[promise]]
id = "criterion-1"
key = "criterion_1_pass"
sentence = "macro-F1 of the judge >= min_f1 on the test split"
scope = ["scripts/01_measure.py:evaluate", "scripts/01_measure.py:filter_items"]
constants = { min_f1 = 0.70 }
```

| Field | Rule |
|---|---|
| `id` | `criterion-<n>`, `quality-check-<n>` or `interpretation-<n>`, unique; also named in the prose |
| `key` | the metrics key reporting it: the id with underscores (`quality_check_2`) or that stem and `_<suffix>` |
| `sentence` | the promise in one sentence |
| `scope` | non-empty list of `file` or `file:function` (top-level function or class), relative to the protocol's directory |
| `constants` | scalars the code reads from here instead of a second copy in the script — `promises.all_constants(promises.load(PROTOCOL))` into the script's config object; a name is lowercase snake_case and stands in exactly one promise (0.71.0) |

TOML, not YAML: labkit is stdlib-only, and `tomllib` is in the standard
library.

## Constants: the name is the mapping

A registered constant is named like the config key it is recorded under
(`min_f1`, `margin`, `max_empty` — `^[a-z][a-z0-9_]*$`), and it stands in
exactly one `[[promise]]` table; `parse_block` refuses `MIN_F1` and a name
declared twice. The name is the whole mapping between protocol and run
record: no second table says which key answers which constant, and a
heuristic ("sounds alike") would be evidence, not a check. The script
builds its config from the block — `MeasureConfig(model=MODEL,
**promises.all_constants(promises.load(PROTOCOL)))` — and records that
object whole; `runlog` refuses, before the run directory exists, a config
that lacks a registered constant or carries it with another value
(type-strict: `True` is not `1`, `1` is not `1.0`). The guarantee behind
the record is therefore: *a run under a block recorded every registered
constant unchanged*. Whether `evaluate_rows` uses the value right is the
agent audit's question, not a mechanical one. A frozen protocol, and
every measurement, including at `repeat_cost = "low"`, owes the block
(`promises.promise_tables_owed`, standard 0.19): without tables, `protocol-check`
reports a MUST failure (frozen or low), `preflight` and `finalize`
block, and no measurement starts under it. The one exception: a
computation (`kind = "compute"`) whose prose names no promise id
registers nothing and owes no tables, including when frozen at `high`.
Its freeze still requires the completed registration and covering preflight
audit. A computation owes no success
criterion at any tier (`standard_contract.has_bar`); its
`[protocol]` head and the release of its number (the analysis audit,
`report-check`) stay owed. Unfrozen preparation and
probe runs can start without tables; low permits no separate probe. The low cut IS the registration — in
prose and in tables, so the machine chain (block digest, scope hashes,
constants) holds for every reportable run, not only for frozen ones. Mechanically guaranteed is the one home of a
*name*; that two differently named constants mean the same threshold no
parser can see.

## What the declared-scope hash states

`declared_scope_sha` hashes one promise's declared scope — the README's
*scope hash*. It is not the area's audit *stamp* (`scope-sha`, README:
*stamp*), which covers a whole area for an audit and binds to no promise.

> **The implementation region declared for this promise was byte-identical
> in the run that produced the reported number.**

It does **not** state that the region is all the code the number depends
on, nor that the code implements the promise correctly.

The counterexample that fixes this: `compute_score()` writes `criterion_1_accuracy`
and calls `filter_items()`. An edit to `filter_items` (now dropping empty
answers instead of counting them wrong) moves the number.

| Version | Sees the edit? | Why |
|---|---|---|
| hash over the function that writes the key | no | `compute_score` itself is unchanged — a stamp that misses exactly the interesting change |
| declared scope, `filter_items` declared | yes (guaranteed) | region changed → hash changed |
| declared scope, `filter_items` not declared | no; a warning is planned (static evidence) | the scope calls repo code outside itself |
| area audit stamp (`scope-sha`) | yes, if in the area | but not per promise: any edit anywhere changes it |

Hence: **scope is declared, not derived.** The author says which region a
promise rests on; the hash makes that statement checkable. A call-closure
warning may help with declaring; it does not replace it.

Details: a `file:function` entry hashes the function's source segment
(decorators included), so edits to neighbouring functions leave the stamp
alone; each entry contributes its spelling and its content digest, so
adding, dropping or renaming an entry changes the stamp; a missing file or
function is an error, never an empty digest. Module-level constants
outside a declared function are not covered — read them from the block.

## Along the chain

| Link | Who | Refuses or reports |
|---|---|---|
| promise | `intent-check` | block malformed; prose and block name different ids |
| execution | `runlog` | malformed block, dangling scope, a missing table where promises are owed, or a config missing or contradicting a registered constant → refused before the run dir exists; otherwise `config.json` records `promises`: the digest of the promises as read (normalized JSON — neither the head nor the spelling of a table moves it) and its format, and per id key, constants, scope, `declared_scope_sha` |
| report | `intent-check` | declared key not reported exactly; run recorded no block, or a different one ("the promises changed after the run"); a run from labkit 0.46/0.47 is told apart by its digest format, not reported as changed |
| recomputation | `recheck.holds` | a declared scope changed since the run, per promise |

A protocol without `[[promise]]` tables has no promise checks; its head is still read.
